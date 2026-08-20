---
topic: topic.hashing-and-passwords
section: internals
title: Why passwords need a hash that is deliberately bad
order: 3
mode: explain
---

Assume the database is gone. Not "might be" — gone, and the attacker has it on
their own hardware with unlimited time and no rate limit, no lockout, no
monitoring and no network round trip.

That is the only threat model that matters for password storage, because every
other control you have — rate limiting, MFA, lockouts, alerting — lives on your
side of a boundary the attacker is now behind.

What is left is the hash. So the question is narrow and quantitative: **how many
guesses per second can they make?**

## Measure it, do not assume it

On the machine these labs run on, one core:

| Operation | Rate, one core |
|---|---|
| SHA-256 of a password-sized input | **3,859,885 / sec** |
| sha512crypt at its default 5,000 rounds | **312 / sec** |
| sha512crypt at 1,000,000 rounds | **2 / sec** |

Both numbers come from `openssl` on this machine, with process-spawn time
measured separately and subtracted — you will reproduce both in the lab.

The ratio is the point. A deliberately slow hash at its *default* setting is
over **ten thousand times slower** than a fast one, and that factor is the entire
difference between a database that falls overnight and one that does not.

:::note
Absolute rates vary with hardware and will be different on your machine. The
**ratio** is what transfers, and it is what you should quote when arguing for a
change. "Our hash is ten thousand times faster to attack than it should be" is an
argument; "SHA-256 is insecure" is not, because it isn't.
:::

Two honest caveats. These are single-core CPU figures, and an attacker uses
neither. Published GPU benchmarks put a single modern card in the region of
10^10 SHA-256 guesses per second and 10^4–10^5 for a properly tuned password
hash — five to six orders of magnitude apart, in the same direction. Those are
other people's numbers rather than ours, but the shape matches what you can
measure here, and the shape is what decides the design.

## Guesses are not uniform

3.8 million per second sounds survivable if you imagine an attacker enumerating
every 12-character string. They do not.

They run a wordlist — every password from every previous breach, hundreds of
millions of real passwords people actually chose — and then mutation rules on
top: capitalise, append a year, swap `a` for `@`. Human password choice is
enormously concentrated, and a few billion candidates covers most of a typical
user population.

At 3.8 million per second, a few billion candidates is **minutes**. At 2 per
second, it is longer than the company will exist.

That is the whole argument, and it is arithmetic rather than opinion.

:::diagram{src=../diagrams/password-storage.mmd caption="Five ways to store a password, and what each costs an attacker who already has the database"}
:::

## What a salt actually does

A salt is a unique random value per password, mixed in before hashing, and
stored in plain sight next to the result. Two things about it surprise people,
and both matter.

**It is not secret.** It is right there in the hash string. If secrecy were
required it would be a key, and it would need protecting like one.

**It does not slow down a single guess.** Salted SHA-256 is exactly as fast as
unsalted SHA-256. This is the part most explanations get wrong by implication.

What it removes is **shared work**:

- Without a salt, one precomputed table maps digests back to common passwords —
  build it once, use it against every leaked database forever. Salts make each
  table useless for anyone else's data, and that is what killed rainbow tables.
- Without a salt, identical passwords produce identical hashes, so an attacker
  sorts the database and sees that 40,000 accounts share a hash. That hash is
  `123456`. One guess, forty thousand accounts.
- Without a salt, one guess is tested against every row at once. With one, each
  row must be attacked separately.

:::predict{question="A service stores passwords as `sha256(salt + password)` with a unique random salt per user. An attacker steals the database and targets one specific executive's account. How much has the salt helped that executive?"}

Almost nothing. The salt removed the attacker's ability to amortise work across
accounts — but against a single targeted account there is no amortisation to
remove. They hash candidates at 3.8 million per second with that user's salt,
and the executive's password falls exactly as fast as if there were no salt at
all.

**Salt defeats bulk. Work factor defeats guessing.** You need both, and they are
answers to different questions. A system with unique salts and a fast hash has
solved the easier half of the problem and left the half that decides the
outcome.

## Work factor

A password hash is a fast hash run many times, plus deliberate awkwardness. The
number of repetitions is a parameter you choose, stored inside the hash so it
can be verified later and raised over time.

```text
$6$rounds=1000000$xK2pLm9Q$Vqq...
 │       │         │        └── the digest
 │       │         └── salt (not secret)
 │       └── work factor
 └── algorithm: 6 = sha512crypt
```

The tuning rule is a budget rather than a number: **pick the largest cost your
login path can absorb.** Around 250ms is a common target — imperceptible to a
person logging in, and a 100,000× tax on someone doing it a billion times.

And it must be revisited. A work factor chosen in 2015 is now roughly a tenth
as expensive in real terms, because the attacker's hardware improved and yours
did too. This is the only security parameter that silently decays on a fixed
schedule, which is why it is stored *in* the hash: you can raise it for new
passwords and upgrade old ones as people log in.

## Memory hardness, and why the modern answer changed

Rounds buy time, and time is the thing an attacker parallelises best. A GPU has
thousands of small cores; a purely computational hash maps onto them beautifully.

So the current generation attacks the hardware rather than the arithmetic:
**make each hash need a large chunk of memory.** GPU cores have very little
memory each, and giving every one of thousands of cores 64 MB is not something
a graphics card can do. The attacker's advantage collapses from
five-orders-of-magnitude to something much smaller.

| Algorithm | Year | Slow | Memory-hard | Use it? |
|---|---|---|---|---|
| MD5, SHA-1, SHA-256 | — | No | No | Never for passwords |
| md5crypt (`$1$`) | 1994 | Barely | No | No |
| sha512crypt (`$6$`) | 2008 | Tunable | No | Only if nothing better exists |
| bcrypt (`$2b$`) | 1999 | Yes | Slightly | Acceptable |
| scrypt | 2009 | Yes | Yes | Good |
| **Argon2id** (`$argon2id$`) | 2015 | Yes | Yes | **The default answer** |

Argon2id won the Password Hashing Competition and is what to reach for absent a
constraint. The labs here use sha512crypt because it is what `openssl` ships
and what you will actually find on Linux systems in `/etc/shadow` — the
*mechanism* is identical, and reading its parameters is the transferable skill.

:::warning
The one rule with no exceptions: **do not implement this yourself.** Not the
hash, not the comparison, not the salt generation. Use the password-hashing
function your platform provides. Home-made schemes fail in ways that are
invisible until a breach makes them public — and the most common failure is not
a broken algorithm but a comparison that leaks timing, or a salt from a
predictable random source.
:::

## HMAC, and why concatenation is not enough

A different job: prove a message came from someone holding a shared key. The
obvious construction is `sha256(key + message)`.

That is broken, and specifically so. SHA-256 is built on a construction whose
internal state after hashing *is* the output. An attacker who sees
`H(key + message)` — without knowing the key — can resume from that state and
compute `H(key + message + anything)`, producing a valid tag for a message they
extended. This is a **length extension attack**, and it works against MD5, SHA-1
and SHA-2.

HMAC exists to fix exactly this, by hashing twice with two derived keys:

```text
HMAC(k, m) = H( (k ⊕ opad) ‖ H( (k ⊕ ipad) ‖ m ) )
```

The outer hash means the visible output is not an internal state anybody can
resume from.

Use `openssl dgst -hmac`, or your language's HMAC function — never a hand-rolled
concatenation. And compare tags with a constant-time comparison, because a
normal string compare returns early on the first differing byte, and an attacker
who can measure that difference recovers the tag one byte at a time.

## Content addressing: the same primitive as a name

`sha256:9f2a…` in a container reference, and a Git commit id, are hashes used as
identifiers. Because the name is derived from the content, the name is a proof:
fetch it, hash what arrived, compare. A mismatch means you did not get what you
asked for, and you do not need to trust the thing that served it.

This is why `image: postgres:18` and `image: postgres@sha256:9f2a…` are
different promises. The tag is a label somebody can move; the digest is the
content. It is the same mechanism as the download check, applied to naming, and
it is why supply-chain work later in the curriculum is mostly about digests.

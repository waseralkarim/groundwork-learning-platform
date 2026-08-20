---
topic: topic.hashing-and-passwords
section: core-concepts
title: Three transformations that get confused for each other
order: 2
mode: explain
---

Before anything about passwords, one distinction has to be solid, because
getting it wrong produces sentences that sound reassuring and mean nothing.

Three things turn data into other data. They are not variations of one idea —
they have different inputs, different reversibility and different purposes.

:::diagram{src=../diagrams/three-transformations.mmd caption="The only one that cannot be undone is also the only one that protects nothing by itself"}
:::

## Encoding

Base64, hex, URL-encoding, JSON escaping. A representation change so data
survives a channel that would otherwise mangle it.

**No key. Reversible by anyone.** It is not security in any sense, and the
reason it gets mistaken for security is that base64 output looks scrambled.

```bash
printf 'hunter2' | base64          # aHVudGVyMg==
printf 'aHVudGVyMg==' | base64 -d  # hunter2
```

If you find credentials base64-encoded in a config file, they are stored in
plaintext. The encoding is a transport detail, not a protection.

## Encryption

**Takes a key. Reversible with it, and not without it.** This is the only one of
the three that protects confidentiality, and the protection lives entirely in
the key rather than in the algorithm.

The point of encryption is that you get the data back. That is a requirement,
not a side effect — and it is exactly why it is the wrong tool for passwords.

## Hashing

**No key. Not reversible by anyone, including you.**

```bash
printf 'hello' | sha256sum
# 2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824
```

There is no `sha256sum -d`. The operation destroys information: the input was
five bytes, the output is thirty-two, and for a one-gigabyte input the output is
still thirty-two. Most of the input is gone, and no amount of cleverness
recovers it.

:::predict{question="Hashing cannot be reversed. So how does an attacker who steals a database of SHA-256 password hashes recover most of the passwords?"}

They guessed. That is the only available move, and it is the whole story of
password cracking: hash a candidate, compare, repeat. Nothing is reversed. The
question that decides whether it works is not "is the hash reversible" but **how
many guesses per second** — which is what the rest of this topic is about.

## The properties, and one that is missing

**Deterministic** — same input, same output, every time, on every machine. It is
what makes a published checksum useful at all.

**Fixed size** — the digest length is a property of the algorithm, never of the
input. SHA-256 always produces 32 bytes.

**Avalanche** — change one bit of input and about half the output bits change.
So digests are compared for *equality only*. Two digests that "look similar"
tell you nothing; there is no such thing as a near match.

**Preimage resistance** — given a digest, no procedure finds an input producing
it, short of trying inputs.

And the one people assume and should not: **a hash does not protect data.**
Hashing is a public operation. Anyone can hash anything. A digest sitting next
to the data it describes stops nobody from replacing both.

:::warning
"We store passwords hashed" and "we store passwords encrypted" describe
different systems, and a breach notice that says *encrypted* is describing a
system where the plaintext passwords still exist somewhere — because encryption
is reversible by design. If a company can email you your password, it is not
hashed.
:::

## Collisions must exist

Inputs are unlimited; digests are 2^256. So different inputs *must* share
digests — infinitely many of them.

That is not a flaw. A hash is broken when finding a collision becomes
**practical**, which is what happened to MD5 (minutes on a laptop) and SHA-1
(demonstrated in 2017, and cheap now).

Two resistances matter, and they break at different times:

| Property | The attacker's task | Where it matters |
|---|---|---|
| Collision resistance | Find *any* two inputs that match | Signatures, certificates, content addressing |
| Preimage resistance | Match a *specific given* digest | Password storage |

MD5's collision resistance is destroyed; its preimage resistance is technically
intact. This is why "MD5 is broken" and "you can still not reverse an MD5" are
both true, and why neither sentence settles whether MD5 is safe for a given job.

It is also why the answer to "which hash should I use" always begins with a
question about the job.

## Four jobs

| Job | Wants | Reasonable choice |
|---|---|---|
| Verify a download | Speed, collision resistance | SHA-256 |
| Name content immutably | Collision resistance | SHA-256 |
| Authenticate a message | A key | HMAC-SHA-256 |
| Store a password | **Slowness**, memory cost | Argon2id, scrypt, bcrypt |

Three of those four want the same fast algorithm. The fourth wants the opposite
of it, and it is the one where being wrong is a headline.

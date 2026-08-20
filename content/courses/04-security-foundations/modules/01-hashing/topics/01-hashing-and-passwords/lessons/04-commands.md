---
topic: topic.hashing-and-passwords
section: commands
title: The commands, and what each output is telling you
order: 4
mode: explain
---

Everything in this topic is reachable with two tools that are already on every
machine you operate: `sha256sum` and `openssl`. No libraries, no scripts.

## Hashing a thing

```bash
printf 'hello' | sha256sum                 # stdin — note printf, not echo
sha256sum /etc/hostname                    # a file
openssl dgst -sha256 /etc/hostname         # the same digest, different format
openssl dgst -sha512 /etc/hostname         # a different algorithm
```

Use `printf` rather than `echo` whenever the exact bytes matter. `echo` appends
a newline, so `echo hello | sha256sum` hashes six bytes and disagrees with every
published digest for `hello`. This trips people up constantly and looks like a
broken hash rather than a shell habit.

:::try{lab=what-a-hash-guarantees run="printf 'hello' | sha256sum; echo hello | sha256sum" title="One byte of difference"}
Two digests with nothing visibly in common, from inputs that differ by a
trailing newline. That is the avalanche property, and it is why digests are only
ever compared for equality.
:::

## Verifying a download

The mechanical form, and the one worth building into muscle memory:

```bash
sha256sum -c SHA256SUMS            # verify every file listed
sha256sum -c SHA256SUMS 2>&1 | grep -v ': OK$'    # show only what failed
```

`sha256sum -c` reads a file of `digest␣␣filename` lines, hashes each named file
and prints `OK` or `FAILED`. It exits non-zero if anything failed, which is what
makes it usable in a pipeline.

A mismatch means exactly one thing: **the bytes you have are not the bytes that
were hashed.** It does not distinguish corruption from tampering, and you should
not try to guess which. Both are "do not use this file".

:::warning
Verifying a download against a digest hosted on the same server as the download
proves almost nothing. Whoever replaced the file could replace the digest. The
check is only meaningful when the digest reaches you through a channel the
attacker does not control — a signature, a different host, or a value you
already had. This is the gap that signing exists to close, and it is why
A04.3's certificates matter.
:::

## Password hashes

```bash
openssl passwd -6 hunter2                              # random salt, default rounds
openssl passwd -6 -salt abcdefgh hunter2               # fixed salt, for comparison
openssl passwd -6 -salt 'rounds=1000000$abcdefgh' hunter2   # explicit work factor
openssl passwd -1 hunter2                              # md5crypt — obsolete, for reading old systems
openssl passwd -5 hunter2                              # sha256crypt
```

The `-salt` form is how you make two runs comparable, which is the only way to
demonstrate determinism. In production the salt is always random, and `openssl`
generates one when you omit it.

Note the shape of the third command: the work factor is smuggled into the salt
field as `rounds=N$salt`. That is not an `openssl` quirk — it is the crypt(3)
format itself, and it is why the parameter survives in the stored string.

:::try{lab=why-passwords-are-different run="openssl passwd -6 -salt abcdefgh hunter2; openssl passwd -6 -salt zzzzzzzz hunter2" title="Same password, two salts"}
One password, two completely different stored values. An attacker sorting the
database for duplicates finds none — which is the first thing a salt buys.
:::

## Reading a stored hash

Every crypt-format hash is `$id$[params$]salt$digest`, split on `$`:

```text
$6$rounds=1000000$xK2pLm9Q$Vqq...
 ↑  ↑              ↑        ↑
 │  │              │        └ digest
 │  │              └ salt
 │  └ parameters (optional — absent means the algorithm default)
 └ algorithm id
```

| `$id$` | Algorithm | Verdict |
|---|---|---|
| *(none — 13 chars)* | DES crypt | Ancient. Only the first **8** characters of the password matter. |
| `$1$` | md5crypt | Obsolete. |
| `$2a$` `$2b$` `$2y$` | bcrypt | Acceptable. Cost is the number after the id. |
| `$5$` | sha256crypt | Weak default; check for `rounds=`. |
| `$6$` | sha512crypt | Weak default; check for `rounds=`. |
| `$argon2id$` | Argon2id | The current answer. |

The operational skill is reading one of these and saying what it costs an
attacker. `$6$` with no `rounds=` is the default 5,000 — which you will measure
at around 300 hashes per second per core. `$6$rounds=1000000$` is around 2.
Same algorithm, same database, and a difference that decides the outcome.

On a real system these live in `/etc/shadow`, mode `0640` and owned by
`root:shadow`:

```bash
ls -l /etc/shadow          # -rw-r----- root shadow
cat /etc/shadow            # Permission denied, as an ordinary user
sudo awk -F: '{print $1, $2}' /etc/shadow | head    # user and hash fields
```

That the file is unreadable to you is the control working. It is also the reason
password hashing exists at all: `/etc/passwd` is world-readable and used to hold
these, which is what "shadow" was invented to stop.

## HMAC

```bash
printf 'transfer 100' | openssl dgst -sha256 -hmac 'shared-secret'
printf 'transfer 100' | openssl dgst -sha256                     # no key — anyone can produce this
```

The two outputs are unrelated, and the difference is the whole point. The plain
digest can be computed by anyone who has the message. The HMAC can only be
computed by someone who also has the key — which is what makes it evidence of
origin rather than merely of content.

This is what webhook signature headers contain. When a provider sends
`X-Signature: sha256=...`, they have HMAC'd the request body with a secret you
both hold, and verifying it is how you know the request came from them rather
than from anyone who learned your endpoint URL.

## Timing the difference

There is no `time` builtin in `dash`, and the lab containers run `dash` for
checks — so measure with `date`:

```bash
t0=$(date +%s%N)
openssl passwd -6 -salt 'rounds=1000000$abcdefgh' hunter2 >/dev/null
t1=$(date +%s%N)
echo "$(( (t1 - t0) / 1000000 )) ms"
```

Nanoseconds since the epoch, subtracted, divided down to milliseconds. Loop it
forty times and subtract a separately-measured spawn cost, and you have a
defensible hashes-per-second figure rather than an impression — which is exactly
what the lab does.

## The four commands worth keeping

```bash
sha256sum -c SHA256SUMS                     # is this the file I was promised?
openssl passwd -6 -salt 'rounds=1000000$s' pw   # what does one hash cost?
openssl dgst -sha256 -hmac "$KEY" file      # did this come from who I think?
awk -F'$' '{print $2, $3}' <<< "$HASH"      # what algorithm and parameters?
```

Four commands, and between them they answer every question this topic poses.

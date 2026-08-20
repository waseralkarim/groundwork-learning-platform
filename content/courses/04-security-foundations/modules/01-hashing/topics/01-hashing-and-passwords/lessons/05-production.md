---
topic: topic.hashing-and-passwords
section: production
title: Where this goes wrong in systems you will operate
order: 5
mode: explain
---

You will rarely choose a password hash. You will frequently inherit one, review
a change that touches one, or read a breach notice about one. These are the
situations where knowing the primitive changes what you do.

## Reading a breach notice

The vocabulary in the disclosure tells you how bad it is, and the words are used
carelessly often enough that you have to read them precisely.

| What it says | What it means |
|---|---|
| "passwords were stored in plaintext" | Every account, immediately. Also every account on every other site where the password was reused. |
| "passwords were **encrypted**" | A key exists. If it was taken too — and it usually lives near the data — this is plaintext with extra steps. Ask where the key was. |
| "passwords were hashed" | Incomplete. Ask *which* hash and whether it was salted. `md5` and `argon2id` are both "hashed". |
| "hashed and salted" | The bulk attack is off the table. Individual accounts still fall at whatever rate the algorithm allows. |
| "hashed with bcrypt / Argon2id" | The right answer. Weak passwords still fall; strong ones do not. |

The question that separates the last two rows is always **work factor**, and it
is almost never in the notice. If you are the one writing it, put it in.

## Reviewing a change

Things worth blocking, and the reason in one line each:

- **A fast hash for passwords.** `sha256(password)` in a migration is the
  finding. It is not "we'll fix it later" — every password hashed that way stays
  that way until every user logs in again.
- **A shared salt, or a salt derived from the username.** Both restore the
  attacker's ability to amortise. A salt is per-record and random, or it is
  decoration.
- **`==` on a digest or a signature.** Use a constant-time comparison. Language
  runtimes provide one (`hmac.compare_digest`, `crypto.timingSafeEqual`,
  `subtle.ConstantTimeCompare`) and the ordinary operator leaks how many leading
  bytes matched.
- **Any hand-written HMAC.** `sha256(secret + body)` is length-extendable. There
  is a correct function in the standard library of every language you will meet.
- **A work factor from a tutorial.** It must come from timing your own login
  path on your own hardware, and it must be revisited.
- **A hash of anything low-entropy treated as anonymised.** Hashing an email
  address, a phone number or an IP address does not anonymise it — the input
  space is small enough to enumerate. A hashed phone number is a phone number
  with an index.

That last one is the least obvious and the most common. "We hash the emails so
it's anonymous" is wrong: there are around 4 billion of them in circulation and
a laptop enumerates that in under an hour at 3.8 million hashes a second.

## Upgrading a bad hash

You cannot recompute stored hashes, because you do not have the passwords. That
is the property working as designed, and it makes migration a real design
problem rather than a script.

Two approaches, and the second is usually right:

**Rehash on login.** When a user authenticates successfully, you hold the
plaintext for one moment — verify against the old hash, then immediately store a
new one with the new algorithm. Zero user impact. But accounts that never log in
stay vulnerable forever, and those are disproportionately abandoned accounts
with reused passwords.

**Wrap the old hash.** Store `argon2id(existing_bad_hash)` for every row
immediately, and record that the row is wrapped. Verification becomes: apply the
old hash, then the new one. Every account gets the new work factor tonight
rather than eventually, and you unwrap opportunistically at next login. It costs
one extra hash per verification and a schema flag.

Whichever you pick, the deadline is the same: **the work factor only helps if it
is applied before the breach, not after.**

## Digests as names

The place hashing shows up most in daily operations has nothing to do with
passwords.

```bash
docker pull postgres:18                       # a label someone can move
docker pull postgres@sha256:9f2a...           # the content itself
```

A tag is a pointer. It can be repointed, and `postgres:18` today and
`postgres:18` next Tuesday can be different images with no record of the change.
A digest cannot: it is derived from the content, so the reference either
resolves to exactly those bytes or fails.

That difference is why a deployment pinned by tag is not reproducible, and why
incident timelines built on tags have a hole in them. `kubectl get pod -o
jsonpath='{..imageID}'` gives you the digest that is actually running, which is
frequently not what the manifest says.

Git works the same way. A commit id is a hash over the tree, the parent and the
metadata, which is why history is tamper-evident: change anything and every
subsequent id changes. It is also why SHA-1 collisions mattered to Git, and why
the migration to SHA-256 exists.

## Rate limiting is not a substitute, and neither is MFA

Both are real controls and both belong in your design. Neither replaces the work
factor, because both live on the wrong side of the boundary.

Rate limiting constrains guesses *against your service*. An attacker with the
database makes guesses on their own machines, and your rate limiter is not
involved. Same for lockouts, CAPTCHAs, anomaly detection and alerting.

MFA is stronger — it means a cracked password is not sufficient to log in. But
it does not protect the password itself, and the password is reused. The real
damage from a password breach is frequently not to you at all; it is to every
other service where those people used the same password, and no control on your
side helps them.

Which is the argument for getting this right even when you have MFA: **the
work factor is the only control that still applies after you have lost.**

## What to check on a system you have just inherited

```bash
# What algorithm are local accounts using?
sudo awk -F: '$2 ~ /^\$/ {split($2,a,"$"); print $1, a[2], a[3]}' /etc/shadow

# Anything still on DES or md5crypt?
sudo awk -F: '$2 !~ /^\$(2|5|6|argon)/ && $2 ~ /[a-zA-Z0-9]/ {print $1}' /etc/shadow

# What does the application use? Look for the hash prefix in the users table.
```

Three commands, and they tell you within a minute whether the machine's password
storage was configured this decade. `$1$` or a 13-character hash on a running
system is a finding worth raising the same day — not because it will be
exploited tomorrow, but because it means nobody has looked at this in fifteen
years, and password storage is unlikely to be the only thing that is true of.

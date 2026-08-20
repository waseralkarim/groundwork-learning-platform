---
topic: topic.hashing-and-passwords
section: overview
title: The same word for four different jobs
order: 1
mode: explain
---

You have used hashes today without deciding to. The container image you pulled
was verified by one. The Git commit you made was named by one. The TLS
certificate your browser accepted was a signature over one. If you logged into
anything, a hash of your password was compared against a stored one.

Four jobs, one word — and the requirements point in opposite directions.

The download check wants a hash that is **fast**, because it runs over gigabytes.
The password check wants one that is **slow**, because an attacker who steals
the database runs it billions of times. Use the fast one for passwords and you
have built a database that decrypts itself.

That is not a hypothetical. It is the single most common way a breach turns from
"they took the hashes" into "they have everyone's password", and it happens
because both jobs are called hashing.

## What a hash actually promises

Three properties, and you will demonstrate each one against a real
implementation rather than take them on faith:

- **Deterministic.** The same input always gives the same output. This is what
  makes verification possible at all.
- **Fixed size.** One byte and one terabyte both produce the same 64 hex
  characters. The digest carries no information about length.
- **One-way.** Given a digest you cannot work backwards to the input. Not
  "difficult" — there is no procedure short of guessing.

And one property people assume that is **false**: a hash does not protect
anything. It reveals nothing, but it also prevents nothing. Anyone can compute
a hash of anything. This is the distinction the rest of the topic is built on.

:::note
A digest is a *fingerprint*, not a *lock*. A fingerprint identifies; it does not
keep anyone out. Most of the confusion in this area comes from expecting a
fingerprint to behave like a lock.
:::

## The specific things this explains

By the end of this topic you will be able to answer these from evidence rather
than from memory:

- Why "the passwords were encrypted" in a breach notice is either a mistake or
  a lie, and how to tell which
- Why two accounts with the same password have different stored hashes, and what
  breaks when they do not
- Why a salt is stored in plain sight next to the hash it salts, and is still
  doing its job
- Why `$6$` and `$6$rounds=1000000$` are the same algorithm with a
  hundred-fold difference in security
- Why hashing your secret together with your data is not the same as HMAC, and
  what an attacker does with the difference
- What `sha256:` in a container image reference actually guarantees, and what it
  does not

## Where this sits

This is the first topic in Security Foundations because everything after it is
built here. A certificate is a signature over a digest. A signature is an
asymmetric operation on a digest. An HMAC is a digest with a key. Content
addressing is a digest used as a name.

Get the primitive right and the rest of the course is composition. Get it wrong
and every later control inherits the mistake.

## How this topic works

You will not be told that SHA-256 is fast and sha512crypt is slow. You will
measure both, on the machine in front of you, and read the numbers.

That matters more here than anywhere else in the curriculum, because security
advice is overwhelmingly transmitted as folklore — "use bcrypt", "salt your
hashes", "don't roll your own crypto" — repeated by people who have never timed
anything. The advice is mostly correct. But you cannot defend a choice you
cannot measure, and you will meet systems where the folklore does not apply.

Four labs, and the last one hands you four systems that each chose the wrong
hash for their job and asks you to say which failure each one bought.

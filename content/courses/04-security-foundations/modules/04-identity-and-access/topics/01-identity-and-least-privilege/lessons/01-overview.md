---
topic: topic.identity-and-least-privilege
section: overview
title: Two questions, and only one of them gets asked
order: 1
mode: explain
---

Every access decision is two questions, asked in order.

**Who are you?** — authentication. It happens once, at the start of a session,
and it either succeeds or fails.

**May you do this?** — authorization. It happens on every single operation, and
it is where all the interesting failures live.

Almost all the attention goes to the first. Password policies, MFA, SSO, key
rotation — an industry of it. And when something goes wrong, the damage is
almost always decided by the second: not *how* the attacker got in, but what the
identity they arrived as was permitted to reach.

That is the argument for least privilege, and it is worth stating as a
measurement rather than a principle: **the cost of a compromise is what the
compromised component could reach.** Everything else is commentary.

## The gap this topic is about

Ask a team what a service runs as and they will read you the manifest. Ask what
it *actually* holds, on the running system, and the answer is usually different
and always longer:

- A uid that was set to non-root two years ago and reverted in a hotfix
- A supplementary group nobody remembers granting
- Capabilities inherited from a base image
- A secret mounted for a feature that was removed
- An `authorized_keys` entry belonging to a machine that was decommissioned

None of these appear in a review of the manifest, because the manifest is a
statement of intent. In this topic you will measure the other thing.

## What you will actually do

**Find out who you are**, from the process rather than the config, and then find
the boundary — read `/etc/shadow` and fail, and understand exactly which rule
stopped you.

**Measure the privilege you hold.** Your effective capability set here is
`0000000000000000` — none at all — while the bounding set holds fourteen. That
difference is the interesting number, and almost nobody has looked at it on
their own workloads.

**Predict access from permission bits**, then test the prediction. Four
directories, and two of them produce an error that names the wrong object:

```text
$ cat listable/data.txt
cat: listable/data.txt: Permission denied
```

The file is mode 644 and perfectly readable. The fault is the directory, and
that error will send you to `chmod` the wrong thing.

**Read a real `authorized_keys`** with more entries than there are people, and
work out which key nobody can account for.

## Where SSH fits

Public key authentication is the asymmetric cryptography from A04.2, applied to
identity, and it is where most engineers actually meet it. The server holds your
public key; you prove you hold the private one by signing a challenge. No secret
crosses the wire, ever — which is the whole reason it is better than a password.

You will generate keys, match public halves to private ones, read a fingerprint
as the SHA-256 it is, and open an encrypted private key to find `aes256-ctr` and
`bcrypt` written in its own header. Both of the previous two topics, visible in
one file.

## The closing question

The topic ends on an audit: four workloads, described as an inventory would
describe them, exactly one correctly scoped. For each of the others the question
is not "is this best practice" but **what does an attacker get by compromising
this, that they should not**.

That is the question worth carrying out of the whole course. It is answerable,
it is specific, and it is the one that survives contact with a real system where
everything is already running and nothing can simply be switched off.

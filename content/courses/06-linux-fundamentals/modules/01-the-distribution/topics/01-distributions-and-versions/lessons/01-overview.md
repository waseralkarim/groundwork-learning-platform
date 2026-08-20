---
topic: topic.distributions-and-versions
section: overview
title: Old on purpose
order: 1
mode: explain
---

The `openssl` in this container is version `3.5.6-1~deb13u2`. Upstream has moved
on. Somebody will eventually file a ticket saying the platform ships an outdated
OpenSSL and should be updated.

That ticket is usually wrong, and being able to say *why* — precisely, with the
version string as evidence — is most of what this topic is for.

## What a distribution actually is

Four things, and only two of them distinguish one distribution from another:

- **A kernel.** Broadly the same one everywhere, give or take a version and some
  patches.
- **A userland** — the shell, the core utilities, the libraries.
- **An archive** of packages built to work together and tested as a set.
- **A policy** about when any of that is allowed to change.

The kernel and the userland are largely common property. **The archive and the
policy are the distribution.** Debian and Ubuntu share an enormous amount of
code and differ on when things move; that difference is the entire product.

Which reframes the usual question. "Which distribution should we use" is really
"whose release policy do we want to live under", and that is answerable.

## Why the software is behind

A fixed release freezes versions at release day and then changes them only for
security fixes and grave bugs. Years pass. The versions do not move.

That is not neglect — it is the thing being sold. It means:

- The system you test on in January behaves identically in November.
- A security fix arrives as a **backport**: the fix is applied to the old
  version, so the bug goes away and the version number does not change.
- Upgrades are events you schedule rather than things that happen to you.

And it costs you: software genuinely older than upstream, features you cannot
have without stepping outside the archive, and an eventual upgrade that is large
because it has been deferred.

:::note
The backport is the part people miss, and it has a practical consequence. A
scanner that compares `3.5.6` against a CVE's "fixed in 3.5.9" will report you
vulnerable when the fix was backported into `3.5.6-1~deb13u2`. Version-based
vulnerability reports against a stable distribution are **wrong by default**, and
knowing why is the difference between triaging findings and chasing them.
:::

## Identifying a system

You will be asked "what is this box" more often than you expect — during
incidents, in tickets, when a script has to branch. The portable answer is one
file:

```bash
cat /etc/os-release
# ID=debian  VERSION_ID="13"  VERSION_CODENAME=trixie
```

The tools people reach for first are all worse. In the lab you will find that
`lsb_release` **is not installed here** — it is a package, not a guarantee, and
it is absent on minimal images and on several major distributions.
`/etc/debian_version` says `trixie/sid` on *Ubuntu*. And `uname` reports the
kernel, which in a container is the host's and says nothing about the userland
you are actually in.

## The version string, and three rules that are not string comparison

```text
4 : 14.2.0 - 1
│    │       └── distribution revision
│    └── upstream version
└── epoch
```

That is the real version of `gcc` on this system, epoch and all. Nine
comparisons in the lab, and four of them do not go the way instinct says:

```text
1.10        >  1.9        numeric, not lexical
1.0~rc1     <  1.0        ~ sorts BEFORE nothing
1:1.0       >  99.0       an epoch beats everything else
4:14.2.0-1  >  15.0.0     which is why gcc has one
```

Every one of those has produced a real outage somewhere: a comparison done with
string operators, a pre-release that sorted after the release, a rollback that
would not install because the old version compared as newer.

## What this topic gives you

**Identify any Linux system** in one command, and know why the alternatives
fail.

**Read a version string** and say what each part records — which is how you tell
a security update from a rebuild from a new upstream release.

**Predict a comparison** before running it, including the traps, and know that
`dpkg --compare-versions` exists to settle the argument.

**Choose a release model** for a stated situation and name what it commits you
to. The last lab has four of them, and the one where the usual answer is wrong
is the one with a kernel module and a seven-year field lifetime.

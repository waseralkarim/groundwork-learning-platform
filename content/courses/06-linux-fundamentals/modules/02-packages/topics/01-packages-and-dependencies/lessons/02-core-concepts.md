---
topic: topic.packages-and-dependencies
section: core-concepts
title: The database, and the two directions
order: 2
mode: explain
---

Everything in this topic reads one thing: a plain-text database on the local
disk describing what is installed on **this machine**. On Debian systems it is
`/var/lib/dpkg/`, and the main file is readable:

```console
$ ls -la /var/lib/dpkg/status
-rw-r--r-- 1 root root 144893 Mar  6 03:01 /var/lib/dpkg/status
```

That is worth internalising before anything else, because it explains a
recurring confusion. **The database describes the machine, not the archive.**
`dpkg` questions are answered locally and offline; `apt` questions about *what
is available* need the archive lists, which in a container are usually deleted:

```console
$ ls /var/lib/apt/lists/
$
```

Empty. The image build ran `rm -rf /var/lib/apt/lists/*` to save space, which is
standard practice. So on this machine "what is installed" works perfectly and
"what could I install" does not work at all — and knowing which category a
command falls into saves you from concluding the container is broken.

## The question has two directions

:::diagram{src=../diagrams/ownership-directions.mmd caption="File ownership runs both ways — except where it runs through a symlink, or nowhere at all."}
:::

**From a file to its package** — the forensic direction, and the one you will
use during an incident:

```console
$ dpkg -S /usr/lib/openssh/ssh-keysign
openssh-client: /usr/lib/openssh/ssh-keysign
```

**From a package to its files** — the auditing direction:

```console
$ dpkg -L openssl | wc -l
400
```

Four hundred paths for one package, most of them directories and certificates.
That number is itself informative: a package is rarely the one binary you think
of it as.

## Why `awk` answers neither way

```console
$ dpkg -S /usr/bin/awk
dpkg-query: no path found matching pattern /usr/bin/awk
$ ls -l /usr/bin/awk
lrwxrwxrwx 1 root root 21 Feb  4  2025 /usr/bin/awk -> /etc/alternatives/awk
```

`/usr/bin/awk` is a symlink into the **alternatives** system, a small layer that
lets several packages provide the same command. `mawk`, `gawk` and `original-awk`
all provide `awk`; the symlink decides which one you get, and it is managed by a
script rather than shipped by any single package.

Follow it and the answer appears:

```console
$ readlink -f /usr/bin/awk
/usr/bin/mawk
$ dpkg -S /usr/bin/mawk
mawk: /usr/bin/mawk
```

The same is true of `/bin/sh`, which points at `dash` here. That is not
trivia — it is the reason a script with a `#!/bin/sh` shebang behaves
differently on Debian than on a distribution where `sh` points at `bash`, and
this platform's own lab harness runs `verify` checks under `dash` for exactly
that reason.

:::note
When `dpkg -S` finds nothing, resolve the path first. `dpkg -S "$(readlink -f
/usr/bin/awk)"` is the habit. If it still finds nothing, the file is genuinely
unowned, and that is a different and more serious answer.
:::

## Asked for, versus installed

The system records whether each package was requested or pulled in:

```console
$ apt-mark showmanual | wc -l
17
$ apt-mark showauto | wc -l
157
```

Eighteen and one hundred and fifty-seven. The eighteen are recognisable — they are
nearly the Dockerfile's `apt-get install` line:

```text
bash binutils ca-certificates coreutils curl file gcc iproute2 less
libc6-dev libcap2-bin netcat-openbsd openssh-client openssl procps strace
```

The other 157 are the **dependency closure**: everything required to make those
eighteen work, computed at install time and recorded.

:::note
"Nearly" is doing real work there. The Dockerfile names **nineteen** packages —
`util-linux` is the one missing from the list above, and it is recorded as
*automatic* despite having been asked for. The record describes what the package
manager did, not a transcript of what you typed, and the two can differ for
packages that were already present. Read the marks as evidence rather than as
intent.
:::

This distinction is not bookkeeping. It is what makes `autoremove` possible: a
package marked automatic, with nothing left depending on it, can be removed
safely because nobody ever asked for it. It is also what makes `autoremove`
dangerous, because "nobody asked for it" is a statement about the *record*, and
the record is wrong the moment somebody installs something as a dependency and
then starts relying on it directly.

## What the closure costs

The 18-to-175 ratio is the honest answer to "how big is this install", and it is
usually a shock in one specific direction: **a small request can pull in an
enormous amount.** Asking for `gcc` on this system brought in `binutils`,
`cpp-14`, `libisl23`, `libmpfr6`, `libgcc-14-dev`, `linux-libc-dev` and dozens
more — a compiler is not one program.

Two consequences follow, and both come back later in the path:

**Image size is a dependency-graph property, not a discipline problem.** Shaving
megabytes off your application while installing a compiler is arithmetic that
does not work. The way to a small image is asking for less, not tidying more.

**Attack surface is the closure, not the request.** Every one of those 157
packages ships code that exists on the machine and can be reached. A CVE in
`libisl23` is yours, and you have almost certainly never heard of it.

:::callback{to=topic.the-layers}
A05.1 measured a container's size and found the base image dominating it. This
is that measurement explained: the base image is a dependency closure somebody
else computed, and you inherit all of it.
:::

## The three states of a file

Every file on the machine is in exactly one of these, and telling them apart is
most of the practical skill:

| State | `dpkg -S` says | You get |
|---|---|---|
| Owned | the package name | upgrades, security fixes, integrity checking, a version to report |
| Owned via alternatives | nothing, until you resolve the symlink | the same, once you know where to look |
| Unowned | nothing, ever | none of it — and no record that the file exists |

The third row is where the work is. Everything installed by a vendor script, a
language package manager, a `make install`, or a `COPY` in a Dockerfile lands
there. That is not wrong — it is often unavoidable — but each one is a permanent
obligation somebody accepted, usually without noticing.

:::objective{id=OBJ-B06.2.2}
:::

:::objective{id=OBJ-B06.2.4}
:::

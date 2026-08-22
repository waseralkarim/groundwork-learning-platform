---
topic: topic.packages-and-dependencies
section: overview
title: What put this file here
order: 1
mode: explain
---

There is a binary at `/usr/bin/openssl` on the machine you are reading this
from. Something put it there. On a Linux system that question has a real answer,
recorded at the time, queryable in about forty milliseconds:

```console
$ dpkg -S /usr/bin/openssl
openssl: /usr/bin/openssl
```

That is the whole of this topic in one command, and the reason it matters is
what happens when the answer comes back empty.

## The two answers that are interesting

Ask the same question about a different path on the same machine:

```console
$ dpkg -S /usr/bin/awk
dpkg-query: no path found matching pattern /usr/bin/awk
```

`awk` exists. You can run it. The database says nothing put it there. That is
the **first** interesting answer, and it has a specific and slightly technical
cause that turns out to explain a family of confusing behaviour.

Now ask about a file that this platform's own image installs:

```console
$ dpkg -S /opt/lab/seed-distro.sh
dpkg-query: no path found matching pattern /opt/lab/seed-distro.sh
```

Same message, completely different meaning. That file really is unowned. No
package placed it, so nothing will upgrade it, nothing will patch it, nothing
will notice if it changes, and nothing on the machine records that it exists.

**A package system is not a way of copying files onto a machine.** It is a way
of being able to answer questions about them afterwards. Every file outside it
is a file you have quietly agreed to answer those questions about yourself.

:::predict{question="On the machine you are about to work on, 18 packages were named in the Dockerfile. How many packages do you think are actually installed?"}
:::

## A package is a manifest first

The archive part of a package is unremarkable — files and their paths. What
makes it a package is everything shipped alongside:

- **Identity**: name, version, architecture, maintainer.
- **A dependency declaration**: what must exist for this to work, in four
  strengths that mean genuinely different things.
- **A file list**: every path it owns, which is what makes ownership queryable
  in both directions.
- **Checksums for configuration files**, so an upgrade can tell whether you
  edited them.
- **Scripts** that run before and after install and removal.

Almost every useful property of a managed system comes from that metadata rather
than from the files. You can ask what is installed, what version, what a file
belongs to, what would break if you removed it, and whether anything has been
tampered with — because somebody wrote it down at packaging time.

## The number nobody expects

This container's Dockerfile names eighteen packages, seventeen of which the
system records as deliberately installed. Count what is actually here:

```console
$ dpkg-query -W -f='${Package}\n' | wc -l
163
```

Seventeen are recorded as requested. **One hundred and forty-six arrived as a
consequence.** The system records which is which, and that distinction is what
makes it possible to remove something later without guessing.

That ratio is not waste, and it is not an accident. It is what "install curl"
actually means once you are honest about it — and if you have ever wondered why
a container image is 180 MB when you installed four things, the gap between 17
and 163 is the entire answer.

## Where this goes wrong in production

Three failures, all common, all with the same root:

**The dependency nobody declared.** A script works on the machine it was written
on and fails on a fresh one, because it calls a command that arrived as a
*recommendation* of something else. Nobody declared it. Nobody installed it on
purpose. It was simply there, until an image was built with
`--no-install-recommends` and it silently was not.

**The config that came back.** Somebody edits a configuration file, an upgrade
runs unattended six months later, and the edit is either reverted or preserved —
and which one happens depends on rules most people have never read. The residue
is left on disk in files with names nobody looks for.

**The file nothing owns.** An agent installed by `curl | sh` in 2023. It has a
version, it has a CVE, and there is no way to ask the machine about either,
because from the package database's point of view it does not exist.

None of these are exotic. All three are diagnosable in under a minute by
somebody who knows which question to ask.

## What you will do

Four labs on the real system underneath you:

- Follow file ownership in both directions, and find out what `awk` is doing.
- Trace 17 requested packages into 163 installed ones, and find the dependency
  that was skipped.
- Simulate removals until you find one the system refuses, and work out why.
- Run the integrity check, get **4,634 findings**, and identify the one that
  matters — which was caused by this platform's own Dockerfile.

:::objective{id=OBJ-B06.2.1}
:::

:::objective{id=OBJ-B06.2.6}
:::

---
topic: topic.the-filesystem-hierarchy
section: core-concepts
title: Who owns what, and what survives
order: 2
mode: explain
---

Two questions separate every directory from every other one: **who is allowed to
write here**, and **what happens if this disappears**. Everything practical
follows from those.

:::diagram{src=../diagrams/ownership-contract.mmd caption="The four ownership zones. The red one is the only part of the filesystem the package system is forbidden from touching."}
:::

## The zone packages own

`/usr` is everything installed by a package, and nothing that changes at
runtime. That second half is the important one, and it is what makes the first
half useful:

```console
$ du -sh /usr
306M   /usr
$ du -sh /usr/* | sort -rh | head -4
143M   /usr/lib
72M    /usr/bin
66M    /usr/libexec
13M    /usr/include
```

306 MB of a roughly 320 MB image. **The image essentially is `/usr`.** That is
worth holding next to what B06.2 measured: 18 packages requested, 175 installed,
and this is where all of them landed.

Because nothing under `/usr` changes while the system runs, it can be mounted
read-only, shared between machines, or shipped as an immutable container layer.
Those are the same property used three different ways.

## The usr-merge

`/bin`, `/sbin`, `/lib` and `/lib64` are not directories:

```console
$ ls -l / | grep '^l'
lrwxrwxrwx  bin   -> usr/bin
lrwxrwxrwx  lib   -> usr/lib
lrwxrwxrwx  lib64 -> usr/lib64
lrwxrwxrwx  sbin  -> usr/sbin
```

Historically the split meant something: `/bin` held what was needed to boot and
repair a system before `/usr` was mounted, and `/usr` could live on a separate
or remote disk. Initramfs made that unnecessary — the tooling needed early now
lives in the initramfs image instead.

Two consequences you will actually meet. **`/bin/sh` and `/usr/bin/sh` are the
same file**, so a path comparison that treats them as different is wrong. And
**`/usr` alone is now a complete installed system**, which is precisely what
makes a container image a single directory tree you can hash.

## The zone you own

Three directories are reserved for software the distribution did not install:

| Directory | For | Owned by a package? |
|---|---|---|
| `/usr/local` | software you build or install yourself | **no** |
| `/opt` | self-contained third-party trees, one per vendor | **no** |
| `/srv` | data this machine serves to others | **no** |

The "no" column is verifiable rather than folklore:

```console
$ for d in /usr/local /usr/local/bin /opt /srv; do dpkg -S $d; done
dpkg-query: no path found matching pattern /usr/local
dpkg-query: no path found matching pattern /usr/local/bin
dpkg-query: no path found matching pattern /opt
dpkg-query: no path found matching pattern /srv
```

And the contrast that proves it is deliberate rather than accidental:

```console
$ dpkg -S /var/log
base-files, apt: /var/log
```

`/var/log` **is** owned. So the package system is perfectly capable of claiming
a directory; it declines to claim these three, because Debian policy forbids any
package from installing files under `/usr/local`. The directories are created by
`base-files.postinst` at install time so that they exist for you to use, without
anybody owning them.

:::note
This is the hierarchy telling you in advance which parts of the filesystem will
answer "no package owns this" — the finding B06.2 treated as a discovery. A
`dpkg -S` that comes back empty under `/usr/local` or `/opt` is the system
working as designed. The same answer under `/usr/bin` is a genuine finding.
:::

## The zone that changes

`/var` is where the system writes as it runs, and treating it as one thing is
the most expensive mistake in this topic. Its subdirectories have completely
different value:

| Path | Holds | If you lose it |
|---|---|---|
| `/var/lib` | state a program cannot regenerate | **information is gone** |
| `/var/cache` | data it can regenerate | it is slow for a while |
| `/var/log` | history | you lose the ability to explain the past |
| `/var/spool` | work in flight — mail, print, at jobs | queued work is lost |
| `/var/tmp` | scratch that survives a reboot | nothing |

On this machine the split is stark:

```console
$ du -sh /var/lib/* | sort -rh | head -3
6.9M   /var/lib/dpkg
40K    /var/lib/systemd
32K    /var/lib/apt
```

`/var/lib/dpkg` — the package database — is 6.9 MB of the 7.0 MB in `/var/lib`.
**The state of this machine is almost entirely the record of what is installed
on it**, which is a fair description of a container.

## The zone that does not survive

`/run` and `/tmp` are both tmpfs, both empty at every boot, and they mean
different things:

- **`/run`** is runtime data for *this boot* — pid files, sockets, lock files.
  It is deliberately empty at start, which is what makes stale pid files a
  solved problem rather than a recurring one.
- **`/tmp`** is scratch for anyone, mode `1777` — world-writable with the sticky
  bit, so anyone may create files and only the owner may delete them.

```console
$ stat -c '%A %U:%G' /tmp /run
drwxrwxrwt root:root
drwxr-xr-x root:root
```

Those two modes differ, and in the lab container that difference decides
something real — `/run` is mounted read-write and a non-root process still
cannot write to it. Which is the subject of the next lesson.

## Reading a machine you have never seen

The contract makes an unfamiliar system legible in about a minute:

```bash
ls -l /            # what is a symlink? (usr-merge, and anything unusual)
du -sh /usr /var /etc /opt /usr/local
ls /opt /usr/local/bin    # what did somebody install outside the archive?
```

That third line is the one worth building a habit around. `/opt` and
`/usr/local/bin` are where unpackaged software is *supposed* to live, so
whatever is there is, by construction, the software nobody is patching.

:::objective{id=OBJ-B06.3.2}
:::

:::objective{id=OBJ-B06.3.4}
:::

---
topic: topic.the-filesystem-hierarchy
section: overview
title: A contract, not a filing system
order: 1
mode: explain
---

Most explanations of the Linux directory layout are a table: `/etc` is
configuration, `/var` is variable data, `/usr` is programs. That is true and it
is not worth a topic, because it does not help you decide anything.

Here is the version that does. Ask the package database who owns `/usr/local`:

```console
$ dpkg -S /usr/local
dpkg-query: no path found matching pattern /usr/local
```

The directory exists. Ten subdirectories under it exist. **No package owns any
of them**, and that is not an oversight — across all 163 packages on this
machine, exactly zero ship a single file under `/usr/local` or `/opt`:

```console
$ grep -rl "usr/local" /var/lib/dpkg/info/*.list | wc -l
0
```

The directories were created by a script, not shipped as package contents.
`base-files` has a function for it, and the name says what it is for:

```sh
install_local_dir /usr/local
install_local_dir /usr/local/bin
install_local_dir /usr/local/lib
```

**The hierarchy is an ownership contract.** Some directories belong to packages,
some belong to you, and the boundary is enforced by policy on one side and
recorded in the database on the other. Once you can see that, the layout stops
being arbitrary and starts telling you things in advance.

:::predict{question="This container image is about 320 MB. How much of that do you think lives under /usr — and which top-level directories do you expect to be completely empty?"}
:::

## Three questions the contract answers

**Where does my software go?** If a package may never write to `/usr/local`,
then software you install there can never be clobbered by an upgrade — and will
never be patched by one either. That is the same trade B06.2 measured from the
other direction, and the hierarchy told you about it before you installed
anything.

**What has to survive?** `/var/lib` holds state a program cannot regenerate.
`/var/cache` holds data it can. They are adjacent, they look identical, and
confusing them means either backing up 210 GB of thumbnails every night or
losing a database.

**What must be writable?** This is the question containers made urgent. Run with
a read-only root filesystem and the answer stops being a matter of opinion:

```console
$ touch /var/log/app.log
touch: cannot touch '/var/log/app.log': Read-only file system
```

The lab container you are about to work in runs exactly like that. Only three
paths accept a write, and finding out which — by trying — is more instructive
than any table.

## What is actually here

The layout was designed for a machine with disks, users and a boot loader. A
container has none of those, and it shows:

| Directory | On this image |
|---|---|
| `/usr` | 306 MB — essentially the entire image |
| `/var` | 8.8 MB, of which the package database is 6.9 MB |
| `/etc` | 1.4 MB, 111 files |
| `/boot` `/media` `/mnt` `/root` `/srv` | **empty** |
| `/bin` `/sbin` `/lib` `/lib64` | not directories at all — symlinks into `/usr` |

That last row is the **usr-merge**, and it is the reason the first row is
possible: once everything installed lives under one directory, `/usr` can be
shared, mounted read-only, or shipped as a layer, because nothing in it changes
while the system runs.

## Where this goes wrong in production

**The mount that hid the files.** A volume mounted over a directory does not
merge with it — it covers it. The files underneath are intact and unreachable,
which looks exactly like data loss and is not.

**The read-only rollout that broke a service that writes nothing.** The
application writes no files. The TLS library caches a random seed in `$HOME`,
the runtime writes performance data to `/tmp`, and neither is in anyone's
mental model of the application.

**The backup that could not be restored.** `/etc` and `/var` were captured
faithfully every night for fourteen months, and the thing that made the service
work was installed by a vendor script into `/opt`.

All three are decidable in a minute by someone who reads the hierarchy as a
statement about ownership and lifetime.

## What you will do

Four labs on the real system underneath you:

- Ask the package database who owns each directory, and find the three it
  refuses to claim.
- Classify one service's seventeen paths into code, config, state, cache and
  ephemeral, then work out what a backup should actually contain.
- Attempt nine ordinary writes under a read-only root, and separate the ones
  the **mount** denied from the one the **permission bits** denied.
- Take a stateful service and produce the shortest list of writable paths that
  lets it run.

:::objective{id=OBJ-B06.3.1}
:::

:::objective{id=OBJ-B06.3.3}
:::

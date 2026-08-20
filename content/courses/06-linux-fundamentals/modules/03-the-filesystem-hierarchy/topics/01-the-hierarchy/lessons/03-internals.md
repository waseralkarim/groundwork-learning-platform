---
topic: topic.the-filesystem-hierarchy
section: internals
title: Two gates, and what a mount hides
order: 3
mode: explain
---

A write can be refused for two entirely independent reasons, and telling them
apart is the difference between a five-minute fix and an afternoon.

:::diagram{src=../diagrams/two-gates.mmd caption="The mount is checked first and knows nothing about who you are. The permission bits are checked second and know nothing about how the filesystem was mounted."}
:::

## The mount is a property of the filesystem, not of the file

`chmod 777` cannot make a read-only filesystem writable. The mount is checked
first, it applies to every process including root, and it produces a distinct
error:

```console
$ touch /var/log/app.log
touch: cannot touch '/var/log/app.log': Read-only file system     # EROFS
$ touch /run/app.pid
touch: cannot touch '/run/app.pid': Permission denied             # EACCES
```

**Two different messages for two different gates.** `Read-only file system` is
the mount. `Permission denied` is the mode. People read both as "permissions"
and go and change the wrong thing.

The lab container demonstrates both at once, because it runs with a read-only
root and three tmpfs mounts:

```console
$ awk '$2=="/run"{print $4}' /proc/mounts
rw,nosuid,nodev,noexec,relatime,size=16384k,mode=755
$ stat -c '%A %U:%G' /run
drwxr-xr-x root:root
```

`/run` is mounted **read-write** and a process running as uid 10001 still cannot
write to it, because the directory is `755` and owned by root. The mount says
yes; the mode says no. That is the case worth being able to recognise, because
the fix is completely different — you cannot remount your way out of it.

## The options that are not about writing

Three mount options deny things the permission bits cannot express:

- **`noexec`** — nothing on this filesystem may be executed, whatever its mode
  bits say.
- **`nosuid`** — setuid and setgid bits are ignored here.
- **`nodev`** — device nodes on this filesystem do not work.

They exist for exactly one reason: **a directory anyone can write to is a
directory anyone can put a program in.** `noexec` on `/tmp` is a standard
hardening measure for that reason, and this platform deliberately does *not*
apply it to `/tmp` — half the curriculum has learners compile and run a program,
and a lab where `gcc hello.c && ./a.out` fails with "Permission denied" is not a
lab. The decision is written down in the broker's configuration next to the flag.

`/dev/shm` shows the other side of the same trade:

```console
$ awk '$2=="/dev/shm"{print $4}' /proc/mounts
rw,nosuid,nodev,noexec,relatime,size=65536k
$ stat -c '%A' /dev/shm
drwxrwxrwt
```

Mode `1777` — anyone may write. Mount `noexec` — nobody may run what they wrote.
Worth noticing that this mount is a **Docker default**: nothing in the lab
broker's configuration mentions `/dev/shm`, so it is a writable, world-writable
path that nobody explicitly authorised. It is harmless because of `noexec`,
which is what defence in depth looks like when it works.

:::predict{question="Under a read-only root, of these nine paths — /var/log, /var/lib, /var/cache, /run, /etc, /usr/local/bin, /tmp, $HOME, /dev/shm — how many accept a write? And which of the failures is NOT caused by the read-only mount?"}
:::

## Mounting over a directory hides it

This is the one that costs people a day.

```console
$ ls /opt/lab
seed.sh  seed-packages.sh  make-zombie  ...

# somebody mounts a volume there
$ mount /dev/sdb1 /opt/lab
$ ls /opt/lab
lost+found
```

The original files are **not gone**. They are on the underlying filesystem,
intact, and unreachable while something is mounted over the top. Unmount and
they reappear.

This platform relies on the behaviour deliberately, which is the clearest way to
see that it is a feature. The Dockerfile writes the learner's shell settings to
`/etc/bash.bashrc` rather than to `~/.bashrc`, and the comment explains why:

> tmpfs is mounted over `/home/learner` at start, masking anything baked in
> there.

Anything the image places in `/home/learner` is invisible the moment the
container starts, because a tmpfs covers it. So the settings go somewhere the
mount does not cover.

The diagnostic, when files "vanish":

```bash
mountpoint /opt/lab              # is something mounted here?
findmnt /opt/lab                 # what, and with which options?
```

If `mountpoint` says yes and you did not expect a mount, you have found it. In a
container the equivalent question is which volumes and binds the runtime
attached, and the answer is in `/proc/1/mountinfo` whether or not anybody
documented it.

## What the runtime hides on purpose

Masking is also used as a security control, and you can watch it happen:

```console
$ grep '^tmpfs /proc' /proc/mounts | awk '{print $2}'
/proc/acpi
/proc/interrupts
/proc/kcore
/proc/keys
/proc/latency_stats
/proc/scsi
/proc/timer_list
```

Seven paths under `/proc` that Docker covers before the container starts.
`/proc/kcore` is the interesting one: on a host it is a window onto all of
physical memory. Inside the container it is `/dev/null` wearing its name.

```console
$ ls -l /proc/kcore
crw-rw-rw- 1 root root 1, 3 ... /proc/kcore
```

A character device, major 1 minor 3 — that is `/dev/null` exactly. The kernel
still has `/proc/kcore`; this process cannot reach it, because something is
mounted over the path. **The same mechanism that loses somebody's data by
accident is what keeps a container out of host memory on purpose.**

## Why read-only roots are worth the trouble

Running with the root filesystem read-only converts an unknown into a list. You
stop guessing where a program writes and get told, at startup, in an error
message with a path in it.

What it buys:

- **A tamper-resistant system.** Nothing can modify a binary or drop one into
  `/usr/local/bin`, because there is no writable path that is also executable.
- **An explicit inventory of state.** Every writable path had to be declared, so
  the list of things worth persisting is the same list.
- **Confidence that a restart is clean**, because there is nowhere for drift to
  accumulate.

What it costs is the work of finding out what actually needs to be writable —
which is nearly always more than the application's authors think, because the
runtime, the TLS library and the resolver all write things nobody remembers.

:::objective{id=OBJ-B06.3.5}
:::

:::objective{id=OBJ-B06.3.6}
:::

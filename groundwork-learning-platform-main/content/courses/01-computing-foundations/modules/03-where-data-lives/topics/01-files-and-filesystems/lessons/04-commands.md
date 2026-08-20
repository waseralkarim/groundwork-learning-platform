---
topic: topic.files-and-filesystems
section: commands
title: Answering "why is the disk full"
order: 4
mode: do
---

The whole diagnosis is four commands, in this order. Running them out of order is
what turns it into an afternoon.

## 1. df -h and df -i, together

```bash
df -h /var    # blocks
df -i /var    # inodes
```

Always both. They fail identically — `ENOSPC` — and have completely different
fixes.

```text
Filesystem      Size  Used Avail Use% Mounted on
/dev/sda1        50G   47G  0.5G  99% /var      ← out of blocks

Filesystem     Inodes  IUsed IFree IUse% Mounted on
/dev/sda1        3.2M   3.2M     0  100% /var   ← out of inodes
```

Out of inodes means millions of small files, and on ext4 the count is fixed at
format time — so the fix is deleting files or reformatting, not adding a disk.

:::try{lab=space-and-inodes run="df -h /tmp; df -i /tmp" title="Both numbers for this lab's /tmp"}
`/tmp` here is a tmpfs, so its size is a mount option rather than a disk. Note
how many inodes it has: tmpfs allocates them dynamically, which is why inode
exhaustion is an ext4 problem far more than a tmpfs one.
:::

## 2. du, and why it disagrees

```bash
du -x -h --max-depth=1 /var | sort -h | tail -15
```

`-x` matters: without it `du` crosses into other filesystems and you spend ten
minutes measuring something that is not full.

If `du`'s total is close to `df`'s used figure, you have found the space and can
go delete something. **If it is far smaller, stop** — the space is held by
something with no name, and deleting more files will not help.

## 3. Deleted-but-open files

```bash
lsof +L1                      # every open file with no name left
lsof -nP | grep '(deleted)'   # the same, on older lsof
```

Without `lsof` — which is most containers — `/proc` has it directly:

```bash
ls -l /proc/*/fd/* 2>/dev/null | grep '(deleted)'
```

:::terminal{title="The answer, in one line"}
$ ls -l /proc/*/fd/* 2>/dev/null | grep '(deleted)'
l-wx------ 1 app app 64 Aug 16 03:33 /proc/1487/fd/3 -> /var/log/app/app.log (deleted)
:::

PID 1487 is holding a deleted log file. Every block it occupies is still charged
to the filesystem and invisible to `du`.

**The fix, in order of preference:**

```bash
kill -HUP 1487          # if the service reopens its logs on SIGHUP — best
: > /var/log/app/app.log  # truncate in place: frees space, keeps the descriptor
systemctl restart app     # works, and costs an outage
```

That middle one is the trick worth remembering: truncating a file the process is
still writing to frees the blocks without breaking anything, because the
descriptor points at the inode and the inode survives.

:::warning
Never delete a log a process is actively writing to. Truncate it. Deleting is
what creates this problem in the first place: the name goes, the writer keeps
its descriptor, the space stays used, and the file keeps growing where nobody can
see it.
:::

## 4. What is actually mounted

```bash
findmnt                 # readable tree
cat /proc/mounts        # always present, even in a minimal image
findmnt -no OPTIONS /   # just the options for one path
```

This answers "why can I not write here" when the answer is not space at all.

:::try{lab=your-root-is-an-overlay run="grep ' / ' /proc/mounts" title="What your lab's root really is"}
Look for `overlay` as the type, and the `lowerdir=` list — those are the image
layers this container was assembled from. Count the colons: each path is one
layer, and every container from this image shares all of them.
:::

## Files and links

```bash
stat file                      # inode, links, size, blocks, timestamps
ls -li                         # inode number in the first column
find /data -inum 4211          # every name for one inode
find /data -type f -links +1   # files with more than one name
ls -l link                     # a symlink shows its target
readlink -f link               # resolve it fully
```

The `-links +1` search is how you find hard links you did not know existed —
usually a backup script that thought it was copying.

## Where the space went, when it is genuinely files

```bash
du -x -h --max-depth=1 / | sort -h | tail
find /var -xdev -type f -size +500M -exec ls -lh {} +
find /var -xdev -type f -printf '%T@ %p\n' | sort -n | tail -20   # oldest
```

And for the container case specifically:

```bash
docker system df           # images, containers, volumes, build cache
docker system df -v        # per-image and per-volume detail
```

Build cache is the usual culprit on a CI host, and it is invisible to everything
above because it lives inside the runtime's own storage.

:::checkpoint
Without scrolling up:

1. `df` says 99% full, `du -x -sh` on the same filesystem says 6 GB. What now?
2. Which command distinguishes running out of space from running out of inodes?
3. How do you free the space held by a log a running process still has open,
   without restarting it?
4. What does `lowerdir=` in a mount line tell you about a container?
:::

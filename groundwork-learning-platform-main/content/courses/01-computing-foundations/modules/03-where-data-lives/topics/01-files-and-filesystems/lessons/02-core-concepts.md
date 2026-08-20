---
topic: topic.files-and-filesystems
section: core-concepts
title: Inodes, links and mounts
order: 2
mode: explain
---

:::objective{id=OBJ-A01.5.1}
Explain what an inode holds and what a filename actually refers to.
:::

## The inode holds everything except the name

```text
$ stat report.txt
  File: report.txt
  Size: 4096       Blocks: 8       IO Block: 4096   regular file
Device: 8,1        Inode: 4211     Links: 2
Access: (0644/-rw-r--r--)  Uid: (1000/ada)   Gid: (1000/ada)
Modify: 2026-08-16 09:14:02.115 +0000
```

Type, permissions, owner, size, timestamps, link count, and pointers to the data
blocks. Every attribute a file has, and not its name — the name lives in the
directory that points at this inode.

That is why `chmod`, `chown` and truncation are visible through *every* name a
file has: they change the inode, and the names are only references.

:::objective{id=OBJ-A01.5.2}
Distinguish a hard link from a symbolic link, and predict what removing each one
does to the data.
:::

## Two kinds of link, and they are not similar

**A hard link is another name for the same inode.**

```bash
ln report.txt backup.txt      # same inode, link count 2
```

There is no original. Both entries are equal, both give the same inode number
under `stat`, and the data survives until both are removed. A hard link cannot
cross a filesystem boundary — inode numbers are only unique within one — and
cannot point at a directory, because a cycle in the directory tree would make it
untraversable.

**A symbolic link is a file whose contents are a path.**

```bash
ln -s /var/log/app/current.log latest    # a separate inode holding text
```

Following it is a second lookup, which is why it can point at a path that does
not exist, can cross filesystems, and breaks when the target moves. `ls -l` shows
the text it holds.

| | Hard link | Symbolic link |
|---|---|---|
| Own inode | No — shares one | Yes |
| Can dangle | No | Yes |
| Crosses filesystems | No | Yes |
| Survives target rename | Yes | No |
| `rm` of the other name | Data survives | Link breaks |

:::warning
This is where the classic log-rotation bug lives. Rotating by *renaming* the file
does not break a writer's descriptor — the process is holding the inode, not the
name — so it happily keeps writing to the renamed file, and the new one stays
empty. That is why `logrotate` has `copytruncate`, and why sending the service a
signal to reopen its log is the more correct fix.
:::

## Deleting is decrementing

`unlink()` — what `rm` calls — removes one directory entry and decrements the
inode's link count. Data is freed when **both** of these are true:

1. The link count is zero, and
2. No process has the file open.

The second condition is the one that fills disks. A process holding a deleted
file keeps every block it occupies, invisibly: no name means nothing for `du` to
find, while `df` still counts the blocks as used.

This is not a bug. Freeing blocks under a process that is still writing to them
would be catastrophic, so the kernel waits. The file genuinely vanishes when the
last descriptor closes — often when someone restarts the service, which is why
restarting "fixes" it and nobody learns anything.

:::objective{id=OBJ-A01.5.3}
Interpret a mount table, identifying filesystem types and the options that decide
what can be written where.
:::

## Mounts: one tree, many filesystems

Linux presents one directory tree, assembled from many filesystems. Attaching one
at a directory is a **mount**, and everything below that point is served by it.

```text
$ findmnt
TARGET      SOURCE     FSTYPE   OPTIONS
/           overlay    overlay  ro,relatime,lowerdir=...,upperdir=...
├─/proc     proc       proc     rw,nosuid,nodev,noexec
├─/sys      sysfs      sysfs    ro,nosuid,nodev,noexec
├─/tmp      tmpfs      tmpfs    rw,nosuid,nodev,size=2097152k
└─/data     /dev/sdb1  ext4     rw,relatime
```

Read it as a set of rules about what is possible where:

- **`/` is `overlay` and `ro`** — this container has a read-only root filesystem
- **`/tmp` is `tmpfs`** — in memory, so it is fast, empty at start, discarded at
  exit, and counted against the memory limit rather than the disk
- **`noexec` on `/proc` and `/sys`** — nothing under them can be executed
- **`/data` is a real device** — the only place here that survives a restart

Mount options are per-mount, not per-file, and they beat permissions. A
read-only mount refuses root. This is why `EROFS` and `EACCES` are different
errors with different fixes, which you met at the kernel boundary and can now
locate on a mount table.

:::note
`findmnt` is the readable one. `cat /proc/mounts` shows the same information as
raw text and is what to reach for when `findmnt` is not installed — which, in a
minimal container image, is most of the time.
:::

## Filesystems have two things to run out of

A filesystem allocates **blocks** for data and **inodes** for files. Both are
finite, and exhausting either produces the same `ENOSPC`.

```bash
df -h /data    # blocks:  100G total, 12G used
df -i /data    # inodes:  6.5M total, 6.5M used   ← this is the problem
```

Classic ext4 defaults allocate one inode per 16 KB of capacity at format time.
Millions of tiny files — session data, cache entries, a mail queue — exhaust
inodes long before space, and `df -h` shows a comfortable disk while every write
fails.

The fix is rarely "add space": inode counts are fixed at format time on ext4, so
it is either delete the small files or reformat with more inodes. XFS allocates
inodes dynamically and mostly avoids the problem.

:::predict{question="`ls -l backup.img` says 10 GB. `du -h backup.img` says 12 KB. Which is lying?"}
Neither. It is a **sparse file**.

`ls -l` reports the file's apparent size — the offset of its furthest byte. `du`
reports the blocks it actually occupies. A file written with large gaps, or
created by seeking past the end, has ranges that were never written and were
never allocated. Reading them returns zeros the kernel produces on demand.

Virtual machine images, database files and core dumps are routinely sparse, and
the difference matters operationally: copying a sparse file with a tool that does
not understand holes writes out every zero, and a 12 KB file becomes a genuine 10
GB one. `cp --sparse=always`, `rsync -S` and `tar -S` preserve the holes.

The same distinction explains one class of "the backup is enormous" surprise —
and it is the second reason `du` and `df` disagree, after deleted-but-open files.
:::

## The one-sentence version

Names point at inodes, inodes own the data, data survives until the last name
*and* the last open descriptor are gone; mounts decide what is writable where;
and a filesystem can run out of files as easily as it runs out of space.

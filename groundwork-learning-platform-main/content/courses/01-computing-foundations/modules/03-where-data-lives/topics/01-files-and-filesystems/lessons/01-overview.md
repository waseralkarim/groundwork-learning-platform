---
topic: topic.files-and-filesystems
section: overview
title: A filename is not a file
order: 1
mode: explain
---

Someone deletes 40 GB of logs. `df` still says the disk is full. They delete
more. It is still full. Eventually somebody restarts the service and the space
comes back all at once, and nobody ever finds out why.

That incident happens somewhere every week, and it has a one-sentence
explanation: **a filename is not a file.** Removing a name is not removing data,
and the kernel frees the blocks only when the last name is gone *and* no process
still has the file open.

This topic is about what a file actually is, where a container's writes really
go, and how to answer "why is the disk full" in two commands instead of an
afternoon.

## The specific things this explains

- Deleting a huge log file frees no space until the service is restarted
- `du -sh /` reports 4 GB on a filesystem `df` says is 100% full
- A filesystem is full with gigabytes free, because it ran out of inodes
- Everything a container writes vanishes when it is removed, but a volume
  survives
- Changing one byte of a large file inside a container consumes its whole size
- Ten containers from one image cost far less disk than ten times one container
- A container gets `Read-only file system` on a path that looks perfectly normal
- `ls -l` says a file is 10 GB and `du` says it is 12 KB, and both are right

## What a file is made of

:::diagram{src=../diagrams/inode-and-names.mmd caption="Names point at an inode; the inode owns the data"}

Everything about a file — its permissions, owner, size, timestamps, and the
location of its data — lives in an **inode**. The inode has a number, and that
number is unique within its filesystem.

What a filename does is far less than people assume. A directory is just a file
containing a list of *(name, inode number)* pairs. Looking up `/tmp/report.txt`
means reading `/`, then `tmp`, then finding the entry called `report.txt` and
learning which inode it refers to.

Three consequences follow immediately, and each of them is a production
behaviour:

**A file can have several names.** Add a second entry pointing at the same
inode and you have a hard link. Neither name is the original; the inode counts
how many exist.

**Removing a name is not removing data.** `rm` deletes a directory entry and
decrements the count. Only when it hits zero does the data become free — and
even then, not while a process still holds the file open.

**Renaming within a filesystem is nearly free.** It rewrites a directory entry.
The data does not move, which is why `mv` across a filesystem boundary is slow
and `mv` within one is instant.

:::predict{question="You delete a 40 GB log file. `df` still shows the disk full. What is holding it, and what would you check first?"}
A process still has the file open.

`rm` removed the name. The inode's link count fell to zero, but the kernel does
not free a file that any process still holds a descriptor for — the writer would
be scribbling into blocks that had been handed to someone else. So the data stays
until the last descriptor closes.

The evidence is that `du` and `df` disagree: `du` walks names, and there is no
name any more, so it does not count the file. `df` asks the filesystem how many
blocks are free, and they are not.

The check is `lsof +L1`, or reading `/proc/*/fd/` for a link that ends in
`(deleted)`. The fix is to make the holder let go — restart it, or if it is a log
you truncate it in place with `: > /path/to/log` instead of deleting it, which
frees the space without breaking the descriptor the process is writing to.
:::

## Your container's root filesystem is a stack

The second half of this topic is the one that matters most for containers.

A container's `/` is not a disk. It is an **overlay**: several read-only layers
from the image, plus one writable layer for this container, presented as a single
tree. Every container from the same image shares one copy of those read-only
layers.

That single design decision explains image size, build caching, why volumes
exist, why `docker run` is instant, and why editing a large file inside a
container is unexpectedly expensive. All of it comes back in **C14** wearing
Docker's vocabulary — but the mechanism is here.

## What you already have

:::callback
From **User Space and the Kernel**: `EROFS` means the filesystem was mounted
read-only and no user, root included, can write to it. This topic explains what
a mount actually is, and why a container's root is read-only in a hardened
deployment while `/tmp` still works.
:::

From **Virtual Memory**: the page cache holds file data in RAM, and writes land
there before they reach the device. That is the same fact this topic's durability
section starts from — a write that returned successfully is not yet on disk.

## How to work through it

Concepts, mechanism, tools, production. Four labs: take a file apart and find
its inode, look at the overlay your own lab is running on, watch `df` and `du`
disagree, and then diagnose a filesystem that stays full after everything has
been deleted.

The last one is the incident from the first paragraph. You will be able to solve
it in two commands.

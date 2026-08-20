---
topic: topic.files-and-filesystems
section: internals
title: The filesystem your containers actually run on
order: 3
mode: explain
---

:::objective{id=OBJ-A01.5.4}
Explain how an overlay filesystem composes image layers, and where a container's
writes actually land.
:::

A container's root filesystem is not a disk, a copy, or a virtual machine's
image. It is a **view**, assembled at start-up from directories that already
exist on the host.

:::diagram{src=../diagrams/overlay-layers.mmd caption="Read-only layers shared by every container, plus one writable layer each"}

## What overlayfs does

Overlayfs takes a stack of read-only directories — the **lowerdirs** — and one
writable directory, the **upperdir**, and presents them as a single tree.

Lookups go top-down: the upper layer first, then each lower layer in order. The
first match wins.

```text
overlay / overlay ro,lowerdir=/…/snapshots/9570/fs:/…/9309/fs:/…/9308/fs,
                     upperdir=/…/snapshots/9571/fs,workdir=/…/9571/work
```

That is a real mount line from a lab container in this course. Each `lowerdir`
path is one image layer — one `RUN` or `COPY` in a Dockerfile — and the
`upperdir` is this container's own writable space, created when it started and
deleted when it is removed.

Five consequences, all of which people meet as separate mysteries:

**Containers start instantly.** Nothing is copied. Starting a container creates
an empty upperdir and mounts a view.

**Ten containers from one image cost one image.** The lowerdirs are shared,
read-only, on one copy on disk — and their page cache is shared too, so they
share RAM as well.

**Everything written is discarded.** The upperdir is removed with the container.
That is not data loss; it is the design, and it is why volumes exist.

**Layers only add.** A file deleted in a later layer is not removed from the
earlier one — overlayfs records a *whiteout* that hides it. So `RUN rm
/big-file` after the layer that added it makes the image no smaller. The fix is
never to add it: one `RUN` that installs, uses and cleans up.

**Modifying a file copies all of it.** This is copy-up, and it is the one that
surprises people.

## Copy-up

Lower layers are read-only, so the first write to any file from a lower layer
copies the **entire file** into the upperdir first, then modifies the copy.

Appending one line to a 2 GB log inherited from the image costs 2 GB of disk and
the time to copy it. Doing that in ten containers costs 20 GB.

:::warning{scope=production}
This is why a database's data directory must be a volume, never the container's
filesystem. Every write to a large data file triggers copy-up on first touch,
then continues in the upper layer — slow, storage-hungry, and discarded when the
container is replaced.

The rule that follows: **anything written frequently or worth keeping belongs on
a volume.** Not for durability alone, but because the overlay is the wrong shape
for writes.
:::

## Volumes and bind mounts

Both put a real directory into the tree, so writes bypass the overlay entirely:
they land on the host filesystem, they survive the container, and they have no
copy-up cost.

- A **volume** is managed by the runtime, in its own storage area.
- A **bind mount** attaches a specific host path, which is why it is the
  development idiom and a supply-chain hazard in production: the container can
  write anywhere the mount allows.

A hardened container is usually a read-only root plus writable mounts exactly
where they are needed:

```yaml
read_only: true
tmpfs:
  - /tmp
volumes:
  - app-data:/var/lib/app
```

Which is precisely the shape of the lab containers in this course, and the reason
writing to `/opt` in an earlier lab produced `EROFS` while `/tmp` worked.

:::objective{id=OBJ-A01.5.7}
Explain what fsync guarantees, and why a write that returned successfully is not
yet durable.
:::

## A successful write is not on disk

`write()` returning success means the kernel has your bytes. It does not mean the
device does.

The data sits in the page cache, marked dirty, and is written out later — by a
kernel thread, on a timer, or under memory pressure. If the machine loses power
in between, the write is gone, and the application was told it succeeded.

**`fsync(fd)`** is the request to make it durable: it returns when the device has
confirmed the data is stored. It is expensive precisely because it is a real
round trip, and it is the difference between "the database says it committed" and
"the transaction survives the power cut".

Three things worth knowing, because each is a real incident:

**`fsync` on the file is not enough for a new file.** The file's data may be
durable while the *directory entry* naming it is not, so after a crash the data
exists in an inode nothing points at. Creating a file durably means fsyncing the
file and then its directory.

**The safe-rename pattern relies on this.** Write to a temporary file, fsync it,
then `rename()` over the target. Rename within a filesystem is atomic, so a
reader sees either the old file or the complete new one, never a half-written
mess.

**Disabling fsync makes everything faster and is sometimes correct.** A cache
that can be rebuilt does not need durability. Deciding that deliberately is fine;
discovering it after an outage is not.

:::callback
From **Virtual Memory**: the page cache is file data held in RAM, reclaimable on
demand. Durability is the other side of that fact — the reason data can be in the
cache and not on the device is the same reason reads are fast.
:::

## Putting it together

A container writes to a path. Which filesystem serves it decides everything that
follows:

| Path | Backed by | Survives restart | Copy-up cost | Counts against |
|---|---|---|---|---|
| `/usr/bin` | image layer, read-only | n/a | writes fail (`EROFS`) | — |
| `/app/cache` | overlay upperdir | no | yes, on first write | disk |
| `/tmp` (tmpfs) | memory | no | none | **memory limit** |
| `/var/lib/app` (volume) | host filesystem | yes | none | host disk |

That table is most of container storage. The rest of **C14** is vocabulary on top
of it.

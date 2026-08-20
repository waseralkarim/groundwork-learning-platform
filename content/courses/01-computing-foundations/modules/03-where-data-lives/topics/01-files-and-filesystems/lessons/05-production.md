---
topic: topic.files-and-filesystems
section: production
title: Five ways storage bites
order: 5
mode: explain
---

:::objective{id=OBJ-A01.5.8}
Troubleshoot a container that cannot write, separating a full filesystem from a
read-only mount from a permission failure.
:::

## 1. The disk that stays full

The incident from the first lesson, and the most common storage failure there is.

Logs are deleted. `df` does not move. Someone deletes more, then restarts the
service, and the space appears — so the runbook grows a line saying "restart the
service when the disk is full", and the actual cause is never found.

Two commands settle it:

```bash
du -x -sh /var/log          # names
ls -l /proc/*/fd/* 2>/dev/null | grep '(deleted)'   # no names
```

A large gap between `du` and `df` means the space is held by files with no name.
The fix is to make the holder let go — a signal to reopen, or truncation in
place — not to delete more.

**The prevention is log rotation that the writer knows about.** Rotating by
renaming leaves the process writing to the renamed file; `copytruncate`, or a
signal that makes it reopen, is the correct arrangement.

## 2. Read-only file system, on a path that looks fine

A hardened container has `readOnlyRootFilesystem: true`, and the application
writes a cache or a PID file somewhere ordinary. It fails at start-up with
`EROFS`, which reads like a permissions problem and is not.

```bash
findmnt -no FSTYPE,OPTIONS /var/lib/app
# overlay ro,relatime,lowerdir=...
```

No `chmod` and no capability changes this. The fix is a writable mount at that
path — a volume for anything worth keeping, a tmpfs for scratch:

```yaml
readOnlyRootFilesystem: true
volumeMounts:
  - { name: cache, mountPath: /var/lib/app }
volumes:
  - name: cache
    emptyDir: {}
```

:::warning
`emptyDir: { medium: Memory }` is a tmpfs, and it counts against the pod's
**memory** limit rather than its disk. Using it for a large cache is how a pod
gets OOM-killed for writing files — which you measured directly in the virtual
memory labs.
:::

## 3. The image that will not get smaller

Someone adds a cleanup step and the image stays the same size:

```dockerfile
RUN apt-get update && apt-get install -y build-essential   # +400 MB
RUN ./build.sh
RUN apt-get purge -y build-essential && rm -rf /var/lib/apt/lists/*   # -0 MB
```

Layers only add. Removing a file in a later layer records a whiteout that hides
it; the earlier layer still carries every byte, and the image is the sum of all
of them.

The fix is never to add it to a layer you keep — one `RUN` that installs, builds
and cleans up, or a multi-stage build that copies out only the artifact:

```dockerfile
FROM golang:1.24 AS build
RUN go build -o /app ./cmd/app

FROM gcr.io/distroless/base
COPY --from=build /app /app        # one layer, one binary
```

## 4. The write amplification nobody expected

A container edits a large file that came from the image, and the disk fills far
faster than the data explains.

Copy-up: the first write to a file from a lower layer copies the whole file into
the writable layer. A one-byte change to a 2 GB file costs 2 GB, per container.

The rule is the one from the internals lesson: **anything written frequently or
worth keeping belongs on a volume**, not on the overlay. That covers database
data directories, upload spools, caches and anything a job rewrites in place.

## 5. Out of inodes with the disk half empty

A session store or a mail queue writes millions of tiny files. `df -h` shows 40%
used. Every write fails with `ENOSPC`.

```bash
df -i /var                       # IUse% 100
find /var -xdev -printf '%h\n' | sort | uniq -c | sort -n | tail   # where they are
```

On ext4 the inode count is fixed when the filesystem is created, so there is no
online fix — delete files, or reformat with `mke2fs -i` and a smaller
bytes-per-inode ratio. XFS allocates inodes dynamically and largely sidesteps
this.

The real prevention is not storing millions of small files on a general-purpose
filesystem: that is what object storage, a database, or a directory-sharding
scheme are for.

## What to monitor

Disk is the failure that gives the most warning and gets the least attention.

| Signal | Why |
|---|---|
| Free **space** per filesystem | The obvious one |
| Free **inodes** per filesystem | The one nobody has, and the one that surprises |
| Growth **rate**, not just level | 80% is fine; 80% climbing 5% a day is an outage on Thursday |
| Container writable-layer size | Catches copy-up and runaway logs before the node notices |
| Image and build-cache size on nodes | The usual cause of node disk pressure in CI |

:::callback
This closes the Foundations arc. **C14** introduces images, layers and volumes as
Docker features — every one of them is the overlay filesystem in this lesson.
**E31** meets the same thing as node disk pressure and image garbage collection,
and **B13** meets fsync as database durability.
:::

:::checkpoint
Explain to someone who has not read this topic:

1. Why deleting a log file can free no space at all
2. Why ten containers from one image cost roughly one image of disk
3. Why `RUN rm big-file` does not shrink an image
4. Why a container with a read-only root can still write to `/tmp`
5. Why a filesystem can be full at 40% usage
:::

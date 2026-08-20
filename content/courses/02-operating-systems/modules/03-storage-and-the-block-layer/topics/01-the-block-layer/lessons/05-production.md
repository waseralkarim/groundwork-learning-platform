---
topic: topic.the-block-layer
section: production
title: Storage decisions you will actually be asked to make
order: 5
mode: explain
---

## "We bought NVMe and it is still slow"

The commonest storage conversation, and it usually ends in one of four places.

**It is not the device.** `await` is high because `aqu-sz` is high — the requests
are waiting for each other, not for the hardware. Deeper queues raise throughput
and raise latency, and somebody chose throughput.

**It is `fsync`, not bandwidth.** A database committing 5000 transactions a
second issues 5000 flushes a second. The relevant number is how fast the device
can promise that a small write is safe, which has almost nothing to do with its
sequential throughput.

**It is not the local device at all.** Cloud block storage is a network service
with a token bucket. `gp3` has a provisioned IOPS figure; exceed it and requests
queue while the device reports itself as healthy. `%util` will say 100% and be
telling you about the queue, not the medium.

**It is the filesystem layer.** Overlayfs copy-up, a small `read_ahead_kb`
against sequential access, a large one against random access, or 512-byte writes
to a 4 KB device.

Each has a different reading behind it, and none of them is visible in a
throughput graph.

## Sizing and configuring, in the order that pays

```bash
# 1. what is the device, really?
cat /sys/block/sda/queue/rotational        # 0 = SSD-like
cat /sys/block/sda/queue/scheduler         # the bracketed one is active

# 2. is the workload random or sequential? (request size answers it)
# rkB/s ÷ r/s = average read size
# small and random -> IOPS matter, readahead hurts
# large and sequential -> bandwidth matters, readahead helps

# 3. who is waiting?
cat /sys/fs/cgroup/io.pressure
```

The scheduler choice follows from step 1 and 2, not from a blog post:

- **NVMe** — `none`. The device reorders better than the kernel can.
- **SATA SSD or cloud volume** — `mq-deadline`. Cheap, and it stops a write
  stream starving reads.
- **Rotational** — `mq-deadline`, or `bfq` if one tenant must not starve
  another.

For a database doing random point lookups, lowering `read_ahead_kb` from 128 to
16 or less can be a large win: every 4 KB lookup was pulling 128 KB off the
device and discarding almost all of it.

:::warning{scope=production}
On a large node, `dirty_ratio: 20` is a lot of data. A 128 GB machine can hold
roughly 25 GB of dirty pages before throttling — minutes of writeback on a cloud
volume, all of it lost on a crash, and a violent stall for whoever trips the
threshold. Prefer `vm.dirty_bytes` and `vm.dirty_background_bytes`, which are
absolute, and size them to a few seconds of the device's real write rate.
:::

## Containers, specifically

Three things behave differently and all three surprise people:

**Writes to the container's own filesystem are amplified and not durable.**
Overlayfs copies a whole file on first write, and the writable layer is deleted
with the container. Anything with state needs a volume — and that is a
performance argument as much as a durability one.

**`/tmp` is often a tmpfs, which is memory.** Writing to it is fast, counts
against the memory limit, and is not reclaimable. A process writing 2 GB of
"temporary files" into a container with a 1 GB memory limit is not doing disk
I/O; it is being OOM-killed.

**Per-container I/O accounting is usually off.** `io.stat` is empty unless the
io controller was enabled for that part of the tree. On a node running mixed
workloads it is worth enabling, because otherwise there is no way to attribute
device load to a container at all.

:::predict{question="A pod writes 2 GB of temporary files and is OOM-killed. Its memory limit is 1 GB and the node has 60 GB free. Why?"}
Because the "files" never went near a disk.

`/tmp` in most container images is a tmpfs — a filesystem that lives entirely in
page cache with no device behind it. Writing 2 GB to it allocates 2 GB of memory,
charged to the pod's cgroup, and it appears in `memory.stat` as `shmem` rather
than as anything a `df` would explain.

The two properties that make it fatal: tmpfs pages are charged to the cgroup
that touched them, and they are **not reclaimable** — there is nowhere to write
them back to, so the kernel cannot free them under pressure the way it would
drop clean file cache. The cgroup hits `memory.max`, reclaim finds nothing to
take, and the OOM killer fires.

The node's 60 GB free is irrelevant, exactly as it was in the cgroups topic: the
limit being enforced is the pod's.

The tells are `wchar` large with `write_bytes` at zero, `shmem` large in
`memory.stat`, and `df` on `/tmp` reporting a `tmpfs` source. The fix is an
`emptyDir` with a real medium, or a volume, or making the application stream
rather than spool.
:::

## What to alert on

```promql
# saturation, honestly — stall time, not utilisation
rate(container_pressure_io_stalled_seconds_total[5m]) > 0.1

# latency, from the device counters
rate(node_disk_read_time_seconds_total[5m])
  / rate(node_disk_reads_completed_total[5m]) > 0.05

# the queue, which distinguishes slow device from deep queue
rate(node_disk_io_time_weighted_seconds_total[5m])

# space, because it is still the most common storage incident
node_filesystem_avail_bytes / node_filesystem_size_bytes < 0.1
```

What not to alert on: **`%util`**, which saturates at 100% on any device that
serves requests concurrently, and **throughput**, which is meaningless without a
request size beside it.

And do not forget inodes. `df -h` showing 40% free with `df -i` showing 100%
used is a filesystem that is completely full for practical purposes, and the
error the application reports is `ENOSPC` — the same one it would report if the
bytes had run out.

## The five things worth remembering

1. `write()` returns before anything reaches a device; `fsync` is the only way
   to know it did.
2. `dirty_ratio` is a cliff, not a slope — full memory speed, then full device
   speed, with nothing in between.
3. `await` mixes queue time with service time; compare it against queue depth
   before blaming the hardware.
4. `%util` at 100% means "something was in flight", which on NVMe means almost
   nothing.
5. In a container, a write may be much larger than you issued, or may not be a
   write at all.

:::checkpoint
1. Why is a database's performance dominated by fsync latency rather than
   throughput?
2. When would you lower `read_ahead_kb`, and what does it cost?
3. Why is `vm.dirty_bytes` a better control than `vm.dirty_ratio` on a large
   node?
4. Name two ways a container write is not what it appears to be.
:::

---
topic: topic.the-block-layer
section: core-concepts
title: Dirty pages, and who waits for them
order: 2
mode: explain
---

:::objective{id=OBJ-A02.4.1}
Trace the path a write takes from the system call to the device, naming each
queue it waits in.
:::

## What `write()` actually does

Three things, none of them involving a device:

1. Copy the bytes from your buffer into page-cache pages.
2. Mark those pages **dirty** — modified in memory, not yet on the device.
3. Return the count.

At that point the data exists in exactly one place: volatile memory. The
filesystem has not been consulted about where the blocks go, no request has been
built, and no device knows anything has happened.

```bash
grep -E '^(Dirty|Writeback):' /proc/meminfo
# Dirty:              8412 kB    <- written, not yet on a device
# Writeback:          1024 kB    <- in flight to a device right now
```

Those two lines are the front of the queue. `Dirty` is work waiting to start;
`Writeback` is work in progress.

:::objective{id=OBJ-A02.4.4}
Explain what writeback is, and how the dirty thresholds decide when a write
reaches a device and when a writer is blocked.
:::

## Four things trigger writeback

:::diagram{src=../diagrams/dirty-thresholds.mmd caption="Below one threshold nothing happens; above the other, your writer blocks"}

```bash
cat /proc/sys/vm/dirty_background_ratio   # 10
cat /proc/sys/vm/dirty_ratio              # 20
cat /proc/sys/vm/dirty_expire_centisecs   # 3000  — 30 seconds
cat /proc/sys/vm/dirty_writeback_centisecs # 500  — how often to check
```

- **`dirty_background_ratio`** — above this percentage of available memory,
  kernel threads start writing back. **Nothing blocks.** The application sees no
  change at all.
- **`dirty_ratio`** — above this, the writing process is throttled: `write()`
  blocks until enough pages have been cleaned. This is the cliff.
- **`dirty_expire_centisecs`** — a page older than this is written back
  regardless of how few dirty pages there are. Thirty seconds is how long your
  data can be nowhere but RAM by default.
- **`fsync()`** — the application asking, explicitly, for its data to be on the
  device before the call returns.

The shape of the failure is worth stating plainly. Below the second threshold,
`write()` runs at memory speed. Above it, `write()` runs at device speed. If your
device is a network-attached volume doing 100 MB/s and your application was
writing at 2 GB/s into cache, crossing that line is a twentyfold slowdown
arriving in one step.

:::warning{scope=production}
The `_ratio` sysctls are percentages of *available* memory, which on a large
machine is a great deal of data. On a 128 GB node, `dirty_ratio: 20` permits
around 25 GB of dirty pages — several minutes of writeback on a cloud volume,
during which a crash loses all of it and any writer that trips the threshold
stalls hard. `dirty_bytes` and `dirty_background_bytes` set absolute limits
instead, and are the better control on big machines.
:::

## fsync is the whole story for databases

A buffered write is fast because it lies about durability. `fsync()` is the
application declining the lie:

```c
write(fd, buf, n);   // fast. Data is in RAM.
fsync(fd);           // slow. Data is on the device, and the device says so.
```

Every database calls it on commit, because a transaction that is not durable is
not a transaction. That is why database performance is dominated by *fsync
latency* rather than throughput — the relevant question is not how many
megabytes per second the device can move but how quickly it can promise that a
small write is safe.

It is also why write caching on the device matters so much. `write_cache` in
sysfs says whether the device acknowledges writes before they are on the media:

```bash
cat /sys/block/sda/queue/write_cache    # "write back" or "write through"
```

`write back` means the device answers quickly and `fsync` must additionally
issue a flush. A device that ignores flushes looks wonderful in benchmarks and
loses data on power failure, which is the entire history of cheap consumer SSDs
in database workloads.

:::objective{id=OBJ-A02.4.2}
Distinguish logical I/O from physical I/O, and measure both for a running
process.
:::

## Logical and physical, per process

```bash
cat /proc/$PID/io
# rchar:       56826358     bytes read through the VFS
# wchar:       67108958     bytes written through the VFS
# syscr:             548    read syscalls
# syscw:             526    write syscalls
# read_bytes:          0    bytes actually fetched from a block device
# write_bytes:         0    bytes actually sent to a block device
```

`rchar`/`wchar` count what your process asked for. `read_bytes`/`write_bytes`
count what a device did about it. The gap between them is the page cache, and
the ratio tells you things nothing else will:

| Pattern | Meaning |
|---|---|
| `rchar` ≫ `read_bytes` | Reads are being served from cache. Working set fits |
| `rchar` ≈ `read_bytes` | Every read reaches the device. Cache is too small, or the access is random |
| `wchar` ≫ `write_bytes` | Buffered writes, not yet flushed — or a tmpfs, where they never will be |
| `write_bytes` ≫ `wchar` | **Write amplification.** You wrote less than the device did |

That last row is the interesting one, and containers produce it routinely.

:::objective{id=OBJ-A02.4.7}
Explain why a database on an overlay filesystem behaves differently from one on
a volume.
:::

## Copy-up, and why databases need volumes

Overlayfs is copy-on-write at **file** granularity, not block granularity. The
first write to any file that lives in a lower layer copies the *entire file* to
the upper layer first.

```text
container writes 1 byte at offset 500 MB of a 2 GB file
  -> overlayfs copies all 2 GB from lower to upper
  -> then applies the 1-byte change
```

For a database this is close to a worst case. Its data files are large, they
live in the image or in the container's writable layer, and it modifies small
parts of them constantly. The first write to each file pays for the whole file,
and every subsequent write goes through an extra filesystem layer.

Three consequences worth knowing before someone proposes it:

- The first write to any file is enormously more expensive than it looks.
- `fsync` on overlayfs must satisfy both layers, and is slower than on the
  underlying filesystem directly.
- The writable layer is deleted with the container, so none of it was durable
  anyway.

A volume — a bind mount or a `PersistentVolume` — mounts the underlying
filesystem straight into the container, bypassing the overlay entirely. That is
what "databases need volumes" means mechanically, and it is a performance
statement as much as a durability one.

## The one-sentence version

`write()` dirties a page and returns; writeback moves it later, in the
background until `dirty_ratio` and then by blocking you; `fsync` is the only way
to know it arrived; and in a container the write may be much larger than the one
you issued.

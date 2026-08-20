---
topic: topic.the-block-layer
section: overview
title: write() returns before anything happens
order: 1
mode: explain
---

Your program calls `write()`, gets a byte count back, and moves on. At that
moment nothing has reached a disk. Nothing is scheduled to. If the machine loses
power in the next thirty seconds, the data is gone and your program was told it
succeeded.

That gap — between the call returning and the bytes existing somewhere durable —
is where storage performance lives, and where most storage incidents happen.

## The specific things this explains

- Why a service writes happily for an hour and then every `write()` blocks for
  four seconds
- Why `iostat` shows 100% utilisation on an NVMe drive that is nearly idle
- Why a database is dramatically slower in a container than on the same hardware
  outside one
- Why changing a single byte in a 2 GB file can write 2 GB
- Why "the disk is fast, we bought NVMe" is not an answer to a latency problem
- What `fsync` actually costs, and why every database does it anyway

:::callback
From **Virtual Memory**: the page cache holds file-backed pages, and clean ones
are reclaimable while anonymous ones are not. A page you have just written to is
**dirty** — file-backed and *not* reclaimable until it has been written out.
This topic is about what happens to those pages, and who waits while it happens.
:::

## The path, and the queues in it

:::diagram{src=../diagrams/the-write-path.mmd caption="Where write() returns, and everything that happens afterwards"}

`write()` copies your bytes into the page cache, marks the page dirty, and
returns. Everything after that is somebody else's problem — kernel writeback
threads, the filesystem, the block layer, a scheduler queue, the device's own
queue.

Each of those is a place work can pile up, and each has its own counter.
Diagnosing storage is largely a matter of knowing which queue is full.

## Two numbers that should not match

Here is a reading from a container in this course, after writing 64 MB to `/tmp`
and reading a dozen large files from the image:

:::terminal{title="/proc/PID/io after 56 MB of reads and 64 MB of writes"}
rchar:        56826358      <- bytes asked for
read_bytes:          0      <- bytes fetched from a device
wchar:        67108958      <- bytes written
write_bytes:         0      <- bytes sent to a device
:::

Fifty-six megabytes read and none of it from a disk: it was all in the page
cache. Sixty-four megabytes written and none of it to a disk: `/tmp` is a tmpfs,
which has no device behind it at all.

Neither number is wrong. They measure different things, and almost every
argument about whether "the disk is slow" is really an argument about which of
the two somebody is looking at.

:::predict{question="A container writes 500 MB/s steadily for ten minutes with no problem, then every write blocks for seconds at a time. What changed?"}
Almost certainly nothing outside the machine. It crossed `dirty_ratio`.

While dirty pages are below `dirty_background_ratio` — 10% of available memory
by default — nothing writes them back and `write()` is a memcpy. Above it,
kernel threads start writing back in the background and still nobody blocks. The
application sees full memory speed and the graph looks wonderful.

Above `dirty_ratio` — 20% by default — the kernel stops trusting the writer and
throttles it: `write()` now blocks until pages have been cleaned. Suddenly the
application is running at the device's speed rather than memory's, and if the
device is a slow cloud volume that is an order of magnitude, arriving all at
once.

This is a cliff, not a slope, which is why it reads as "it was fine and then it
broke". The tell is `Dirty` in /proc/meminfo climbing toward the threshold
before the latency starts, and the fix is usually to make the writer flush
deliberately — writing 500 MB/s into a cache the device drains at 100 MB/s only
postpones the arithmetic.
:::

## What you already have

From **Files and Filesystems** you read your own overlay mount and the image
layers under it. From **Virtual Memory** you established what the page cache
holds and what can be reclaimed. From **cgroups** you have `io.pressure` and the
habit of reading a counter rather than a graph.

This topic joins them: the page cache is the front of the write path, the
overlay is why containers write more than they think, and the counters are how
you tell a slow device from a full queue.

## An honest note about the labs

Two of the four labs measure this sandbox directly — its queue configuration,
its dirty thresholds, and the gap between logical and physical I/O, which is
unusually stark here because the writable filesystem is a tmpfs.

The other two work from captured `/proc/diskstats` samples taken off real
machines. A container with a read-only image and a RAM-backed scratch directory
cannot generate controlled block I/O — that is the isolation doing its job, and
pretending otherwise would teach you arithmetic on invented numbers. The samples
are real, and the arithmetic on them is what `iostat` does.

## How to work through it

Concepts, mechanism, tools, production. Four labs: read your storage's actual
configuration; measure logical against physical I/O and watch them disagree by
100%; compute from `/proc/diskstats` what `iostat` computes, so the derived
numbers stop being magic; and finally diagnose three storage problems where
throughput looks fine.

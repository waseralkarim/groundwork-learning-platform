---
topic: topic.the-block-layer
section: internals
title: Queues, schedulers, and the arithmetic behind iostat
order: 3
mode: explain
---

:::objective{id=OBJ-A02.4.3}
Identify a device's queue configuration — scheduler, depth, readahead — from
sysfs.
:::

## Every device's configuration is a directory

```bash
ls /sys/block/sda/queue/
cat /sys/block/sda/queue/scheduler          # [none] mq-deadline kyber
cat /sys/block/sda/queue/nr_requests        # 1267
cat /sys/block/sda/queue/rotational         # 0 for SSD, 1 for spinning
cat /sys/block/sda/queue/read_ahead_kb      # 128
cat /sys/block/sda/queue/max_sectors_kb     # 1280
cat /sys/block/sda/queue/logical_block_size # 512
cat /sys/block/sda/queue/physical_block_size # 4096
cat /sys/block/sda/queue/write_cache        # write back
```

The bracketed entry in `scheduler` is the active one. Everything here is a
number you can read before you argue about it, which puts most storage
discussions on a different footing.

Two of them are worth dwelling on.

**`nr_requests`** is how deep the scheduler queue is. A deeper queue means more
requests available to merge and reorder, so more throughput — and more time each
individual request spends waiting, so worse latency. It is the throughput-latency
trade expressed as a single integer, and the right value depends entirely on
which of the two you are being paid for.

**`read_ahead_kb`** is how far ahead the kernel speculatively reads. For
sequential access it is why a 4 KB read costs nothing extra — the next 128 KB
arrived with it. For random access it is pure waste: every 4 KB read pulls 128 KB
off the device and discards almost all of it. Databases doing random point
lookups routinely want this much smaller than the default.

## Physical and logical block size are not the same

`logical_block_size 512` with `physical_block_size 4096` is nearly universal and
matters more than it looks. The device accepts 512-byte addressing for
compatibility, and internally works in 4 KB units. A 512-byte write to a 4 KB
device becomes read-modify-write: fetch 4 KB, change part of it, write 4 KB back.

This is why filesystem and partition alignment matters, and why a misaligned
partition can cost a large fraction of write performance while every tool
reports the hardware as healthy.

:::objective{id=OBJ-A02.4.6}
Distinguish the I/O schedulers, and say which fits a given device and workload.
:::

## Four schedulers, and how to choose

:::diagram{src=../diagrams/scheduler-choice.mmd caption="Choosing by device first, then by what must not be starved"}

| Scheduler | What it does | Where it belongs |
|---|---|---|
| **none** | No reordering. Straight to the device | NVMe and anything with deep hardware queues, which reorder better than the kernel can |
| **mq-deadline** | Gives reads a deadline so writes cannot starve them | SATA SSDs, cloud volumes, rotational disks. The safe default |
| **kyber** | Targets a latency figure, throttling to hold it | Fast devices where you care about tail latency specifically |
| **bfq** | Proportional share between processes, with heuristics | Desktops, and multi-tenant cases where fairness beats throughput. Costs CPU |

The reasoning behind `none` on NVMe is worth having, because it looks like
giving up. An NVMe device has tens of thousands of queue entries and reorders
internally with knowledge the kernel does not have — how the flash is laid out,
what is being garbage-collected, which channels are free. Kernel-side reordering
adds CPU cost and gets in the way.

The reasoning behind `mq-deadline` on everything else is the one that saves
incidents: without a deadline, a stream of writes can starve reads indefinitely,
because merging writes is more efficient and the scheduler will keep doing the
efficient thing. A read deadline caps how long that can go on. It is cheap and
it bounds the failure.

```bash
# change it at runtime, per device
echo mq-deadline > /sys/block/sda/queue/scheduler
```

:::objective{id=OBJ-A02.4.5}
Calculate service time, average queue depth and utilisation from two samples of
/proc/diskstats.
:::

## /proc/diskstats, and what iostat does with it

```text
   8  48 sdd 319452 67609 16308266 126276 1439254 1687662 90900160 6771584 0 982400 7357732 ...
```

The fields, in order:

| # | Field | Note |
|---|---|---|
| 1–3 | major, minor, name | |
| 4 | reads completed | |
| 5 | reads merged | adjacent requests combined before dispatch |
| 6 | **sectors read** | always 512-byte sectors, whatever the device's block size |
| 7 | **ms spent reading** | summed across requests, so it can exceed wall clock |
| 8–11 | writes: completed, merged, sectors, ms | |
| 12 | **I/Os in progress** | instantaneous, not cumulative |
| 13 | **ms spent doing I/O** | wall-clock time with at least one request in flight |
| 14 | **weighted ms doing I/O** | ms × queue depth, integrated over time |
| 15–18 | discards | |
| 19–20 | flushes: completed, ms | `fsync` shows up here |

Everything `iostat -x` prints comes from two samples of that line:

```text
r/s      = Δfield4  / Δseconds
rkB/s    = Δfield6  × 512 / 1024 / Δseconds
r_await  = Δfield7  / Δfield4                 milliseconds per read
w_await  = Δfield11 / Δfield8                 milliseconds per write
aqu-sz   = Δfield14 / Δms                     average queue depth
%util    = Δfield13 / Δms × 100
```

Two of those are routinely misread.

**`await` is not device service time.** It is queue time plus service time — how
long a request took from being handed to the block layer to completing. A
device answering in 200 microseconds behind a queue of fifty requests has an
`await` of 10ms and is not slow. Comparing `await` against `aqu-sz` separates
"the device is slow" from "the queue is deep".

**`%util` is nearly meaningless on modern devices.** It measures the fraction of
time at least one request was in flight. For a spinning disk, which serves one
request at a time, that genuinely approximates saturation. An NVMe drive serves
thousands concurrently, so it can sit at 100% `%util` while using a few percent
of its capability. Reading it as "the disk is maxed out" is one of the most
common storage misdiagnoses there is.

The honest saturation signals are `aqu-sz` climbing, `await` climbing, and
`io.pressure` from the previous topic.

:::callback
From **cgroups**: `io.pressure` reports how much time tasks spent stalled
waiting for I/O, per cgroup. It is the same relationship as `cpu.pressure` had
to CPU utilisation — pressure is about the work, `%util` is about the device,
and only one of them answers "is this hurting us".
:::

## The one-sentence version

Requests queue twice — once in the scheduler and once in the device — every
knob is a file under `/sys/block/*/queue/`, and every number `iostat` shows is
arithmetic on two samples of `/proc/diskstats`, including two that most people
read backwards.

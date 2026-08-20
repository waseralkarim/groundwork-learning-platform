---
topic: topic.the-block-layer
section: commands
title: Measuring storage without trusting throughput
order: 4
mode: do
---

:::objective{id=OBJ-A02.4.8}
Diagnose a storage-related latency problem from counters rather than from
throughput.
:::

## What is this device, and how is it configured?

```bash
lsblk                                        # the tree, with sizes and mounts
findmnt -no SOURCE,FSTYPE,OPTIONS /var/lib   # what is actually mounted there

d=sda
for f in scheduler nr_requests rotational read_ahead_kb write_cache \
         logical_block_size physical_block_size; do
  printf '%-22s %s\n' "$f" "$(cat /sys/block/$d/queue/$f)"
done
```

:::try{lab=what-your-storage-is run="lsblk" title="The devices this machine has"}
Note the `RO` column and the mount points. The lab has you find which device is
behind your own root filesystem, which is less obvious than it looks when the
root is an overlay.
:::

## Is anything dirty, and is anyone blocked?

```bash
grep -E '^(Dirty|Writeback):' /proc/meminfo
cat /proc/sys/vm/dirty_ratio /proc/sys/vm/dirty_background_ratio
cat /sys/fs/cgroup/io.pressure
```

Watching `Dirty` climb toward the threshold before latency degrades is the
clearest early warning there is for a write-throttling stall — and it is
available with no exporter, no agent and no agreement with anyone.

## Per-process: what did this program actually ask for?

```bash
cat /proc/$PID/io
# rchar / wchar        what it asked the VFS for
# read_bytes / write_bytes   what a device did about it
```

Take two samples and subtract, as always. The ratio is the diagnosis:

- `wchar` large, `write_bytes` zero — buffered and not yet flushed, or a tmpfs
- `write_bytes` larger than `wchar` — write amplification, and worth explaining
- `rchar` large, `read_bytes` near zero — cache is doing its job

:::try{lab=logical-and-physical run="grep -E '^(rchar|wchar|read_bytes|write_bytes)' /proc/self/io" title="Your own I/O so far"}
Almost nothing yet, because this shell has barely done any. The lab makes it do
64 MB of writes and 56 MB of reads and takes the reading again — and both
physical counters stay at zero, for two different reasons.
:::

## Per-device: the counters, and the arithmetic

```bash
# two samples, ten seconds apart
grep ' sda ' /proc/diskstats > /tmp/a; sleep 10; grep ' sda ' /proc/diskstats > /tmp/b

awk 'NR==FNR {for (i=1;i<=NF;i++) a[i]=$i; next}
     { rd = $4-a[4]; rms = $7-a[7]; wr = $8-a[8]; wms = $11-a[11];
       busy = $13-a[13]; wgt = $14-a[14]; secs = 10;
       printf "r/s      %.1f\n", rd/secs;
       printf "w/s      %.1f\n", wr/secs;
       printf "r_await  %.2f ms\n", (rd ? rms/rd : 0);
       printf "w_await  %.2f ms\n", (wr ? wms/wr : 0);
       printf "aqu-sz   %.2f\n", wgt/(secs*1000);
       printf "%%util    %.1f\n", busy/(secs*1000)*100 }' /tmp/a /tmp/b
```

That is `iostat -x` in nine lines, and writing it once is worth more than
reading the manual page, because afterwards none of the derived columns are
mysterious.

```bash
iostat -x 1              # if sysstat is installed
pidstat -d 1             # per-process disk I/O
biolatency               # bcc/bpftrace: a histogram of completion times
```

`biolatency` is the tool to reach for when `await` is bad and you need to know
whether it is bad for everything or bad for a tail — an average of 8ms can be
every request at 8ms, or 99% at 0.5ms and 1% at 700ms, and those are different
problems with different causes.

## Reading the derived numbers correctly

| Reading | What it means | What it does not mean |
|---|---|---|
| `%util` at 100% | Something was in flight the whole interval | That the device is saturated — not on NVMe |
| `await` high, `aqu-sz` high | Deep queue. Requests are waiting for each other | That the device is slow |
| `await` high, `aqu-sz` ≈ 1 | The device really is slow, or the requests are large |  |
| `r_await` ≫ `w_await` | Reads are being starved, often by write merging | Look at the scheduler — `none` on a slow device is a common cause |

:::warning
Throughput is the worst single number to judge storage by. A device moving
50 MB/s might be at its limit or a tenth of it, depending entirely on the request
size — 50 MB/s of 4 KB random writes is about 12800 IOPS and is a great deal of
work; 50 MB/s of 1 MB sequential writes is 50 IOPS and is nearly idle. Always
carry the IOPS figure alongside.
:::

## In a container

```bash
cat /sys/fs/cgroup/io.stat        # per-device bytes and IOPS for this cgroup
cat /sys/fs/cgroup/io.pressure    # stall time — the honest saturation signal
cat /sys/fs/cgroup/io.max         # any bandwidth or IOPS limits set on us
findmnt -no SOURCE,FSTYPE /       # overlay? then writes may be amplified
```

`io.stat` is empty when the io controller has not been enabled for the cgroup,
which is common and is not a failure — it means the parent never wrote `+io` to
`cgroup.subtree_control`. When it *is* populated it is the only per-container
I/O accounting there is, and it is worth enabling deliberately on nodes running
mixed workloads.

:::checkpoint
1. Which two `/proc/PID/io` fields differ by exactly the page cache?
2. Why is `%util` misleading on NVMe, and what would you use instead?
3. What distinguishes "the device is slow" from "the queue is deep"?
4. Why must a throughput figure be quoted with a request size to mean anything?
:::

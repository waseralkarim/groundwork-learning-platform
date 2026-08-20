---
topic: topic.virtual-memory
section: commands
title: Reading memory honestly
order: 4
mode: do
---

Six places to look, in the order you should look at them.

## /proc/PID/status — the summary

```bash
grep -E '^(Name|VmSize|VmRSS|RssAnon|RssFile|RssShmem|VmSwap)' /proc/self/status
```

```text
Name:   bash
VmSize:   8452 kB      ← VSZ: everything mapped
VmRSS:    4360 kB      ← RSS: physically present
RssAnon:   792 kB      ← of which heap and stack
RssFile:  3568 kB      ← of which file-backed (droppable)
VmSwap:      0 kB
```

`RssAnon` versus `RssFile` in one glance. A process whose RSS is mostly file-backed
is holding memory the kernel can take back; one whose RSS is mostly anonymous is
holding memory that has to be swapped or killed.

:::objective{id=OBJ-A01.4.2}
Interpret a process's memory map, identifying which regions are code, heap,
stack and shared libraries.
:::

## /proc/PID/maps — every region

```bash
head -12 /proc/self/maps
```

```text
55d3f1c00000-55d3f1c2a000 r--p 00000000 fd:00 1049601  /usr/bin/bash
55d3f1c2a000-55d3f1cd8000 r-xp 0002a000 fd:00 1049601  /usr/bin/bash
55d3f2f00000-55d3f2f21000 rw-p 00000000 00:00 0        [heap]
7f8e4c000000-7f8e4c028000 r--p 00000000 fd:00 1049233  /usr/lib/libc.so.6
7ffd3a1e0000-7ffd3a201000 rw-p 00000000 00:00 0        [stack]
```

Reading a line: address range, permissions, offset, device, inode, path.

The permissions column is the interesting part. `r-xp` is executable code —
readable, executable, **p**rivate. `rw-p` is writable data. A region with no path
and no `[label]` is anonymous memory: someone's `malloc`.

Three things worth spotting immediately:

- **Anything both writable and executable (`rwx`)** — rare, and a red flag in
  anything but a JIT
- **The same library mapped several times** with different permissions — that is
  one file, mapped in segments
- **A vast number of anonymous regions** — often a fragmented allocator

## /proc/PID/smaps_rollup — the honest total

```bash
grep -E '^(Rss|Pss|Shared_Clean|Private_Dirty)' /proc/self/smaps_rollup
```

```text
Rss:               4360 kB
Pss:               1204 kB      ← the number that sums correctly
Shared_Clean:      3160 kB      ← shared library pages
Private_Dirty:      792 kB      ← this process's own, unshareable
```

`Private_Dirty` is the closest thing to "memory that would be freed if this
process exited". For sizing a limit, it is the number to reason from.

:::try{lab=three-numbers run="grep -E '^(Rss|Pss|Private_Dirty)' /proc/self/smaps_rollup" title="Your shell's real footprint"}
Compare `Rss` with `Pss` here. Most of the difference is libc and the shell's own
code — pages that exist once in RAM no matter how many shells are running.
:::

## The cgroup files — what the limit sees

The most important reading in a container, and nothing else answers it:

```bash
cat /sys/fs/cgroup/memory.max        # the limit
cat /sys/fs/cgroup/memory.current    # what is charged
grep -E '^(anon|file|shmem|slab) ' /sys/fs/cgroup/memory.stat
cat /sys/fs/cgroup/memory.events     # low/high/max/oom counters
```

```text
536870912                            ← 512 MiB limit
501219328                            ← 478 MiB charged: 93%
anon 209715200                       ← 200 MiB, not reclaimable
file 283115520                       ← 270 MiB on the file line
shmem 8388608                        ← of which 8 MiB is tmpfs (also not reclaimable)
oom 0
oom_kill 0
```

Ninety-three per cent, and healthy: most of it is cache. The same percentage with
`anon` at 450 MiB would be one allocation from a kill.

:::warning{scope=production}
`free -m` inside a container reports the **host's** memory, not the limit.
`/proc/meminfo` is not namespaced. Any number you read from it inside a
container is about a machine your container does not have.

Read `memory.max`. Every time.
:::

:::try{lab=what-the-cgroup-counts run="cat /sys/fs/cgroup/memory.max; cat /sys/fs/cgroup/memory.current" title="This lab's own limit"}
The lab containers are capped tightly. Compare what `free -m` claims in the same
shell — that number belongs to the host, and it is the trap this warning is
about.
:::

## ps and top — with the right columns

```bash
ps -eo pid,comm,vsz,rss,pmem --sort=-rss | head
```

Remember what you are looking at: `vsz` is address space, `rss` double-counts
shared pages, and neither knows about cgroup limits. Useful for ranking
processes, misleading as a total.

In `top`, press `f` and add `RES` and `SHR`. `RES - SHR` is a rough private
footprint and a better ranking than `RES` alone.

## /proc/vmstat and pressure

Two counters tell you whether the machine is *working* for its memory:

```bash
grep -E '^(pgscan_kswapd|pgsteal_kswapd|oom_kill)' /proc/vmstat
```

Rising `pgscan`/`pgsteal` means the kernel is reclaiming — the system is under
memory pressure even if nothing has died yet. This is the early warning that
"memory usage %" does not give you.

:::checkpoint
Without scrolling up:

1. Which file tells you a container's real memory limit, and which one lies?
2. A process has RSS 800 MB and PSS 120 MB. What does that tell you?
3. Which part of `memory.current` can the kernel give back under pressure?
4. What is the first thing you check when a container exits with code 137?
:::

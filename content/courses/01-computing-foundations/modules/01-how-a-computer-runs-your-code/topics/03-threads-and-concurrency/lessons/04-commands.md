---
topic: topic.threads-and-concurrency
section: commands
title: Seeing threads and their limits
order: 4
mode: do
---

:::objective{id=OBJ-A01.6.2}
Interpret a process's thread list, and identify which threads are doing the work.
:::

## Every thread of a process

```bash
ls /proc/<pid>/task            # one directory per thread, named by TID
ps -L -p <pid> -o pid,tid,pcpu,stat,comm
top -H -p <pid>                # live, per thread
```

```text
    PID     TID %CPU STAT COMMAND
      7       7  0.0 S    spin      ← the main thread, waiting
      7       9 13.2 R    spin
      7      10 13.3 R    spin
      7      11 12.5 R    spin
      7      12 13.3 R    spin
```

Four workers at roughly 13% each. On a container limited to half a CPU that adds
to about 52% — the limit, shared out. It is not that each thread is slow; it is
that together they have half a core.

`STAT` is worth reading per thread: `R` is running or runnable, `S` is an
interruptible sleep — waiting for work — and `D` is uninterruptible, almost
always I/O.

:::try{lab=count-the-threads run="ls /proc/self/task | wc -l" title="How many threads is your shell?"}
One. A shell is single-threaded, which makes it a good baseline before you look
at a process that is not.
:::

## Proving threads share memory

```bash
diff <(cat /proc/<pid>/task/<tid1>/maps) <(cat /proc/<pid>/task/<tid2>/maps)
```

No output. Two threads, the same address space, byte for byte — because there is
only one, and each `task` directory is a view onto it.

Contrast with two processes running the same program, whose maps differ in
addresses and whose data is invisible to each other.

## The CPU limit and whether it is binding

The two files that matter, and nothing else answers the question:

```bash
cat /sys/fs/cgroup/cpu.max      # quota period, in microseconds
cat /sys/fs/cgroup/cpu.stat     # usage, periods, throttling
```

```text
50000 100000                    ← half a CPU

usage_usec 1611932
nr_periods 1205
nr_throttled 31                 ← periods where the quota ran out
throttled_usec 10528034         ← 10.5 seconds spent stopped
```

Convert `cpu.max` to a CPU count with `quota / period`. `max` in the first field
means unlimited.

:::try{lab=the-limit-is-real run="cat /sys/fs/cgroup/cpu.max; nproc" title="Your limit, and what nproc claims"}
Two numbers that disagree by a factor of thirty or more. The first is what this
container may use; the second is what the host has, and it is what most
runtimes will size themselves from unless told otherwise.
:::

## Context switches, and which kind

```bash
grep ctxt /proc/<pid>/status
grep -E 'nr_involuntary_switches|nr_throttled' /sys/fs/cgroup/cpu.stat
```

```text
voluntary_ctxt_switches:     4821    ← gave up the CPU, waiting for something
nonvoluntary_ctxt_switches:  91043   ← was taken off it
```

Nonvoluntary far exceeding voluntary means the threads wanted to run and could
not — contention, or the quota. Voluntary dominating means they are waiting on
I/O or locks, and more CPU will not help.

## What a thread is waiting for

```bash
ps -L -o pid,tid,stat,wchan:24,comm -p <pid>
cat /proc/<pid>/task/<tid>/stack     # kernel stack, needs privilege
```

`wchan` names the kernel function the thread is sleeping in. `futex_wait` is a
lock. A socket or filesystem function names the dependency directly. This is the
fastest way to distinguish "stuck on a lock" from "waiting for a database".

## Load average, read correctly

```bash
uptime
cat /proc/loadavg
```

Remember what Linux counts: runnable **and** uninterruptible tasks. High load
with an idle CPU is I/O, not CPU pressure — and inside a container the figure is
the host's anyway, like `nproc`.

:::warning{scope=production}
Three numbers that are about the machine and not your container: `nproc`,
`/proc/loadavg`, and `/proc/meminfo`. None is namespaced. Anything that sizes
itself from them inside a container is configuring for hardware it does not
have — and that single sentence covers the most common CPU *and* memory
misconfiguration in container deployments.
:::

## Sizing a worker pool honestly

```bash
read -r quota period < /sys/fs/cgroup/cpu.max
if [ "$quota" = "max" ]; then cpus=$(nproc); else cpus=$(( (quota + period - 1) / period )); fi
echo "usable CPUs: $cpus"
```

For CPU-bound work, that number is roughly your worker count. For I/O-bound work
you can exceed it — the threads are waiting, not computing — but the ceiling is
then memory and context-switching, not CPUs.

:::checkpoint
Without scrolling up:

1. Which file tells you whether a container is being throttled, and which field?
2. A container shows 45% CPU utilisation and slow requests. What do you check?
3. How would you prove two threads share an address space?
4. Load average is 90 and the CPU is 5% busy. What is happening?
:::

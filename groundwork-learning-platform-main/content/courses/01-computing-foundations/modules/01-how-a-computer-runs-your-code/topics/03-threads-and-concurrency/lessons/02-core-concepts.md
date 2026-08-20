---
topic: topic.threads-and-concurrency
section: core-concepts
title: Sharing, switching and quotas
order: 2
mode: explain
---

:::objective{id=OBJ-A01.6.1}
Distinguish a thread from a process by what each shares and what each keeps
private.
:::

## One call, two outcomes

On Linux, creating a process and creating a thread are the same system call with
different flags. `clone()` takes a set of "share this" options:

```text
fork()            → clone() sharing almost nothing: a new address space
pthread_create()  → clone() sharing CLONE_VM | CLONE_FILES | CLONE_FS | CLONE_THREAD
```

`CLONE_VM` is the important one: share the memory map rather than copy it. That
single flag is the entire difference between a sibling process and a sibling
thread.

So a thread is not a lightweight process in some vague sense. It is the same
kernel object — a task — that happens to share more.

| | Separate processes | Threads of one process |
|---|---|---|
| Address space | One each | **Shared** |
| Open files | One table each | **Shared** |
| Global variables | Private | **Shared** |
| Stack | Private | Private |
| Registers | Private | Private |
| A crash in one | Others survive | **The whole process dies** |
| Corrupting shared state | Impossible | Easy |

The last two rows are the trade. Threads are cheap to communicate between because
they share memory; they are dangerous for exactly the same reason, and a segfault
in any one of them takes the process down.

:::objective{id=OBJ-A01.6.3}
Distinguish concurrency from parallelism, and say which one a single CPU can
provide.
:::

## What a context switch costs

The scheduler gives a thread a slice of CPU and then moves on. Switching costs:

- Saving and restoring registers — cheap
- Between processes, switching page tables — more expensive, and it discards part
  of the TLB
- Refilling the CPU caches with the new thread's data — usually the largest cost
  and the least visible

The direct cost is a few microseconds; the cache effects can be far larger. That
is affordable thousands of times a second and ruinous millions of times a second,
which is why a thread per request stops scaling and why event loops exist.

Two kinds appear in `/proc/PID/status`, and the difference matters:

```text
voluntary_ctxt_switches:     4821    ← gave up the CPU: waiting on I/O or a lock
nonvoluntary_ctxt_switches:  91043   ← was taken off: quota spent, or preempted
```

A high **voluntary** count means the threads are waiting for something. A high
**nonvoluntary** count means they wanted the CPU and could not have it — which in
a container usually means the limit.

:::objective{id=OBJ-A01.6.4}
Explain what a CPU limit actually restricts, and what happens to threads when the
quota for a period is spent.
:::

## A CPU limit is a quota, not a speed

This is the piece that produces the most confusion in production, and it is
simple once stated plainly.

```bash
cat /sys/fs/cgroup/cpu.max
# 50000 100000
```

Two numbers: **quota** and **period**, in microseconds. 50,000µs of CPU time in
every 100,000µs of wall clock — half a CPU.

:::diagram{src=../diagrams/cpu-quota.mmd caption="Spend the quota early and every thread stops until the next period"}

The critical detail: when the quota is gone, threads are not slowed down. They
are **stopped** until the period rolls over. A container that burns its 50ms in
the first 20ms of a period does nothing at all for the remaining 80ms.

And the quota is shared by every thread in the cgroup. Four threads spend it four
times as fast as one, so more workers means throttling starts earlier in each
period and every worker sits out longer.

```text
1 thread,  needs 100ms of CPU  → about 200ms wall, no throttling
4 threads, need 100ms each     → 400ms of demand against 50ms per period
                               → about 800ms wall, most of it stopped
```

Adding workers did not add capacity. It added contention for a fixed budget.

## The counters that prove it

```bash
cat /sys/fs/cgroup/cpu.stat
```

```text
usage_usec 1611932       ← CPU actually consumed
nr_periods 1205          ← periods elapsed
nr_throttled 31          ← periods in which the quota ran out
throttled_usec 10528034  ← total time stopped by the limit
```

`throttled_usec` is the number to plot. It is unambiguous: any non-zero value
means the limit is binding, and a growing one means requests are waiting on the
quota rather than on the work.

:::warning
CPU utilisation cannot show you this, which is why throttling goes undiagnosed
for months. A throttled container is *idle* while it is stopped, so its
utilisation looks moderate — sometimes better than an unthrottled one. Kubernetes
horizontal autoscaling on CPU utilisation is measuring the wrong thing for
exactly this reason.
:::

## nproc lies inside a container

`nproc` and `/proc/cpuinfo` report the **machine's** CPUs. Neither is namespaced,
so a container limited to half a CPU on a 64-core host is told there are 64.

Anything sizing itself from that number is configuring for hardware it does not
have:

- Go sets `GOMAXPROCS` from the CPU count
- Java sizes its common ForkJoin pool and its GC threads the same way
- Nginx, gunicorn, Puma and most worker pools default to one per core

The result is dozens or hundreds of threads competing for a fraction of one CPU:
throttling, context switching, and worse latency than a single worker would have
produced.

:::callback
This is the same bug you met in **Virtual Memory**, where a JVM read the host's
RAM and chose a heap that guaranteed its own death. Same cause: a value that
describes the machine, read by a process that lives in a container.
:::

The fix is to derive the worker count from the limit:

```bash
read -r quota period < /sys/fs/cgroup/cpu.max
if [ "$quota" = "max" ]; then
  cpus=$(nproc)                       # genuinely unlimited
else
  cpus=$(( (quota + period - 1) / period ))   # round up, never zero
fi
```

Go has honoured cgroup limits since 1.25; before that `automaxprocs` was the
standard fix. The JVM does it with container support enabled. Everything else
needs telling.

## The one-sentence version

Threads share an address space and are scheduled individually; a CPU limit is a
quota per period that stops every thread when it runs out; and the machine's CPU
count is not your CPU count.

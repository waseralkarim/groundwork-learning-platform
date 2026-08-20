---
topic: topic.the-scheduler
section: internals
title: CFS, EEVDF, and the policies you did not know you had
order: 3
mode: explain
---

:::objective{id=OBJ-A02.3.5}
Explain how EEVDF chooses the next task, and how that differs from CFS picking
the smallest virtual runtime.
:::

## What CFS did, and what it could not express

From 2007 to kernel 6.5, Linux used the Completely Fair Scheduler. The rule was
one line: **run the runnable task with the smallest vruntime.** Tasks lived in a
red-black tree keyed on vruntime, so "smallest" was the leftmost node and the
decision was O(1) to read.

It worked extremely well and had one structural gap. CFS was fair about *how
much* CPU each task got, and had no way to express *how often* a task needed to
be scheduled. Those are different requirements, and the second one is what
latency-sensitive work actually cares about.

An audio thread needing 1ms of CPU every 10ms, and a compile job wanting all the
CPU it can get, might receive identical shares over a second and one of them is
broken. The only lever was `nice`, which changes the amount and not the
frequency — so people niced interactive work down, gave it a larger share it did
not need, and hoped.

CFS's slice length also fell out of a target latency divided by the number of
runnable tasks. Two tunables, `sched_latency_ns` and `sched_min_granularity_ns`,
therefore had non-obvious interactions, and a great deal of internet advice
consisted of changing them and observing something.

## What EEVDF does instead

:::diagram{src=../diagrams/cfs-vs-eevdf.mmd caption="From 'furthest behind' to 'eligible, and due soonest'"}

Since kernel 6.6, the default is **EEVDF** — Earliest Eligible Virtual Deadline
First. It adds two ideas to the same vruntime machinery.

**Eligibility.** A task is eligible if it has not run *ahead* of its fair share.
A task that just used a big slice becomes ineligible for a while, and cannot be
picked again until the others have caught up. This bounds how far ahead anyone
can get, which CFS did only approximately.

**Virtual deadline.** Each task asks for a slice — `se.slice`, 3ms by default —
and its virtual deadline is the time it becomes eligible plus that request. The
scheduler picks the eligible task with the earliest deadline.

The consequence is the point of the whole change: **a task that asks for a
shorter slice gets a nearer deadline, so it is picked sooner and more often —
without receiving any more total CPU.** Frequency and amount became separate
knobs, which under CFS they were not.

```bash
grep -E 'se.slice|se.vruntime|policy' /proc/self/sched
# se.vruntime  : 0.508924
# se.slice     : 3000000     <- 3ms, in nanoseconds
```

For an operator, three practical consequences:

- Latency under load is better on 6.6+ with no configuration at all, which is
  worth knowing when comparing benchmarks across kernel versions.
- `sched_latency_ns` and `sched_min_granularity_ns` are **gone**. Tuning advice
  that references them predates EEVDF and no longer applies.
- Shares still come from weights, exactly as before. Nothing about `nice`,
  `cpu.weight` or the 1.25×-per-step table changed.

:::objective{id=OBJ-A02.3.6}
Distinguish the scheduling policies, and say which require privilege and what
they risk.
:::

## Five policies, and only three you can use

| Policy | Number | Behaviour | Needs privilege |
|---|---|---|---|
| `SCHED_OTHER` / NORMAL | 0 | Weight-based. Everything you deploy | no |
| `SCHED_BATCH` | 3 | Like NORMAL, but no wake-up preference | no |
| `SCHED_IDLE` | 5 | Runs only when nothing else wants the CPU | no |
| `SCHED_FIFO` | 1 | Real-time. Preempts all normal tasks, runs until it blocks | **CAP_SYS_NICE** |
| `SCHED_RR` | 2 | Real-time, with a time slice between equal priorities | **CAP_SYS_NICE** |

```bash
chrt -p $$              # what am I?
chrt -b 0 ./batch-job   # run as SCHED_BATCH
chrt -i 0 ./cleanup     # run as SCHED_IDLE
chrt -f 10 ./thing      # SCHED_FIFO — EPERM without CAP_SYS_NICE
```

**`SCHED_BATCH`** removes the small bonus the scheduler gives tasks that have
just woken up. That bonus is what makes interactive work feel responsive, and it
is exactly wrong for a compute job, which gets it repeatedly and briefly
preempts the latency-sensitive neighbour every time. Marking batch work as batch
costs nothing and it does not need privilege.

**`SCHED_IDLE`** is weaker than nice 19 — it runs only when a CPU would
otherwise be idle. For genuinely discardable work (a cache warmer, a
prefetcher), it is the honest setting, and the one people reach for `nice 19`
instead of.

**The real-time policies are a different world.** A runnable `SCHED_FIFO` task
preempts every normal task immediately and runs until it blocks or yields. A
real-time thread with a bug that spins is not slow — it makes the machine
unresponsive, because no normal task, including your shell, will run again.

Linux ships a safety valve for exactly that:

```bash
cat /proc/sys/kernel/sched_rt_runtime_us   # 950000
cat /proc/sys/kernel/sched_rt_period_us    # 1000000
```

Real-time tasks may consume at most 950ms of every second, leaving 50ms in which
normal tasks — such as the shell you would use to kill it — can run. Setting
`sched_rt_runtime_us` to −1 removes the valve, which is occasionally correct on
a dedicated appliance and is otherwise how a machine is lost.

:::warning{scope=production}
`--cap-add=SYS_NICE` on a container grants real-time scheduling and negative
nice values. It is requested surprisingly often, usually to "improve latency",
and it lets that container preempt every other workload on the node — including
the kubelet. Treat it as a node-level grant rather than a container-level one,
because that is what it is.
:::

## Why negative nice needs privilege and positive does not

```bash
nice -n 5 ./thing     # fine
nice -n -5 ./thing    # nice: cannot set niceness: Permission denied
```

Lowering your own priority gives resources away and harms nobody. Raising it
takes CPU from your neighbours, so it needs `CAP_SYS_NICE` — or an `RLIMIT_NICE`
allowance granted per user in `limits.conf`.

The asymmetry is worth noticing as a design pattern. It is the same shape as the
namespace rules from earlier in this course: the operation that only affects you
is unprivileged, and the one that affects others is not.

## The one-sentence version

CFS ran the task furthest behind; EEVDF runs the eligible task whose deadline is
nearest, which separates *how often* from *how much*; the policies that only
lower your standing are free, and the ones that raise it above everyone else's
need a capability for the obvious reason.

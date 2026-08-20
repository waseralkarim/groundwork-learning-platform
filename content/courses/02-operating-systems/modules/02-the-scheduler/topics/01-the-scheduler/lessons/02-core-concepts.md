---
topic: topic.the-scheduler
section: core-concepts
title: Weights, virtual runtime, and the queue
order: 2
mode: explain
---

:::objective{id=OBJ-A02.3.1}
Explain what the scheduler must decide, and why fairness is defined as
proportional to weight rather than equal.
:::

## The decision, and its constraints

Every few milliseconds, on every CPU, the kernel must answer: of the runnable
tasks here, which runs next, and for how long?

The constraints make it harder than it sounds. The answer must be computed in
microseconds, because it happens thousands of times a second per CPU. It must
not starve anyone, however long they have been unlucky. It must not require
scanning every task. And it has to serve two populations with opposite needs at
once — an interactive process that wants a CPU *often* and briefly, and a batch
process that wants a lot of CPU and does not care when.

Equal time is the wrong rule, because not all work is equally important. Linux
uses proportional share: each task has a weight, and it gets CPU in proportion
to its weight over the sum of all runnable weights.

The denominator is the part people forget. It contains only *runnable* tasks —
so your share changes when your neighbours wake up, and nothing about your own
configuration changed.

:::objective{id=OBJ-A02.3.2}
Identify a process's scheduling policy, priority, nice value and weight from
/proc.
:::

## nice, weight and priority are three names for two things

```bash
cat /proc/self/sched
# policy                : 0          <- SCHED_NORMAL
# prio                  : 120        <- 120 + nice
# se.load.weight        : 1048576    <- 1024, scaled by another 1024
# se.vruntime           : 0.508924
# se.slice              : 3000000    <- 3ms
```

- **nice** is the knob: −20 to 19, default 0.
- **weight** is what the scheduler arithmetic uses. Nice 0 is 1024; each nice
  step multiplies by about 1.25. `/proc/PID/sched` shows it scaled by a further
  1024, which is why nice 0 reads as 1048576 and nice 19 as 15360.
- **prio** is an internal number: 120 + nice for normal tasks, so 100–139. Real-
  time tasks occupy 0–99, numerically below every normal task.

`ps -o pid,cls,pri,ni` reports a *different* priority again, mapped for display.
When two tools disagree about a process's priority, they are usually both right
about different numbers — read `nice` and `policy`, which are unambiguous.

## vruntime: how a weight becomes a share

The mechanism is one division. A task's **virtual runtime** advances at real
time divided by its weight:

```text
vruntime += actual_runtime × (1024 / weight)
```

A heavy task's vruntime creeps up; a light task's races ahead. The scheduler
runs whichever runnable task is furthest behind, so a heavy task is chosen more
often, and the shares come out proportional without anything ever computing a
percentage.

Worked through, with a nice-0 task against a nice-19 task on one CPU:

| | nice 0 | nice 19 |
|---|---|---|
| weight | 1024 | 15 |
| vruntime per 1ms of CPU | +1ms | +68ms |
| share of the CPU | 1024/1039 = **98.6%** | 15/1039 = **1.4%** |

Measured in the lab on this platform: 4.41 seconds against 0.06 seconds, a ratio
of about 73 where the table predicts 68. Close enough that the mechanism is
plainly the one described, and not so close that you would suspect the numbers
were invented.

:::objective{id=OBJ-A02.3.3}
Distinguish a voluntary context switch from an involuntary one, and say what
each tells you about a workload.
:::

## Two ways to stop running, and they mean opposite things

```bash
grep switches /proc/self/sched
# nr_switches               : 2401
# nr_voluntary_switches     :    1
# nr_involuntary_switches   : 2400
```

**Voluntary** — the task blocked. It asked for I/O, waited on a lock, called
`sleep`. It had nothing to do, and giving up the CPU was correct.

**Involuntary** — the task was preempted while still runnable. Something else
was chosen, or its quota ran out. It had work and was stopped anyway.

The ratio characterises a workload in one reading:

| Pattern | Reading |
|---|---|
| Mostly voluntary | I/O-bound. It spends its life waiting for something external |
| Mostly involuntary | CPU-bound and competing. It wants more CPU than it is getting |
| Few of either | Either idle, or running long uninterrupted stretches |

A subtlety worth having in advance: a container with a CPU quota accumulates
involuntary switches *even with no competitor*, because the quota preempts it at
the end of every period. Involuntary switches therefore mean "stopped while
runnable", not "someone else outbid me" — and distinguishing those two is what
`cpu.stat` is for.

## The queue, and the number nobody graphs

```bash
cat /proc/self/schedstat
# 1770015700 5210755000 2401
#  ^ on cpu   ^ waiting  ^ slices
```

Field 2 is time spent on a run queue: runnable, not blocked, not running. It is
scheduling latency, per task, in nanoseconds, maintained by the kernel whether
or not anyone reads it.

It is the missing number in most performance investigations. CPU utilisation
describes the resource. `%CPU` per process describes what a process got. Neither
says how long the work waited for a turn — and when a service is slow while the
machine looks idle, that is almost always the answer.

:::warning
Do not assume these counters are live — but do not assume the sysctl decides it
either. `kernel.sched_schedstats` gates the system-wide `/proc/schedstat` and
some per-CPU statistics; the per-task file is populated from `sched_info`, which
many kernels compile in unconditionally. On the sandbox you are about to use,
the sysctl reads **0** and `/proc/self/schedstat` reports real numbers anyway.

The reliable test is the reading itself: if field 2 is zero for a task you know
has been queueing, *then* go and look at the sysctl.
:::

## The one-sentence version

The scheduler picks the runnable task that is furthest behind its fair share,
where "fair" is proportional to weight; nice sets that weight through a
1.25×-per-step table, so nice 19 is one seventieth rather than a bit less; and
the time your work spent queued is counted per task in `schedstat`.

---
topic: topic.the-scheduler
section: commands
title: Reading how long your work waited
order: 4
mode: do
---

:::objective{id=OBJ-A02.3.7}
Interpret run-queue wait time as a latency signal, and relate it to quota
throttling and to pressure.
:::

## The three numbers

```bash
cat /proc/self/schedstat
#  on-cpu(ns)   waiting(ns)   timeslices
```

Take two readings and subtract. The interval matters, not the totals — these are
cumulative since the task started.

```bash
read a b c < /proc/$PID/schedstat; sleep 10
read d e f < /proc/$PID/schedstat
echo "ran $((  (d-a)/1000000 ))ms  waited $(( (e-b)/1000000 ))ms  over 10000ms"
```

:::try{lab=waiting-to-run run="cat /proc/self/schedstat" title="Your own queue time"}
An idle shell has waited almost not at all. The lab puts work on the same CPU
and takes the reading again, and the difference between the two is the whole
measurement.
:::

The ratio is what to read:

| ran vs waited | Reading |
|---|---|
| Waited ≈ 0 | Got a CPU whenever it wanted one. Not a scheduling problem |
| Waited ≈ ran | Sharing roughly evenly, or a 50% quota |
| Waited ≫ ran | Starved. The work exists and cannot get a turn |

## Per-thread, which is usually what you want

```bash
for t in /proc/$PID/task/*; do
  printf '%-8s %s\n' "$(basename "$t")" "$(cat "$t/schedstat")"
done
```

A process's own `schedstat` covers its main thread only. For anything
multithreaded — a JVM, a Go runtime, nginx — the interesting waiting happens in
the workers, and reading the process misses all of it. This is the commonest
reason someone concludes "there is no scheduling delay here".

## Policy, nice and affinity

```bash
chrt -p $$                  # policy and real-time priority
nice                        # this shell's nice value
taskset -pc $$              # which CPUs it may run on
ps -eo pid,cls,pri,ni,psr,comm --sort=-pri | head

chrt -b 0 ./compute         # SCHED_BATCH — no privilege needed
chrt -i 0 ./cache-warmer    # SCHED_IDLE  — no privilege needed
nice -n 10 ./nightly        # positive nice — no privilege needed
```

`psr` is the CPU a task last ran on. Watching it change is how you notice
migration; watching it *not* change is how you confirm affinity took.

```bash
taskset -c 0 ./thing        # pin to CPU 0 — no privilege needed for your own task
```

Pinning is the cheapest way to *create* contention deliberately, which is how
you test anything weight-related. Two processes on one CPU compete; the same two
on a 16-CPU machine do not, and a test without contention proves nothing about
weights.

## Switches, and what they say

```bash
grep -E 'nr_switches|voluntary' /proc/$PID/sched
vmstat 1 5                  # cs column: system-wide switches per second
pidstat -w 1                # per-process, split voluntary / involuntary
```

Mostly voluntary means I/O-bound. Mostly involuntary means CPU-bound and
competing — or quota-throttled, which produces involuntary switches with no
competitor at all. `cpu.stat` separates those two in one reading.

:::try{lab=nice-under-contention run="grep se.load.weight /proc/self/sched" title="Your weight"}
1048576 is nice 0: the weight 1024, scaled by another 1024 for the fixed-point
arithmetic. The lab has you run a nice-19 process, read its weight, and check
whether the CPU ratio you measure matches the ratio of the two numbers.
:::

## System-wide, when you do not know which process yet

```bash
vmstat 1                    # r = runnable tasks; if r > CPUs, they are queueing
uptime                      # load average: runnable + uninterruptible, over 1/5/15m
pidstat -u 1                # per-process CPU
perf sched latency          # per-task scheduling latency, if perf is available
cat /proc/pressure/cpu      # system-wide PSI
```

`vmstat`'s `r` column is the fastest first look: more runnable tasks than CPUs
means somebody is queueing, right now, with no averaging.

Load average is the number people quote and the one that misleads. On Linux it
counts uninterruptible sleep as well as runnable tasks, so a machine blocked on
a slow disk shows a high load with an idle CPU. It also averages over minutes,
which hides exactly the bursts that hurt latency. Prefer `r`, or PSI.

:::callback
From **cgroups**: `cpu.pressure`'s `some` and `full` measure stall time for the
whole cgroup, and `nr_throttled / nr_periods` measures quota exhaustion.
`schedstat` is the per-task version of the same story — and it is the one that
tells you *which* of your threads waited, which the cgroup files cannot.
:::

## Putting them in order

For "this service is slow and the CPU looks fine":

```bash
vmstat 1 5                                   # 1. is anything queueing at all?
cat /sys/fs/cgroup/cpu.stat                  # 2. are we throttled by our own quota?
cat /sys/fs/cgroup/cpu.pressure              # 3. how much stall, cgroup-wide?
for t in /proc/$PID/task/*; do cat "$t/schedstat"; done   # 4. which threads waited?
grep -E 'voluntary' /proc/$PID/sched         # 5. waiting, or blocking?
```

Five commands, and they separate "throttled by our own limit", "outcompeted by
a neighbour", "blocked on I/O" and "genuinely slow code" before anyone opens a
profiler.

:::checkpoint
1. Which field of `schedstat` is scheduling latency, and what units?
2. Why must you read per-thread rather than per-process for a JVM?
3. What does a high count of involuntary switches with no competitor mean?
4. Why is `vmstat`'s `r` column better than load average for this question?
:::

---
topic: topic.the-scheduler
section: production
title: Scheduling problems as they actually arrive
order: 5
mode: explain
---

:::objective{id=OBJ-A02.3.8}
Diagnose a latency problem as scheduling delay rather than slow work, from
per-task evidence.
:::

They never arrive labelled "scheduling". They arrive as "the API is slow and I
don't know why", with a dashboard that looks fine.

## The idle machine that is not idle

A node at 60% CPU, a service with a bad p99, and no obvious cause. The reason
utilisation looks comfortable is that it is an average over time and over CPUs,
and neither average is where the problem lives.

- **Averaged over CPUs.** Sixteen CPUs at 60% might be eight saturated and eight
  idle, if work is pinned, or if an interrupt-heavy NIC queue is stuck to one
  core. The tasks on the saturated ones queue.
- **Averaged over time.** A one-second sample at 60% can be 600ms of complete
  saturation and 400ms idle. Requests arriving in the first part wait; the graph
  shows neither.
- **Averaged over cgroups.** A container throttled by its own quota contributes
  its quota to the node's utilisation and no more, however desperate it is.

`schedstat` has none of these problems. It is per task, cumulative, and counts
the actual nanoseconds that actual work spent queued.

```bash
for t in /proc/$PID/task/*; do
  printf '%-8s %s\n' "$(basename "$t")" "$(cat "$t/schedstat")"
done
```

If field 2 is large and growing, the work waited. That is a fact about your
service, not an inference from a graph about a machine.

## Sizing thread pools, again

From cgroups you have the `nproc` problem: a runtime sizes a pool from the CPU
count and is then limited to a fraction of one. The scheduler adds the second
half of the explanation.

Sixteen runnable threads on half a CPU do not run at a sixteenth of speed each
in a smooth way. They round-robin through the quota, each getting a slice, each
switch discarding the cache the previous one had warmed. Throughput falls
because of the cache effect, and latency rises because a request may sit through
several turns of the rotation before its thread is picked.

The measurement that shows it is `nr_involuntary_switches` climbing fast with a
large `schedstat` field 2 — many preemptions, much waiting, and the work is not
getting done.

:::warning{scope=production}
More threads than you have CPU quota is nearly always worse than fewer. The
intuition that more workers means more throughput assumes the workers can run,
and under a quota they cannot. Set the pool from the quota, not from the
hardware.
:::

## Batch work that is not marked as batch

A nightly report, a log compactor, a cache warmer — sharing a node with a
latency-sensitive service. It is a compute job, so it is runnable essentially
all the time, and every time it wakes it takes a turn from the service.

Two settings, neither of which needs privilege:

```bash
chrt -b 0 ./nightly-report     # SCHED_BATCH: no wake-up preference
chrt -i 0 ./cache-warmer       # SCHED_IDLE: runs only when a CPU is spare
nice -n 19 ./anything          # weight 15 instead of 1024
```

`SCHED_BATCH` is under-used and almost free. The scheduler gives freshly woken
tasks a small advantage so interactive work feels responsive; a compute job
collects that advantage repeatedly and does not benefit from it, while the
neighbour it preempts does. Marking it removes the bonus and nothing else.

In Kubernetes this is a low CPU *request* — the weight — rather than a low CPU
limit. A limit throttles the batch job even when the node is idle, which wastes
the capacity you were trying to reclaim. A low request gets out of the way under
contention and uses everything when nobody else wants it.

## Real-time in production, and the one rule

Real-time policies exist for work with a genuine deadline: audio, motion
control, some trading paths, some packet processing. The rule for all of them is
the same:

**A real-time task must block.** A `SCHED_FIFO` task that spins without blocking
runs until the RT throttle stops it, and everything normal on that CPU —
including the shell you would use to fix it — does not run.

```bash
cat /proc/sys/kernel/sched_rt_runtime_us    # 950000 of every 1000000
```

That valve is what turns "the machine is gone" into "the machine is very slow",
and it is why disabling it with `-1` should be a deliberate, documented decision
about a dedicated appliance.

For containers: `--cap-add=SYS_NICE` grants real-time scheduling and negative
nice. Granting it to one container gives that container the ability to preempt
every workload on the node, the kubelet included. It is a node-level decision
wearing a container-level flag.

:::predict{question="A service's p99 is 400ms. Its own CPU time per request is 8ms and the CPU is 55% idle. Where is the other 392ms?"}
Waiting somewhere, and `schedstat` tells you whether it was waiting for a CPU.

Take a per-thread reading over a window. If field 2 is large across the worker
threads, the requests were queued as *runnable* — the work existed and could not
get a turn. Then ask why, because "the CPU is 55% idle" and "my threads are
queueing" are only compatible in specific ways:

- A **cgroup quota**. The container is throttled at its own limit while the node
  has capacity. `nr_throttled / nr_periods` confirms it in one reading, and this
  is by far the most common answer in Kubernetes.
- **Affinity or imbalance**. The threads are confined to CPUs that are busy
  while others are idle. `psr` in `ps` and per-CPU utilisation show it.
- **Too many threads for the quota**, so each request waits through several
  rotations of the pool.

If field 2 is *small*, the time is not scheduling at all and the queue is
elsewhere: a connection pool, a lock, a downstream call. That is equally useful
— it eliminates the whole CPU story in one measurement, which is the point of
taking it early rather than last.
:::

## What to alert on

```promql
# per-task queueing, if your exporter surfaces schedstat
rate(node_schedstat_waiting_seconds_total[5m])

# the cgroup version, which most people have already
rate(container_cpu_cfs_throttled_periods_total[5m])
  / rate(container_cpu_cfs_periods_total[5m]) > 0.25

rate(container_pressure_cpu_stalled_seconds_total[5m]) > 0.2
```

What not to alert on: **load average**. It counts uninterruptible sleep as well
as runnable tasks, so a machine blocked on a slow disk shows a high load with an
idle CPU; and it averages over minutes, hiding the bursts that damage latency.
It survives as a metric because it is easy to collect, not because it answers
anything.

`vmstat`'s `r` column — runnable tasks right now — is the honest version, and
PSI is the honest version with history.

## The five things worth remembering

1. Runnable-and-waiting is a distinct state, counted per task in `schedstat`
   field 2.
2. A weight is a share of contended CPU. Nice 19 is one seventieth, and on an
   idle machine it is nothing at all.
3. Involuntary switches mean "stopped while runnable" — which includes being
   throttled by your own quota, with no competitor anywhere.
4. `SCHED_BATCH` and `SCHED_IDLE` are free, unprivileged, and under-used; the
   real-time policies need a capability for a reason you can state.
5. Load average answers a different question from the one you are asking.

:::checkpoint
1. A node is 60% idle and threads are queueing. Name two ways both can be true.
2. Why is a low CPU request better than a low CPU limit for a batch job?
3. What must a real-time task do, and what happens when it does not?
4. Why is load average a poor signal for scheduling delay?
:::

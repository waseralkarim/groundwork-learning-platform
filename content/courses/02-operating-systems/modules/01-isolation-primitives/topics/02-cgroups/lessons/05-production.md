---
topic: topic.cgroups
section: production
title: Sizing, alerting, and the arguments you will have about limits
order: 5
mode: explain
---

:::objective{id=OBJ-A02.2.8}
Diagnose a workload's resource problem from its cgroup files alone, and say
which knob would fix it.
:::

## The `nproc` problem, which is everywhere

A runtime that sizes itself from the CPU count gets 16 on a node and is then
limited to half a CPU. It is the single most common resource defect in
containerised software, and each language has its own version:

| Runtime | Symptom | Fix |
|---|---|---|
| **JVM** (pre-10) | Heap sized from host RAM, then OOM-killed | `-XX:+UseContainerSupport` — on by default since 10 |
| **Go** | `GOMAXPROCS` = host cores; heavy throttling and scheduler churn | Set `GOMAXPROCS` from the limit, or use `automaxprocs` |
| **Node.js** | `UV_THREADPOOL_SIZE` and cluster workers sized from `os.cpus()` | Set both explicitly |
| **nginx** | `worker_processes auto` → 16 workers on 0.5 CPU | Set the number |
| **CI tooling** | `make -j$(nproc)` in a limited build container | `-j` from the quota |

They share a shape: the software asks the kernel a question whose honest answer
is not the number it needs. Adding workers past the quota does not add
throughput — it adds context switches and lengthens the queue during the part of
each period when everything is stopped.

The diagnosis is always the same two files:

```bash
nproc
cat /sys/fs/cgroup/cpu.max
```

If they disagree and the workload sized itself from the first, you have found
it.

## Sizing a limit from a measurement

The routine is short, and it is a measurement rather than a guess:

```bash
# under representative load, for long enough to include a peak
cat /sys/fs/cgroup/memory.peak      # high-water mark, not a sample
cat /sys/fs/cgroup/cpu.stat         # nr_throttled / nr_periods
cat /sys/fs/cgroup/cpu.pressure     # is the delay real?
```

**Memory limit** — `memory.peak` plus headroom you can justify. If the workload
has a periodic spike, the peak has it and `memory.current` does not.

**CPU limit** — raise it until `nr_throttled / nr_periods` is near zero at your
target throughput. That is a number you can defend, unlike a round one.

**CPU request** — this is the weight, and it should reflect the workload's share
of a busy node rather than its peak. Requests that equal limits everywhere waste
capacity by design.

:::warning{scope=production}
The argument about whether to set CPU limits at all is worth having with these
numbers rather than opinions. Limits give predictability and prevent one
workload from consuming a node; they also throttle a service that could have
used idle capacity, and the throttling is invisible in a utilisation graph. If
you remove them, `cpu.weight` from requests still protects everyone under
contention — which is the strongest form of the argument for removing them, and
it depends on requests actually being set.
:::

## What to alert on

Four signals, in the order they earn their place:

```promql
# 1. Something in this cgroup was OOM-killed. Not a rate — any increase.
increase(container_oom_events_total[5m]) > 0

# 2. Throttled in most periods. The utilisation graph will look fine.
rate(container_cpu_cfs_throttled_periods_total[5m])
  / rate(container_cpu_cfs_periods_total[5m]) > 0.25

# 3. Close to the memory limit, sustained.
container_memory_working_set_bytes / container_spec_memory_limit_bytes > 0.9

# 4. Pressure — work is being delayed, whatever utilisation says.
rate(container_pressure_cpu_stalled_seconds_total[5m]) > 0.2
```

The first is the only one that is unambiguous, and it is the one most often
missing. `memory.events`' `oom_kill` counter survives the process that was
killed — a log line does not, if nothing was tailing.

What *not* to alert on: CPU utilisation against a limit. A throttled container
sits at exactly its limit and looks healthy, which is why signal 2 exists.

:::callback
From **Threads and Concurrency**: you measured a service that got slower when it
was given more workers, and found the limit responsible. That is this failure
mode from the application's side. From the cgroup's side it is one ratio in
`cpu.stat`, and it is visible without touching the application at all.
:::

## Reading a node you have just been handed

```bash
systemd-cgtop                                  # who is consuming what, live
cat /sys/fs/cgroup/kubepods.slice/memory.max   # what the kubelet reserved
grep -c . /sys/fs/cgroup/kubepods.slice/*/cgroup.procs 2>/dev/null

# the tree with limits, three levels down
find /sys/fs/cgroup/kubepods.slice -maxdepth 3 -name memory.max \
  -exec sh -c 'printf "%-80s %s\n" "$1" "$(cat "$1")"' _ {} \;
```

`kubepods.slice`'s own `memory.max` is the node's allocatable memory after
system and kubelet reservations. Everything scheduled competes inside it, which
is why a node can OOM-kill pods that are all individually within their limits:
the parent ran out first.

:::predict{question="A pod's containers are all well under their memory limits, and one is OOM-killed. What do you check?"}
The pod cgroup one level up, and then the slice above that.

A pod's cgroup has a limit of its own — the sum of its containers' limits — and
the containers share it. If one container has no limit set, it can consume the
headroom the others were relying on, and the kernel then picks a victim from
inside the pod by `oom_score`. That victim is often the largest process, which
is often not the one that misbehaved.

Above the pod, `kubepods.slice` caps everything the kubelet scheduled. When
*that* fills, pods within their own limits are killed because the parent could
not be brought under its limit by any other means.

Both cases share one property: nothing in the killed container's own cgroup
files predicts the kill. `memory.max` looks fine, `memory.current` looks fine,
and the only evidence is `oom_kill` incrementing in `memory.events` — plus the
limits on a path the container cannot see. Diagnosing it needs node access, and
knowing that in advance saves a long time spent staring at the wrong files.
:::

## The three arguments you will have

**"Just remove the CPU limits."** Sometimes right. It removes throttling and
lets services use idle capacity, and `cpu.weight` from requests still keeps
things fair under contention. It also means one workload can consume a node's
spare CPU entirely, which is fine until the workload has a bug. Decide per
workload, with `nr_throttled` in hand.

**"Set requests equal to limits everywhere."** That is Guaranteed QoS, it gets
the best eviction treatment, and it wastes the difference between typical and
peak usage on every pod. Right for latency-critical services, expensive as a
blanket policy.

**"We'll tune it when it becomes a problem."** The counter is that the signal is
already there and free: `oom_kill`, `nr_throttled` and `memory.peak` are
counters the kernel maintains whether or not anyone reads them. "When it becomes
a problem" is usually the moment the graphs are least readable.

## The five things worth remembering

1. `nproc` and `cpu.max` answer different questions, and most runtimes ask the
   wrong one.
2. Throttling is invisible in utilisation graphs. `nr_throttled / nr_periods` is
   the signal.
3. Pressure says how much your work is being delayed; utilisation cannot.
4. The limit that kills you may be on a path you cannot see from inside the
   container.
5. `oom_kill` in `memory.events` is the one unambiguous alert, and it is the one
   most often not configured.

:::checkpoint
1. A container is at 50% CPU utilisation and its p99 is terrible. Which file do
   you read first?
2. Why is `memory.peak` the right input for sizing a memory limit?
3. What does a pod's QoS class change about where it sits in the tree?
4. Name the alert that is unambiguous, and say why a log line is not a
   substitute.
:::

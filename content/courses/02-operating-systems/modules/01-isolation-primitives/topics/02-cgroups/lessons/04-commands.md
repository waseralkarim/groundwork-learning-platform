---
topic: topic.cgroups
section: commands
title: Reading pressure instead of guessing at utilisation
order: 4
mode: do
---

:::objective{id=OBJ-A02.2.5}
Interpret pressure stall information, and distinguish what `some` reports from
what `full` reports.
:::

## Where am I, and what am I allowed?

```bash
cat /proc/self/cgroup                      # 0::/  — your path, re-rooted
cat /sys/fs/cgroup/cgroup.controllers      # what you may use
cat /sys/fs/cgroup/cpu.max                 # quota period
cat /sys/fs/cgroup/memory.max              # bytes, or "max"
cat /sys/fs/cgroup/pids.max
```

:::try{lab=find-your-cgroup run="cat /sys/fs/cgroup/cpu.max; nproc" title="Two answers, one question"}
The first line is what this cgroup may use. The second is what the kernel has.
If a runtime sizes a thread pool from the second and is then limited by the
first, the extra threads do not add throughput — they add contention and
scheduling latency.
:::

## Am I being throttled?

```bash
cat /sys/fs/cgroup/cpu.stat
# usage_usec 3101127
# nr_periods 62
# nr_throttled 61
# throttled_usec 21023894
```

Read the ratio, not the absolute figures. `nr_throttled / nr_periods` is the
fraction of periods that ended early — 61 of 62 here, which means this cgroup is
stopped almost every period. `throttled_usec` is how long tasks spent stopped.

A container at 50% CPU utilisation and 98% throttled periods is not
half-loaded. It is saturated for the part of each period it is allowed to run,
and asleep for the rest.

## Pressure, which says it in one number

```bash
cat /sys/fs/cgroup/cpu.pressure
# some avg10=36.85 avg60=7.75 avg300=1.66 total=5077376
# full avg10=36.85 avg60=7.75 avg300=1.66 total=5076919

cat /sys/fs/cgroup/memory.pressure
cat /sys/fs/cgroup/io.pressure
```

:::diagram{src=../diagrams/psi-some-full.mmd caption="One second, four tasks: 'some' counts any stall, 'full' counts only total ones"}

The numbers are percentages of wall-clock time over the last 10, 60 and 300
seconds. `total` is microseconds since boot, which is the one to graph — it only
increases, so a rate over it is honest in a way the averages are not.

**`some`** is time when at least one task was stalled waiting for the resource.
Work is being delayed.

**`full`** is time when *every* task was stalled. Nothing is getting done at
all.

Utilisation tells you how busy a resource is. Pressure tells you how much your
work is being delayed by not having it — which is the thing you actually care
about, and the thing utilisation can never tell you. A resource at 100%
utilisation with zero pressure is perfectly sized. One at 60% with high pressure
is a problem.

:::try{lab=pressure-under-a-limit run="cat /sys/fs/cgroup/cpu.pressure" title="Pressure at rest"}
Near zero, because nothing is competing. Note the `total` value; the lab has you
put load on and read the same file again, and the difference between the two
`total` figures is the honest measurement.
:::

:::warning
In a CPU-throttled container, `some` and `full` are usually equal. That is not a
bug — when the quota is spent, *every* task in the cgroup is stopped
simultaneously, so any stall is a total stall. Seeing `some ≈ full` on
`cpu.pressure` is a fairly reliable signature of quota throttling rather than
ordinary CPU contention.
:::

## Memory, and what the limit is counting

```bash
cat /sys/fs/cgroup/memory.current      # what you are using now
cat /sys/fs/cgroup/memory.peak         # the high-water mark
cat /sys/fs/cgroup/memory.max
grep -E '^(anon|file|shmem|slab) ' /sys/fs/cgroup/memory.stat
cat /sys/fs/cgroup/memory.events       # oom_kill is the one to alert on
```

`memory.peak` is the file to reach for when sizing a limit. `memory.current` is
a sample and tells you nothing about the spike that happened while you were not
looking; `peak` remembers it.

## From the host, where you can see the tree

```bash
# which cgroup is a container actually in
cat /proc/$(docker inspect -f '{{.State.Pid}}' <container>)/cgroup

# walk the path and read the limit at every level
p=/sys/fs/cgroup/kubepods.slice/kubepods-burstable.slice/kubepods-...-pod9f3c.slice
while [ "$p" != /sys/fs/cgroup ]; do
  printf '%-70s %s\n' "$p" "$(cat "$p/memory.max" 2>/dev/null)"
  p=$(dirname "$p")
done
```

That loop is the answer to "why was this killed when its own limit was fine".
It cannot be run from inside the container, which is the whole reason the
question is hard.

```bash
systemd-cgls                 # the tree, as systemd sees it
systemd-cgtop                # live usage per cgroup — top, but for the tree
```

`systemd-cgtop` is the fastest way to find which cgroup on a node is consuming
something, and it needs no exporter, no dashboard and no agreement with anyone.

## The Kubernetes translation

| Manifest | Cgroup file | Kind |
|---|---|---|
| `resources.requests.cpu: 500m` | `cpu.weight` ≈ 20 | Weight |
| `resources.limits.cpu: 1` | `cpu.max` = `100000 100000` | Limit |
| `resources.requests.memory: 256Mi` | scheduling only (or `memory.min` with MemoryQoS) | Protection |
| `resources.limits.memory: 512Mi` | `memory.max` = 536870912 | Limit |

And the QoS class falls out of the combination rather than being set:

- **Guaranteed** — every container has requests equal to limits for both
  resources. Lands in its own slice, evicted last.
- **Burstable** — some requests are set, but not equal to limits. Lands under
  `kubepods-burstable.slice`.
- **BestEffort** — nothing set at all. Under `kubepods-besteffort.slice`, first
  to be evicted, `cpu.weight` at the floor.

You can read a pod's QoS class straight off the node without asking the API
server, because it is a directory name in the path.

:::checkpoint
1. Which file tells you whether a cgroup is being throttled, and which ratio in
   it matters?
2. What does `full` pressure mean that `some` does not?
3. Why is `memory.peak` more useful than `memory.current` for sizing a limit?
4. How would you find a pod's QoS class from the node, with no cluster access?
:::

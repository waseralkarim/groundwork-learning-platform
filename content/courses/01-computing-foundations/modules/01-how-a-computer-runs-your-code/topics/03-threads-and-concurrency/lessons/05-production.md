---
topic: topic.threads-and-concurrency
section: production
title: Four ways concurrency bites
order: 5
mode: explain
---

:::objective{id=OBJ-A01.6.6}
Diagnose a service that became slower after being given more workers, and
identify the limit responsible.
:::

## 1. More workers, worse latency

The story this topic opened with. Workers go from 4 to 16, p99 latency doubles,
and CPU utilisation on the dashboard goes *down*.

Every part of that is the quota. Sixteen threads spend a fixed budget four times
faster, so throttling begins earlier in each period and every request spends more
wall time stopped. Utilisation falls because a throttled container is idle while
it is stopped.

```bash
grep -E 'nr_throttled|throttled_usec' /sys/fs/cgroup/cpu.stat
```

Non-zero and climbing settles it in one command.

**The fix is to size workers from the limit**, not from `nproc` — and if the work
genuinely needs more CPU, to raise the limit rather than the worker count. Those
are different changes with different costs, and conflating them is what produced
the incident.

## 2. The runtime that started 200 threads

A Java or Go service is deployed with a 500m CPU limit. Inside, the runtime sees
64 CPUs and sizes itself accordingly: GC threads, a ForkJoin pool, `GOMAXPROCS`,
a connection pool, an HTTP server's worker count — each independently deciding
that 64 is the right number.

The result is hundreds of threads sharing half a core. Throttling is constant,
context switching is enormous, and the service is slower than it would be with a
single worker.

```bash
docker exec <c> sh -c 'nproc; cat /sys/fs/cgroup/cpu.max'
docker exec <c> ls /proc/1/task | wc -l
```

Two numbers that disagree, and a thread count that explains the latency.

Modern Go honours cgroup limits; older Go needs `automaxprocs`. The JVM needs
container support enabled, which is the default on current versions. Everything
else — application worker counts, pool sizes, anything computed from "CPUs" —
has to be set explicitly.

:::warning{scope=production}
This is the CPU twin of the JVM heap bug from **Virtual Memory**, and it has the
same shape: a value that describes the host, read by a process that lives in a
container, used to size something that then does not fit. If you fixed the memory
version and not this one, you fixed half of it.
:::

## 3. Autoscaling that never fires

A Kubernetes HPA is configured on CPU utilisation at 80%. The service is
throttled constantly, latency is terrible, and the HPA never scales up because
utilisation sits at 55%.

It is not broken. It is measuring usage against the request, and a throttled pod
genuinely does not use more than its quota — being stopped is not usage.

The signals that would have caught it:

```promql
rate(container_cpu_cfs_throttled_seconds_total[5m]) > 0
container_cpu_cfs_throttled_periods_total / container_cpu_cfs_periods_total > 0.25
```

The second is the more honest one: what fraction of periods hit the limit.
Anything above a few per cent means the limit is shaping latency.

Two structural fixes, and the choice between them is a real decision:

**Raise or remove the CPU limit.** Requests still guarantee the pod its share;
limits only cap the upside. Many production platforms deliberately set CPU
requests and no CPU limits, accepting noisy-neighbour risk in exchange for
removing throttling entirely.

**Or keep the limit and scale on a signal that reflects the work** — queue depth,
request rate, latency — rather than on a utilisation figure the limit is
suppressing.

## 4. The service that hangs with an idle CPU

No errors, no crash, no CPU. Requests time out. A restart fixes it, and it
happens again next week.

Zero CPU is the discriminator. A saturated service is busy; a deadlocked one is
doing nothing, and the difference is visible before you read a single line of
code:

```bash
ps -L -o pid,tid,stat,wchan:24 -p <pid>    # threads blocked in futex_wait
grep ctxt /proc/<pid>/status               # voluntary switches stopped climbing
grep -E 'nr_throttled' /sys/fs/cgroup/cpu.stat   # not throttling — rules that out
```

Threads parked in `futex_wait` with no forward progress is a lock. A thread dump
— `jstack`, `SIGQUIT` to a Go process, `py-spy dump` — names the lines involved.

The prevention is dull and effective: acquire locks in a consistent order
everywhere, hold them for as little code as possible, and prefer a timeout on
acquisition so a deadlock becomes a slow error rather than a permanent hang.

## What to monitor

| Signal | Why |
|---|---|
| `container_cpu_cfs_throttled_seconds_total` | The only unambiguous CPU signal a container has |
| Throttled periods ÷ total periods | Better than seconds: says how often the limit binds |
| Thread count per process | Catches a runtime that sized itself from the host |
| Voluntary vs nonvoluntary switches | Separates waiting from being preempted |
| CPU utilisation | Useful only *alongside* throttling, never instead of it |

:::callback
**E29** expresses `cpu.max` as Kubernetes requests and limits, and this is where
the "should we set CPU limits at all" argument comes from — it is an argument
about throttling, and now you can measure both sides of it. **E31** meets the
same numbers as node CPU pressure.
:::

:::checkpoint
Explain to someone who has not read this topic:

1. Why raising the worker count can make a service slower
2. Why a throttled container shows moderate CPU utilisation
3. Why `nproc` is the wrong number to size a thread pool inside a container
4. How you would tell a deadlock from a saturated service in two commands
5. Why Linux load average can be 90 on a machine with an idle CPU
:::

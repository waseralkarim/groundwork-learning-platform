---
topic: topic.the-machine
section: production-considerations
title: Why this matters, and what it becomes
order: 5
mode: design
---

:::objective{id=OBJ-A01.1.8}

## Sizing, and the failure order

You are asked: *we need to run 200 copies of a process that uses about 300MB
each, on a 32GB machine. Fine?*

The arithmetic is the easy half:

```text
200 × 300MB = 60,000MB ≈ 58.6 GB
Available:                 ~30 GB (32GB total, minus OS and page cache)
Shortfall:                 ~29 GB
```

It does not fit. But the useful answer is not "no" — it is **what happens, in
what order**:

1. Processes start. Memory fills. The page cache is squeezed out first, so file
   I/O quietly gets slower as cached reads become disk reads.
2. Around process 90–100, RAM is genuinely exhausted. The kernel starts
   **swapping**. Latency does not degrade gracefully; it falls off a cliff,
   because a memory access that cost 80ns now costs 50µs.
3. The machine becomes unresponsive while technically still working. SSH takes
   30 seconds. Health checks time out. Monitoring reports the service as down
   while the process list shows everything running.
4. The **OOM killer** fires and kills the largest process. Then another.
5. If a supervisor restarts them, you now have a **restart loop** that consumes
   the remaining capacity, and the machine gets worse rather than recovering.

Step 3 is the one that surprises people. The symptom of memory exhaustion is
usually *timeouts*, not out-of-memory errors — which is why "the service is
slow" and "the service is out of memory" are so often the same incident.

The right follow-up questions: is 300MB RSS or VSZ? Is it steady-state or peak?
Is swap enabled at all, and should it be? Could 200 processes be 8 processes
with 25 threads each?

## Development is not production

| Assumption | Fine locally | Costs money in production |
|---|---|---|
| "It fits in memory" | Your laptop has 32GB and one user | The server has 4GB and 500 concurrent users |
| "Startup time is fine" | Once a day | Every deploy, every autoscale event, every restart |
| "Disk is fast" | Local NVMe | Network-attached storage, ~10× slower |
| "One core is enough" | One request at a time | Requests arrive concurrently |
| "Swap will save us" | Nothing swaps at 5% load | Swapping under load reads as an outage |

The general form: local development has one user, warm caches, fast local disk
and no contention. Every one of those is false in production.

## What this topic becomes

Nothing here is a dead end. Each piece is load-bearing later:

| From this topic | Becomes |
|---|---|
| Volatile vs persistent | Docker volumes, Kubernetes PersistentVolumes |
| Virtual memory, RSS | Container memory limits, `OOMKilled`, requests and limits |
| Cores and scheduling | CPU limits, throttling, HPA |
| Architecture (amd64/arm64) | Multi-arch images, `--platform`, Graviton migrations |
| The kernel boundary | Namespaces, cgroups, capabilities, seccomp |
| Page cache | Database tuning, why the first query is slow |
| Memory hierarchy | Caching strategy, Redis, CDNs |
| `vmstat` diagnosis | Every production incident you will ever work |

:::note
When you reach the Kubernetes track and read that a pod was `OOMKilled`, you
will not be learning a new concept. You will be recognising this one, scoped to
a cgroup. That is the entire reason this topic comes first.
:::

## Common mistakes

**Reading the `free` column.** The single most common mistake in this topic.
Read `available`.

**Assuming more cores means faster.** Only if the workload is parallel.

**Confusing VSZ with RSS.** VSZ is a reservation. RSS is the bill.

**Treating the OOM killer as an error handler.** It is `SIGKILL`. No cleanup, no
flush, no shutdown hook. If your process needs to shut down cleanly, it must
never reach this point.

**Believing "same specs" means "same machine".** Same core count and same RAM,
different architecture, different storage class, different NUMA topology — the
performance can differ by an order of magnitude.

**Ignoring the first `vmstat` line.** It is an average since boot. It is not
telling you about now.

## Security note

Two of the mechanisms in this topic are security boundaries, not just
performance features.

**Virtual memory isolation** is why one process cannot read another's memory.
When that boundary has failed — Meltdown and Spectre — it was serious enough to
warrant emergency patching across the entire industry, at a measurable
performance cost that we all still pay.

**The user/kernel split** is why a program must ask the kernel to touch
hardware. Every container isolation feature you will meet later is built on that
boundary. When you read that `--privileged` "disables container isolation", what
it disables is a set of restrictions on crossing exactly this line.

:::checkpoint
The topic is complete when you can:

1. Size a workload and state the failure order, not just the verdict
2. Explain what `OOMKilled` will mean before you have read anything about Kubernetes
3. Diagnose CPU- vs memory- vs I/O-bound from `vmstat` output and cite the evidence

The [labs](../labs) and the assessment are where you find out whether you can.
:::

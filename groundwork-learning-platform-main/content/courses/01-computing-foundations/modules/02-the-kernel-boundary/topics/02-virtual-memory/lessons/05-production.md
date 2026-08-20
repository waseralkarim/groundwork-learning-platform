---
topic: topic.virtual-memory
section: production
title: The five memory incidents
order: 5
mode: explain
---

Five failures you will meet. Each is this topic wearing different clothes, and
each has a wrong fix that is easier than the right one.

## 1. Exit code 137

The container is gone. No stack trace, no shutdown log, no error from the
application. Just `137` and a restart.

137 is 128 + 9: killed by SIGKILL. In a container that is almost always the OOM
killer, and the confirmation is one file:

```bash
kubectl get pod <pod> -o jsonpath='{.status.containerStatuses[0].lastState.terminated.reason}'
# OOMKilled
```

**The wrong fix** is raising the limit until it stops. Sometimes that is correct —
the limit was genuinely too small. Often it converts a fast, obvious failure into
a slow, expensive one, and hides a leak for another quarter.

**The right first question** is which kind of memory was at the limit. If `anon`
was near the cap, the application really needs that much or is leaking. If `file`
dominated, the kill was pushed over the edge by cache and the limit may be fine.

## 2. The runtime that sized itself from the wrong machine

A JVM starts in a container with a 512 MB limit, reads 64 GB from
`/proc/meminfo`, and chooses a heap of 16 GB. It is killed under the first real
load, usually in production and not in the test environment, because the test
node was smaller.

```bash
docker exec <c> sh -c 'free -m | head -2; cat /sys/fs/cgroup/memory.max'
```

Two numbers that disagree by two orders of magnitude, and everything in the
container that trusts the first one is a hazard.

Modern JVMs honour cgroup limits with `-XX:+UseContainerSupport` (on by default
since 10). Go needs `GOMEMLIMIT`. Node needs `--max-old-space-size`. Anything
that computes workers from "RAM / 4" needs its input replaced.

:::warning{scope=production}
This is the failure that makes people distrust containers. The container is
behaving exactly as configured — it is the application that asked the wrong
question. The fix belongs in the application's configuration, not in the limit.
:::

## 3. Memory that climbs forever and is not a leak

A service's memory rises steadily for days and plateaus just under the limit.
Restarting it drops the number to nothing. It looks exactly like a leak.

Three possibilities, distinguished by `memory.stat`:

| What you see | What it is | What to do |
|---|---|---|
| `file` grows, `anon` flat | Page cache. Working as designed | Nothing |
| `anon` grows and never falls | A real leak, or an unbounded cache in the app | Heap profile |
| `anon` grows in steps and plateaus | Allocator arenas — freed memory not returned to the OS | Often nothing |

That third row is the one that wastes the most time. Freeing memory in an
application does not necessarily return it to the kernel: allocators keep arenas
for reuse, so RSS stays high while the application's own heap usage has dropped.
The application is not leaking and the memory is not lost — it is held for the
next allocation.

A heap profile shows what the *application* thinks it is using. Comparing that
against RSS is what separates the second row from the third.

:::objective{id=OBJ-A01.4.8}
Troubleshoot a service whose memory use climbs steadily, and separate a leak
from cache growth from fragmentation.
:::

## 4. The node that evicts pods for no visible reason

Kubernetes evicts pods when a node is under memory pressure, and the pod that
gets evicted is frequently not the one responsible. Eviction ranks by usage
above requests, so a well-behaved pod with a low request and honest usage can be
chosen over the one that actually caused the pressure.

The mechanism is the same accounting from the node's side, and the lever is
`requests` rather than `limits`:

- **requests** decide scheduling and eviction ranking
- **limits** decide when the kernel kills the container

A pod with `requests` far below its real usage is asking to be evicted first.
That is one of the most common causes of unexplained restarts on a busy cluster,
and it is a configuration mistake rather than a kernel behaviour.

## 5. Alerting that pages for healthy systems

The last one is self-inflicted and enormously common:

- Alerting on **free** memory rather than **available** — pages at 3am for
  machines whose only sin is a warm page cache
- Alerting on **container memory usage %** without splitting anon from file — a
  container at 95% cache is fine and a container at 95% anon is nearly dead, and
  the alert cannot tell them apart
- Summing **RSS** across processes — a total the machine cannot reach
- No alert on **`oom_kill` count**, which is the one signal that is never a
  false positive

If you take one operational change from this topic, make it that last bullet.
`container_memory_failcnt`, `memory.events`' `oom_kill`, or the Kubernetes
`OOMKilled` reason are unambiguous: something died, and it died in a way that
lost work.

:::callback
This topic completes the foundations of container resource behaviour. **C14**
introduces cgroups as the mechanism, **C16** hardens them, and **E29** expresses
the same numbers as Kubernetes requests and limits. None of them adds a new
concept — they configure the accounting you have just read.
:::

:::checkpoint
Explain to someone who has not read this topic:

1. Why a container can be killed while its application reports healthy memory
2. Why summing per-process RSS across a machine gives the wrong answer
3. Why a JVM in a container may choose a heap that guarantees its own death
4. Which of `anon` and `file` you should alert on, and why the distinction
   matters more than the percentage
5. Why there is no graceful handling of an OOM kill from inside the process
:::

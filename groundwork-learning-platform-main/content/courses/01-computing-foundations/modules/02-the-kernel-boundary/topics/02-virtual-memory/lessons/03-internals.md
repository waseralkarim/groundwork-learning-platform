---
topic: topic.virtual-memory
section: internals
title: What a cgroup is actually counting
order: 3
mode: explain
---

:::objective{id=OBJ-A01.4.5}
Measure how a cgroup accounts for page cache separately from anonymous memory,
and predict which of the two is reclaimable under pressure.
:::

Everything so far has been per-process. Container memory limits are not: they
are per **cgroup**, and the difference is where most production surprises live.

## The limit is on a group, not a process

A container is a cgroup. Its limit applies to everything in it — every process,
plus the kernel memory the group causes to be allocated, plus the page cache for
files those processes read.

That last clause is the one nobody expects.

:::diagram{src=../diagrams/cgroup-accounting.mmd caption="What is charged, and what can be given back"}

Under cgroup v2 the numbers live in files, and they are worth knowing by name:

| File | What it holds |
|---|---|
| `memory.max` | The limit. `max` means unlimited |
| `memory.current` | Total charged now: anon + file + kernel |
| `memory.stat` | The breakdown — `anon`, `file`, `shmem`, `slab`, and much more |
| `memory.events` | Counters: `low`, `high`, `max`, `oom`, `oom_kill` |
| `memory.high` | Throttling threshold, if set. Reclaim gets aggressive here |

The important relationship: **`memory.current` is compared against
`memory.max`,** and `memory.current` includes page cache.

## Why a container dies with "plenty free"

Here is the sequence that catches people, in order:

1. The application uses 300 MB of heap. Anonymous, cannot be dropped.
2. It processes files — logs, uploads, a database's data. The kernel caches
   what it reads: 200 MB of page cache, charged to this cgroup.
3. `memory.current` now reads 500 MB against a 512 MB limit. Everything is
   fine: 200 MB of that is reclaimable on demand.
4. The application allocates 50 MB more heap.
5. The kernel reclaims page cache to make room. This is silent and normal.
6. The application keeps growing. Eventually the cache is gone, only anonymous
   memory remains, there is nothing left to reclaim, and the group is over its
   limit.
7. **OOM kill.** SIGKILL, no handler, no cleanup, exit code 137.

The application's own memory number never looked alarming. Every monitoring
graph of "application memory" was healthy right up to the kill.

:::predict{question="A container sits at 95% of memory.max for hours without incident. Is that a problem?"}
Not necessarily — and this is the reading that matters.

Check `memory.stat`. If most of the charge is `file`, that is page cache doing
its job, and it will be handed back the instant anything needs it. A container
that reads files will always drift toward its limit, because the kernel has no
reason to discard cache before it must.

If most of it is `anon`, the situation is entirely different: none of that can
be dropped, so the headroom is real and it is nearly gone.

Same percentage, opposite conclusions. This is why "memory usage %" alone is a
poor alert, and why `memory.stat` is the first file to read.
:::

## The `file` line is not all reclaimable

`memory.stat`'s `file` figure covers everything file-backed, and the `shmem`
subset of it is tmpfs and shared memory. That subset behaves like anonymous
memory: there is no disk copy, so it cannot be dropped, only swapped — and swap
is usually off.

This matters because the obvious reading of a high `file` figure is "cache,
reclaimable, harmless", and for a tmpfs that reading is exactly backwards:

```bash
grep -E '^(anon|file|shmem) ' /sys/fs/cgroup/memory.stat
```

If `shmem` is close to `file`, almost none of that charge can be given back. A
service spooling uploads to `/tmp`, a pod with an in-memory `emptyDir`, anything
using `/dev/shm` — all of them are consuming their own memory limit while
appearing to write files.

## Page cache is charged to whoever touched it first

A subtlety with real consequences: page cache is charged to the cgroup that
caused the read. Two containers reading the same file get one physical copy, and
the first one to touch it carries the charge.

That produces genuinely confusing behaviour — a container's memory rising
because of a file another container also uses — and it is why per-container
memory graphs sometimes move for no reason visible inside that container.

## What the OOM killer chooses

When a cgroup cannot reclaim enough, the kernel kills something inside it. The
choice is scored by `oom_score`, which is dominated by how much memory a process
is using, adjusted by `oom_score_adj`.

In practice, in a container, the biggest process is usually the application, and
the application is usually PID 1. So:

- The container dies, not just the process
- Exit code is **137** — 128 + 9, meaning SIGKILL
- No stack trace, no shutdown hook, no final log line
- The kernel logs it, but `dmesg` needs a capability the container does not have

:::callback
From **Processes**: SIGKILL cannot be caught, blocked or ignored. That is exactly
why an OOM kill takes your in-flight work with it, and why there is no such thing
as handling one gracefully from inside.
:::

## Swap, and its absence

Swap gives the kernel somewhere to put anonymous pages when RAM runs short. It
trades speed for survival: a swapping machine is slow, but it is alive.

Most container platforms disable swap, and Kubernetes historically required it
off. The reasoning is that a swapping node is so slow it is effectively down
while looking up, which makes it hard to schedule around.

The consequence is worth stating clearly: **without swap, the gap between "fine"
and "killed" is one allocation.** There is no gradual slowdown to alert on. The
first symptom is the kill.

## Why the runtime has to know

The last piece, and the one that produces the most self-inflicted outages.

A process inside a container that asks the kernel how much memory the machine
has gets **the machine's** answer, not the container's limit. `/proc/meminfo` is
not namespaced.

So a runtime that sizes itself from available RAM — a JVM choosing a heap, a Go
program setting `GOMEMLIMIT`, a connection pool sized by "memory / 4" — reads 64
GB on a host, on a container limited to 512 MB, and configures itself to die.

Modern JVMs read cgroup limits when told to. Go needs `GOMEMLIMIT` set from the
limit. Everything else needs checking, and the check is one command:

```bash
docker exec <container> sh -c 'free -m; cat /sys/fs/cgroup/memory.max'
```

If those two disagree — and they will — anything in the container that trusts
the first number is a problem waiting for load.

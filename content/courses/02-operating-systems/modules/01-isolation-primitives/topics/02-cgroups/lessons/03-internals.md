---
topic: topic.cgroups
section: internals
title: Weights, limits, protections — and the path they sit on
order: 3
mode: explain
---

:::objective{id=OBJ-A02.2.4}
Distinguish a weight, a limit and a protection, and say which of them does
anything when there is no contention.
:::

Three kinds of knob, and confusing them is where most resource misconfiguration
comes from.

## A limit is a ceiling, enforced always

```bash
cat /sys/fs/cgroup/cpu.max        # 50000 100000  -> half a CPU
cat /sys/fs/cgroup/memory.max     # 536870912     -> 512 MiB
```

`cpu.max` is a quota and a period, both in microseconds. The cgroup may consume
50ms of CPU time in every 100ms of wall clock. When it is spent, every task in
the cgroup is stopped until the next period begins — on an idle 16-core machine
just as firmly as on a busy one. A ceiling does not care whether anyone else
wants the resource.

`memory.max` is the same idea for memory, with a harsher enforcement: the kernel
reclaims what it can, and if it cannot get under the limit it OOM-kills
something in the cgroup.

## A weight is a share, and only of what is contended

```bash
cat /sys/fs/cgroup/cpu.weight     # 100 by default
```

Weights are relative. Two cgroups with weights 100 and 200 get a third and two
thirds of the CPU — *when the CPU is scarce*. When it is not, both get as much
as they ask for and the weights change nothing at all.

This is the source of a specific, recurring confusion. Someone raises a
container's CPU shares, tests on an idle staging node, sees no change, and
concludes the setting does not work. It works exactly as designed; the test had
no contention in it, and a weight with no contention is a number in a file.

Kubernetes CPU *requests* become weights. The conversion is arithmetic: shares
are `millicores × 1024 / 1000`, and the weight is
`1 + (shares − 2) × 9999 / 262142`. So 100m becomes `cpu.weight 4`, 500m becomes
20, and 2 CPUs becomes 79. A request is not a reservation of CPU — it is a claim
on a
share of the CPU *when there is competition*, plus a number the scheduler uses
when choosing a node.

## A protection is a claim on someone else's memory

```bash
cat /sys/fs/cgroup/memory.low     # 0 by default — no protection
cat /sys/fs/cgroup/memory.min     # 0
cat /sys/fs/cgroup/memory.high    # max — no throttling
```

:::diagram{src=../diagrams/weight-limit-protection.mmd caption="What happens to a cgroup's memory, by which threshold it has crossed"}

These three are the memory knobs almost nobody sets, and the reason to know them
is that they do things `memory.max` cannot.

**`memory.low`** — a soft protection. Memory below this figure is reclaimed only
when there is nothing else to take. Set it on a database's page cache and the
kernel will evict a batch job's cache first.

**`memory.min`** — a hard protection. Memory below it is never reclaimed. If
that makes the system unable to free enough, the OOM killer fires *somewhere
else*. This is genuinely a weapon and worth treating as one.

**`memory.high`** — a throttle rather than a wall. Above it the kernel reclaims
aggressively and deliberately slows the offending cgroup down, but never kills
it. For a workload with a memory spike you would rather serve slowly than not at
all, this is the knob you actually wanted when you reached for `memory.max`.

:::warning{scope=production}
`memory.high` is the most under-used file here, and Kubernetes does not expose
it directly — you get `memory.max` from a limit and nothing else. Nodes with
MemoryQoS enabled set `memory.high` from the request as a percentage, which is
the feature to look for if you have workloads that would rather degrade than
die.
:::

:::objective{id=OBJ-A02.2.6}
Calculate the effective limit on a cgroup from the limits along its path, and
explain why a parent can kill a child that is within its own.
:::

## The effective limit is the tightest one on the path

A cgroup's limit is not its own file. It is the minimum of every limit between
the root and itself.

```text
/                                     memory.max = max
└── kubepods.slice                    memory.max = 28G
    └── kubepods-burstable.slice      memory.max = max
        └── pod-9f3c.slice            memory.max = 512M     <- the pod
            ├── container-app.scope   memory.max = 448M
            └── container-sidecar     memory.max = max      <- effectively 512M
```

The sidecar's own file says `max`. Its effective limit is 512 MiB, because the
pod slice above it says so — and the 512 MiB is shared with the app container,
which has already claimed 448 MiB of it.

So the sidecar can be OOM-killed with `memory.max: max` in its own cgroup and
`memory.current` reading 40 MiB. Nothing about its own files predicts it. This
is the shape of the confusing Kubernetes OOM kill, and reading it requires
walking the path from the node.

For CPU the composition is the same but the consequence is gentler: the tightest
`cpu.max` on the path is the ceiling, and hitting a parent's quota throttles
every cgroup under it. A noisy sidecar can throttle the application container it
was supposed to be helping.

## Who gets killed

When a cgroup cannot be brought under its limit, the kernel picks a victim from
inside it — by `oom_score`, which is roughly "how much memory would killing this
free", adjusted by `oom_score_adj`. It is not necessarily the process that
allocated last, and it is very often not the one you would have chosen.

`memory.oom.group` changes the calculation entirely: set it, and the whole
cgroup is killed together rather than one process at a time. For a container
whose processes are useless without each other — which is most containers — that
is the honest behaviour, because the alternative is a half-dead container that
still passes its liveness probe.

```bash
cat /sys/fs/cgroup/memory.events
# low 0
# high 0
# max 0
# oom 0
# oom_kill 0
```

`oom_kill` is the counter worth alerting on. It is a count of kills in this
cgroup, it survives the process that was killed, and unlike a log line it cannot
be missed because nobody was tailing at the time.

:::callback
From **Virtual Memory**: the cgroup counts page cache as memory, and file-backed
pages are reclaimable while anonymous ones are not. That is what "the kernel
reclaims what it can" means above — and why a container full of cache survives a
tight limit while one full of heap does not.
:::

## The one-sentence version

Limits are ceilings enforced always, weights are shares of contended resources
only, protections take from someone else — and the number that applies to you is
the tightest one on the path from the root, most of which you cannot see from
inside.

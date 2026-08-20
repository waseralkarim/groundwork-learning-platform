---
topic: topic.cgroups
section: core-concepts
title: One hierarchy, and what hangs off it
order: 2
mode: explain
---

:::objective{id=OBJ-A02.2.1}
Explain what a cgroup is, and how v2's single hierarchy differs from v1's
separate tree per controller.
:::

## A cgroup is a directory

```bash
ls /sys/fs/cgroup/
# cgroup.controllers  cgroup.procs  cgroup.subtree_control
# cpu.max  cpu.stat  cpu.weight  cpu.pressure
# memory.max  memory.current  memory.stat  memory.pressure
# pids.max  pids.current  io.stat
```

Every operation is a file operation. Create a cgroup with `mkdir`. Move a
process into it by writing its PID to `cgroup.procs`. Set a limit by writing a
number. Read usage by reading a file. Destroy it with `rmdir`, which fails while
processes remain.

That is the entire interface. There is no library, no daemon, and nothing that
systemd or Docker does here that you could not do with a shell — which is worth
knowing the first time a tool refuses to tell you what it configured.

## v1 had one tree per controller, and it did not work

Under cgroup v1 each controller had its own hierarchy, mounted separately:

```text
/sys/fs/cgroup/cpu/mygroup/
/sys/fs/cgroup/memory/somewhere-else/
/sys/fs/cgroup/blkio/a-third-place/
```

A process could be in `/mygroup` for CPU and `/somewhere-else` for memory. That
sounds flexible and was a disaster: the kernel could not reason about a group's
resources together, because "a group" did not exist as one thing. Memory
reclaim, which needs to know about I/O, could not coordinate with the I/O
controller because the two hierarchies disagreed about who was who.

v2 has one tree. A process is in exactly one cgroup, its path is the same for
every controller, and the kernel can finally reason about a group as a group.
That is why `io.pressure` and `memory.pressure` mean something in v2 and had no
v1 equivalent.

You will still meet v1 on older nodes. `cat /sys/fs/cgroup/cgroup.controllers`
answers which you are on in one command: the file exists only in v2.

:::objective{id=OBJ-A02.2.2}
Identify a process's cgroup and the controllers available to it, from inside a
container and from the host.
:::

## Controllers are enabled downward, one level at a time

A cgroup's available controllers are not inherited automatically. Its parent has
to hand each one down:

```bash
cat /sys/fs/cgroup/cgroup.controllers      # what this cgroup may use
cat /sys/fs/cgroup/cgroup.subtree_control  # what it passes to its children
```

`cgroup.controllers` is read-only and lists what the parent enabled. To give
children the memory controller, a cgroup writes `+memory` to its own
`subtree_control`. A controller not enabled at some level simply does not exist
below it, however deep the tree goes — so a missing `memory.max` in a child is
usually a parent that never enabled `memory`, not a bug.

There is one structural rule that catches people: **a cgroup with children may
not also contain processes.** Everything except the root is either a branch or a
leaf. It removes v1's ambiguity about whether a parent's own processes compete
with its children, by making the situation impossible.

## Reading which cgroup you are in

```bash
cat /proc/self/cgroup
# 0::/
```

That `0::/` says: hierarchy 0 (v2's only one), no controller name (v2 does not
name them), path `/`. This process is at the root of the tree.

Except it is not. Read the same thing on the host for the same process and you
get:

```text
0::/kubepods.slice/kubepods-burstable.slice/kubepods-burstable-pod9f3c.slice/cri-containerd-8a1f.scope
```

:::objective{id=OBJ-A02.2.3}
Explain why a container sees itself at the root of the hierarchy, and what the
host sees in its place.
:::

## The cgroup namespace, which is why

This is the eighth namespace from the last topic, and it exists for exactly this
reason. A cgroup namespace re-roots the view: the cgroup the container was
placed in becomes `/` as far as anything inside can tell.

Two reasons it works this way, and both matter operationally:

**Not leaking the tree.** Without it, every container could read its position in
the node's hierarchy — pod UIDs, QoS class, namespace names, the shape of the
cluster. Information about other tenants, for free, from a file.

**Making the container portable.** Software inside reads `/sys/fs/cgroup/memory.max`
and gets its own limit, without knowing or caring where it sits. That path works
identically under Docker, containerd, systemd-nspawn and a bare `mkdir`.

The consequence you have to remember: **from inside, you cannot see what is
above you.** Your `memory.max` may say `max` while a parent slice caps the whole
pod at 512 MiB. The container is not lying and neither is the kernel — you are
reading one node of a path whose other nodes are not visible from here.

:::warning
This is the commonest confusing OOM kill in Kubernetes. A container's own
`memory.max` is unset, `memory.current` is nowhere near anything, and it is
killed anyway — because the *pod* cgroup one level up hit its limit, and the
kernel chose a victim from inside it. Diagnosing it requires reading the tree
from the node, which is exactly what the container cannot do.
:::

## The four controllers you will actually use

| Controller | Key files | What it does |
|---|---|---|
| **cpu** | `cpu.max`, `cpu.weight`, `cpu.stat` | Quota per period, relative share, throttling counters |
| **memory** | `memory.max`, `memory.high`, `memory.low`, `memory.current`, `memory.stat`, `memory.events` | Hard limit, throttle point, protection, usage and accounting |
| **pids** | `pids.max`, `pids.current` | A ceiling on processes and threads. The fork-bomb wall |
| **io** | `io.max`, `io.stat`, `io.latency` | Bandwidth and IOPS per device, and a latency target |

Plus `cpu.pressure`, `memory.pressure` and `io.pressure`, which belong to no
controller in particular and are the most useful files in the directory. They
get their own lesson.

## The one-sentence version

A cgroup is a directory of files holding a set of processes; v2 puts every
controller in one tree so the kernel can reason about a group as a whole; your
container sees itself at the root because of the cgroup namespace, which means
the limit that kills it may be one you cannot see.

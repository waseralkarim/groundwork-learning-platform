---
topic: topic.cgroups
section: overview
title: You have already used these. Now find out where they live
order: 1
mode: explain
---

In Computing Foundations you read `memory.max`, watched `nr_throttled` climb,
and diagnosed a container killed at sixty percent of its limit. You have already
used cgroups, quite hard.

What you did not do is ask where those files came from, why your container sees
itself at the root of the tree, or what happens when a limit above you is
tighter than your own. This topic is about the structure the numbers live in —
which turns out to be where most of the surprising behaviour comes from.

## The specific things this explains

- Why `nproc` says 16 in a container limited to half a CPU, and what that breaks
- Why a pod can be OOM-killed while its own `memory.max` is `max`
- Why `cpu.weight` appears to do nothing when you test it on an idle machine
- What `memory.high` is, and why almost nobody sets it despite it being the knob
  they actually want
- Why a Kubernetes pod's QoS class is a position in a tree, not a label
- What PSI is, and why "some" and "full" being equal is itself a diagnosis

:::callback
From **Virtual Memory**: the cgroup counts page cache as memory, and file-backed
pages are reclaimable while anonymous pages are not — which is why a container
can be killed with what looks like headroom. That accounting is the memory
*controller* doing its job. This topic is about which cgroup it does that job
for, and what sits above it.
:::

## One tree, not seven

:::diagram{src=../diagrams/one-hierarchy.mmd caption="A node's cgroup tree. Limits apply at every level, and the tightest one wins"}

A cgroup is a directory of interface files with a set of processes attached. The
directory *is* the cgroup — creating one is `mkdir`, moving a process into one
is writing its PID to `cgroup.procs`, and setting a limit is writing a number to
a file. There is no API beyond the filesystem.

In cgroup v2 there is exactly one hierarchy, and every controller uses it. A
process belongs to exactly one cgroup, and its full path determines every limit
that applies to it.

That last sentence is the whole topic. Limits are not a property of your
container. They are a property of every cgroup between the root and your
container, and the effective limit is the tightest one on that path.

## The finding this topic is built around

Here is a real reading from inside a container that is limited to half a CPU:

:::terminal{title="Two answers to 'how many CPUs do I have'"}
$ nproc
16
$ cat /sys/fs/cgroup/cpu.max
50000 100000
:::

`nproc` counts the CPUs the kernel has. `cpu.max` says this cgroup may use 50ms
of CPU in every 100ms — half of one. Both are correct answers to different
questions, and almost every runtime asks the wrong one.

The JVM before it learned about cgroups, Go's `GOMAXPROCS`, Node's thread pool,
nginx's `worker_processes auto`, every `nproc`-based CI parallelism flag: they
size themselves from the first number and are then throttled by the second.
More workers, more contention, less throughput — and the machine looks idle
while it happens.

:::predict{question="A container has cpu.max of 50000 100000 and runs 16 busy threads. What is its CPU utilisation?"}
About 50%, and that number is a lie in an interesting way.

The cgroup gets 50ms of CPU per 100ms period. Sixteen threads spend it in the
first few milliseconds of every period, and then all sixteen are stopped until
the next one. Averaged over time the container is using half a CPU, exactly as
configured, and a utilisation dashboard shows a flat, healthy 50%.

What that hides is the latency. For most of every 100ms window, nothing is
running. A request that arrives in the stopped part of the period waits for the
next one — so a service which is "at half its CPU limit" can have a p99 of
100ms with no slow code anywhere.

`cpu.stat` tells you directly: `nr_throttled` counts the periods that ended
early. If it is close to `nr_periods`, you are throttled almost every period,
whatever the utilisation graph says. PSI tells you the same thing in one number,
which is why this topic ends up there.
:::

## Weight, limit, protection

Most people know one of the three knobs. The other two are where the useful
behaviour is:

| Kind | Example | When it acts |
|---|---|---|
| **Weight** | `cpu.weight` | Only under contention. On an idle machine it does nothing at all |
| **Limit** | `cpu.max`, `memory.max` | Always. A ceiling, enforced whether or not anyone else wants the resource |
| **Protection** | `memory.low`, `memory.min` | Under pressure, in your favour. It takes memory away from someone else |

Kubernetes uses all three and only names two of them. A CPU *request* becomes a
weight; a CPU *limit* becomes a limit; a memory *request* is a scheduling
figure that may also become a protection. Being able to say which is which is
most of what makes a resources block reviewable.

## What you already have

From **Threads and Concurrency** you measured throttling and watched more
workers make a service slower. From **Virtual Memory** you established what the
memory controller counts. From **Namespaces** you know why your container thinks
it is at the root of the tree — the cgroup namespace, which is the eighth one
you listed and the only one this topic needs.

## How to work through it

Concepts, the hierarchy, the tools, production. Four labs: find your own cgroup
and confront the `nproc` problem; put a real load on a real limit and read
pressure rather than utilisation; work out effective limits down a node's tree;
and finally reconstruct three pods' resources blocks from their cgroup files
alone.

Every number in this topic comes out of a file you can read.

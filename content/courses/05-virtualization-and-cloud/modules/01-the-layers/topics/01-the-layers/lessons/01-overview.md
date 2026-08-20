---
topic: topic.the-layers
section: overview
title: Four layers, and three numbers that are not true
order: 1
mode: explain
---

Run `nproc` in the lab container for this topic and it says **16**. The cgroup
allows **1.5 cores**. Both are readable, one is what you get, and every runtime
that sizes a thread pool from the first one is about to spend its life being
throttled.

That gap is this topic. Not "what is a container" as a definition, but: what is
actually underneath a running process, what does each layer provide, and which
of the numbers it reports are describing something else.

## The layers, and what each one virtualises

| Layer | Virtualises | Shares | Starts in |
|---|---|---|---|
| Bare metal | nothing | — | minutes |
| Virtual machine | the **hardware** | the physical machine | tens of seconds |
| Container | the **operating system's view** | the host **kernel** | milliseconds to a second |
| Function | the **machine entirely** | whatever the platform runs | a cold start, then nothing |

The one that matters most is the third row's middle column. **A container shares
the host kernel.** It did not boot one, it cannot load a module into one, and
its isolation is a set of kernel features rather than a hardware boundary. A VM
brings its own kernel, which is why it costs hundreds of megabytes and seconds
to start, and why its boundary is stronger.

Everything else about the two follows from that single difference.

## What you can read from inside

You are always standing on a stack, and every layer leaves a fingerprint:

```text
hypervisor flag in /proc/cpuinfo   → something is virtualising this CPU
Hypervisor vendor: Microsoft       → which something
uname -r → …-microsoft-standard-WSL2  → a kernel this process did not boot
/.dockerenv exists                 → containerised
Model name: Intel i7-10700         → the actual silicon underneath it all
```

That is four layers, identified in five commands: a container, inside a VM,
under a hypervisor, on a physical CPU. In the first lab you will take that
census yourself, and it is a genuinely useful skill — "what am I actually
running on" comes up constantly and most people cannot answer it.

## The three numbers that lie

`/proc/cpuinfo`, `/proc/meminfo` and `/proc/uptime` are not lying exactly. They
are describing **the machine**, accurately, while you are asking about **your
cgroup**.

```text
/proc/cpuinfo    16 CPUs        cpu.max        1.5 cores
/proc/meminfo    15.5 GiB       memory.max     512 MiB
/proc/uptime     5 days         this container 40 seconds
```

Every one of those is a real production failure. A JVM sizing its heap from
`MemTotal` and getting OOM-killed. A Go program setting `GOMAXPROCS` to 16 under
a 1.5-core quota. A thread pool with eleven times more workers than it has CPU
for. Monitoring that reports 9% CPU usage on a container that is being throttled
into the ground.

:::note
You will measure the consequence directly. Sixteen threads under a 1.5-core
quota produced **31 throttled periods and 44 seconds of throttled time in 6
seconds of wall clock** — the process spent most of its life stopped, and every
CPU-usage graph would show it looking fine.
:::

## The startup figure that is quoted and the one you wait for

"Containers start in milliseconds" is true of the container runtime creating a
process. Timing `docker run --rm image true` on the machine these labs run on
gave **~760 ms**, and `docker exec` into an already-running container **~245
ms**.

Both numbers are in the lab's reference table with their sources, because the
gap between them is the more useful fact. It is why "why is my pod taking eight
seconds to become ready" has a real answer rather than being a broken cluster.

## What this topic is for

Three things you will be able to do afterwards:

**Answer "what am I running on"** from inside anything, in under a minute.

**Predict which numbers to distrust**, and read the allowed value instead — which
is one file in `/sys/fs/cgroup` and almost nobody looks at it.

**Choose a layer for a workload** and say what the alternatives would have cost.
The last lab gives you four workloads, and the one whose constraint eliminates
every layer but one is not the one with the largest resource requirement.

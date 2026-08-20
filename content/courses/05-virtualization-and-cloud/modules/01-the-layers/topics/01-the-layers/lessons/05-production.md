---
topic: topic.the-layers
section: production
title: Choosing a layer, and the failures each one produces
order: 5
mode: explain
---

## The choice is usually made by a constraint, not a preference

Most workloads run fine on any of the layers, and the decision is density and
speed. Then occasionally a constraint appears that eliminates options outright,
and recognising those is most of the skill:

**Hostile tenancy** — you run code your customers wrote. Containers alone are
not sufficient; you need a hypervisor boundary. gVisor, Kata Containers or
Firecracker, or a function platform that is already doing this for you. This is
the constraint that most often decides the answer and it is not negotiable by
configuration.

**A kernel requirement** — a specific kernel version, a module, a sysctl that is
not namespaced. Containers share the host kernel, so any of these means a VM.
The tell is a request to `modprobe` something or set a sysctl and finding it is
read-only.

**Hardware access** — a GPU passed through, a specific NIC, a device the
hypervisor will not virtualise. Bare metal, or a VM with passthrough.

**Latency at the tail** — the hypervisor tax is a few percent on throughput and
occasionally much worse at p99, because of steal time and noisy neighbours. Most
services never notice; a trading system does.

**Idle most of the time** — a function, if the cold start fits the latency
budget. The economics are decisive: paying for execution rather than for uptime
turns a mostly-idle service from a monthly bill into a rounding error.

Absent one of these, use containers. Not because they are best in any absolute
sense, but because the density and the start-up speed are real and the isolation
is sufficient for your own code.

## The failures each layer actually produces

**Bare metal** — one workload takes the machine down for everything on it.
Capacity is a purchase-order problem, so it is provisioned for peak and idle
most of the time. Recovery is manual and measured in hours.

**VM** — the noisy-neighbour problems the hypervisor was supposed to hide, which
show up as **steal time**: your vCPU is ready and the hypervisor is running
somebody else. `%steal` in `top` or `vmstat`, and it is the number to check when
a VM is slow for no reason visible inside it. Also: everything is slower to
start, so autoscaling reacts in minutes rather than seconds and you over-provision
to compensate.

**Container** — the whole of this topic. A runtime that sized itself from the
host's numbers, throttling that looks like healthy CPU usage, memory limits
producing exit code 137 with no application error, and disk quotas that `df`
does not know about. Plus the boundary being the kernel, which matters the day
there is a kernel CVE.

**Function** — cold starts on the path that matters, timeouts that cannot be
extended past the platform's ceiling, and a cost model that is excellent when
idle and can be startling under sustained load. There is a crossover point where
paying per-execution becomes more expensive than a container running constantly,
and it is worth knowing roughly where it is for your workload.

## Reading exit code 137

Worth being able to translate on sight, because it is the most common container
failure and it does not say what it means.

`137` is `128 + 9` — killed by SIGKILL. In a container that is almost always the
**OOM killer**, because the process exceeded `memory.max`. There is no
application error and no stack trace, because SIGKILL cannot be caught.

```bash
# What actually happened
cat /sys/fs/cgroup/memory.events        # look at oom_kill
dmesg | grep -i 'killed process'        # if you can read dmesg
kubectl describe pod <name>             # Last State: OOMKilled
```

And then the diagnosis is usually one of two things: the limit is genuinely too
low, or **the runtime sized itself from the host's memory** and was always going
to exceed it. Check `MaxRAMPercentage` or its equivalent before raising the
limit, because raising it on a JVM that is sizing from 15.5 GiB just moves the
failure.

## Monitoring that reads the right number

This is the practical payoff of the whole topic, and most dashboards get it
wrong:

- **CPU** — alert on `nr_throttled` increasing and on `cpu.pressure`, not only
  on utilisation. A throttled container shows low utilisation and is failing.
- **Memory** — compare `memory.current` against `memory.max`, never against
  `MemTotal`. And alert on `memory.events` `oom_kill` rather than waiting for a
  crash loop.
- **Load average** — do not use it in a container. It is the machine's, including
  every neighbour. `cpu.pressure` is the per-cgroup answer.
- **Disk** — the volume's quota, not what `df` reports.
- **Steal time** on VMs, which is invisible from inside a container and is the
  layer below it being oversubscribed.

If a dashboard shows a service at 9% CPU while its p99 is terrible, the number
being shown is a fraction of the host and the process is throttled against its
own quota. That single misreading probably wastes more engineering time than any
other item in this topic.

## What the layers cost, roughly

Rules of thumb rather than precise figures, and worth sanity-checking against
your own bill:

- A VM idles at its full price. A container idles at the cost of the VM it is on,
  divided by density.
- Density is the whole commercial argument for containers: tens of VMs per
  machine against hundreds of containers.
- Functions are dramatically cheaper for bursty and idle workloads and can be
  dramatically more expensive for steady ones. The crossover is usually
  somewhere around "busy more than a few hours a day".
- Bare metal is cheapest per unit of compute and most expensive per unit of
  flexibility, and the flexibility is usually what you are actually buying.

The next module takes this further into what "the cloud" is actually selling and
where the responsibility boundary sits — which is the same question as this one,
asked commercially instead of technically.

## The habit worth keeping

**Know which layer you are asking about.** A pod in a managed cluster is a
container, in a VM, on a hypervisor, in a datacentre, and any of those can be why
something is slow. "The service is slow" is not a question until you have picked
a layer, and the census in the first lab takes under a minute.

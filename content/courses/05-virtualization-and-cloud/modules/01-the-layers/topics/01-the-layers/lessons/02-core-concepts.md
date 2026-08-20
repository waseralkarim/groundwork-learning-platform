---
topic: topic.the-layers
section: core-concepts
title: What each layer actually does
order: 2
mode: explain
---

## Bare metal

A kernel on hardware, nothing between them. Full performance, full hardware
access, and the machine is one failure domain with no isolation between whatever
runs on it.

It has not disappeared — databases with strict latency requirements, GPU
training, high-frequency trading, and anything needing a device the hypervisor
will not pass through. What it lacks is the thing everything above it exists to
provide: **you cannot safely put two untrusting workloads on it**, and you cannot
create another one in less than a purchase order.

## The hypervisor and the virtual machine

A hypervisor presents *virtual hardware*: a virtual CPU, virtual disks, virtual
network cards. A guest OS boots on that hardware exactly as it would on real
hardware, and mostly cannot tell the difference.

**Type 1** runs directly on the metal — ESXi, Hyper-V, KVM, Xen. This is what
every cloud provider runs. **Type 2** runs as an application inside a host OS —
VirtualBox, and Docker Desktop, which is why the lab container in this topic
turns out to be inside a VM.

The guest *can* tell, if it looks. The CPU exposes a **hypervisor flag**, and
the virtual firmware identifies itself:

```text
$ grep -o hypervisor /proc/cpuinfo | head -1
hypervisor

$ cat /sys/class/dmi/id/sys_vendor
Amazon EC2
```

Modern virtualisation is hardware-assisted — Intel VT-x, AMD-V — so the guest's
instructions mostly execute directly on the CPU rather than being interpreted.
The overhead is a few percent, not the order of magnitude people sometimes
assume. What you actually pay for is **memory**: every guest carries its own
kernel and its own page cache, so a few hundred megabytes each before your
application has allocated anything.

What you get for that is the strongest boundary short of separate machines. The
guest kernel can be entirely compromised and the hypervisor is still between it
and everything else — which is why cloud providers put different customers on
one physical machine and are comfortable doing so.

## The container

A container is **a process on the host kernel** with two kernel features applied:

- **Namespaces** decide what it can *see* — its own process tree, network
  interfaces, mount table, hostname.
- **cgroups** decide what it can *use* — CPU quota, memory limit, I/O weight.

Both were covered in A02. What matters here is what they are *not*: there is no
guest kernel, no virtual hardware, and no hypervisor.

:::diagram{src=../diagrams/the-stack.mmd caption="Four layers, each leaving a fingerprint — and the two that decide what a container gets do not rewrite what it reads"}
:::

Three consequences follow directly, and they are the whole of the container
trade-off:

**It starts fast and costs nothing to hold.** No kernel to boot, no memory
duplicated. This is why density went up by an order of magnitude and why
containers displaced VMs for most workloads — it is a commercial argument as
much as a technical one.

**Its boundary is the kernel.** A kernel vulnerability is a container escape.
Namespaces, cgroups and seccomp are excellent and they are software running in
the same kernel as the thing being contained. This is why hostile multi-tenancy
— running code your customers wrote — is the one case where containers alone are
not the answer.

**It sees the host's numbers.** Namespaces virtualise process ids, network
interfaces and mounts. They do not virtualise `/proc/cpuinfo`. So the container
reads the machine's CPU count and the machine's memory, because that is what
those files describe, and nothing in the container's configuration changes them.

:::predict{question="A container is limited to 512 MiB. A JVM starts inside it with no explicit heap setting and reads MemTotal to size itself. What happens, and at what point?"}

It sizes its heap from the *machine's* memory — 15.5 GiB here — typically taking
a quarter of it, so roughly 4 GiB. That is eight times its limit.

Nothing fails immediately, which is the awkward part. The JVM only commits
memory as the heap grows, so the container runs fine under light load and gets
**OOM-killed** the first time real traffic makes it fill. The failure arrives
hours or weeks after the mistake, under load, with an exit code 137 and no
application-level error.

Modern JVMs are cgroup-aware and read the limit instead — but "modern" means
8u191 or later with the right flags, and there is a great deal of code in
production older than that, plus every runtime and library that never learned.

## The function

The unit of deployment stops being a machine and becomes a handler. The platform
starts it when a request arrives and stops it when idle, and you pay for
execution rather than for time.

The trade is the **cold start**: the first request after a scale-from-zero waits
for something to be created. Underneath, that something is usually a **microVM**
— Firecracker or similar — a stripped-down VM booting in around 125 ms, which
gives hypervisor-grade isolation with container-like startup. That combination is
exactly why it is what multi-tenant function platforms are built on.

So "serverless" is not a fifth kind of thing. It is a microVM, scheduled
aggressively, with the machine hidden from you.

## Comparing them honestly

| | Bare metal | VM | Container | Function |
|---|---|---|---|---|
| Isolation | none between tenants | hypervisor | kernel | usually hypervisor |
| Start | minutes | tens of seconds | ms to ~1 s | cold start, then none |
| Overhead | none | 256 MB - 1 GB each | none | platform-dependent |
| Density | 1 | tens | hundreds | thousands |
| Own kernel | yes | yes | **no** | yes (hidden) |
| Hostile tenants | no | yes | no | yes |

Two rows decide most real choices. **Own kernel** determines the isolation
strength, and **hostile tenants** is the row that eliminates options outright
rather than trading them off.

The rest is usually a preference until a constraint appears.

## Where the strong claim gets weaker

"Containers are less secure than VMs" is repeated a lot and needs qualifying, in
both directions.

It is true that the boundary is kernel-enforced and the kernel is a large piece
of software that has had escapes. It is also true that a well-configured
container — non-root, capabilities dropped, seccomp on, read-only root — is a
harder target than a badly-configured VM, and that most real compromises go
through the application rather than through either boundary.

The precise version, which is the one worth carrying: **for hostile
multi-tenancy, containers alone are not sufficient and a hypervisor boundary is**
— which is why gVisor, Kata Containers and Firecracker exist, and why every
function platform runs one. For your own code, containers are the right default
and the argument is about density and speed rather than about security.

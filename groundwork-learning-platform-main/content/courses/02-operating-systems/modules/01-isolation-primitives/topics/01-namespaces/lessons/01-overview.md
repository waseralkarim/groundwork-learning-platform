---
topic: topic.namespaces
section: overview
title: There is no such thing as a container
order: 1
mode: explain
---

Search the Linux kernel source for a container and you will not find one. There
is no container struct, no container syscall, no container subsystem.

What exists is a process — the same object you took apart in Foundations —
given its own view of a few global resources. Its own process numbering. Its own
mounts. Its own network interfaces. Nothing else changes: same kernel, same
scheduler, same memory manager, same everything you have already measured.

"Container" is the name of a particular combination of those views, plus a
filesystem to run in and some limits. Docker did not add a feature to Linux; it
made a convenient product out of features that were already there.

This topic is the first of those parts: **namespaces**.

## The specific things this explains

- Why a container sees itself as PID 1 while the host sees it as PID 8455
- Why `ps` inside a container shows four processes on a machine running four
  hundred
- Why a container has its own `eth0` that is not the host's `eth0`
- Why root inside a container is often still root outside — and why that is the
  single most important sentence in container security
- Why an unprivileged container cannot start another container
- What `hostPID: true` and `hostNetwork: true` actually give away
- How `docker exec` and `nsenter` get a shell into something with no shell

## Eight views, and they are independent

:::diagram{src=../diagrams/eight-namespaces.mmd caption="Containers get their own pid, mnt and net — and share the host's user namespace"}

| Namespace | What it virtualises |
|---|---|
| **pid** | Process IDs. The first process becomes PID 1 |
| **mnt** | The set of mounts, so the filesystem tree differs |
| **net** | Interfaces, addresses, routes, firewall rules |
| **user** | User and group ID mappings |
| **uts** | Hostname and domain name |
| **ipc** | System V IPC and POSIX message queues |
| **cgroup** | The view of the cgroup hierarchy |
| **time** | Boot and monotonic clock offsets |

They are independent. A process can have its own network namespace and share
everything else, or the reverse. "Container" is a conventional bundle, not a
kernel concept — which is exactly why `hostNetwork: true` is a coherent thing to
ask for.

## The one your containers are still sharing

Here is the finding this topic is built around. Two containers running at the
same time on one host:

:::terminal{title="Namespace inode numbers, two concurrent containers"}
$ container A: user=4026531837 pid=4026535616 mnt=4026535613 net=4026535618
$ container B: user=4026531837 pid=4026535794 mnt=4026535791 net=4026535796
:::

Different pid. Different mnt. Different net. **The same user namespace** — and
that number, `4026531837`, is the kernel's initial user namespace, created at
boot. Neither container has one of its own; both are still in the host's.

The consequence is the sentence worth memorising: **uid 0 in a container is uid
0 on the host.** A process that escapes its mount namespace, or reaches a device
node, or exploits a kernel bug, is doing so as real root.

That is why capability dropping, seccomp and read-only filesystems are not
belt-and-braces extras. With a shared user namespace they are the confinement,
and this topic is where that becomes concrete rather than received wisdom.

:::predict{question="A container runs as uid 0 and drops all capabilities. Is it root on the host?"}
It is uid 0 on the host, and that is not the same question as whether it can do
anything with it.

The user namespace is shared, so the kernel genuinely sees uid 0 — there is no
translation. What has been taken away is the *authority*: with an empty
capability set, uid 0 can do nothing privileged, which you measured directly in
Foundations.

So the honest statement is: it is root, disarmed. If something restores a
capability — a `--privileged` flag, a setuid binary the bounding set still
allows, a kernel bug that bypasses the check — it is root with that power, on
the host, immediately.

A **user namespace** changes this at the root: uid 0 inside maps to an ordinary
unprivileged uid outside, so even a full escape lands as nobody in particular.
That is what rootless containers do, and it is why they are a genuinely
different security posture rather than a hardening tweak.
:::

## What you already have

:::callback
From **User Space and the Kernel**: capabilities are what the kernel checks, not
your uid, and `CAP_SYS_ADMIN` covers mounting and much else. That capability is
also what creating most namespaces requires — which is why your lab container
cannot create one, and why you will watch it be refused rather than be told
about it.
:::

From **Files and Filesystems**, you read your own overlay mount and saw the
image layers it was assembled from. That mount table belongs to your **mount
namespace**, and the host's is different.

## How to work through it

Concepts, mechanism, tools, production. Four labs: read your own namespaces and
work out which are yours; explore what the PID and network namespaces hide;
try to create a namespace and be refused, which is the lesson; and finally
diagnose which isolation a workload is missing from evidence alone.

Nothing here requires you to take anything on trust. Every claim in this topic
is a file you can read.

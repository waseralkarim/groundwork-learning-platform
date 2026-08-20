---
topic: topic.namespaces
section: internals
title: Assembling a container by hand
order: 3
mode: explain
---

:::objective{id=OBJ-A02.1.6}
Justify why sharing the host's user namespace makes capability dropping
load-bearing rather than optional.
:::

Once namespaces are separate views, "starting a container" stops being magic and
becomes a list. Here is what a runtime does, in order, with the kernel calls
named.

## What `docker run` actually performs

1. **`clone()` with namespace flags** — `CLONE_NEWPID | CLONE_NEWNS |
   CLONE_NEWNET | CLONE_NEWIPC | CLONE_NEWUTS`. Not `CLONE_NEWUSER`, by default.
   The child is now PID 1 in a new PID namespace.
2. **Set up the root filesystem** — mount the overlay you read in Foundations,
   then `pivot_root` into it so the host tree is unreachable rather than merely
   unmounted.
3. **Mount the kernel filesystems** — a fresh `/proc` reflecting the new PID
   namespace, `/sys`, and the tmpfs mounts the spec asks for.
4. **Create the network** — a veth pair, one end in the container namespace, the
   other on a bridge on the host.
5. **Apply cgroup limits** — write to `memory.max`, `cpu.max`, `pids.max`.
6. **Drop capabilities**, apply the seccomp profile, set `no_new_privs`.
7. **`execve()` the entrypoint.**

Every step is a syscall an unprivileged process cannot make. That is why the
Docker daemon runs as root, and why holding its socket is equivalent to root on
the host — the point you met when the lab broker was given one.

## Order matters, and it is a security property

Notice that capabilities are dropped at step 6, *after* the namespaces and
mounts exist. A runtime cannot drop them earlier because it needs them to do the
setup.

That ordering is why `no_new_privs` matters so much: it is the flag that says no
later `execve` may regain what step 6 gave up. Without it, a setuid binary
inside the image could restore privilege that the container was deliberately
denied — inside a user namespace still shared with the host.

## The isolation you did not get

It is worth being precise about what remains shared, because this is where
container security actually lives:

| Shared with the host | Consequence |
|---|---|
| **The kernel** | One bug reachable through one syscall is a path out |
| **The user namespace** (by default) | Container uid 0 is host uid 0 |
| **The scheduler and memory manager** | Noisy neighbours are real; limits are the only remedy |
| **The clock, mostly** | A time namespace exists but is rarely used |

:::callback
From **User Space and the Kernel**: every container makes syscalls into the same
kernel as the host, which is the entire security argument for and against
containers. Namespaces change *what those calls see*. They do not add a second
kernel, and nothing in this topic changes that.
:::

## Why a container cannot start a container

Your lab container cannot run `unshare`, and the reason is worth stating exactly:
creating a namespace requires `CAP_SYS_ADMIN` **in the current user namespace**,
and the capability set is empty.

This is also why Docker-in-Docker traditionally required `--privileged`: nesting
means creating namespaces, which means holding the capability, which means giving
up most of the isolation to get it. Sysbox and rootless runtimes exist to break
that trade — by giving the inner container a user namespace, so it can hold
capabilities that mean nothing outside it.

:::objective{id=OBJ-A02.1.8}
Evaluate a proposal to share a namespace with the host, and state what it gives
up.
:::

## Opting out, one namespace at a time

Because namespaces are independent, each can be individually surrendered — and
each surrender is a specific, nameable loss:

| Option | What it shares | What you give up |
|---|---|---|
| `hostPID: true` | The host's PID namespace | Process isolation. The container can see and signal every process on the node |
| `hostNetwork: true` | The host's network namespace | Network isolation and port separation. It binds host ports directly |
| `hostIPC: true` | The host's IPC namespace | Shared memory isolation between the container and everything else |
| `shareProcessNamespace` | One PID namespace across a pod | Isolation between containers in that pod — deliberately, for debugging sidecars |

None of these is automatically wrong. `hostNetwork` is how a CNI plugin or a
node exporter does its job. What is wrong is choosing one without being able to
say which isolation it removes, which is exactly what this table is for.

## The one-sentence version

A container is seven syscalls and a filesystem, assembled in an order that ends
in dropping the privilege used to assemble it — and every "host" option in a pod
spec is a decision to skip one of the steps.

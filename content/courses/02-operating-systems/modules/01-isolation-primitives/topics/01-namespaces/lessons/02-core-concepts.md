---
topic: topic.namespaces
section: core-concepts
title: What each namespace hides
order: 2
mode: explain
---

:::objective{id=OBJ-A02.1.1}
Explain what a namespace virtualises, and why the kernel has no object called a
container.
:::

## A namespace is a view, not a boundary you can touch

Every process belongs to one namespace of each kind, and that membership is
visible as a symlink:

```bash
ls -l /proc/self/ns/
# pid -> pid:[4026535616]
# mnt -> mnt:[4026535613]
# net -> net:[4026535618]
```

The number is an inode. Two processes with the same inode for a kind are in the
same namespace and see the same thing; different inodes mean different views.
That is the entire mechanism for answering "are these isolated from each other",
and it is a comparison you can do by eye.

:::objective{id=OBJ-A02.1.3}
Explain what the PID namespace changes about what a process can see and signal.
:::

## PID: numbering, and therefore reachability

:::diagram{src=../diagrams/pid-namespace.mmd caption="One process, two numbers — and everything outside has no number at all"}

The first process in a new PID namespace becomes **PID 1** there. The host still
sees it under its own number; both are real, and neither is a translation of the
other in any sense the process can observe.

Two consequences, and the second is the one that matters:

**Processes outside are invisible.** `ps` in a container lists only its own
namespace. Nothing is being filtered — those processes have no number in this
namespace to be listed under.

**Processes outside cannot be signalled.** `kill` takes a PID, and a PID is
meaningless outside its namespace. This is not a permission check that a
capability could bypass; there is no way to name the target.

:::callback
From **Processes**: PID 1 is treated specially — it adopts orphans, and signals
with no installed handler are not applied to it by default. Your application
becomes PID 1 in a container, inherits both behaviours, and is usually written
for neither. That is the PID 1 problem, and this is where it comes from.
:::

## Mount: the filesystem tree is per-process

A mount namespace holds its own set of mounts. Two processes on one kernel can
disagree entirely about what is at `/`.

This is what makes a container's root filesystem possible: the overlay you read
in Foundations is mounted *in that namespace*, and the host's `/` is untouched.
It is also why a bind mount into a container is a mount performed in the
container's namespace, and why `docker exec` shows you the container's tree
rather than the host's.

## Network: its own everything

A network namespace has its own interfaces, addresses, routing table, firewall
rules and socket bindings.

```bash
ip addr        # inside: lo and eth0 only
ip route       # inside: a default route via the bridge
```

Two containers can both bind port 8080 without conflict, because they are
different ports in different namespaces. Publishing a port is not "opening" it —
it is a forwarding rule from the host's namespace into the container's, which is
why `-p 8080:80` has two numbers.

`hostNetwork: true` puts the process in the host's network namespace instead.
Then there is no forwarding, no separate `eth0`, and no second port 8080 —
because now it is the host's.

:::objective{id=OBJ-A02.1.5}
Explain why creating a namespace is a privileged operation, and what a user
namespace changes about that.
:::

## User: the one that decides what root means

The user namespace maps uids and gids between itself and its parent. A process
can be uid 0 inside while being uid 100000 outside.

:::diagram{src=../diagrams/who-may-create.mmd caption="One namespace an unprivileged process may create, and seven it may not"}

It is also the exception in a second way: **it is the only namespace an
unprivileged process may create.** Every other kind requires `CAP_SYS_ADMIN`,
which is why your lab container — capabilities dropped — cannot make one, and
why containers cannot nest without privilege.

The interaction between those two facts is the whole design:

1. An unprivileged user creates a user namespace, in which they hold all
   capabilities — over that namespace only.
2. Holding `CAP_SYS_ADMIN` *there*, they can now create the other namespaces.
3. So an unprivileged user can build a container, and its root maps to their own
   unprivileged uid outside.

That is a rootless container, and it is why user namespaces are the security
feature rather than a convenience.

One caveat you will meet the moment you try it. "Unprivileged users may create
one" is true of a Linux host and *not* true inside a container: Docker's default
seccomp profile blocks `CLONE_NEWUSER` outright, because unprivileged user
namespaces have been the entry point for a long series of kernel
privilege-escalation bugs. So the refusal you get in a container is a seccomp
refusal, not a capability one — same error, different mechanism, different fix.

:::warning
By default, Docker and Kubernetes do **not** give containers a user namespace.
Every container shares the host's, so container uid 0 is host uid 0.

This is a deliberate trade — user namespaces complicate volume ownership, some
filesystems and some workloads — but it is why capability dropping,
`no-new-privileges`, seccomp and read-only roots carry the weight they do. They
are not defence in depth on top of user-namespace isolation; with a shared user
namespace, they are the defence.
:::

## Joining rather than creating

`setns()` puts a process into an *existing* namespace, and it is how tooling
reaches inside a container:

```bash
nsenter -t <host-pid> -m -p -n /bin/sh
```

`docker exec` does the same thing: a new process, joined to the container's
namespaces, running from the container's filesystem. That is why exec'ing into a
distroless image gives you nothing useful — the namespaces are joinable; the
tools simply are not there.

The technique that follows is worth knowing: join the container's *network*
namespace from a debugging container that has the tools, and you can `tcpdump`
its traffic without adding anything to the image.

## The one-sentence version

A namespace is a per-process view of one global resource; there are eight, they
are independent, creating any but the user namespace needs `CAP_SYS_ADMIN`, and
your containers almost certainly still share the host's user namespace.

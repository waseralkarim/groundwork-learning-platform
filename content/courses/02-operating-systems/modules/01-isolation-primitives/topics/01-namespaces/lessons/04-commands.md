---
topic: topic.namespaces
section: commands
title: Reading and joining namespaces
order: 4
mode: do
---

:::objective{id=OBJ-A02.1.2}
Identify which namespaces a process belongs to, and which of them it shares with
another process.
:::

## Which namespaces am I in?

```bash
ls -l /proc/self/ns/
readlink /proc/self/ns/pid          # pid:[4026535616]
```

The inode number is the identity. Everything else in this lesson is a comparison
between two of these numbers.

:::try{lab=read-your-namespaces run="ls -l /proc/self/ns/" title="Your own eight"}
Note the numeric ranges. The namespaces created for this container cluster
together; any that sit far below them were not created for you, and you are in
someone else's — which for the user namespace is the point of the whole topic.
:::

## Are two processes isolated from each other?

```bash
readlink /proc/<pid-a>/ns/net
readlink /proc/<pid-b>/ns/net       # same number = same network
```

Same inode, same view. Different inode, different view. That single comparison
answers "is this actually isolated" for any dimension, and it needs no tooling
beyond `readlink`.

## lsns — everything at once

```bash
lsns                     # every namespace visible to you, with process counts
lsns -t net              # just network namespaces
lsns -p 1                # the namespaces of a specific process
```

```text
        NS TYPE   NPROCS PID USER    COMMAND
4026531837 user        3   1 learner bash
4026535613 mnt         3   1 learner bash
4026535616 pid         3   1 learner bash
```

`lsns` can only report what it can see. Inside a PID namespace it lists the
processes in that namespace, so its counts are a view from inside — not the
host's answer.

## Getting inside one

```bash
nsenter -t <host-pid> -m -p -n -- /bin/sh    # mount, pid and network
nsenter -t <host-pid> -n -- ip addr          # just the network namespace
docker exec -it <container> sh               # the same mechanism, packaged
```

The flags select which namespaces to join, and they are independent. That
independence is the useful part: joining only the **network** namespace, from a
container that has tools, lets you debug a distroless image's traffic without
adding anything to it.

```bash
# Run a debug container in the target's network namespace
docker run --rm -it --net=container:<name> nicolaka/netshoot tcpdump -i eth0
```

Nothing was installed in the target, nothing was restarted, and the capture is of
its real traffic.

## What the container sees, and what the host sees

```bash
# inside
ps -ef                 # only this namespace's processes
ip addr                # only this namespace's interfaces
cat /proc/mounts       # only this namespace's mounts
hostname               # the UTS namespace's name

# on the host, for the same container
docker inspect -f '{{.State.Pid}}' <container>    # its host PID
ps -o pid,ppid,cmd -p <host-pid>                  # the same process, host number
```

The pair of PIDs is the clearest demonstration in the topic: one process, two
numbers, both real.

:::try{lab=the-pid-namespace run="ps -ef" title="Every process you can see"}
Count them. This is a machine running hundreds of processes, and the PID
namespace means the rest have no number here to be listed under — they are not
hidden, they are unnameable.
:::

## Who may create one

```bash
unshare --user true                  # unprivileged on a host; blocked in a container
unshare --pid --fork true            # EPERM without CAP_SYS_ADMIN
unshare --mount true                 # EPERM without CAP_SYS_ADMIN
```

In a hardened container **all three fail**, with the same six words each time —
and they do not fail for the same reason. That is the part worth slowing down
for, because the two causes have different fixes:

| Attempt | Requires | What refuses it in a container |
|---|---|---|
| `unshare --user` | nothing | The **seccomp** profile, which blocks `CLONE_NEWUSER` outright |
| `unshare --pid` | `CAP_SYS_ADMIN` | The **empty capability set** |
| `unshare --mount` | `CAP_SYS_ADMIN` | The **empty capability set** |

Docker's default seccomp profile blocks user-namespace creation deliberately:
unprivileged user namespaces have been the route to a long line of kernel
privilege-escalation bugs, and almost no containerised workload needs one.

The practical consequence is that `--cap-add=SYS_ADMIN` will not make the first
line work. A seccomp filter is evaluated before the kernel reaches any
capability check, so it is refusing a call that never arrives at the check you
just relaxed. Two mechanisms, one error message — and the diagnosis is knowing
which operation needs a capability at all.

:::warning{scope=production}
If a container *can* run `unshare --mount`, it holds `CAP_SYS_ADMIN`. That is
worth treating as an alarm rather than a curiosity: with that capability the
container can mount filesystems, and mounting is most of the way to reading
anything on the host.
:::

## Checking a container's user namespace from outside

```bash
readlink /proc/<host-pid-of-container>/ns/user
readlink /proc/1/ns/user             # the host's own
cat /proc/<host-pid>/uid_map         # the mapping, if it has one
```

Two identical inodes mean the container shares the host's user namespace, and
container uid 0 is host uid 0. A `uid_map` reading `0 100000 65536` means the
opposite: its root is host uid 100000, and an escape lands as an unprivileged
user.

:::checkpoint
Without scrolling up:

1. How do you tell whether two processes share a network namespace?
2. Why can a container not signal a process on the host?
3. Which namespace can an unprivileged process create, and why does that matter?
4. How would you packet-capture a distroless container that has no tcpdump?
:::

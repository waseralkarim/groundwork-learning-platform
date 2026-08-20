---
topic: topic.namespaces
section: production
title: Namespaces in review, in incidents, and in policy
order: 5
mode: explain
---

:::objective{id=OBJ-A02.1.7}
Diagnose which isolation a workload is missing, given evidence from inside and
outside it.
:::

Three situations where this stops being background knowledge, in the order you
are likely to meet them.

## Reviewing a manifest

Every "host" option in a pod spec is a decision to skip one of the assembly
steps, and the review question is always the same: *which isolation does this
give up, and does the workload's job actually require it?*

```yaml
spec:
  hostPID: true          # sees and signals every process on the node
  hostNetwork: true      # binds node ports; sees node traffic
  hostIPC: true          # shares memory segments with everything on the node
  shareProcessNamespace: true    # merges the pod's containers into one PID namespace
```

Legitimate uses exist for all of them:

- `hostNetwork` for a CNI plugin, a node exporter, or anything that must see the
  node's real interfaces
- `hostPID` for a process-level monitoring agent that genuinely needs the node's
  process table
- `shareProcessNamespace` for an ephemeral debug container that needs to see the
  application's processes

What makes a review finding is not the flag. It is the flag with no reason
attached, or a reason that a narrower option would satisfy — and the commonest
of those by far is `hostNetwork: true` used to reach a service that a normal
`Service` or `hostPort` would have reached.

:::warning{scope=production}
`hostNetwork: true` also gives up NetworkPolicy. Policies select pods by their
pod IP, and a host-networked pod does not have one — it has the node's address.
Every ingress and egress rule you thought applied to it silently does not.
:::

## Debugging with namespaces instead of against them

The technique that pays for this topic on its own: a distroless container with
no shell can still be debugged, because namespaces are joinable.

```bash
# packet-capture a container that has no tcpdump, no shell, nothing
docker run --rm -it --net=container:api nicolaka/netshoot tcpdump -i eth0 -n

# the Kubernetes equivalent
kubectl debug -it pod/api --image=nicolaka/netshoot --target=api
```

`kubectl debug` with `--target` joins the target container's PID namespace as
well, so `ps` shows the application's processes and `/proc/1/...` is the
application's. Nothing was installed, nothing restarted, and the image stayed
minimal.

The mental model is worth stating plainly: **you are not getting into the
container. You are starting a new container in some of its namespaces.** Which
is also why `kubectl debug` cannot see the target's filesystem unless you ask
for the mount namespace too — the container's `/` belongs to a namespace you did
not join.

## Diagnosing what you inherited

When a workload behaves as though it can see too much, the comparison takes
under a minute:

```bash
for t in pid net mnt ipc uts; do
  printf '%-4s %s vs %s\n' "$t" \
    "$(readlink /proc/self/ns/$t)" "$(readlink /proc/1/ns/$t)"
done
```

Run it inside the workload and on the node. Any type where the two inodes match
is a dimension in which that workload is not isolated from the node.

Two matches are expected on almost every cluster and are not findings on their
own: the **user** namespace, because Kubernetes does not enable user namespaces
by default, and the **time** namespace, because almost nothing uses it. A shared
namespace is only interesting when it is not shared by everything.

:::predict{question="A pod's namespace inodes are all its own, and it still reads the node's filesystem. How?"}
Namespaces were never the only thing holding it back.

The likeliest answer is a `hostPath` volume: the node's directory is mounted
*into* the pod's own mount namespace, which is why the inodes differ and the
access happens anyway. Perfect mount isolation, deliberately punctured.

The more serious answer is `privileged: true`. That leaves every namespace in
place and hands back `CAP_SYS_ADMIN`, seccomp and `no_new_privs` — so the
container can mount the host's disk itself, inside its own mount namespace.
Since it also shares the host's user namespace, it does so as real root.

Both are the same lesson from different directions: namespaces without
capability confinement are not a security boundary. Check `CapEff`, `Seccomp`
and the volume list before concluding that matching inodes are the whole story.
:::

## Making it policy rather than vigilance

Catching these in review does not scale, and the cluster-level answer is
admission control. Kubernetes Pod Security Standards define three profiles, and
the middle one exists almost exactly for this topic:

| Profile | What it does about namespaces |
|---|---|
| `privileged` | Nothing. Anything goes |
| `baseline` | Forbids `hostPID`, `hostIPC`, `hostNetwork`, `privileged`, host ports |
| `restricted` | All of the above, plus non-root, dropped capabilities, seccomp required |

```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: applications
  labels:
    pod-security.kubernetes.io/enforce: baseline
    pod-security.kubernetes.io/warn: restricted
```

`enforce: baseline` refuses the manifest outright. `warn: restricted` tells the
author what they are still short of without blocking them — a combination worth
knowing, because it lets you tighten a cluster in two steps rather than one
argument.

:::callback
From **User Space and the Kernel**: `EPERM` means the kernel understood the
request and refused the authority; `EACCES` means a permission check on an
object failed. Namespaces add a third possibility that is neither — **ESRCH**,
no such process — and it is the strongest of the three, because there is no
capability that grants the ability to name something that has no name here.
:::

## The five things worth remembering

1. A container is a process with its own views, plus a filesystem and limits.
   There is no container object in the kernel.
2. Comparing two inodes under `/proc/*/ns/` answers "are these isolated" for any
   dimension, with no tooling.
3. Your containers almost certainly share the host's user namespace, so
   container root is host root, and capability dropping is the actual defence.
4. Every `host*` option gives up one specific, nameable isolation — and
   `hostNetwork` also gives up NetworkPolicy.
5. Namespaces are joinable, which makes them a debugging tool as often as a
   security one.

:::checkpoint
1. Which two namespaces will match the node's on almost any cluster, and why
   are they not findings?
2. Why does `hostNetwork: true` break NetworkPolicy?
3. A pod has all its own namespaces and can still read the node's disk. Name two
   ways.
4. What does `baseline` forbid that `privileged` allows?
:::

---
topic: topic.user-space-and-the-kernel
section: production
title: What the boundary explains
order: 5
mode: explain
---

Five things you will meet in production, each of which is this boundary wearing
different clothes.

## 1. "Containers share the host kernel"

The sentence appears in every container introduction and is usually left
unexplained. It means exactly this: a process in a container makes system calls
into the **same kernel** as a process on the host, and as every process in every
other container on that machine.

There is no second kernel. There is no translation layer. When your containerised
service calls `write()`, the same kernel code runs as when a host process calls
it. The container is not a small machine — it is a normal process whose view of
the other side has been restricted.

That single fact explains both halves of the container trade-off:

**Why containers are fast.** Nothing is emulated. A syscall from a container
costs what a syscall from any process costs. A VM has to trap into a hypervisor
and run a second kernel; a container does not, which is why it starts in
milliseconds and has no measurable syscall overhead.

**Why containers are a weaker boundary than VMs.** One kernel bug reachable
through one syscall is a path out. A VM escape means defeating the hypervisor,
which exposes a far smaller interface; a container escape means finding a flaw
anywhere in 350 system calls' worth of kernel code, all of which your container
can reach.

:::note
This is precisely why gVisor and Kata Containers exist. gVisor puts a
user-space kernel in front of the real one so containers' syscalls are handled
by a smaller, sandboxed implementation; Kata gives each container a real VM. Both
accept a performance cost to avoid sharing one kernel — which is only a sensible
trade if you understand what is being shared.
:::

## 2. Root in a container, and `Operation not permitted`

The support question that turns up forever:

> Our container runs as root. It still gets "Operation not permitted" when it
> tries to mount an NFS share. How can root not be allowed?

Because uid 0 is not the check. The check is the capability set, and mounting
needs `CAP_SYS_ADMIN`, which no container runtime grants by default.

The diagnosis is two commands:

```bash
docker exec <container> grep -E 'Uid|CapEff' /proc/1/status
capsh --decode=<the CapEff value>
```

If `CapEff` is Docker's default `00000000a80425fb`, the fourteen capabilities in
it do not include `cap_sys_admin`, and the refusal is correct behaviour rather
than a bug.

The fix hierarchy, best first:

1. **Do not need the privilege.** Mount on the host and bind-mount the result
   in. Most "the container needs to mount" requirements dissolve on contact
   with this question.
2. **Grant the one capability.** `--cap-add=NET_BIND_SERVICE` for a low port.
   Narrow, auditable, defensible in review.
3. **Grant `CAP_SYS_ADMIN`.** Understand that this is close to giving root on
   the host, and write down why you did it.
4. **`--privileged`.** All capabilities, no seccomp filter, device access. This
   is not a configuration; it is the removal of the isolation. If it "fixes" a
   problem, it has told you which capability you needed — go back to step 2.

:::warning{scope=production}
`--privileged` in a CI runner or a Kubernetes DaemonSet is a standing escape
hatch to the host. A process inside it can mount the host filesystem and write
to `/etc`. Whenever you see it in a manifest, the correct question is not "is
this safe" but "which single capability was actually needed".
:::

## 3. A service at 90% system time

The performance signature that misleads people most reliably.

:::terminal{title="A service that looks CPU-bound and is not"}
$ top -bn1 | head -3
%Cpu(s):  4.1 us, 89.7 sy,  0.0 ni,  5.9 id,  0.3 wa
$ time ./report-generator
real    0m41.2s
user    0m1.8s
sys     0m38.9s
:::

Nearly all CPU, nearly none of it in the program's own code. Adding CPU will not
help, a faster disk will not help, and optimising the program's algorithms will
not help — the program is barely running.

`strace -c -p <pid>` for three seconds names the culprit, and in practice it is
almost always one of these:

- **Unbuffered writes.** One `write()` per log line, per row, per record
- **A poll loop with no sleep.** Millions of `epoll_wait` or `read` calls
  returning nothing
- **Stat storms.** A file watcher or a language runtime checking thousands of
  paths per second
- **Tiny reads.** Reading a large file 1 byte or 128 bytes at a time

Every one of them is the same fix: fewer, larger crossings.

:::objective{id=OBJ-A01.3.8}
Troubleshoot a workload spending most of its CPU time in the kernel, and
identify the syscall pattern responsible.
:::

## 4. Logs that disappear exactly when you need them

A service crashes. The logs stop several seconds before the crash, and the
useful part is missing.

The bytes were in a libc buffer in the process's own memory when it died. They
had never crossed the boundary, so nothing outside the process ever had them —
not the file, not the log collector, not the kernel.

It works interactively because stdout to a terminal is line-buffered; it fails
in production because stdout to a file or a pipe is block-buffered at 4 KB.

```bash
stdbuf -oL -eL ./program        # force line buffering
PYTHONUNBUFFERED=1 python app.py
```

In application code, flush explicitly on the paths that matter — and note that
this is a real trade. Line-buffered logging on a hot path means one crossing per
line, which is item 3 above. Fast or complete: choose deliberately, per stream,
rather than by accident.

## 5. Hardening, in the language of this topic

Every container security control in C16 and E29 is one of three sentences:

| Control | What it restricts |
|---|---|
| `cap_drop: [ALL]` | What a call is permitted to do |
| `seccomp` profile | Which calls may be made at all |
| `readOnlyRootFilesystem` | Where writes may land — enforced by the mount |
| `runAsNonRoot` | Which uid the file permission checks see |
| `no-new-privileges` | Whether privilege can be gained by exec |

They are independent, and they fail differently. A dropped capability gives
`EPERM`. A read-only filesystem gives `EROFS`. A failed file permission check
gives `EACCES`. A blocked syscall gives `EPERM` or a killed process, depending
on the profile.

:::note
The lab environment you have been using applies all five, more strictly than a
normal container: every capability dropped, read-only root filesystem, non-root
uid, no-new-privileges, and no network. When lab 3 shows you `CapEff:
0000000000000000`, that is not a simplification for teaching — it is the actual
configuration running your shell.
:::

## The through-line

:::callback
This topic is the foundation the container track is built on. **C14** introduces
namespaces and cgroups as changes to what a process sees and may consume on the
other side of this boundary. **C16** is entirely about restricting crossings.
**E29** expresses the same controls as Kubernetes YAML. None of them introduce a
new mechanism — they configure this one.
:::

The reason this topic sits in Foundations rather than in the container track is
that people who meet capabilities for the first time as a Kubernetes
`securityContext` field learn to copy a working YAML block. People who meet them
here can read a refusal, name the missing capability, and grant exactly that one.

:::checkpoint
Explain to someone who has not read this topic:

1. Why a container starts in 50 ms and a VM takes 30 seconds
2. Why a container escape and a VM escape are not the same class of problem
3. Why a program can run as root and still be told "Operation not permitted"
4. What a service at 90% system time is actually doing
5. Why `--privileged` makes problems go away, and why that is a diagnosis rather
   than a solution
:::

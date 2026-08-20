---
topic: topic.user-space-and-the-kernel
section: overview
title: The line your code cannot cross
order: 1
mode: explain
---

Write a program that reads a file. Compile it, run it, watch it work. Now
answer a question that sounds trivial and is not: which of your instructions
read the disk?

None of them. Your code never touched the disk, never spoke to the controller,
never saw a sector. It asked. Something else did the reading and handed back
bytes.

That "asked" is the subject of this topic. There is a hard line between the code
you write and the code that owns the hardware, the CPU itself enforces it, and
crossing it is a specific mechanism with a specific cost and a specific set of
rules about who may cross for what.

Almost everything later in this curriculum that sounds like a separate subject
is a variation on this one line.

## The specific things this explains

By the end you should be able to say precisely why each of these happens:

- A container "shares the host kernel" — and why that sentence is the entire
  security argument for and against containers
- A process running as **root** inside a container gets `Operation not permitted`
- A program writes a log file and spends 90% of its CPU in the kernel
- Reading a file one byte at a time is a hundred times slower than reading it in
  blocks, with identical total bytes
- `strace` can show you everything a program does, no matter what language it
  was written in and without its source
- A Kubernetes `securityContext` with `capabilities: drop: [ALL]` breaks a
  service that needs to bind port 80
- `--privileged` "fixes" a container problem, and why that is not a fix

## The shape of the answer

:::diagram{src=../diagrams/privilege-boundary.mmd caption="Everything you run is on the top half"}

Everything on the top is *user space*. Your shell, your database, your service,
every process in every container on the machine. Code up there cannot touch
hardware. It cannot read another process's memory. It cannot even decide to stop
running and let something else run.

The bottom is *kernel space*: one kernel per machine, with complete access to
everything. Not a privileged program — a different privilege level of the
processor itself.

The arrows are the only way across, and they all have the same name. A **system
call** is a program asking the kernel to do something on its behalf, and it is
the only thing a program can do that has any effect outside its own memory.

That is the whole model. Roughly 350 system calls exist on Linux, and every file
you have opened, every packet you have sent, every process you have started went
through one of them.

## Why this is not trivia

:::predict{question="A process inside a container runs as root — uid 0. It calls mount(). What happens, and why?"}
It fails with `EPERM`, in a normal container.

Being uid 0 is not the same as being allowed. Since Linux 2.2, the powers that
used to come as one indivisible "root" have been split into around forty
**capabilities**, and mounting requires `CAP_SYS_ADMIN`. Container runtimes drop
that capability by default, so the kernel refuses the call from a process that
is, by every other measure, root.

This one distinction — *who you are* versus *what you are permitted to ask* — is
most of container security, and it lives entirely at this boundary.
:::

Once the boundary is real to you, a large amount of infrastructure stops looking
like separate technologies:

**Containers** are processes whose view of the other side has been altered.
Namespaces change what the kernel shows them; cgroups change how much they may
consume. Both are enforcements applied at this boundary — which is why a
container is not a small virtual machine, and why "shares the kernel" is the
only sentence you need to explain both its speed and its risk.

**Container hardening** is entirely about restricting crossings. Dropping
capabilities restricts what a call may do. A seccomp profile restricts which
calls may be made at all. `--privileged` removes both restrictions, which is why
it works and why it is not a fix.

**Performance work** frequently reduces to counting crossings. Every buffered
writer in every language exists to make fewer of them. When you see a process at
90% system time, it is not computing — it is asking, over and over.

## What you already have

:::callback
From **Processes**: a process is the unit the kernel tracks, `fork` and `exec`
create one, and signals are the kernel interrupting it. Every one of those is a
system call — you have been looking at this boundary from the other side for a
whole topic.
:::

From **The Machine**, you compiled a three-line C program and counted about
thirty system calls under `strace` for one line of logic. This topic explains
what those thirty were, what each cost, and why `printf` needed the kernel at
all.

## How to work through it

The core concepts come next, then the mechanics of a single crossing, then the
tools, then what all of it means in production.

Four labs. The first two are measurement: watch the crossings, then measure what
they cost — with numbers from the machine in front of you rather than numbers
from this page. The third is about permission to cross. The fourth gives you
three refused operations that all look identical and asks you to say which check
rejected each.

That last skill — reading a refusal correctly — is worth more on a bad day than
anything else in this topic.

---
topic: topic.user-space-and-the-kernel
section: core-concepts
title: Two privilege levels and one way across
order: 2
mode: explain
---

:::objective{id=OBJ-A01.3.1}
Describe the two privilege levels a CPU runs code in, and identify which of the
kernel, a shell and a web server runs in each.
:::

## The CPU has modes, not just instructions

The enforcement here is hardware. An x86-64 processor is always executing in one
of four privilege levels, called **rings**, numbered 0 to 3. Linux uses two of
them: ring 0 for the kernel, ring 3 for everything else. (Other architectures
use different names — arm64 calls them exception levels — and the same two-level
arrangement.)

Some instructions only work in ring 0. Writing to a device register, changing
the page tables that define which memory a process can see, disabling
interrupts, halting the processor. Attempt one in ring 3 and the CPU does not
execute it and report an error to your program. It **traps**: it stops your
process, switches to ring 0, and hands control to the kernel, which usually
responds by killing you with `SIGSEGV` or `SIGILL`.

This matters more than it first appears. The restriction is not a policy the
kernel implements and could get wrong. The kernel does not check whether your
program is allowed to write to the disk controller, any more than a locked door
checks whether you would like to walk through it. The instruction cannot execute
in the mode your process is running in.

:::note
This is why a segfault kills one process and a kernel panic takes the machine.
Faulty user-space code is contained by the hardware; faulty kernel code is
running in the mode where everything is permitted.
:::

## So how does anything get done?

Programs need the hardware constantly. Reading files, sending packets,
allocating memory, starting processes — none of it is possible in ring 3.

The answer is a controlled crossing: the process asks, the kernel decides, the
kernel acts. That request is a **system call**, and the point of it is that the
transition is not arbitrary. A process cannot jump to any address it likes in
kernel code. The `syscall` instruction transfers control to one fixed entry
point the kernel registered at boot, and the kernel dispatches from there based
on a number the process put in a register.

The vocabulary is small and fixed. About 350 calls, and you can list them:

```text
read  write  open  close  stat  mmap  brk  ioctl  clone  execve
fork  wait4  kill  socket  connect  accept  bind  listen  mount  ...
```

Everything a program can do to the world outside its own memory is somewhere in
that list. That is a remarkable fact about Linux and it is what makes `strace`
so powerful: there is a complete, enumerable list of ways a program can affect
anything, and you can watch all of them.

:::objective{id=OBJ-A01.3.2}
Explain why a program cannot read a disk or send a packet directly, and what it
must do instead.
:::

## The kernel is a service, not a library

The most useful mental correction at this stage: stop thinking of the kernel as
"the low-level part of my program's stack" and start thinking of it as a service
you make requests to.

A library call — `strlen`, `qsort`, `json_parse` — is your code. It runs in your
process, at your privilege level, with your memory, and costs a function call.

A system call is a request to a different, more privileged program that manages
a resource shared by every process on the machine. It costs a mode switch, it
can fail for reasons that have nothing to do with your program, and it can
block — your process stops running until the kernel is ready.

The confusion arises because they look identical in source:

```c
size_t n = strlen(name);        /* library call — your code, nanoseconds */
ssize_t w = write(1, buf, n);   /* system call — a request, microseconds */
```

Nothing in the syntax tells you one of these leaves your process entirely. You
have to know. And most of the time you do not need to — until you are looking at
a profile wondering why a function that "just writes a string" is the slowest
thing in your service.

## What crosses, exactly

Only numbers and addresses. Registers carry the syscall number and up to six
arguments; anything larger is passed as a pointer into your memory, and the
kernel explicitly copies data across the boundary rather than dereferencing your
pointer casually. `copy_from_user` and `copy_to_user` exist precisely because
trusting a user-space pointer is how kernels get exploited.

Coming back you get a single integer. Non-negative means success and usually
carries meaning — bytes written, a file descriptor, a PID. Negative means an
error number, which the C library turns into `-1` plus `errno`.

:::warning
`write()` returning a number smaller than what you asked for is a success, not
an error. A **short write** means the kernel accepted some of your bytes and you
must call it again with the rest. Code that ignores the return value works fine
against a fast local disk for years and then loses data against a slow network
filesystem or a saturated pipe.
:::

## Who is allowed to ask

Every process may make any system call. Whether the kernel *honours* it is a
separate question with several independent answers, and confusing them is the
single most common source of wasted debugging time in containers.

Four checks, applied in roughly this order:

1. **Is the call permitted at all?** A seccomp filter can reject a system call
   before the kernel looks at what it wants. The process gets `EPERM`, or the
   kernel kills it outright, depending on the profile.
2. **Does the file permission check pass?** Mode bits, ownership, ACLs — the
   `rwx` model. Failure is `EACCES`.
3. **Is the filesystem writable?** A read-only mount refuses writes from
   everyone, root included. Failure is `EROFS`.
4. **Does the process hold the required capability?** Mounting, binding a port
   below 1024, changing the system clock, loading a kernel module. Failure is
   `EPERM`.

:::diagram{src=../diagrams/why-refused.mmd caption="Four different refusals, four different fixes"}

The errno is not decoration. `EACCES` and `EPERM` print almost identically —
"Permission denied" and "Operation not permitted" — and they mean genuinely
different things with genuinely different fixes. Fixing the wrong one is how an
afternoon disappears.

:::objective{id=OBJ-A01.3.6}
Explain what a capability is, and why "running as root" and "being allowed to do
a privileged thing" are two different questions.
:::

## Root is not one thing

Historically uid 0 meant all-powerful, and every privilege check was `if (uid ==
0)`. That is a terrible unit of authority: a program that needs to bind port 80
and nothing else had to be given the power to also reformat the disk.

Linux splits it. Around forty **capabilities**, each one slice of what root used
to mean:

| Capability | What it permits |
|---|---|
| `CAP_NET_BIND_SERVICE` | Bind a port below 1024 |
| `CAP_SYS_ADMIN` | Mount filesystems, and a great deal else |
| `CAP_NET_RAW` | Raw sockets — this is what `ping` needs |
| `CAP_SYS_TIME` | Change the system clock |
| `CAP_CHOWN` | Change file ownership |
| `CAP_SYS_MODULE` | Load kernel modules |
| `CAP_SYSLOG` | Read the kernel log ring buffer |

A process has a set of these, and the set is what the kernel actually consults.
uid 0 with an empty capability set can do nothing privileged. A non-root process
holding `CAP_NET_BIND_SERVICE` can bind port 80 and nothing else.

This is why the answer to "it works as root locally but not in the container" is
almost never "run it as root" — it already is. The capability is missing.

:::note
`CAP_SYS_ADMIN` is the exception that proves the design. It accumulated so many
unrelated powers that granting it is close to granting root outright. When a
tutorial suggests `--cap-add=SYS_ADMIN`, treat it the way you would treat
`--privileged`: as a request to disable the isolation, not to configure it.
:::

## The one-sentence version

Your code computes; the kernel acts; the CPU enforces the difference; system
calls are the only crossing; and what you may ask for depends on your
capabilities, not your user ID.

Everything else in this topic is detail on those five clauses.

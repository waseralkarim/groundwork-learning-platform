---
topic: topic.processes
section: internals
title: States, signals and dying
order: 3
mode: explain
---

:::objective{id=OBJ-A01.2.4}

## Process states

`ps` shows a one-letter state for every process. Five matter.

:::diagram{src=../diagrams/process-states.mmd caption="A process spends almost all its life in S"}

| | State | What it means |
|---|---|---|
| **R** | Running / runnable | Executing, or ready to and waiting for a core |
| **S** | Interruptible sleep | Waiting for something, and can be woken by a signal |
| **D** | **Uninterruptible sleep** | Waiting for something the kernel will not interrupt |
| **Z** | Zombie | Exited; waiting for its parent to collect the exit code |
| **T** | Stopped | Suspended, by `SIGSTOP` or a debugger |

Most processes on a healthy machine are in **S** almost all the time — a web
server waiting for a request is asleep, not running. A machine showing hundreds
of processes is not necessarily doing hundreds of things.

Two of these states cause production incidents, and they are the two everyone
gets wrong.

### D — the state you cannot kill

A process in **uninterruptible sleep** is waiting on something the kernel has
decided must not be interrupted — nearly always I/O. Not "should not". *Cannot*.
Signals are not delivered to it, including `SIGKILL`.

```text
$ ps -eo pid,stat,comm | grep ' D'
   4821 D    rsync

$ sudo kill -9 4821
$ ps -eo pid,stat,comm -p 4821
   4821 D    rsync          # still there
```

This is the correct answer to "I killed it with -9 and nothing happened". The
process is not ignoring you — the kernel is not delivering the signal, because
the process is mid-way through an operation that cannot be safely abandoned.

The signal is queued. The moment the I/O completes, it is delivered and the
process dies. If the I/O never completes — a hung NFS mount, a failed disk — the
process stays in D until the machine is rebooted.

:::warning{scope=production}
A handful of processes in D is normal. A *growing* number of them is a storage
problem announcing itself, and no amount of killing will help. Look at the
storage, not the processes.
:::

### Z — the process that is already dead

A **zombie** is a process that has exited but whose parent has not yet collected
its exit status. It holds no memory, has no open files, and runs no code. What
it holds is one entry in the process table and one integer.

You cannot kill a zombie. It is already dead; that is what "zombie" means.
`kill -9` on one does nothing, because there is nothing left to signal.

The fix is always the same, and it is never the zombie: **signal the parent.**
Either it starts reaping, or it exits — at which point the zombie is reparented
to PID 1, which reaps it immediately.

:::aside
A few zombies flickering in and out are normal — every process is briefly a
zombie between exiting and being reaped. Zombies that *accumulate* mean a parent
that forks and never calls `wait()`. Since each one holds a PID, enough of them
exhaust the PID space and the machine can no longer start anything at all —
while showing plenty of free memory and idle CPU.
:::

## Signals

:::objective{id=OBJ-A01.2.5}

A signal is a notification the kernel delivers to a process. Roughly thirty
exist; six account for nearly everything you will meet.

| Signal | № | Default | Catchable | Sent when |
|---|---|---|---|---|
| `SIGTERM` | 15 | Terminate | **Yes** | Asking politely to stop |
| `SIGKILL` | 9 | Terminate | **No** | Ending it, now |
| `SIGINT` | 2 | Terminate | **Yes** | You press Ctrl-C |
| `SIGHUP` | 1 | Terminate | **Yes** | Terminal closed; by convention, "reload config" |
| `SIGSTOP` | 19 | Suspend | **No** | Freezing a process |
| `SIGCHLD` | 17 | Ignore | Yes | A child died — this is the reaping cue |

The column that matters is **catchable**. A catchable signal is a *request*: the
program installs a handler and decides what to do. `SIGKILL` and `SIGSTOP` are
the two that cannot be caught, blocked or ignored, and that is deliberate — the
operating system needs a way to stop a process that has stopped cooperating.

### Graceful shutdown is a signal handler

"Graceful shutdown" sounds like a feature. It is one specific thing:

```text
1. Something sends SIGTERM
2. The process's handler runs:
     stop accepting new work
     finish what is in flight
     flush buffers, close connections
     exit
3. If it has not exited within a grace period, SIGKILL arrives
```

Step 3 is not optional and not a punishment — it is the guarantee that shutdown
terminates. A program that ignores `SIGTERM` does not get to stay alive; it gets
to skip its cleanup.

:::callback
This is exactly `docker stop`: SIGTERM, wait ten seconds, SIGKILL. And exactly
Kubernetes: SIGTERM, wait `terminationGracePeriodSeconds` (30 by default),
SIGKILL. Neither invented anything — both are driving this mechanism (**C14**,
**E26**).
:::

## Why PID 1 is different

:::objective{id=OBJ-A01.2.7}

PID 1 has two properties no other process has, and both are set by the kernel.

**It adopts orphans.** Any process whose parent dies is reparented to PID 1,
which is expected to reap it. On a real machine, PID 1 is `systemd` or `init`,
and reaping is a large part of its job.

**Default signal actions do not apply to it.** For any other process, a signal
with no installed handler does the default thing — usually terminate. For PID 1,
the kernel *skips* the default action. A signal with no handler is discarded.

Read that again, because it is the source of a bug you will absolutely meet:

> **If PID 1 does not explicitly handle `SIGTERM`, `SIGTERM` does nothing.**

This exists so a stray signal cannot accidentally kill init and panic the
kernel. It is entirely sensible on a real machine, where PID 1 is a program
written to be PID 1.

In a container, PID 1 is *your program* — because a PID namespace renumbers the
first process to 1. And your program was almost certainly not written to be init.

So:

```text
$ docker stop myapp
   ... ten seconds pass ...
$ echo $?
0
```

Ten seconds, every time. Docker sent `SIGTERM`; your app is PID 1 and installed
no handler; the kernel discarded it; Docker waited out the grace period and sent
`SIGKILL`. Your shutdown code never ran, your connections were cut mid-flight,
and nothing reported an error.

You will fix this three ways in the container track: install a signal handler,
use `exec` in your entrypoint so your program *is* PID 1 rather than a child of
`sh`, or run a tiny init that forwards signals and reaps orphans. **C14** covers
all three. You now know why each of them works.

:::checkpoint
1. Why does `kill -9` sometimes appear to do nothing?
2. Why can you not kill a zombie, and what do you do instead?
3. Your container takes exactly ten seconds to stop. What happened, in order?
:::

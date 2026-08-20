---
topic: topic.processes
section: core-concepts
title: Where processes come from
order: 2
mode: explain
---

:::objective{id=OBJ-A01.2.1}

## What the kernel remembers

A process is not just running code. It is an entry in a kernel table, and that
entry holds everything the system knows about it:

| The kernel tracks | Which is why |
|---|---|
| **PID** | Anything can be addressed — signalled, inspected, killed |
| **PPID** — its parent | The process tree exists, and orphans can be adopted |
| **State** | The scheduler knows whether it can run |
| **UID / GID** | Permissions apply to it |
| **Open file descriptors** | It can read and write things |
| **Current directory** | Relative paths mean something |
| **Memory maps** | It has an address space of its own |
| **Exit code** — once dead | Its parent can find out how it went |

That last row is the surprising one. A process that has exited still has an
entry in the table, holding one number, until somebody comes to collect it. That
detail is the whole of zombies, later in this topic.

:::terminal{title="Everything above, for one process"}
$ ps -p 1 -o pid,ppid,user,state,comm
    PID    PPID USER     S COMMAND
      1       0 root     S systemd
:::

## Two calls, not one

Here is the thing that surprises everyone: **Linux has no "run this program"
system call.** Starting a program takes two, and they do quite different jobs.

:::diagram{src=../diagrams/fork-exec.mmd caption="fork duplicates; exec replaces"}

**`fork()`** creates a new process by *duplicating the calling one*. The child
gets a copy of the parent's memory, its open files, its environment, its working
directory — everything. The only differences are its PID, its PPID, and what the
call returns: the parent gets the child's PID, the child gets `0`. That return
value is how each half knows which one it is.

**`execve()`** replaces the program running inside the current process with a
different one. Same PID, same PPID, same open file descriptors — new code.

So a shell running `ls` does this:

1. `fork()` — now there are two shells
2. In the child: `execve("/usr/bin/ls", ...)` — the child stops being a shell
   and becomes `ls`, keeping its PID
3. In the parent: `wait()` — the shell waits for the child to finish

:::aside
**Why two calls, rather than one `spawn()`?**

Because everything a program needs set up *before* it starts — redirected
output, a changed directory, dropped privileges, a closed file descriptor —
happens in the gap between fork and exec, in the child, using ordinary code.

That gap is why `ls > out.txt` works without `ls` knowing anything about files.
The shell forks, and *in the child, before exec*, it points file descriptor 1 at
`out.txt`. Then it execs `ls`, which writes to descriptor 1 as it always does.

A single `spawn()` call would need a parameter for every one of those setups.
The two-call design needs none — you just write normal code in the gap. It is a
genuinely elegant piece of design and it is nearly fifty years old.
:::

:::warning{scope=production}
`fork()` does not really copy the parent's memory — that would make forking a
4GB process cost 4GB. Pages are shared and marked copy-on-write, so they are
only duplicated when one side writes. This is why forking is cheap, and why a
large process forking under memory pressure can still fail: the kernel may need
to honour those writes later.
:::

## The process tree

:::objective{id=OBJ-A01.2.3}

Every process has a parent, so processes form a tree. At the root is **PID 1**,
started by the kernel at boot; everything else descends from it.

:::terminal{title="The tree, as it actually is"}
$ ps -ef --forest | head -12
UID    PID  PPID  C STIME TTY      TIME CMD
root     1     0  0 09:00 ?    00:00:01 /sbin/init
root   412     1  0 09:00 ?    00:00:00  \_ /usr/sbin/sshd -D
root  8821   412  0 11:30 ?    00:00:00      \_ sshd: alice [priv]
alice 8834  8821  0 11:30 ?    00:00:00          \_ sshd: alice@pts/0
alice 8835  8834  0 11:30 pts/0 00:00:00              \_ -bash
alice 9012  8835  0 11:42 pts/0 00:00:00                  \_ ps -ef --forest
:::

Read that bottom-up and you have the story of how your command came to exist:
init started sshd, sshd forked for your connection, that forked your shell, your
shell forked to run `ps`.

### Orphans

What happens to a child whose parent exits first?

It becomes an **orphan** — and the kernel immediately reparents it to PID 1. Not
after a delay, not on request; it is part of process teardown. A process is
never actually without a parent.

This matters more than it sounds. It is why a background job survives you
logging out, why a daemon that "detaches" works by forking and letting the
parent exit, and — as you will see — why a container with the wrong PID 1
accumulates processes nobody is collecting.

:::checkpoint
Before continuing, make sure you can answer these:

1. What are the only differences between a parent and the child it just forked?
2. What is the PID of a process after `exec` replaces its program?
3. A process's parent exits. What is its PPID one second later?
:::

---
topic: topic.processes
section: overview
title: The unit of everything
order: 1
mode: explain
---

The previous topic ended with a claim it did not earn: *a container is just a
process*. This topic earns it.

A process is the unit the operating system actually manages. Not a program, not
a service, not an application — a process. When you run a command, start a
server, or deploy a container, what exists afterwards is one or more processes,
and everything the system does to them is drawn from a small, fixed vocabulary:
create, signal, wait, kill.

Learn that vocabulary and a large amount of production behaviour stops being
mysterious.

## The specific things this explains

By the end of this topic you should be able to say exactly why each of these
happens, without looking anything up:

- `docker stop` on your container takes ten seconds and then kills it anyway
- A process shows in `ps` as `<defunct>` and `kill -9` does nothing to it
- A machine runs out of process slots while barely using any memory or CPU
- A process is stuck in state `D` and even `kill -9` will not remove it
- Your application's shutdown handler never runs in production but works locally
- A Kubernetes pod takes exactly 30 seconds to terminate, every time

Every one of those is the same handful of mechanisms seen from a different
angle. None of them is a Docker or Kubernetes concept — they are all here, in
how Linux creates and destroys processes, and those tools inherited them.

## What you already have

:::callback
From **The Machine**: a program is a file on disk, a process is a running
instance of one; `execve` is the system call that starts it; memory a process
occupies is RSS; `SIGKILL` cannot be caught, which is why an OOM kill is not
survivable.
:::

That gives you what a process *is*. This topic is about where processes come
from, what the kernel remembers about them, and the three quite different ways
they can end.

## Prerequisites

**[The Machine](/topics/the-machine)** — required. If you cannot yet say what the
difference is between a program and a process, start there; the rest of this
will not land.

:::note
Every command in this topic works on any Linux machine, including inside the
labs. Nothing here needs root, and nothing here is distribution-specific.
:::

---
topic: topic.threads-and-concurrency
section: overview
title: Adding workers made it slower
order: 1
mode: explain
---

A service is slow. It has four worker threads. Someone raises it to sixteen,
deploys, and it gets slower — not a little slower, measurably worse, with p99
latency doubling and CPU usage on the dashboard *falling*.

Everything about that is explicable, and none of it is mysterious once you know
what a CPU limit does. The service was never using the CPU it appeared to have,
and the extra workers spent a fixed budget faster.

This topic is about threads: what they share, what they cost, and why the limit
on them is the one number people misread most often.

## The specific things this explains

- Adding workers makes a service slower rather than faster
- Container CPU usage sits at 40% while every request is slow
- A Go or Java service starts hundreds of threads on a container limited to half
  a CPU
- `nproc` reports 64 inside a container that may use one core
- A pod is not autoscaled because its "CPU utilisation" looks fine, while it is
  being stopped thousands of times a minute
- Two threads increment a counter a million times each and it ends at 1.2
  million
- A service hangs with zero CPU usage and no errors

## What a thread actually is

:::diagram{src=../diagrams/process-vs-thread.mmd caption="Threads share everything except a stack and a place in the queue"}

The kernel schedules **threads**, not processes. A process is a container for
resources — an address space, a table of open files, a working directory — and a
thread is a flow of execution using them.

Threads of one process share:

- The **address space**: every global, every heap allocation, every mapping
- **Open file descriptors**, the working directory, the user and group

Each thread keeps its own:

- **Stack** — its local variables and call chain
- **Registers**, including the instruction pointer
- **TID**, its scheduling identity

That list explains both why threads are attractive and why they are dangerous.
Sharing memory is why passing work between them costs nothing; sharing memory is
also why two threads can corrupt the same counter.

:::callback
From **Virtual Memory**: a process's address space is a per-process mapping the
MMU walks on every access. Threads of one process share *one* of those mappings,
which is exactly why they can see each other's data and processes cannot.
:::

## Concurrency is not parallelism

Two words used interchangeably that mean different things, and the difference
decides whether more threads help.

**Concurrency** is several tasks in progress over the same period, interleaved
by the scheduler. One CPU can do this all day, and it is what most servers
actually need: while one request waits for a database, another can be parsed.

**Parallelism** is several tasks executing at the same instant. It requires more
than one CPU, and a container limited to half a CPU cannot have any, no matter
how many threads it starts.

That is the whole of the opening story. Sixteen threads on half a CPU are not
sixteen times the work; they are the same work with more switching, more cache
pressure, and a quota that runs out sooner.

:::predict{question="A container is limited to 0.5 CPU. Its dashboard shows 45% CPU utilisation and every request is slow. Where is the time going?"}
It is almost certainly being **throttled**, and the utilisation figure is
measured against the wrong denominator.

A CPU limit is a quota per period: `cpu.max` of `50000 100000` means 50ms of CPU
in every 100ms. When the container's threads spend that 50ms after 30ms of wall
clock, every one of them is **stopped** until the next period begins. Not
slowed — stopped, for 70ms.

Averaged over a second, the container did use about half a CPU, and 45% of a
whole CPU looks unremarkable on a graph scaled to the host. Meanwhile a request
that needed 5ms of CPU took 120ms of wall time because it sat out two periods.

The number that shows this is `throttled_usec` in `cpu.stat`, and it is the most
useful CPU metric a container has. Almost nobody plots it.
:::

## What you already have

:::callback
From **Processes**: `fork` creates a process with a copy of the address space.
Creating a thread uses the same underlying call with different flags — sharing
the address space rather than copying it. A thread is not a different kind of
object; it is the same object sharing more.
:::

From **User Space and the Kernel**, you measured what crossing the boundary
costs. A context switch is the same kind of expense: between threads of one
process it is cheap, and between processes the page tables change too.

## How to work through it

Four labs, all measurement. Count the threads in a running process and prove
they share memory; watch a CPU limit stop them and read the throttling counters;
watch two threads lose updates to a shared counter; and finally diagnose a
service that got slower when it was given more workers.

That last one is the story this lesson opened with. You will have the two
commands that explain it.

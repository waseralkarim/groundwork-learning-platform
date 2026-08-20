---
topic: topic.threads-and-concurrency
section: internals
title: When sharing goes wrong
order: 3
mode: explain
---

:::objective{id=OBJ-A01.6.7}
Explain how a lost update happens between two threads, and what a lock actually
prevents.
:::

Sharing an address space is what makes threads cheap. It is also what makes them
able to destroy each other's data, and the mechanism is worth seeing precisely
once.

## A lost update

```c
counter = counter + 1;
```

One line of source, three machine operations: read the value, add one, write it
back. Between any two of them the scheduler may run another thread.

:::diagram{src=../diagrams/lost-update.mmd caption="Two increments, one result"}

Both threads read 41. Both compute 42. Both write 42. Two increments happened and
the counter advanced by one.

This is not rare and it is not a timing curiosity. In the lab for this topic, two
threads incrementing a shared counter for a few seconds attempt hundreds of
millions of increments and **lose most of them** — the counter ends at a fraction
of the true total. The interleaving is not an edge case; it is the normal case
under contention.

Three properties make this the hardest class of bug to deal with:

**It depends on timing**, so it may never appear in testing and appear
immediately under load.

**It is invisible.** Nothing errors. The number is simply wrong, and the wrongness
is silent.

**It gets worse with more CPUs.** With one CPU the window is a scheduling
boundary; with several the threads genuinely run at the same instant.

## What a lock actually does

A **mutex** makes an interleaving impossible: one thread at a time may hold it,
so the read-add-write completes without interruption.

```c
pthread_mutex_lock(&m);
counter = counter + 1;
pthread_mutex_unlock(&m);
```

Two things worth being precise about, because both are commonly misstated.

**A lock does not make code fast.** It removes parallelism from the section it
protects. A lock around something expensive turns concurrent work into a queue,
and a service can be limited by one lock while every CPU sits idle.

**A lock does not make code correct on its own.** It makes one interleaving
impossible. If the invariant spans two locked sections, the state can still be
inconsistent in between — which is what transactions exist to solve at the
database layer.

For a counter specifically, an **atomic** operation is better than a lock: the
hardware performs read-modify-write as one indivisible step, with no scheduling
window and no lock to contend on.

## Deadlock

The other direction of failure. Two threads, two locks, acquired in opposite
orders:

```text
Thread A: holds lock 1, waiting for lock 2
Thread B: holds lock 2, waiting for lock 1
```

Neither can proceed and neither will ever give up. The signature is distinctive
and worth recognising:

- The service stops responding
- **CPU usage drops to zero** — deadlocked threads are not spinning, they are
  blocked
- No errors, no crash, no log lines
- A restart "fixes" it

That zero-CPU detail is the discriminator. A saturated service is busy; a
deadlocked one is doing nothing at all, and the two look identical from the
outside.

:::objective{id=OBJ-A01.6.8}
Troubleshoot a stuck service, distinguishing a deadlock from saturation from
waiting on something external.
:::

## Three ways to be stuck, and how to tell them apart

A service that is not responding is one of these, and they need different
answers:

| | CPU | Threads' state | Where the time goes |
|---|---|---|---|
| **Deadlock** | ~0% | blocked on locks, forever | nowhere — no progress at all |
| **Saturated** | at the limit, throttled | runnable, waiting for quota | queued behind the CPU limit |
| **Waiting on I/O** | low | `S` or `D` in `ps` | a database, a disk, a remote call |

The diagnosis is one command each:

```bash
grep -E 'nr_throttled|throttled_usec' /sys/fs/cgroup/cpu.stat   # saturated?
ps -L -o pid,tid,stat,wchan,comm -p <pid>                       # what are threads doing?
cat /proc/<pid>/status | grep ctxt                              # voluntary vs not
```

`wchan` names the kernel function a thread is sleeping in, which usually names
the cause outright — a futex for a lock, a socket call for a network wait.

:::callback
From **Processes**: state `D` is uninterruptible sleep, almost always I/O, and a
process in `D` cannot even be killed. Threads in `D` with an idle CPU are the
third row of that table, and no amount of CPU will help them.
:::

## Load average is not CPU usage

One number that misleads more than any other on Linux, because it does not mean
what it means on other systems.

Linux's load average counts tasks that are **runnable or in uninterruptible
sleep**. A machine with 100 threads blocked on a slow disk shows a load average
of 100 with an idle CPU.

So:

- **High load, high CPU** — genuinely CPU-bound
- **High load, low CPU** — waiting on I/O, and adding CPU will not help
- **Low load, slow service** — a lock, a throttled quota, or an external
  dependency

Which is why load average is a poor alert on its own, and why the useful pair is
CPU utilisation *and* throttled time.

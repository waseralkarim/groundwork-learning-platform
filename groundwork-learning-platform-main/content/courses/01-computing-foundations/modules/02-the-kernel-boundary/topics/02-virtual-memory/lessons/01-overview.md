---
topic: topic.virtual-memory
section: overview
title: The address that is not an address
order: 1
mode: explain
---

Two processes on the same machine, both reading address `0x7f2a1000`. Both
succeed. Neither sees the other's data.

That is not a special case or a clever trick — it is how every process on every
Linux machine has always worked. The addresses your program uses are not
addresses in RAM. They are entries in a table the kernel keeps for your process
alone, and hardware translates them on every single memory access.

Once that is real to you, a whole category of production confusion resolves at
once.

## The specific things this explains

- A process shows 400 MB of "memory" in one column and 50 MB in another, and
  both numbers are correct
- Adding up RSS across your processes gives a total larger than the machine's RAM
- A container with a 512 MB limit is killed while the application reports using
  300 MB
- `free -h` shows almost no free memory on a perfectly healthy server
- A JVM in a container sizes its heap from the host's RAM and is killed
  immediately
- `malloc` returns successfully for an amount of memory the machine does not have
- A Kubernetes pod is evicted for memory pressure and its application logs show
  nothing wrong

Every one of those is the same mechanism seen from a different angle.

## The lie, and why it is told

:::diagram{src=../diagrams/address-translation.mmd caption="Same address, different physical pages — except when sharing is deliberate"}

Each process gets its own **page table**. When it reads an address, the MMU walks
that table and produces a physical address. Two processes with the same virtual
address get different physical pages, because they have different tables.

The reasons this design won are worth knowing, because each one shows up later:

**Isolation.** A process cannot name another process's memory, so it cannot read
it. Not "is prevented from" — cannot express it. This is the same enforcement you
met at the kernel boundary, applied to memory instead of instructions.

**Sharing without copying.** libc is one physical copy mapped into hundreds of
processes. So is a container image layer read by ten containers.

**Lazy allocation.** A mapping can exist with no physical memory behind it at
all. Memory is allocated when it is first *touched*, not when it is asked for —
which is why a process can map 400 MB and use 50.

**Files as memory.** A file can be mapped so that reading memory reads the file.
That is how programs load, and how the page cache stops being a separate idea.

## What this means for a number on a dashboard

:::predict{question="A process has 400 MB mapped and 50 MB resident. Your monitoring shows one number. Which one should page you at 3am?"}
Neither, on its own — but if you must pick one, **resident**.

Virtual size counts everything the process has mapped: reservations it has never
touched, files it has never read, and guard regions that will never hold
anything. A Go runtime reserves a large address range at startup and uses a
fraction of it. Alerting on virtual size means alerting on an allocator's habits.

Resident size is real physical memory — but it counts every shared page in full,
in every process that maps it. Add it up across ten processes sharing libc and
you have counted libc ten times, which is how a machine appears to be using more
memory than it has.

The number that actually adds up is **PSS**, where each shared page is divided
between the processes sharing it. Almost nothing reports it by default, and the
next lesson explains why you should ask for it anyway.
:::

## What you already have

:::callback
From **User Space and the Kernel**: the kernel is the only thing that can touch
hardware, and a process asks for what it needs. Memory is the clearest case —
`malloc` is not a system call at all, and the syscall behind it does not hand you
memory. It hands you *permission* to touch an address range.
:::

From **The Machine**, you watched `eat-memory` allocate 400 MB and hold only 52
MB resident, and you read the `available` column of `free` rather than `free`.
This topic explains both numbers properly.

## How to work through it

Concepts, then the mechanism, then the tools, then production. Four labs, all
measurement: read your own address space, watch the three numbers disagree, see
what a cgroup actually counts, and finally diagnose a container killed with what
looked like plenty of headroom.

That last one is the most valuable half-hour in this topic. It is the failure
people misdiagnose most often, and the fix is almost never "raise the limit".

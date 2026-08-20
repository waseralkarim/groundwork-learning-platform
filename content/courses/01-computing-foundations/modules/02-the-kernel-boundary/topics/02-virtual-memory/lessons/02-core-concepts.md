---
topic: topic.virtual-memory
section: core-concepts
title: Pages, tables and the three numbers
order: 2
mode: explain
---

:::objective{id=OBJ-A01.4.1}
Explain what a virtual address is, and why two processes can hold the same
address without seeing each other's data.
:::

## Everything is pages

Memory is managed in fixed-size **pages** — 4 KiB on x86-64, almost always. Not
bytes, not allocations: pages. Every mapping, every fault, and every number in
`/proc` is a multiple of 4096.

This is why a program that allocates one byte costs a page, and why the kernel
can share, protect and evict at that granularity and no finer.

The **page table** maps a process's pages to physical ones. The MMU walks it on
every access, cached by the TLB so it is not as slow as it sounds. Switching
processes switches page tables, and that switch is why the same address in two
processes lands in different physical memory.

:::note
This is also the isolation. Process A cannot read process B's memory because
there is no virtual address in A's table that points at B's pages. It is not a
permission check that could be got wrong — the mapping does not exist.
:::

## A mapping is a promise, not memory

The single most useful correction in this topic: **asking for memory does not
give you memory.**

```c
void *p = malloc(400 * 1024 * 1024);   /* succeeds instantly */
```

At this point the process has 400 MB of address space and, quite possibly, zero
additional physical memory. The kernel has recorded that the range is valid. No
page tables have been filled in. Nothing has been taken from RAM.

Then the program writes to it:

```c
memset(p, 0, 50 * 1024 * 1024);        /* now 50 MB is real */
```

Each first touch of a page causes a **page fault**: the CPU traps into the
kernel, the kernel finds a free physical page, zeroes it, updates the page table
and returns. The instruction re-runs and succeeds. This happens thousands of
times a second on a busy machine and is entirely routine.

Lazy allocation is why the three numbers exist at all.

:::objective{id=OBJ-A01.4.3}
Distinguish virtual size, resident size and proportional set size, and say which
one answers "how much memory is this using".
:::

## VSZ, RSS, PSS

:::diagram{src=../diagrams/memory-numbers.mmd caption="Three answers to one question, only one of which sums correctly"}

**VSZ — virtual size.** Everything mapped: touched or not, file-backed or
anonymous, reserved or in use. A Go program reserves a large address range at
startup; a database maps its data files; a thread costs 8 MB of stack address
space and uses a few KB of it. High VSZ means nothing on its own, and alerting
on it generates false pages.

**RSS — resident set size.** Physical pages the process currently has. Real
memory, and the number most tools show. Its flaw is exactly one thing: a shared
page is counted in full by every process sharing it.

**PSS — proportional set size.** Each page divided by the number of processes
mapping it, so a libc page shared by ten processes contributes one tenth to
each. PSS is the only one of the three where summing across processes gives an
answer that matches the machine.

:::warning
Summing RSS across processes is the most common memory-accounting mistake, and
it looks perfectly reasonable. Ten workers each showing 80 MB RSS do not use 800
MB — most of those pages are one shared copy of the interpreter and its
libraries. The real figure might be 150 MB.

Any dashboard that sums per-process RSS is reporting a number the machine could
not reach.
:::

## Anonymous versus file-backed

Every page is one of two kinds, and the difference decides what happens under
pressure.

**File-backed** pages hold data that also exists on disk: program code, shared
libraries, anything read from a file. Under memory pressure the kernel can
simply drop them. Nothing is lost — reading the file again brings them back, at
the cost of the read.

**Anonymous** pages are heap and stack. There is no file to go back to. The
kernel's only options are to swap them out or keep them, so when memory runs
short and everything droppable has been dropped, the only remaining move is to
kill something.

:::callback
This is why the OOM kill you saw in **The Machine** could not be avoided:
`eat-memory` had touched its pages, they were anonymous, swap was off, and there
was nothing left to reclaim.
:::

## The page cache is not a leak

When a process reads a file, the kernel keeps the data in RAM in case it is read
again. That is the **page cache**, and on a healthy server it occupies most of
the memory that processes are not using.

It is not waste and it is not a leak. It is released the moment anything needs
the memory. This is why `free` shows almost nothing free while `available` shows
most of the machine.

The complication — and the reason people get caught — is that inside a
**cgroup**, page cache counts against your limit. A container that reads a lot
of file data can sit at 95% of its memory limit with an application using a
fraction of that, and be perfectly healthy. Until something else pushes it over.

:::warning
One kind of "file" memory is not reclaimable at all: **tmpfs**. A file written
to a tmpfs — `/tmp` in most containers, `/dev/shm`, a Kubernetes `emptyDir` with
`medium: Memory` — *is* memory. It appears on the `file` line of `memory.stat`,
counts against the limit, and has no disk copy to be dropped to.

So "most of the charge is `file`, therefore reclaimable" is a reasonable
inference that is sometimes wrong, and the `shmem` line is what tells the two
apart. Lab 3 measures exactly this, and the answer surprises most people:
spooling an upload to `/tmp` allocates memory against your own limit.
:::

:::objective{id=OBJ-A01.4.7}
Explain what overcommit means, and why a successful allocation is not a promise
that the memory exists.
:::

## Overcommit: why malloc almost never fails

Linux will happily promise more memory than it has, because most programs ask
for far more than they touch. The alternative — refusing allocations until every
promise is backed by real memory — would waste most of the RAM in the world.

The consequence is that **a successful allocation is not a guarantee**. The
failure does not arrive at `malloc`; it arrives later, when a page is touched
and there is nothing to give. At that point the kernel cannot return an error to
a memory access, so it kills a process instead.

That is the OOM killer, and it is a direct consequence of overcommit. Code that
carefully checks `malloc` for NULL is checking for something that, on a default
Linux configuration, will almost never happen.

## The one-sentence version

Addresses are per-process fictions; memory becomes real when it is touched;
shared pages make RSS double-count; file pages are reclaimable and anonymous
pages are not; and the kernel promises more than it has, which is why it
sometimes has to kill.

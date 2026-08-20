---
topic: topic.the-machine
section: internals
title: From source code to a running process
order: 3
mode: explain
---

:::objective{id=OBJ-A01.1.5}

You type `./server` and press enter. Between that keystroke and your code
running, a surprising amount happens — and almost every "it works on my machine"
failure lives somewhere in this sequence.

:::diagram{src=../diagrams/program-to-process.mmd caption="Source code to running process"}

## Program versus process

These are not the same thing, and the distinction is the single most useful
mental model in this topic.

A **program** is a file on disk. Passive. Bytes. It has a size, an owner, a
permission bit that says it may be executed. It is not doing anything.

A **process** is a program that is *running*. It has a process ID, a chunk of
memory it is using right now, a set of open files, a user it runs as, a parent,
a current position in the instruction stream, and a scheduling state.

One program can become many processes — running `nginx` three times gives you
three processes from one file on disk. And a process can outlive its program:
delete the binary while it runs and the process carries on perfectly happily,
because the kernel is holding a reference to the file's contents, not its name.

:::note
"A container is just a process" is a sentence you will hear often. It is nearly
true, and it is only meaningful if you already know what a process is. A
container is a process (or a small tree of them) that the kernel has been asked
to lie to about what it can see. That is genuinely most of it.
:::

## Compiled versus interpreted

**Compiled** languages — C, Go, Rust — are translated ahead of time into machine
instructions for one specific architecture. The output is a binary. It starts
fast, needs no runtime installed, and only runs on the architecture it was built
for.

**Interpreted** languages — Python, Ruby, shell — ship as source. A separate
program, the interpreter, reads it and does the work. The source is portable;
the interpreter is the thing that has to be installed and architecture-specific.

**Hybrid** — Java, C# — compile to bytecode for a virtual machine, which is then
executed by a VM built for the real architecture. Portable bytecode, per-platform
VM.

This distinction is exactly why container images differ so much in size. A Go
binary can ship in an image with literally nothing else in it — no shell, no
libc, a few megabytes total. A Python application needs the interpreter, the
standard library, and every dependency, and starts around 50MB before you have
written a line.

## What is inside a binary

On Linux, an executable is in **ELF** format — Executable and Linkable Format.
Its header states, among other things, which architecture it was built for.

That header is what produces `exec format error`. The kernel reads it, sees
`AArch64` where it expected `x86-64`, and refuses. It is not a subtle failure
and it is not a corrupt file — it is the loader doing exactly its job.

### Static and dynamic linking

Almost no program is self-contained. Even `printf` lives in the C standard
library.

- **Statically linked** — the library code is copied into the binary at build
  time. Bigger file, no runtime dependencies, runs anywhere with a compatible
  kernel.
- **Dynamically linked** — the binary records that it *needs* `libc.so.6`, and
  the dynamic linker finds and loads it at startup. Smaller file, shared between
  processes, and it fails at startup if the library is missing or too old.

Dynamic linking is why this happens:

```text
$ ./app
./app: /lib/x86_64-linux-gnu/libc.so.6: version `GLIBC_2.34' not found
```

The binary was built against a newer C library than the machine has. It is the
same class of problem as the architecture mismatch — a promise the file makes
that the system cannot keep.

:::warning{scope=production}
This is the single most common cause of "it works in my container and not on the
server". Building on Ubuntu 24.04 and running on Debian 11 gives you two
different glibc versions. Building inside the same base image you deploy is the
fix, and it is most of why reproducible builds matter.
:::

## What happens on exec

When you run `./server`:

1. The shell asks the kernel to run it, via the `execve` **system call**.
2. The kernel checks permissions and reads the ELF header.
3. It verifies the architecture. Wrong one, and you get `Exec format error` here.
4. It creates a fresh virtual address space and maps the binary's code and data
   into it.
5. If dynamically linked, control passes to the dynamic linker, which loads each
   required library — failing here if one is missing.
6. Control transfers to the program's entry point.
7. Your code runs.

Steps 3 and 5 are where most startup failures live. Knowing that the check
happens *there*, before a single line of your code executes, is why an
`exec format error` never means "my application has a bug".

## Virtual memory

:::objective{id=OBJ-A01.1.6}

Every process believes it has an enormous private memory space starting at
address zero. This is a lie, maintained jointly by the CPU and the kernel, and
it is one of the most important lies in computing.

The addresses a process uses are **virtual**. Hardware translates them to
physical RAM locations on every access. This buys three things:

- **Isolation.** Process A cannot read process B's memory, because A's address
  0x1000 and B's address 0x1000 map to different physical places.
- **Overcommit.** A process can reserve far more address space than the machine
  has RAM, as long as it does not touch it all.
- **Flexibility.** The kernel can move pages around, share them, or write them
  to disk, without the process noticing.

Two numbers follow from this, and confusing them causes a lot of wasted time:

- **Virtual size (VSZ)** — how much address space the process has reserved.
  Frequently enormous and almost always uninteresting.
- **Resident set size (RSS)** — how much physical RAM it is actually occupying.
  This is the number that matters.

A JVM with a 4GB heap setting may show 8GB VSZ and 900MB RSS. It is using 900MB.

## The page cache, and why "free memory" is the wrong number

Here is the thing that trips up nearly everyone.

When the kernel reads a file, it keeps a copy in RAM in case someone reads it
again. That copy is the **page cache**. It is not wasted memory — it is memory
doing useful work — and the kernel will hand it back instantly the moment a
process needs it.

But it counts as "used". So on a healthy 32GB server that has been up for a
week, you will see something like 300MB free. This is normal. This is *good*.
Unused RAM is wasted RAM.

The number you actually want is **available**: free memory plus everything the
kernel could reclaim immediately if asked.

```text
              total        used        free      shared  buff/cache   available
Mem:           31Gi       8.2Gi       412Mi       1.1Gi        22Gi        22Gi
```

`free` says 412Mi. `available` says 22Gi. The machine has plenty of memory. An
alert on the `free` column would page someone at 3am for nothing, and that alert
exists in a great many companies.

:::warning{scope=production}
Read the `available` column. Alert on the `available` column. The `free` column
on a busy Linux server is nearly always small and nearly always meaningless.
:::

## When memory really does run out

If processes genuinely need more than exists, the kernel has three moves, in
order of desperation:

1. **Drop page cache.** Free, instant, invisible.
2. **Swap.** Write memory pages to disk to reclaim RAM. Correct, and roughly a
   thousand times slower to read back. A swapping machine does not feel slow, it
   feels broken.
3. **Invoke the OOM killer.** Choose a process and terminate it with `SIGKILL`.
   No cleanup, no shutdown hook, no chance to flush. Just gone.

The OOM killer scores processes roughly by how much memory they are using and
kills the highest scorer. It is a last resort to keep the machine alive, not an
error-handling mechanism, and it is why the largest process is often the one
that dies even when a smaller one caused the problem.

```text
$ dmesg | tail -3
[12345.678] Out of memory: Killed process 4242 (python3)
            total-vm:2097152kB, anon-rss:1048576kB, file-rss:0kB
```

:::callback
Registered for later: this is exactly what `OOMKilled` means on a Kubernetes pod
(**E26**), and container memory limits (**C14**) are this mechanism scoped to a
cgroup rather than the whole machine. The pod did not crash — it was executed.
:::

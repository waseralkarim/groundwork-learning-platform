---
topic: topic.user-space-and-the-kernel
section: internals
title: One crossing, step by step
order: 3
mode: explain
---

:::objective{id=OBJ-A01.3.3}
Trace one line of code from a library call, through the system call boundary,
into the kernel and back.
:::

Take the smallest interesting line of C:

```c
printf("hello\n");
```

Here is everything that happens.

:::diagram{src=../diagrams/syscall-path.mmd caption="One printf, end to end"}

## Step 1 — your code, and only your code

`printf` is a C library function. It parses the format string, converts
arguments to text, and writes the result into a buffer that libc owns inside
your process memory. All ring 3, all your process, no kernel involvement
whatsoever.

Then it makes a decision most people never learn about: **whether to actually
send those bytes anywhere yet**. If stdout is a terminal, libc flushes on every
newline. If stdout is a pipe or a file, it buffers — typically 4096 bytes —
and returns to you having done nothing observable.

:::warning
This is why a crashing program's last log lines vanish, and why the same program
prints everything when you run it by hand. On a terminal it flushed line by
line; redirected to a file it buffered, then died with up to 4 KB of your most
important output still in user-space memory that nobody will ever read.

`stdbuf -oL`, `PYTHONUNBUFFERED=1`, and every logging library's `flush=True`
exist for this reason.
:::

## Step 2 — the wrapper

When libc does decide to send the bytes, it calls its own `write()` wrapper.
That wrapper is thin: it loads registers and executes one instruction.

```text
rax = 1                 ; syscall number for write
rdi = 1                 ; first argument: fd 1, stdout
rsi = <buffer address>  ; second argument: where the bytes are
rdx = 6                 ; third argument: how many
syscall                 ; cross
```

The calling convention is fixed by the kernel ABI: number in `rax`, arguments in
`rdi`, `rsi`, `rdx`, `r10`, `r8`, `r9`. Six maximum — a system call that needs
more takes a pointer to a struct.

Nothing here is C-specific. Go, Rust and Python programs put the same values in
the same registers, because the kernel does not know or care what language you
used. This is why `strace` works on any binary: it observes the ABI, not the
language.

## Step 3 — the crossing

The `syscall` instruction is the boundary. In one instruction the CPU:

- switches from ring 3 to ring 0
- saves the return address and flags
- jumps to the address the kernel registered at boot, in a register called
  `MSR_LSTAR` — not an address your process chose

That last point is the security property. A process cannot enter the kernel
anywhere it likes; there is exactly one door and the kernel installed it.

The kernel entry code then switches to a kernel stack — your process has one for
this purpose, separate from its user stack — and, on modern kernels, switches
page tables. That page-table switch is the Meltdown mitigation, and it is why
system calls got measurably more expensive in 2018.

## Step 4 — the kernel does the work

Now in ring 0, the kernel:

1. Reads `rax` (1), looks it up in the syscall table, finds `sys_write`
2. Checks that fd 1 is open in this process and is writable
3. Copies your bytes out of your memory with `copy_from_user` — deliberately,
   never by trusting the pointer directly
4. Hands them to whatever fd 1 refers to: a tty driver, a file's page cache, a
   socket buffer
5. Returns the number of bytes accepted

Step 2 is where a permission check would fail. Step 4 is where it might
**block** — if the pipe is full or the socket buffer has no room, the kernel
puts your process to sleep, marks it not-runnable, and schedules something else.
Your process resumes when there is room, potentially milliseconds later.

That is the difference between a mode switch and a blocked call, and it is
enormous:

| Event | Rough cost |
|---|---|
| Function call in your own code | ~1 ns |
| System call that does not block | ~100 ns – 1 µs |
| System call that blocks and reschedules | 1 µs – forever |

:::objective{id=OBJ-A01.3.5}
Measure what crossing the boundary costs, and explain why buffering exists in
every I/O library you have ever used.
:::

## Step 5 — coming back

The kernel executes `sysret`, the CPU returns to ring 3, and execution resumes
at the instruction after `syscall` with the result in `rax`.

libc checks the sign. Negative means an error, so it stores the negated value in
`errno` and returns `-1` to you. Everything you know as `errno` is a negative
integer from a register, translated.

Your program continues, having caused bytes to appear on a terminal without ever
having been permitted to touch one.

## Why buffering exists

Put the costs together and the design of every I/O library follows.

Writing one megabyte one byte at a time is 1,048,576 crossings. At ~500 ns each
that is half a second of pure overhead, before any actual work. In 64 KB blocks
it is 16 crossings — about 8 microseconds.

Same bytes. Same result on disk. Roughly a hundred times the CPU cost, and all
of it appears as **system time**, not user time.

:::predict{question="A program builds a 10 MB report by calling write() once per line, 200,000 times. It is slow. Someone suggests a faster disk. Will that help?"}
Barely. The disk is not the constraint — the crossings are.

200,000 `write()` calls at roughly half a microsecond each is about 0.1 seconds
of pure boundary overhead, spent in the kernel, on the CPU, before the disk is
even asked to do anything. The writes themselves land in the page cache and get
flushed in large batches by the kernel regardless.

The fix is a buffered writer: accumulate lines in memory and issue one `write()`
per 64 KB. Same disk, same bytes, two orders of magnitude fewer crossings.

You can see this in a profile before you change anything. High **system** time
with low **user** time and modest disk throughput is the signature of a program
that is asking too often rather than computing too much.
:::

## The exception: calls that do not cross

Some system calls are so frequent that crossing for them is intolerable.
Reading the clock is the worst offender — a logging library might call
`clock_gettime` for every line.

The kernel's answer is the **vDSO**: a small page of kernel-provided code mapped
into every process's address space at startup. Your `clock_gettime` call jumps
into that page, reads a timestamp the kernel keeps updated in shared memory, and
returns — all in ring 3, no boundary crossing at all.

```bash
ldd /bin/ls | head -2
```

```text
        linux-vdso.so.1 (0x00007ffd8f1f4000)
        libc.so.6 => /lib/x86_64-linux-gnu/libc.so.6
```

That first line is not a file on disk. It is the vDSO, and it is in every
process on the machine.

This is also why `clock_gettime` does not appear in `strace` output: `strace`
watches boundary crossings, and this one never crosses. A call you cannot see in
`strace` has not necessarily been skipped.

## What this makes possible

`strace` works because the kernel can be asked to stop a process on every
crossing and report it. Since every effect on the outside world is a crossing,
that report is complete — you are watching the total set of things a program
can do to anything.

That is a genuinely unusual debugging position. It requires no source, no
symbols, no cooperation from the program, and no knowledge of its language. A
closed-source binary that will not start can be diagnosed in one command,
because whatever it is failing to find, it must ask the kernel for it first.

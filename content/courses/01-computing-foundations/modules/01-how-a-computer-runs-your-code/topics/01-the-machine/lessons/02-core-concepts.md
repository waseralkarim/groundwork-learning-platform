---
topic: topic.the-machine
section: core-concepts
title: The three resources
order: 2
mode: explain
---

:::objective{id=OBJ-A01.1.1}

A computer, stripped to its essentials, is three things and a set of wires
between them.

| Part | What it does | Speed | Survives power loss? |
|---|---|---|---|
| **CPU** | Executes instructions | Billions per second | — |
| **RAM** | Holds what is being worked on | Nanoseconds | **No** |
| **Storage** | Holds what must be kept | Microseconds to milliseconds | **Yes** |

The whole discipline of making computers fast is the management of the tension
between those last two columns. Fast memory is volatile and expensive. Durable
storage is slow and cheap. Everything else — caching, buffering, page cache,
Redis, CDNs, `fsync` — is a strategy for living with that trade.

## The CPU

The **central processing unit** does exactly one thing, forever, until it is
switched off:

:::diagram{src=../diagrams/instruction-cycle.mmd caption="The fetch-decode-execute loop"}

1. **Fetch** the next instruction from memory.
2. **Decode** it — work out what operation it names and what it operates on.
3. **Execute** it.
4. Go to 1.

This is the **instruction cycle**. A modern CPU runs it a few billion times per
second per core, and pipelines several instructions at once so the stages
overlap, but the loop is the loop.

The instructions are tiny. Not "read this file" — more like "add the number in
register 3 to the number in register 4", "copy eight bytes from this address to
that register", "if the last result was zero, jump to this address". A single
line of Python becomes dozens or hundreds of them.

### Cores

A **core** is one complete instruction-executing unit. A four-core CPU can
genuinely run four instruction streams at the same instant.

**Hyper-threading** (Intel's name; AMD calls it SMT) presents each physical core
to the operating system as two logical cores. It works because a core spends a
lot of its time waiting — for memory, mostly — and a second instruction stream
can use the gaps. It is not two cores. Depending on the workload it buys
somewhere between 0% and about 30%.

:::warning{scope=production}
"More cores" is not "faster". A single-threaded program on a 64-core machine
uses one core and runs at exactly the speed of one core. Doubling the cores on a
service that cannot use them is a way of doubling the bill.
:::

### Architecture

An **instruction set architecture** (ISA) is the vocabulary of instructions a
particular CPU understands. The two that matter today:

- **amd64** (also written `x86_64`) — Intel and AMD server and desktop chips
- **arm64** (also written `aarch64`) — Apple Silicon, AWS Graviton, Raspberry Pi,
  almost every phone

They are genuinely different languages. A program compiled into amd64
instructions is a file full of numbers that mean nothing to an arm64 CPU. It
will not run slowly; it will not run at all:

```text
$ ./tool
bash: ./tool: cannot execute binary file: Exec format error
```

You will meet this error again the first time you build a container image on an
Apple laptop and deploy it to an Intel server. It is the same problem wearing a
different hat.

:::callback
Registered for later: **C14 Containers** returns to this exact error when it
covers multi-architecture images, and refers back to this lesson.
:::

## Memory

:::objective{id=OBJ-A01.1.4}

**RAM** — random access memory — is where a program's working state lives while
it runs. "Random access" means reading address 4 billion costs the same as
reading address 4; there is no seeking.

RAM is **volatile**. Cut the power and it is empty. Everything in RAM that
matters must have been written to storage first, or it is gone. Every database's
durability guarantee, every `fsync` call, every "your changes have been saved"
is ultimately about this one property.

### The hierarchy

RAM is fast compared to disk and desperately slow compared to the CPU. So there
is not one memory — there is a ladder, fast and tiny at the top, slow and vast
at the bottom:

:::diagram{src=../diagrams/memory-hierarchy.mmd caption="Each step down is roughly an order of magnitude slower"}

| Level | Typical size | Typical latency | Relative |
|---|---|---|---|
| Register | ~1 KB | ~0.3 ns | 1× |
| L1 cache | ~64 KB/core | ~1 ns | ~3× |
| L2 cache | ~1 MB/core | ~4 ns | ~13× |
| L3 cache | ~32 MB shared | ~15 ns | ~50× |
| RAM | 8 GB – 2 TB | ~80 ns | ~250× |
| NVMe SSD | 0.5 – 8 TB | ~50 µs | ~150,000× |
| Network (same DC) | — | ~500 µs | ~1,500,000× |
| Spinning disk seek | — | ~5 ms | ~15,000,000× |

Do not memorise the numbers. Memorise the **shape**: each step down is roughly
one order of magnitude, and the step from RAM to SSD is closer to three.

That single fact explains an enormous amount of production behaviour. It is why
a cache hit is transformative rather than merely nice. It is why a machine that
starts swapping does not get 20% slower, it stops responding. It is why "just
add an index" turns a 30-second query into a 3-millisecond one.

:::aside
A useful way to feel these numbers: scale them so one CPU cycle is one second.
Then reading from L1 is 3 seconds. RAM is about 4 minutes. An SSD read is about
2 days. A spinning-disk seek is about 6 months. A network round trip to another
continent is roughly 5 years.

When someone says a service is "waiting on I/O", that is the scale of the wait.
:::

## Storage

**Persistent storage** keeps its contents without power. Three kinds matter:

- **NVMe SSD** — flash connected directly to the CPU's high-speed bus. Fast, no
  moving parts, wears out after a finite number of writes.
- **SATA SSD** — flash on an older, slower connection. Perhaps a quarter the
  speed of NVMe.
- **HDD** — a spinning magnetic platter with a physical arm. Cheap per terabyte,
  and dramatically slower for anything that is not read in one long sweep,
  because the arm has to physically move.

### What a filesystem adds

A storage device natively offers something very unglamorous: a numbered array of
fixed-size **blocks**. Block 0, block 1, block 2, up to a few billion. That is
all. It has no concept of a file, a name, or a folder.

A **filesystem** is the layer that turns that array into names, directories,
sizes, permissions and timestamps. `ext4`, `xfs`, `btrfs`, `NTFS` and `APFS` are
all different strategies for the same trick.

This is worth knowing precisely because the distinction goes on mattering. A
container image is a stack of filesystem layers. A Kubernetes PersistentVolume
is a block device that gets a filesystem put on it. "The disk is full" and "the
filesystem is out of inodes" are two different failures on the same hardware,
and you will eventually meet the second one.

:::callback
Registered for later: **C14 Containers** builds image layers on this;
**E27 Kubernetes Storage** builds PersistentVolumes on it.
:::

:::checkpoint
Before continuing, make sure you can answer without looking:

1. Which of the three resources loses its contents when the power goes out?
2. Roughly how much slower is an SSD read than a RAM read — 10×, 100×, or 1000×?
3. Why can a binary built on an Apple laptop fail to start on an Intel server?
:::

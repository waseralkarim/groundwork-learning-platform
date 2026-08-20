---
topic: topic.the-machine
section: commands
title: Reading a real machine
order: 4
mode: show
---

:::objective{id=OBJ-A01.1.7}

Theory is worth nothing until you can point at a real machine and say what it is
made of and what it is doing. Here is the toolkit.

## What CPU is this?

:::terminal{title="Architecture — one word, high value"}
$ uname -m
x86_64
:::

`x86_64` means amd64. `aarch64` means arm64. This is the first thing to check
when a binary refuses to start.

:::terminal{title="Full CPU picture"}
$ lscpu | head -14
Architecture:            x86_64
  CPU op-mode(s):        32-bit, 64-bit
  Address sizes:         46 bits physical, 48 bits virtual
  Byte Order:            Little Endian
CPU(s):                  8
  On-line CPU(s) list:   0-7
Vendor ID:               GenuineIntel
  Model name:            Intel(R) Xeon(R) CPU E5-2686 v4 @ 2.30GHz
    CPU family:          6
    Thread(s) per core:  2
    Core(s) per socket:  4
    Socket(s):           1
:::

Read that carefully, because the interesting number is not the first one.

`CPU(s): 8` is **logical** processors. `Core(s) per socket: 4` with
`Thread(s) per core: 2` means **four physical cores**, presented as eight.

If you size a thread pool at 8 believing you have eight independent cores, you
will be disappointed. `nproc` reports the same logical count — useful for
`make -j`, misleading for capacity planning.

## How much memory, really?

:::predict{question="A server has 31 GiB of RAM and has been up for three weeks. Roughly what will the `free` column of `free -h` report?"}
A few hundred mebibytes — frequently under 2% of the machine. That is healthy,
not a leak and not memory pressure. The kernel deliberately fills spare RAM with
page cache, because idle RAM does no work, and it hands that memory back the
instant a process asks for it. The number that answers "can I start another
process" is `available`, and on this machine it will be most of the 31 GiB.
:::

:::terminal{title="The command everyone reads wrong"}
$ free -h
               total        used        free      shared  buff/cache   available
Mem:            31Gi       8.2Gi       412Mi       1.1Gi        22Gi        22Gi
Swap:          2.0Gi          0B       2.0Gi
:::

Column by column:

- **total** — physical RAM the kernel can see
- **used** — genuinely allocated to processes
- **free** — untouched. On a busy server this is small, and that is correct
- **buff/cache** — page cache and kernel buffers. Reclaimable
- **available** — **the number you want**: what a new process could get without
  swapping

:::try{lab=inspect-the-machine run="free -m" title="Read it on a real machine"}
This shell has a memory limit of its own, so the totals are far smaller than the
example above. The shape is what matters: `free` small, `available` large, and
`buff/cache` holding the difference.
:::

The `Swap` line matters too. `used` of `0B` is healthy. Anything steadily
climbing there means the machine is under memory pressure and paying
disk-latency prices for RAM accesses.

:::terminal{title="The raw source, if you want it"}
$ grep -E 'MemTotal|MemAvailable|SwapTotal' /proc/meminfo
MemTotal:       32873516 kB
MemAvailable:   23068672 kB
SwapTotal:       2097148 kB
:::

`/proc` is not a real directory on a disk. It is a view into kernel data
structures presented as files. Reading `/proc/meminfo` is asking the kernel a
question, and the answer is generated at the moment you read it.

## What storage is attached?

:::terminal{title="Block devices — the hardware view"}
$ lsblk
NAME        MAJ:MIN RM  SIZE RO TYPE MOUNTPOINTS
nvme0n1     259:0    0  100G  0 disk
├─nvme0n1p1 259:1    0   99G  0 part /
└─nvme0n1p2 259:2    0    1G  0 part /boot
:::

:::terminal{title="Filesystems — the usable view"}
$ df -h
Filesystem      Size  Used Avail Use% Mounted on
/dev/nvme0n1p1   98G   71G   23G  76% /
tmpfs           16G   1.2G   15G   8% /dev/shm
:::

`lsblk` shows devices; `df` shows mounted filesystems and how full they are.
Both are worth reading, because "the disk is full" can mean the device is full,
or a single filesystem is full, or — the one that catches people —
inodes are exhausted while gigabytes remain free:

:::terminal{title="The disk-full that is not about space"}
$ df -i /
Filesystem       Inodes   IUsed   IFree IUse% Mounted on
/dev/nvme0n1p1  6553600 6553598       2  100% /
:::

Plenty of gigabytes. No inodes. Every write fails with `No space left on
device`, and `df -h` will show you nothing wrong. Millions of tiny files, often
from a logging bug, will do this.

## What is it doing right now?

This is the diagnostic core of the topic.

:::terminal{title="vmstat — five one-second samples"}
$ vmstat 1 5
procs -----------memory---------- ---swap-- -----io---- -system-- ------cpu-----
 r  b   swpd   free   buff  cache   si   so    bi    bo   in   cs us sy id wa st
 2  0      0 412000 180000 2200000    0    0     4    18  120  240 15  3 82  0  0
 1  0      0 411800 180000 2200000    0    0     0     0  118  235 14  2 84  0  0
:::

The columns that carry the signal:

| Column | Meaning | What a high value tells you |
|---|---|---|
| `r` | Processes waiting for CPU | **CPU-bound** if consistently above core count |
| `b` | Processes blocked on I/O | **I/O-bound** |
| `si`/`so` | Swap in / swap out per second | **Memory-bound** — this is the alarm bell |
| `bi`/`bo` | Blocks in / out per second | Disk throughput |
| `us` | User CPU time % | Your code is doing work |
| `sy` | System CPU time % | The kernel is doing work — high means syscall-heavy |
| `id` | Idle % | Spare capacity |
| `wa` | Waiting for I/O % | **I/O-bound** — CPU is idle but cannot proceed |

**The one move that makes you useful:** run `vmstat 1 5` and read three
columns — `r`, `si`/`so`, and `wa`.

- `r` high, `id` near zero → **CPU-bound**
- `si`/`so` non-zero → **memory-bound**, and everything else is a symptom
- `wa` high, `us` low → **I/O-bound**

That is a genuine diagnosis in five seconds, and it is the method rather than
the answer.

:::warning{scope=production}
The first line `vmstat` prints is an average since boot, not a current sample.
Ignore it. This is why `vmstat 1 5` and not `vmstat`: you want the samples after
the first.
:::

:::terminal{title="Per-process view"}
$ ps -eo pid,comm,%cpu,%mem,rss --sort=-rss | head -5
    PID COMMAND         %CPU %MEM   RSS
   4242 java            45.2 12.1 4063232
   1180 postgres         2.1  3.4 1140736
    892 nginx            0.3  0.2   68432
:::

Sorting by `rss` answers "what is actually using the memory" — the number that
matters, not `VSZ`.

:::checkpoint
You should now be able to, on any Linux machine:

1. State its architecture and its true physical core count
2. Say how much memory is genuinely available
3. Say whether it is CPU-, memory- or I/O-bound, and cite the column that proves it
:::

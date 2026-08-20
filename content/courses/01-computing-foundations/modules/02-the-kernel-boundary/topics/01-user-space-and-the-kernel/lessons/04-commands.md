---
topic: topic.user-space-and-the-kernel
section: commands
title: Watching the boundary
order: 4
mode: do
---

Five tools. The first one alone will save you more time than most of what you
will learn this year.

## strace — every crossing, as it happens

```bash
strace ./program              # every syscall, live
strace -f ./program           # follow children too — usually what you want
strace -c ./program           # counts and timings instead of a firehose
strace -e trace=openat ls     # only the calls you care about
strace -p 1234                # attach to something already running
strace -o out.txt ./program   # to a file, so it does not mangle the output
```

`-c` is the one to reach for first, because it turns a wall of text into a
summary you can actually read:

:::terminal{title="strace -c on a program that writes badly"}
$ strace -c ./slow-writer
% time     seconds  usecs/call     calls    errors syscall
------ ----------- ----------- --------- --------- ----------------
 94.12    0.412355           0    204800           write
  3.11    0.013622          13      1024           brk
  1.44    0.006301         210        30           openat
------ ----------- ----------- --------- --------- ----------------
100.00    0.438110                 205884         3 total
:::

204,800 writes. You do not need to read the source to know what is wrong.

:::try{lab=every-crossing run="strace -c /bin/ls /tmp" title="Count what `ls` asks for"}
`ls` on a nearly empty directory still makes dozens of calls — the loader has to
open libc, map it, and resolve symbols before `main` runs at all. Look for
`execve` (there is exactly one), then the `openat` calls that load the libraries.
:::

:::warning{scope=production}
`strace` stops the traced process on every syscall. A syscall-heavy service can
run **10 to 100 times slower** while attached, which is enough to trip health
checks and get it restarted underneath you.

On a production process, prefer `strace -c -f -p <pid>` for a few seconds and
then detach, and know what your health check timeout is before you start.
:::

## time — the user/system split

The single fastest way to characterise a workload.

```bash
time ./program
```

```text
real    0m2.104s
user    0m0.088s
sys     0m1.981s
```

Read it like this:

- **real** — wall clock, including time spent waiting for anything
- **user** — CPU running your instructions
- **sys** — CPU running kernel code on your behalf

Those numbers say the program spent 22 times more CPU in the kernel than in its
own logic. It is not computing; it is asking. The next command should be
`strace -c`, and the answer is nearly always "far too many small calls".

The opposite shape — user high, sys near zero — is a compute-bound program, and
`strace` will tell you nothing useful about it. Reach for a profiler instead.

:::objective{id=OBJ-A01.3.4}
Interpret user time against system time for a workload, and attribute the
difference to what the program is actually doing.
:::

The same split for the whole machine is the `us` and `sy` columns in `top`, and
for one running process it is fields 14 and 15 of `/proc/<pid>/stat`, in clock
ticks:

```bash
awk '{print "utime="$14, "stime="$15}' /proc/self/stat
```

## /proc/self/status — what am I allowed to do?

`/proc` is the kernel answering questions about itself in plain text, and
`status` is the summary sheet for a process.

```bash
grep -E '^(Name|Uid|Gid|CapEff|CapPrm|CapBnd|NoNewPrivs|Seccomp)' /proc/self/status
```

```text
Name:   bash
Uid:    10001   10001   10001   10001
CapEff: 0000000000000000
CapPrm: 0000000000000000
CapBnd: 0000000000000000
NoNewPrivs:     1
Seccomp:        2
```

Line by line, because every one of these is a question people ask in incident
channels:

- **Uid** — real, effective, saved, filesystem. The effective one is what
  permission checks use
- **CapEff** — the capabilities currently in force. `0000000000000000` means
  none at all
- **CapBnd** — the bounding set: the ceiling. Nothing outside this can ever be
  gained, even by executing a setuid binary
- **NoNewPrivs: 1** — this process can never gain privilege through `exec`.
  `docker run --security-opt=no-new-privileges` sets exactly this
- **Seccomp: 2** — a filter is installed and active. `0` means none

## capsh and getpcaps — capabilities in words

The hex is unreadable. Decode it:

```bash
capsh --decode=00000000a80425fb          # a typical Docker default set
getpcaps $$                              # this shell's capabilities
capsh --print                            # everything, verbosely
```

:::terminal{title="What a normal container actually gets"}
$ capsh --decode=00000000a80425fb
0x00000000a80425fb=cap_chown,cap_dac_override,cap_fowner,cap_fsetid,
cap_kill,cap_setgid,cap_setuid,cap_setpcap,cap_net_bind_service,
cap_net_raw,cap_sys_chroot,cap_mknod,cap_audit_write,cap_setfcap
:::

That is fourteen capabilities — Docker's default. Note what is *not* there:
`cap_sys_admin`, `cap_sys_module`, `cap_sys_time`, `cap_syslog`. A container
that "runs as root" holds those fourteen and no more.

:::try{lab=what-you-may-ask run="grep Cap /proc/self/status" title="Read your own capabilities"}
This shell holds fewer than Docker's default — the lab platform drops every
capability, which is stricter than a normal container. All zeros is what maximum
restriction looks like from the inside.
:::

## ltrace — the other half of the picture

`strace` shows system calls. `ltrace` shows *library* calls, which is where the
work often actually is.

```bash
ltrace ./program
```

Use it when `strace` shows almost nothing but the program is clearly busy: the
activity is in user space, in library code, and never reaches the boundary.

## Reading a refusal

The single highest-value habit in this topic. When something is denied, get the
errno rather than the message, because the message is ambiguous and the errno is
not.

```bash
strace -e trace=openat,mount,bind ./program 2>&1 | grep -E 'EACCES|EPERM|EROFS'
```

| errno | Message | What failed | First thing to check |
|---|---|---|---|
| `EACCES` | Permission denied | File permission check | `ls -l`, `id`, the whole path's `x` bits |
| `EPERM` | Operation not permitted | Capability or seccomp | `grep Cap /proc/<pid>/status` |
| `EROFS` | Read-only file system | The mount, not you | `mount \| grep <path>` |
| `ENOENT` | No such file or directory | Nothing was denied | The path — often a *library*, not your file |

:::warning
`ENOENT` from a program that clearly exists usually means a missing shared
library, not a missing program. `strace` shows the `openat` that failed and
names the file, which turns a baffling "No such file or directory" into a
one-line fix.
:::

:::checkpoint
Without scrolling up:

1. Which command tells you whether a slow program is computing or asking?
2. Which two errno values both print as some form of "permission", and how do
   their fixes differ?
3. Where do you look to find out whether a process holds `CAP_NET_BIND_SERVICE`?
4. Why does `clock_gettime` not appear in `strace` output?
:::

---
topic: topic.processes
section: commands
title: Inspecting processes
order: 4
mode: show
---

:::objective{id=OBJ-A01.2.6}

Six commands. Learn these and you can answer almost any process question on a
machine you have never seen.

## What is running

:::terminal{title="The one to memorise"}
$ ps -eo pid,ppid,stat,user,etime,comm --sort=-etime | head -8
    PID    PPID STAT USER       ELAPSED COMMAND
      1       0 Ss   root      21-04:11 systemd
    412       1 Ss   root      21-04:10 sshd
   1180       1 Ssl  postgres   6-22:30 postgres
   8835    8834 Ss   alice        14:02 bash
:::

Pick your own columns rather than memorising `ps aux` — `-o` takes exactly what
you want. The ones worth having: `pid`, `ppid`, `stat`, `user`, `etime`, `rss`,
`comm`, `args`.

The `STAT` column carries more than the state letter:

| Suffix | Means |
|---|---|
| `s` | Session leader |
| `l` | Multi-threaded |
| `+` | In the foreground process group |
| `<` | High priority |
| `N` | Low priority (niced) |

So `Ssl` is a sleeping, multi-threaded session leader — which is what nearly
every daemon looks like.

:::terminal{title="Ancestry, when you need to know who started what"}
$ ps -ef --forest | grep -A3 sshd
:::

:::terminal{title="Hunting the two states that matter"}
$ ps -eo pid,stat,comm | awk '$2 ~ /^[DZ]/'
   4821 D    rsync
   5102 Z    python3
:::

That one line answers "is anything stuck or unreaped" and is worth putting in
your fingers.

## What a specific process is doing

`/proc/<pid>/` is the kernel's per-process view, presented as files. Nothing here
is on a disk; each read asks the kernel a question.

:::terminal{title="The per-process directory"}
$ ls /proc/8835/
cmdline  cwd  environ  exe  fd/  limits  maps  status  task/
:::

| Path | Answers |
|---|---|
| `status` | State, PPID, UID, threads, memory — start here |
| `cmdline` | The exact arguments it was started with |
| `exe` | Symlink to the binary, even if deleted |
| `cwd` | Symlink to its working directory |
| `fd/` | Every open file, socket and pipe |
| `limits` | Its ulimits, as actually applied |

:::terminal{title="The three questions you will ask most"}
$ grep -E '^(State|PPid|Threads|VmRSS)' /proc/8835/status
State:  S (sleeping)
PPid:   8834
Threads:        1
VmRSS:     4820 kB

$ tr '\0' ' ' < /proc/8835/cmdline; echo
/usr/bin/python3 /srv/app/worker.py --queue default

$ ls -l /proc/8835/fd/ | head -5
lrwx------ 1 alice alice 64 Aug 15 11:42 0 -> /dev/pts/0
lrwx------ 1 alice alice 64 Aug 15 11:42 1 -> /dev/pts/0
lrwx------ 1 alice alice 64 Aug 15 11:42 2 -> /dev/pts/0
lr-x------ 1 alice alice 64 Aug 15 11:42 3 -> /srv/app/data.db
:::

`cmdline` uses NUL bytes between arguments, which is why it needs `tr` — and why
`cat` on it looks like everything ran together.

:::note
`/proc/<pid>/fd/` is how you answer "what file is this process holding open" —
including a deleted file it has not closed, which is the usual reason `df` and
`du` disagree about free space. A file's blocks are only released when the last
descriptor closes.
:::

## Sending signals

:::terminal{title="kill sends signals; killing is only its default"}
$ kill 8835            # SIGTERM — the polite request
$ kill -TERM 8835      # identical, spelled out
$ kill -HUP 1180       # reload configuration, by convention
$ kill -9 8835         # SIGKILL — last resort
$ kill -0 8835         # send nothing; just test whether it exists
$ kill -l              # list every signal
:::

`kill -0` is the useful one nobody knows: it delivers no signal and simply
succeeds or fails, which makes it the correct way to ask "is this process still
alive" from a script.

:::warning{scope=production}
Reach for `kill` before `kill -9`, always. `SIGTERM` lets a database flush, a
queue worker finish its job, a server drain its connections. `SIGKILL` takes
those away with no warning and no error.

`kill -9` as a first move is a habit that eventually costs you data.
:::

:::terminal{title="By name, when you do not have the PID"}
$ pkill -f 'python3 worker.py'    # match the full command line
$ pgrep -a -f worker              # list what would match, first
:::

Run `pgrep` before `pkill`, every time. `-f` matches the whole command line, and
a loose pattern will happily match more than you meant.

## Live view

:::terminal{title="top, with the keys worth knowing"}
$ top
# then:
#   1   per-core breakdown
#   M   sort by memory
#   P   sort by CPU
#   H   show individual threads
#   c   full command line instead of the short name
:::

The load average in the header is the number to read first, and it is widely
misunderstood: it counts processes **runnable or in uninterruptible sleep**. So a
machine with load 40 and idle CPUs is not CPU-starved — it has 40 processes
stuck waiting on I/O, in state D.

:::checkpoint
On any machine, you should now be able to:

1. List every process in state D or Z in one command
2. Find the full command line and working directory of a PID
3. Discover which files a process has open
4. Test whether a process exists without disturbing it
:::

---
topic: topic.concurrency-and-locking
section: overview
title: The night the job ran twice
order: 1
mode: explain
---

A report builder, on a five-minute cron. One night the source database is slow
and a run takes six minutes. Cron does not care: the next run starts on
schedule.

Two runs, same output file:

```console
$ report.sh A & report.sh B & wait
  [B] reading
  [A] reading
  [A] writing
  [B] writing
```

```csv
B,row-1
A,row-1
B,row-2
A,row-2
B,row-3
A,row-3
```

Neither run failed. Both exited 0. The file has ten rows where five were
expected, in an order that belongs to neither run, and every downstream consumer
will read it as one report.

**A script that runs on a schedule will eventually run twice at once.** Not
because anything broke — because one run was slower than the gap between runs.

## The fix is three lines, and one of them is subtle

```bash
exec 9>/var/lock/report.lock
flock -n 9 || { echo "another run holds the lock"; exit 0; }
```

`flock` takes an **advisory lock** on an open file. The second run's `flock -n`
returns 1 immediately, and it exits without doing any work:

```console
  [A] start
  [B] another run holds the lock - exiting
  [A] finish
```

The subtle line is the first. `exec 9>` opens the file and keeps the descriptor
open **for the life of the script**, which is what the lock is attached to.

:::predict{question="A script takes a `flock`, then its cleanup trap runs `rm -f \"$LOCK\"` on exit. What does the next pair of overlapping runs do?"}
:::

## The tidy version that stops working

Removing your own lock file looks like good hygiene. It is the one thing you
must not do:

```console
  A: holds the lock
  (lock file removed while A still holds it)
  B: ACQUIRED - a NEW file, so both now run
```

**A lock belongs to the inode, not the path.** When `rm` unlinks the file, run A
still holds a lock on an inode that no longer has a name. Run B opens the same
*path*, gets a brand-new inode, and locks that — successfully, because nobody
else holds it.

Two runs, two locks, two inodes, no mutual exclusion. And the script that does
this is the one that looked more careful.

## A PID file is not the same thing

The other common approach writes `$$` to a file and checks it on the way in. It
has a failure the kernel cannot help with:

```console
$ # holder is SIGKILLed
  pid file still present?  YES
  it says pid 26, which is  GONE
```

**A PID file outlives its process.** After a crash, an OOM kill, or a node
reboot, the file is still there naming a process that no longer exists — so the
next run either refuses forever, or has to guess whether that PID is real, and
guessing is a race of its own once PIDs are reused.

`flock` has no such problem:

```console
  while holder alive: refused
  after SIGKILL:      acquired - the kernel released it
```

The kernel closes the descriptor when the process dies, however it dies, and the
lock goes with it. **A `flock` cannot go stale.**

## And a timeout does not necessarily stop anything

```console
$ watchdog.sh 1
importer did not finish in 1s - terminated (rc=124)

$ cat importer.log
importer: ignoring TERM, batch in progress
importer: batch 2 written
...
importer: FINISHED WRITING ALL BATCHES
```

`timeout` sends `TERM` and reports **124**. A process that handles or ignores
`TERM` keeps running, and the watchdog reports a termination that did not
happen. `timeout -k` sends `KILL` after a grace period, and the same importer
stops at batch 2 with status **137**.

## What this topic covers

- What overlapping runs actually do to a file, measured rather than imagined.
- `flock` — the descriptor idiom, `-n`, `-w`, and the status each returns.
- Why a lock is on the inode, and what `rm` does to it.
- `flock` against PID files, `mkdir`, and check-then-create, and which failures
  each survives.
- `timeout`, its statuses, and what `-k` buys.
- Which operations are safe to retry, and what a retry loop does when they are
  not.

Four labs:

- Start two runs at once and watch them corrupt a file, then fix it three ways.
- Delete a lock file while it is held, and watch the lock stop working.
- Kill a lock holder and find out which locking scheme survives it.
- Retry a charge three times and count the money.

:::objective{id=OBJ-B08.8.1}
:::

:::objective{id=OBJ-B08.8.3}
:::

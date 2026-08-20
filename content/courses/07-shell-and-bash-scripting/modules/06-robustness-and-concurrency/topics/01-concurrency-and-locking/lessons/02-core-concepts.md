---
topic: topic.concurrency-and-locking
section: core-concepts
title: Four ways to be the only one running
order: 2
mode: explain
---

## `flock`, and the descriptor idiom

```bash
exec 9>/var/lock/myjob.lock
flock -n 9 || { echo "already running" >&2; exit 0; }
```

Two things are happening, and the first is the one people drop.

**`exec 9>FILE`** opens the file on descriptor 9 and leaves it open for the rest
of the script. Not a redirection on one command — a descriptor the shell holds.
Any number above 2 works; 9 and 200 are the conventional choices.

**`flock -n 9`** takes an exclusive lock on that *descriptor*. `-n` means do not
wait: if somebody else holds it, return **1** immediately.

Three ways to ask:

```bash
flock -n 9          # fail immediately if held        → rc 1
flock 9             # wait, however long it takes     → rc 0 eventually
flock -w 30 9       # wait up to 30 seconds, then give up → rc 1
```

And the one-line form, which opens, locks and runs in one go:

```bash
flock -n /var/lock/myjob.lock -c 'the-command'
flock -n /var/lock/myjob.lock ./myjob.sh        # in crontab
```

That form is the right answer in a crontab, because it needs no changes to the
script at all.

**Which to choose.** `-n` for anything on a schedule: if the previous run is
still going, this run has nothing useful to add, and queuing them up guarantees a
pile-up. Blocking for anything that *must* happen and can wait its turn. `-w` when
waiting is right but forever is not — always with a message, so a run that gave
up says so.

:::note
`flock` locks are **advisory**. They coordinate processes that ask; nothing
prevents a program that never calls `flock` from writing to the same file. This
is mutual exclusion by agreement, and the agreement has to be kept by every
writer.
:::

## Why the lock is on the inode

This is the part that decides whether your lock works.

`flock` attaches to an **open file description** — the kernel object behind the
descriptor — which points at an **inode**. Not at the path. The path is just how
you found the inode.

So `rm` on the lock file does not release anything. It unlinks a name. Run A
keeps its lock on a now-nameless inode, and the next run that opens the path
creates a **new** inode and locks that:

```console
  A: holds the lock
  (lock file removed while A still holds it)
  B: ACQUIRED - a NEW file, so both now run
```

Which gives one hard rule: **never delete the lock file.** Not in a cleanup trap,
not in a "tidy up /var/lock" cron job, not by hand during an incident. An empty
lock file costs an inode; a deleted one costs mutual exclusion. Create it once
and leave it forever.

`/var/lock` and `/run/lock` exist precisely so these files have a home that is
cleared on reboot — when no process can be holding one.

## A PID file, and what it cannot survive

```bash
[ -e "$PIDFILE" ] && kill -0 "$(cat "$PIDFILE")" 2>/dev/null && exit 0
echo $$ > "$PIDFILE"
trap 'rm -f "$PIDFILE"' EXIT
```

Three defects, in increasing order of how long they take to find.

**It goes stale.** A process killed with `SIGKILL`, OOM-killed, or lost to a
node reboot never runs its trap. The file remains, naming a dead process.

**The `kill -0` check is a guess.** PIDs are reused. On a busy machine the
recorded PID may now belong to something else entirely, and the check says
"running" about a process that has nothing to do with your job.

**It is TOCTOU.** Between the test and the `echo $$`, another run can do exactly
the same test. Both find no live PID, both write, both proceed. The window is
small and it is real — and it is the same shape as `[ -e lock ] || touch lock`,
which has no defence at all.

`flock` has none of these, because the kernel is doing the bookkeeping. The only
reason to keep a PID file is to record *which* process holds the lock, for a
human — and it is fine to write one **inside** the lock, as information rather
than as the lock itself.

## `mkdir` as a lock

```bash
if mkdir /var/lock/myjob.d 2>/dev/null; then
  trap 'rmdir /var/lock/myjob.d' EXIT
else
  exit 0
fi
```

`mkdir` is **atomic**: it either creates the directory or fails with `EEXIST`,
with no window in between.

```console
  first  mkdir: acquired
  second mkdir: refused rc=1 - atomic
```

That makes it a real lock, and it is the portable answer where `flock` is not
available — including inside a shell that has no spare descriptors, and on
filesystems where `flock` semantics are unreliable, such as some network mounts.

Its weakness is the same as the PID file's: **it goes stale.** The `rmdir` is in
a trap, and a trap does not run on `SIGKILL`. Use it when you cannot use `flock`,
and expect to clean up after crashes.

## The four, side by side

| | Survives SIGKILL | Atomic | Needs a tool | Stale-proof |
|---|---|---|---|---|
| `flock` | **yes** | yes | `flock`, or a shell with `exec` | **yes** |
| `mkdir` | no | **yes** | none | no |
| PID file | no | no | none | no |
| `[ -e ] \|\| touch` | no | **no** | none | no |

The last row is not a lock. It is a comment about intent with a race in the
middle, and it appears in production more often than the other three combined.

:::objective{id=OBJ-B08.8.2}
:::

:::objective{id=OBJ-B08.8.4}
:::

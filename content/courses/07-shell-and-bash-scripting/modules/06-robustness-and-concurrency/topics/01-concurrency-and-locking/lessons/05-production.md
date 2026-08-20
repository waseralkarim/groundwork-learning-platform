---
topic: topic.concurrency-and-locking
section: production
title: Deciding what "already running" should mean
order: 5
mode: explain
---

## The question before the lock

"Should this script take a lock" is the second question. The first is **what
should happen when a run is already going**, and there are four different right
answers.

**Skip.** The work is periodic and the next run will pick it up anyway — a
metrics scrape, a cache warm, a report that reflects current state. `flock -n`
and `exit 0`. This is the common case and the safest default.

**Queue.** Every run must happen, and order matters — applying a batch of
migrations, processing a per-run input file. Blocking `flock`. The hazard is a
pile-up: if runs arrive faster than they complete, the queue grows without
limit, and the machine falls over hours later for reasons that look unrelated.
Blocking needs a monitor on how long the wait was.

**Wait a bit, then give up.** The work is worth doing slightly late but not much
— `flock -w 30`. Say so on stderr when you give up, or a job that quietly never
runs looks exactly like one that runs fine.

**Refuse loudly.** Concurrency here means something is already wrong: a deploy,
a schema change, anything with a human waiting. `flock -n` and **exit non-zero
with a message**, so it pages rather than passing.

The mistake is picking one by habit. A scrape that queues turns a slow morning
into an outage; a deploy that skips silently tells you it succeeded.

## Where the lock file lives

```bash
LOCK=/var/lock/myjob.lock          # or /run/lock — cleared on reboot
```

Not in `/tmp`, where a predictable name is a symlink-attack surface and a tmpfiles
cleaner may remove it while it is held. Not in the working directory, which may
be a different path for different runs — two runs holding "the same" lock at two
paths is two locks.

The name should identify the **resource**, not the script. Two scripts writing
the same report must share one lock; one script writing per-customer files can
lock per customer and run in parallel, which is a lock choice that buys
throughput rather than costing it.

And once more, because it is the failure this topic exists for: **never delete
the lock file.** Not in a trap, not in a cleanup job, not by hand.

## What a lock does not give you

**It is advisory.** Only processes that call `flock` are excluded. A colleague's
one-off `psql` at 2am is not.

**It is per-machine.** Two hosts running the same cron entry share nothing. That
is the usual reason a "locked" job still runs twice, and the fix is a lock
somewhere both can see — a database row, a lease in Consul or etcd, a Kubernetes
`CronJob` with `concurrencyPolicy: Forbid` — or, more often, deciding that only
one host should run it.

**It does not make the work safe to interrupt.** A run that holds the lock and is
killed halfway leaves whatever it had done. The lock is released correctly, and
the next run starts on top of a half-finished state. That is what idempotency is
for, and it is a separate property.

**It does not bound the run.** A holder that hangs holds the lock forever, and
every subsequent run skips. A stuck job that reports "already running" every five
minutes for a week is a common and very quiet outage — so pair the lock with a
`timeout -k`, and alert on consecutive skips.

## The shape worth copying

```bash
#!/bin/bash
set -eEuo pipefail

LOCK=/var/lock/report.lock
exec 9>"$LOCK"
if ! flock -n 9; then
  echo "report: another run holds the lock, skipping" >&2
  exit 0
fi
echo "$$ $(date -Is)" >&9        # information, INSIDE the lock — not the lock

WORK=$(mktemp -d)
cleanup() { [ -n "${WORK:-}" ] && rm -rf "$WORK"; WORK=; }   # NOT the lock file
trap cleanup EXIT
trap 'cleanup; exit 143' TERM

timeout -k 30 3600 build_report > "$WORK/report.csv"
[ -s "$WORK/report.csv" ] || { echo "empty report" >&2; exit 1; }

tmp=$(mktemp /srv/reports/report.csv.XXXXXX)
mv "$WORK/report.csv" "$tmp"
mv -f "$tmp" /srv/reports/report.csv       # atomic replace
```

Every line answers something this course has met: the descriptor held open; the
skip message on stderr; the PID written *into* the lock file as information;
cleanup that removes the work directory and **not** the lock; a signal handler
that exits (B08.5); `timeout -k` so a hang cannot hold the lock forever; the
output asserted before it is published; and an atomic rename so no reader ever
sees a half-written report.

## Testing it

Concurrency bugs do not appear under a single run, which is why they reach
production. Three tests, all cheap:

```bash
./job.sh & ./job.sh & wait          # do two runs both do the work?
./job.sh & sleep 0.2; kill -9 %1; ./job.sh    # does the lock survive a SIGKILL?
./job.sh & sleep 0.2; rm -f "$LOCK"; ./job.sh # does deleting the file break it?
```

The third is the one nobody writes, and it is the one that fails.

## What to take from this topic

- **A scheduled script will eventually run twice.** Design for it before it
  happens.
- **`exec 9>FILE` then `flock -n 9`** — the descriptor must stay open.
- **A lock lives on the inode.** Deleting the lock file silently ends mutual
  exclusion; never remove it.
- **`flock` cannot go stale**; a PID file, `mkdir` and `noclobber` all can,
  because the kernel is not the one keeping the record.
- **`[ -e lock ] || touch lock` is not a lock** — it is a race with a comment.
- **`timeout` exits 124 and sends a request**; `-k` sends `SIGKILL` and gives
  137. Only the second is a guarantee.
- **A non-zero status means "I did not hear that it worked"**, so retrying a
  non-idempotent operation may repeat it. Use an idempotency key, or record the
  step before the next one.
- **Backoff needs jitter and two caps** — per-delay and total.
- **A lock is per-machine and advisory**, and it does not make the work safe to
  interrupt.

:::objective{id=OBJ-B08.8.7}
:::

:::objective{id=OBJ-B08.8.8}
:::

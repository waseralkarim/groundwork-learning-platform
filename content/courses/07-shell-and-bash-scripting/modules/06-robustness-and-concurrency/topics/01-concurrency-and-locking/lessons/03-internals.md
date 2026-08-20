---
topic: topic.concurrency-and-locking
section: internals
title: Timeouts that stop nothing, and retries that charge twice
order: 3
mode: explain
---

:::diagram{src=../diagrams/lock-on-inode.mmd caption="A flock is held on an open file description, which points at an inode. Remove the path and the next run opens a different inode — so both locks succeed and neither sees the other."}
:::

## What `timeout` actually promises

```console
$ timeout 0.2 sleep 5;  echo $?     → 124
$ timeout 5 true;       echo $?     → 0
```

**124** means the time limit was reached. Any other non-zero status is the
command's own. That distinction matters to a wrapper: 124 is "took too long",
1 is "tried and failed", and they usually deserve different responses.

But 124 does not mean the process stopped.

```console
$ watchdog.sh 1
importer did not finish in 1s - terminated (rc=124)

$ cat importer.log
importer: started pid 28
importer: batch 1 written
importer: ignoring TERM, batch in progress
importer: batch 2 written
...
importer: FINISHED WRITING ALL BATCHES
```

`timeout` sends **`SIGTERM`**, which is a request. The importer installs a
handler — a reasonable thing for something mid-batch to do — and carries on. It
wrote every batch. The watchdog reported a termination that never happened, and
exited 124, and a supervisor reading that status believes the job was stopped.

`-k` adds a second signal that cannot be caught:

```console
$ timeout -k 0.2 1 ./importer; echo $?     → 137
$ cat importer.log
importer: batch 1 written
importer: ignoring TERM, batch in progress
importer: batch 2 written        ← and nothing more
```

**137 is 128 + 9** — killed by `SIGKILL`. The grace period between the two
signals is what lets a well-behaved process finish its batch and exit cleanly,
while guaranteeing that a badly-behaved one still stops.

So: **`timeout LIMIT` is a request; `timeout -k GRACE LIMIT` is a guarantee.**
On anything whose whole purpose is to bound a runaway, `-k` is not optional.

:::warning
A trap handler **returns**, so a signal does not necessarily end even a
cooperative process — B08.5 measured this. A `sleep` interrupted by `SIGTERM`
returns early, the handler runs, and execution continues at the next line. A
handler that means to stop must `exit`.
:::

## Which operations are safe to retry

A retry loop is the standard answer to a flaky dependency, and it is only safe
for operations that are **idempotent** — applying them twice has the same effect
as applying them once.

The dangerous case is not a failure. It is a **lost response**:

```bash
charge_once() {
  echo "charge" >> "$LEDGER"     # the action succeeds...
  return 1                        # ...and the reply never arrives
}
for attempt in 1 2 3; do charge_once && break; done
```

```console
  attempt 1 failed, retrying
  attempt 2 failed, retrying
  attempt 3 failed, retrying
giving up after 3 attempts
$ wc -l < ledger.txt
3
```

Three charges, and the script reports failure. **A non-zero status means "I did
not hear that it worked", not "it did not work"** — and every retry of a
non-idempotent operation is a second attempt at something that may already have
happened.

Roughly:

| Usually safe | Usually not |
|---|---|
| `GET`, `HEAD` | `POST` that creates something |
| `PUT` to a fixed path | appending to a file or a queue |
| `mkdir -p`, `ln -sfn` | `mkdir` without `-p` |
| `rsync -a --delete` | `tar --append` |
| Setting a value | Incrementing a counter |
| `DELETE` by id | Charging, emailing, paging |

**The fix for the unsafe ones is an idempotency key**: generate an identifier
before the first attempt, send it with every retry, and let the far side reject a
duplicate. Where you cannot — no API support, no shared store — record that the
step happened *before* doing the next thing, and check that record on the way in.

## Backoff, and why jitter matters

```bash
delay=1
for attempt in 1 2 3 4 5; do
  if do_the_thing; then break; fi
  sleep "$delay"
  delay=$((delay * 2))
done
```

Doubling gives 1, 2, 4, 8, 16 — 31 seconds across five attempts, with most of the
waiting where it is most likely to help.

The missing piece is **jitter**. Every client that failed at the same moment
retries at the same moments, so a service that has just come back is hit by the
entire fleet at once and falls over again. That is a **thundering herd**, and it
is caused by the retry logic being correct and identical everywhere.

```bash
sleep "$(( delay + RANDOM % delay ))"
```

Two more constraints worth writing down. **Cap the delay**, or the eighth retry
waits two minutes. And **cap the total**, because a retry loop with no ceiling
turns a fast failure into a hang — and a job that hangs is harder to diagnose
than one that fails.

## Only retry what is worth retrying

```bash
case $status in
  0)          return 0 ;;
  22|404)     return "$status" ;;   # it will not become true later
  28|52|56)   ;;                    # timeout / empty / recv error — retry
  *)          return "$status" ;;
esac
```

A 404 will still be a 404 in eight seconds. Retrying a permanent failure spends
the whole budget discovering something the first attempt already knew, and delays
the alert by exactly the length of the loop.

:::objective{id=OBJ-B08.8.5}
:::

:::objective{id=OBJ-B08.8.6}
:::

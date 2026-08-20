---
topic: topic.where-output-goes
section: production
title: Logging a job you will read at 3am
order: 5
mode: explain
---

Everything in this topic converges on one design question: when a scheduled job
fails at 02:00, what is on disk at 08:00, and can you tell what happened from
it?

## The default is worse than nothing

```bash
0 2 * * * /opt/jobs/nightly.sh >> /var/log/nightly.log 2>&1
```

That is the standard line, and it has three problems.

**No timestamps.** A log without them cannot be correlated with anything — not
with an alert, not with a deploy, not with another service's log. Whatever you
do about the rest, add these.

**Everything in one stream.** Results and diagnostics are interleaved, so "did
this produce output" and "did it complain" become one question you cannot answer
separately.

**It grows forever.** `>>` with no rotation is a disk-full incident scheduled for
some unspecified date.

A better default:

```bash
0 2 * * * /opt/jobs/nightly.sh >> /var/log/nightly.out 2>> /var/log/nightly.err
```

Two files, and reading `nightly.err` in the morning is now a meaningful action.
Add rotation, and add timestamps inside the script.

## Timestamps, cheaply

```bash
log() { printf '%s %s\n' "$(date -Is)" "$*"; }
log "starting reconciliation"
```

Four lines including the blank one, and it makes every subsequent question
answerable. `date -Is` gives an ISO-8601 timestamp that sorts correctly and that
every log tool understands.

For stamping a *stream* rather than your own messages:

```bash
cmd | while IFS= read -r l; do printf '%s %s\n' "$(date -Is)" "$l"; done
```

That forks a `date` per line, which is fine at human rates and not at thousands
of lines a second. `ts` from moreutils does it properly if it is available.

## Do not lose the exit status

The pipeline above has already destroyed it: piping into a `while` loop means
the script's status is the loop's. Combine that with cron and you get a job that
fails silently.

```bash
set -euo pipefail

if ! /opt/jobs/reconcile > "$OUT" 2> "$ERR"; then
  status=$?
  printf '%s reconcile failed with %d\n' "$(date -Is)" "$status" >&2
  exit "$status"
fi
```

And in a pipeline where the interesting command is not last:

```bash
pg_dump "$DB" | gzip > backup.sql.gz
st=("${PIPESTATUS[@]}")
[ "${st[0]}" -eq 0 ] || { echo "pg_dump failed: ${st[0]}" >&2; exit 1; }
```

`set -o pipefail` would catch that too, and `PIPESTATUS` tells you **which**
stage failed, which is the difference between an alert you can act on and one
that says "something went wrong".

:::callback{to=topic.environment-and-shell-startup}
B06.4's backup ran for eight months producing empty files, and one of the three
reasons was exactly this — `pg_dump | gzip` returns `gzip`'s status, so a failed
dump was invisible behind a successful compression of nothing.
:::

## Buffering, in the two places it bites

**Watching a live log.** `tail -f app.log | grep ERROR` block-buffers and shows
you nothing during the incident you are trying to observe. `grep
--line-buffered` fixes it, and it is worth putting in an alias rather than
rediscovering at 2am.

**A job whose output you are streaming somewhere.** If a script's output is
piped into a log shipper, the shipper receives nothing until 4–8 KB accumulate
or the job exits — so a long-running job appears to produce nothing and then
everything, and the timestamps in the log are the times things were *written*,
not the times they happened.

That second one is why in-script timestamps matter more than they look: they
record when the event occurred, independent of when the line was flushed.

For a containerised process, the equivalent question is whether the runtime is
attached to a pty. It usually is not, so **anything that behaves differently when
piped will behave the "piped" way in production** — and the difference between a
local run and a container run is exactly the difference this topic measures.

## Containers log to stdout, and that changes the rules

A container's log is whatever the main process writes to descriptors 1 and 2.
Which means:

- **A service that writes to a file inside the container logs nowhere** that
  anybody will find, and fills a writable layer that B06.3 argued should not
  exist.
- **`exec` matters.** An entrypoint that runs `cmd` as a child rather than
  `exec cmd` puts a shell at PID 1, and the shell's descriptors are what the
  runtime captures — usually fine, but it also breaks signal delivery, which is
  A02.4's territory.
- **Both streams end up in the same place** for most runtimes, so the careful
  separation above collapses. Structured output — one JSON object per line, with
  a level field — is the container-native equivalent, and it survives being
  merged.

## What to write down

For any scheduled job, the design worth defending is short:

```text
stdout  -> results, timestamped, rotated
stderr  -> diagnostics, separate file or a level field
status  -> checked explicitly, and PIPESTATUS if a pipeline is involved
buffering -> line-buffered if anything is watching it live
retention -> rotation configured, so this is not a future incident
```

Five lines, and each one corresponds to a failure this topic demonstrated.

## What to take from this topic

- **`2>&1` copies the current target of descriptor 1.** Order decides the
  outcome, and `cmd 2>&1 >file` sends errors to the terminal.
- **`>` truncates before the command runs**, so `sort f > f` empties the file.
  Some tools warn; the file is destroyed either way. Use a temp file and `&&`.
- **Every pipeline stage is a subshell**, so a variable set inside `cmd | while
  read` is gone. `< <(cmd)` avoids it.
- **A pipeline's status is its last command's.** `pipefail` and `PIPESTATUS`
  are how you find out the truth.
- **SIGPIPE is normal** — status 141 — and it interacts with `pipefail` in a way
  that will surprise you once.
- **Buffering depends on what is downstream.** Piped output is block-buffered,
  so it arrives late or not at all, and the program is behaving correctly.
- **`2>/dev/null` hides real errors for months.** Discard stderr only when you
  know which message you are discarding.

:::objective{id=OBJ-B08.2.8}
:::

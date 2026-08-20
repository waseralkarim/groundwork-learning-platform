# Restoring the database

> Not an alert. This is the procedure for the day something has gone wrong, and
> the reason it exists in advance is that nobody reads a restore procedure
> calmly.

## What is actually at risk

Two very different things live in Postgres:

| Data | If it is lost |
|---|---|
| Accounts, progress, quiz attempts, hypotheses | **Gone.** Nothing can rebuild it. |
| Courses, topics, lessons, labs, quiz questions | Rebuilt from git with one ingest. |

Backups exist for the first row. The second is a projection of `content/`, and
`docker compose exec api python -m app.content.cli ingest` recreates it exactly —
which is why a restore that brings back stale content is not a problem worth
worrying about.

This split is also why the deterministic content keys matter. Progress rows point
at content UUIDs derived from content ids, so a restore that lands alongside a
newer curriculum still resolves. `scripts/verify-restore.sh` asserts precisely
that, and it is the check that would catch a design regression.

## Taking a backup

```bash
task db:backup          # ./backups/groundwork-<timestamp>.dump
```

Custom format, compressed, `--clean --if-exists` baked in. The script reads the
dump back with `pg_restore --list` before declaring success, because a file that
nobody has opened is a guess.

Keeps the newest 14 by count, not by age: on a machine that has been off for a
month, an age-based policy deletes everything you have.

**Backups are gitignored.** They contain real accounts and password hashes.

## Testing a backup

```bash
task db:verify-restore
```

Restores into a scratch database and asserts:

- row counts match the live database
- every topic-progress row still resolves to a topic
- every account kept a usable Argon2 hash

It never touches the live database. Run it after any change to the schema or to
the ingest, and treat a failure as a data-loss incident that has not happened
yet.

## Restoring for real

```bash
task db:restore                 # dry run: prints what it would replace
task db:restore -- --yes        # does it
```

The script refuses to run without `--yes`, takes a safety dump of what it is
about to overwrite, stops the services holding connections, terminates any
remaining backends, restores, and restarts. If `pg_restore` reports errors on
real objects it stops and leaves the safety dump in place.

Afterwards:

```bash
docker compose exec api python -m app.content.cli ingest   # if content has moved on
bash scripts/smoke.sh
```

## If the restore fails

The safety dump is in `./backups/pre-restore-<timestamp>.dump`. Restoring *that*
puts you back exactly where you started:

```bash
bash scripts/restore.sh backups/pre-restore-<timestamp>.dump --yes
```

That is the entire reason it is taken. A restore that cannot be undone is a
second outage waiting behind the first.

## What this procedure does not cover

- **Point-in-time recovery.** These are periodic dumps, so the exposure is
  everything since the last one. PITR needs WAL archiving and is a different
  design — worth having before this platform holds anything a learner would be
  upset to lose.
- **Off-machine copies.** `./backups` is on the same disk as the database. A
  backup that dies with the host is not a backup, and copying these somewhere
  else is a manual step today.

Both are honest gaps rather than oversights. They are written down here so the
next person does not assume they are covered.

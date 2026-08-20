# ContentIngestFailing

> `content_ingest_errors_total` increased in the last 30 minutes.

## What it means

Ingest rewrites the projection of `content/` that every learner reads and every
progress row points at. A failed run means the database and git now disagree
about what the curriculum is.

## Urgency

**Ticket.** Nothing is broken for learners *yet* — the previous projection is
still there and still serving. What has stopped is the ability to ship content.

The exception: if the failure happened partway through a run, check whether the
transaction rolled back cleanly before deciding it is not urgent.

## Confirm the cause

```bash
docker compose exec api python -m app.content.cli lint     # is the content valid?
docker compose logs api | grep content_ingest
```

Almost every ingest failure is one of four things, in order of likelihood:

1. **Invalid content** — the linter says so, precisely, with a file and a rule.
2. **A schema change without a migration** — a new field in `schema.py` with no
   column to hold it. The traceback names the column.
3. **A duplicate content `id`** — two files claiming the same id, usually after
   a copy-paste. Deterministic keys mean the second one collides rather than
   silently overwriting.
4. **Database unavailable** — check `docker compose ps db`.

## What to do

Fix the content or the migration and re-run:

```bash
docker compose exec api python -m app.content.cli ingest
```

Ingest is idempotent and runs in one transaction, so a failed run leaves the
previous projection intact. There is no partial state to clean up, and no reason
to restore anything.

**Do not** hand-edit the curriculum tables to unblock a release. The keys are
derived from content ids; a hand-written row will be pruned by the next
successful ingest, and any progress attached to it will be orphaned.

---
topic: topic.finding-files
section: production
title: Deleting things on a schedule
order: 5
mode: explain
---

Bulk file operations are the most destructive thing most scripts do, and they
run unattended. This is the design worth defending.

## State the blast radius in one sentence

Before writing the command, write the sentence: *"this deletes files matching X
under Y, and at most N of them."* If you cannot, the predicate is not ready.

That sentence becomes three assertions:

```bash
DIR=${1:?DIR required}
case "$DIR" in
  /srv/archive/*) ;;                       # an allow-list, not a deny-list
  *) echo "refusing to operate on $DIR" >&2; exit 1 ;;
esac

count=$(tr -dc '\0' < /tmp/victims | wc -c)
[ "$count" -le 10000 ] || { echo "refusing: $count files exceeds the limit" >&2; exit 1; }
```

The path check is an **allow-list** deliberately. A deny-list of dangerous paths
is a list of the ones somebody thought of, and the first unusual value — an
empty variable expanding to nothing, a relative path, a symlink — is the one
that was not on it.

The count ceiling catches the case where the predicate is right and the input is
not: a mount that failed, a directory that filled with garbage, a date that
rolled over wrongly. A job that normally deletes 40 files and suddenly wants to
delete 400,000 should stop and ask.

## Compute the list once, then act on it

```bash
find "$DIR" -type f -name '*.log' ! -newermt "-${DAYS} days" -print0 > "$LIST"
find_status=$?

[ "$find_status" -eq 0 ] || { echo "find could not read part of $DIR" >&2; exit 1; }

n=$(tr -dc '\0' < "$LIST" | wc -c)
printf '%s selected %d files\n' "$(date -Is)" "$n"
tr '\0' '\n' < "$LIST" | head -20

[ "$DRY_RUN" = yes ] && exit 0
xargs -0 -r rm -- < "$LIST"
```

Four properties, each answering a failure from this topic:

- **Computed once**, so nothing changes between deciding and acting. `find …
  -delete` re-walks a tree that other processes are writing to.
- **find's status is checked**, so a permission error is not silently a smaller
  deletion.
- **Printable**, so the selection can be reviewed by a human, logged, or diffed
  against yesterday's.
- **`-0 -r --`**, so hostile filenames, an empty result and a leading hyphen are
  all handled.

`DRY_RUN` as the default for a new job, flipped only once somebody has read the
list, is cheap and has prevented more incidents than any amount of care.

## Get the time predicate right, in writing

Write the policy and the predicate next to each other, because the English and
the flag disagree:

```text
policy:    delete archives after they have existed for 7 full days
predicate: ! -newermt '-7 days'          # explicit, no truncation
NOT:       -mtime +7                     # excludes 7-day-old files; means 8
```

`-mtime` truncates to whole 24-hour periods, so `+7` keeps everything for eight
days. That extra day is invisible — the job runs, reports success, and the
retention window is quietly 14% longer than the policy says. On a compliance
window that is a finding; on a disk-space job it is why the disk still fills.

`-newermt` takes a real timestamp and has no rounding, which is why it is the
form to use whenever the boundary is written down somewhere.

## Prefer not deleting

Several alternatives are cheaper than getting a delete exactly right:

- **Move to a quarantine directory** and delete that on a longer schedule. The
  first delete becomes reversible, and a wrong predicate is discovered while the
  files still exist.
- **Let the storage layer do it.** Object-store lifecycle rules, log rotation
  with `maxage`, a database TTL. They are declarative, they are visible in the
  configuration, and they do not run as root on a machine.
- **Rotate rather than delete**, so the retention count is a number of files
  rather than an age computation.

Reach for `find -delete` when none of those fit, not first.

## What to monitor

A cleanup job that deletes nothing looks identical to one that is working
perfectly on an empty backlog:

```bash
printf '%s deleted=%d remaining=%d\n' "$(date -Is)" "$deleted" "$remaining"
```

Emit both numbers every run, and alert on the shape rather than the absence:

- **deleted = 0 for N consecutive runs** where it is normally non-zero — the
  predicate has probably stopped matching.
- **deleted far above the usual range** — the predicate is matching too much.
- **remaining growing run over run** — the job is losing ground, which is the
  actual thing you care about and neither of the others will tell you.

That third one is the metric worth having. Whether the job ran is a proxy;
whether the backlog is shrinking is the outcome.

## What to take from this topic

- **`-mtime +7` means eight days.** Use `! -newermt '-7 days'` when the boundary
  is written in a policy.
- **`-exec cmd \;` ignores the command's exit status** and forks once per file.
  `-exec cmd +` batches and propagates failures.
- **find returns 1 when it could not read part of the tree**, and a pipeline
  throws that away without `pipefail`.
- **`xargs` runs on empty input** unless you pass `-r`, and **`-I{}` silently
  gives up batching**.
- **`-prune` never enters a directory**; filtering afterwards walks all of it.
- **Quote `-name` patterns**, or the shell globs them against the wrong
  directory first.
- **Compute the list, print it, then act on it** — and keep `DRY_RUN` on until
  somebody has read the output.
- **`cp -r` destroys the mtimes** a retention test depends on. Use `cp -a`.

:::objective{id=OBJ-B08.4.8}
:::

---
topic: topic.set-euo-pipefail
section: production
title: A preamble worth defending
order: 5
mode: explain
---

## The skeleton

```bash
#!/bin/bash
set -eEuo pipefail

usage() { echo "usage: $0 SOURCE DEST" >&2; exit 64; }

SOURCE=${1:?$(usage)}
DEST=${2:?$(usage)}
: "${DEPLOY_ENV:?DEPLOY_ENV must be set}"

for cmd in jq rsync; do
  command -v "$cmd" >/dev/null || { echo "$cmd is required" >&2; exit 1; }
done

WORKDIR=$(mktemp -d)
cleanup() { [ -n "${WORKDIR:-}" ] && rm -rf "$WORKDIR"; WORKDIR=; }
trap cleanup EXIT
trap 'cleanup; exit 143' TERM
trap 'cleanup; exit 130' INT
trap 'echo "failed at line $LINENO: $BASH_COMMAND" >&2' ERR

main() {
  ...
}

main "$@"
```

Every line answers a failure this course has met:

- **`-e`** — an unhandled failure stops the script rather than continuing into
  a worse state.
- **`-E`** — without it the ERR trap is silent inside functions, which is where
  you need it.
- **`-u`** — a typo'd variable name fails instead of expanding to nothing. B08.4's
  cleanup job would have refused to run rather than deleting from `/`.
- **`pipefail`** — B06.4's backup ran for eight months because `pg_dump | gzip`
  reported gzip's success.
- **`${VAR:?}`** — B06.4's nightly report died at line 40 with an obscure error
  instead of at line 6 with a sentence.
- **The tool check** — B06.2's deploy guard used `fuser`, which was absent, and
  the missing command inverted a safety check for five months.
- **`trap cleanup EXIT`** — cleanup on every path out, including an errexit
  abort.
- **Separate signal handlers that exit** — otherwise the script resumes after
  its working directory has been removed.
- **The ERR trap** — turns a silent exit into a line number and a command.
- **`main "$@"`** — the script is parsed completely before anything runs, so a
  truncated download cannot execute half of it.

That last one is worth more than it looks. A script piped from `curl` or copied
mid-write executes line by line as it arrives; wrapping the body in `main` and
calling it on the final line means a partial file does nothing at all.

## What it still cannot catch

Say this out loud when proposing the preamble, because overselling it is how it
gets blamed later.

**It catches unhandled failures, not wrong behaviour.** A `curl` that received a
404 error page with status 200, an `rm` on the wrong path, a migration applied to
the wrong database — all succeed.

**It cannot see a masked status.** `local x=$(cmd)` is the common one, and it is
the single most likely line in your codebase to be silently discarding an error.

**It is not idempotency.** A script killed halfway leaves whatever it had already
done. `set -e` decides when to stop, not how to recover.

**And it does not reach into what you call.** A child script runs with its own
options.

So the preamble is a **floor**. The rest of the work is asserting outcomes:

```bash
[ -s "$BACKUP" ]                     || { echo "backup is empty" >&2; exit 1; }
[ "$processed" -gt 0 ]               || { echo "nothing processed" >&2; exit 1; }
[ "$(running_version)" = "$WANT" ]   || { echo "deploy did not take" >&2; exit 1; }
```

**The exit status is the command's opinion of itself; the resulting state is
evidence.** Every incident in this course has turned on that distinction.

## Idempotency, and why it matters more than the preamble

A script that is safe to run twice converts "it failed halfway, now what" into
"run it again".

```bash
mkdir -p "$DIR"                        # not: mkdir, which fails if it exists
ln -sfn "$TARGET" "$LINK"              # replaces an existing link
rsync -a --delete "$SRC/" "$DEST/"     # converges rather than appends
grep -qxF "$LINE" "$FILE" || echo "$LINE" >> "$FILE"   # append once
```

The pattern is to describe the **desired state** rather than the change. That is
also the entire argument for configuration management over scripts, and meeting
it here first makes D22 land as a solution to a problem you have had rather than
a new tool.

Where a step genuinely cannot be repeated — charging a card, sending a
notification, allocating an identifier — record that it happened before doing the
next thing, and check that record on the way in.

## When to stop writing shell

The preamble is a sign of a script that has grown up. Several more signs mean it
should stop being shell:

- It has **more than a few functions**, or needs data structures beyond a list.
- It parses **structured data** — JSON, YAML — with text tools.
- It needs **real error handling**: retries with backoff, partial rollback,
  distinguishing four failure modes.
- It is **tested**, and the tests are becoming harder to write than the script.
- Multiple people are editing it and quoting bugs keep appearing.

Shell is excellent at gluing commands together and poor at everything else. The
tell is when the majority of the lines are handling errors and manipulating
strings rather than running programs.

## What to take from this topic

- **`set -e` is exempt** in every `if`/`while` condition, in `&&`/`||` operands,
  after `!`, and in non-final pipeline stages — **including inside functions
  called from those positions.**
- **`local x=$(cmd)` discards the status.** Declare, then assign.
- **`((count++))` exits the script** when count is 0. Use `count=$((count+1))`.
- **`set -u` exits 127**, and permits `${VAR:-}`, `${VAR:?}` and `"$@"`.
- **The EXIT trap runs on an errexit abort** — which is what makes it the right
  place for cleanup.
- **A signal handler must `exit`**, or the script resumes after cleanup.
- **`set -E`** or the ERR trap is silent exactly where it matters.
- **The preamble is a floor.** Assert the outcome, and prefer a script that is
  safe to run twice.

:::objective{id=OBJ-B08.5.8}
:::

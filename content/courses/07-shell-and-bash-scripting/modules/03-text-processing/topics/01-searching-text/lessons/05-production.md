---
topic: topic.searching-text
section: production
title: Parsing output you do not control
order: 5
mode: explain
---

Everything in this topic is ultimately about the same risk: **you are parsing
something whose format is not a contract.**

## The output of a command is not an API

`ps`, `df`, `kubectl get`, `docker ps` and every cloud CLI produce text designed
for humans. That format changes — a column is added, a width shifts, a value
becomes localised, a version pads differently. Nothing warns you, because
nothing promised.

Which gives a hierarchy worth applying in order:

1. **Ask for structured output if the tool offers it.** `--json`, `-o json`,
   `--format`. Then parse with a tool that understands the format.
2. **Ask for exactly the fields you want.** `ps -o pid=,rss=`, `kubectl get -o
   custom-columns=`, `docker ps --format '{{.Names}}'`. The tool does the
   splitting and cannot get it wrong.
3. **Only then** split text yourself — and count from the end with `$NF` where
   you can, because columns get added on the left.

```bash
ps -o pid=,rss= -C nginx              # two fields, no header, nothing to parse
kubectl get pods -o json | jq -r '.items[].metadata.name'
docker ps --format '{{.Names}}\t{{.Status}}'
```

Every one of those removes a whole class of bug, and they are all shorter than
the `awk` they replace.

## Where the failures actually come from

**A column moves.** A tool adds a field and every `$3` in your estate now means
something else. `$NF` and `--format` survive it; `awk '{print $3}'` does not.

**A field contains the separator.** A container name with a space, a commit
message with a comma, a path with a colon. Delimited parsing of anything
user-supplied is a guess.

**The pattern came from data.** A version string `1.2.3` matched as a regex also
matches `1x2y3`. A config value `[warn]` is a character class matching four
common letters. `grep -F` is the answer and almost nobody reaches for it.

**A search legitimately finds nothing.** Under `set -e`, that ends the script —
and the healthier the system, the earlier it happens.

## The set -e interaction, as a policy

`set -euo pipefail` is correct and it makes `grep` dangerous, so the team needs a
convention rather than a per-person habit:

```bash
# branching on the result — the usual intent
if grep -q PATTERN "$f"; then ...

# a count where zero is fine
count=$(grep -c PATTERN "$f" || true)

# deliberate: absence is acceptable here
grep PATTERN "$f" || true   # config key is optional
```

The comment on the third form is the part that scales. Without it a reviewer
cannot tell "absence is fine" from "somebody silenced a failure", and a bare
`|| true` also hides exit status **2** — a missing or unreadable file.

That is the same rule this course keeps arriving at: **the deliberate exception
needs to be marked, or it is indistinguishable from the mistake.**

## When to stop using the shell

A pipeline of four tools that each do a little is a signal, not an achievement:

```bash
grep ERROR app.log | grep -v health | awk '{print $3}' | sort | uniq -c | sort -rn
```

That is fine — it is a one-off at a terminal, and every stage is doing one thing.
What is not fine is the same chain inside a script that runs nightly, where the
input format is not guaranteed and nobody will notice when it silently produces
nothing.

Signs it is time for a real language:

- You are parsing **structured data** — JSON, YAML, XML — with `grep` and `sed`.
  Use `jq` or a language with a parser; regex cannot match nested structures and
  will succeed against malformed input.
- You need to **hold state** across lines beyond a counter.
- The transformation is more than about **ten lines** of awk.
- **Correctness matters more than convenience** — the pipeline silently
  producing nothing is an outcome somebody must notice.

And the counter-signal: a single awk program is often the right answer where a
four-stage pipeline is the wrong one. `grep | grep -v | awk | sed` is usually one
awk with two conditions, and it is faster and clearer.

## Make silence loud

The unifying failure in this topic is a command that produces **nothing** and
exits 0 — an empty field, a search with no matches, a pattern that matched the
wrong thing and then filtered everything out.

```bash
result=$(awk -F, 'NR>1 {print $3}' services.csv)
[ -n "$result" ] || { echo "no rows extracted from services.csv" >&2; exit 1; }
```

Two lines, and they convert the most common silent failure into a message with a
filename in it. The same idea as asserting a backup's size rather than its exit
status: **the tool's success is an opinion, and the output is the evidence.**

## What to take from this topic

- **grep returns 1 for "no match" and 2 for "error"**, and `set -e` cannot tell
  1 from a failure. Branch with `-q`, or `|| true` with a comment.
- **BRE and ERE invert the escaping.** Use `-E` and the patterns say what they
  mean.
- **A pattern from data needs `grep -F`.** `[warn]` as a regex matched every
  line of a sixteen-line file.
- **`cut -d' '` is wrong on command output.** Runs of spaces make empty fields,
  silently. `awk` splits on runs.
- **Count from the right** with `$NF` — columns get added on the left.
- **Prefer `--format` or `-o json`** over parsing human-readable output at all.
- **Assert that you extracted something.** Empty output plus exit 0 is this
  topic's signature failure.

:::objective{id=OBJ-B08.3.8}
:::

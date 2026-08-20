---
topic: topic.how-a-line-becomes-a-command
section: production
title: A quoting rule a team can actually follow
order: 5
mode: explain
---

Everything so far is mechanism. The production question is what rule to give a
team, and the honest answer is that "quote your variables" is not enough,
because it does not say when not to.

## The rule

**Quote every expansion, unless you are deliberately using splitting or
globbing — and when you are, say so in a comment.**

```bash
cp "$src" "$dst"                  # normal: quote
rm -- "$f"                        # normal: quote, and end option parsing

# deliberate: EXTRA_FLAGS is a list of separate flags, splitting is the point
run_tool $EXTRA_FLAGS "$input"
```

That second form is legitimate and rare. Writing it without a comment is what
makes reviewers unable to tell a decision from an oversight — and the review
comment "why is this not quoted?" is the one worth being able to answer.

The exceptions where quoting is not needed, for completeness:

- **Assignments.** `x=$f` does not word-split. Quote anyway, so the reader does
  not have to know that.
- **Inside `[[ ]]`.** Bash does not split there. Quote anyway, so the line
  survives being moved into `[ ]`.
- **Arithmetic contexts.** `$(( x + 1 ))` — no splitting.

Three exceptions, all of which you should ignore in favour of quoting
everything. Consistency is worth more than the characters.

## What it costs

Being honest about this makes the rule easier to sell. Quoting costs:

- **Two characters per expansion**, and some visual noise.
- **A genuine trap with `"$@"` versus `$@`** that people get wrong in both
  directions — over-quoting `"$*"` when they wanted `"$@"`.
- **Nothing else.** There is no performance cost and no case where correct
  quoting breaks a working script.

Against a class of bug that is silent, data-dependent and often destructive.

## Make the machine enforce it

A rule nobody checks is a preference. `shellcheck` finds unquoted expansions,
missing `-r` on `read`, `ls` parsing, and a hundred other things — and it runs
in under a second:

```bash
shellcheck -S warning scripts/*.sh
```

Add it to CI and the argument stops being about taste. Two things that make
adoption survive contact with an existing codebase:

- **Start at `-S error`, then tighten.** A first run against a mature repository
  produces hundreds of findings, and a wall of warnings gets disabled wholesale
  — the same failure mode as the integrity check in B06.2.
- **Allow inline suppressions with a reason.** `# shellcheck disable=SC2086 —
  splitting is intended, EXTRA_FLAGS is a flag list` documents the deliberate
  case, which is exactly what the rule above asks for.

And a parse check costs nothing:

```bash
bash -n script.sh      # syntax only
dash -n script.sh      # and is it actually POSIX?
```

## Defaults worth setting in every script

```bash
#!/bin/bash
set -euo pipefail
shopt -s nullglob      # unmatched patterns disappear rather than staying literal
IFS=$'\n\t'            # optional: stop splitting on spaces
```

The first two lines are near-universal advice and belong in the next module,
where `set -e`'s real behaviour gets the treatment it deserves — it has several
exemptions that surprise people.

`shopt -s nullglob` is this topic's contribution, and it prevents the loop that
runs once with a literal `*.log`.

The `IFS` line is more controversial and worth understanding rather than
copying. Removing space from `IFS` means unquoted expansions split only on
newlines and tabs, which turns many latent bugs into working code. It also means
a genuine list of space-separated flags stops splitting, which breaks the
deliberate case above. Set it if your scripts handle filenames and rarely build
argument lists; leave it alone otherwise.

## Where filenames come from

The reason this matters more now than it did twenty years ago: **filenames are
increasingly derived from user input**.

- Uploaded documents keep their original names, including spaces and Unicode.
- Object storage keys become local paths during sync.
- Branch names, ticket IDs and container tags end up in paths, and any of them
  can start with a hyphen.
- Anything round-tripped through Windows arrives with spaces as standard.

A script written against `app-2026-08-18.log` will work for years, and the day
it stops is the day somebody adds a feature you were not consulted about. That
is the shape of this whole class of bug: **it is not triggered by a change to
the script.**

## The habits that survive

- **Measure, do not reason.** `set -x` or `printf '[%s]\n' "$@"` answers "what
  did it actually receive" in one line. Every argument about quoting is settled
  by running it.
- **Quote everything; comment the exceptions.**
- **`rm -- "$f"`, always.** The `--` costs three characters and removes a whole
  class of surprise.
- **Never parse `ls`.** Use a glob if you want files in a directory, or `find
  -print0 | xargs -0` if you need recursion. `ls | wc -l` is wrong the moment a
  filename contains a newline, and this topic's lab directory contains one.
- **Know which shell.** `#!/bin/sh` is dash on Debian. Write bash and say bash.
- **Test with a hostile filename.** One file called `a file.log` and one called
  `-n` in your test fixtures catches most of this class before review does.

That last one is the highest-value habit in the topic. It costs two `touch`
commands and it converts a rare production incident into a test failure.

:::objective{id=OBJ-B08.1.8}
:::

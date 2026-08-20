---
topic: topic.set-euo-pipefail
section: overview
title: The preamble everyone copies
order: 1
mode: explain
---

```bash
#!/bin/bash
set -euo pipefail
```

Three courses of this curriculum have put that at the top of a script and moved
on. This topic is the part that was owed: **where it stops working**.

## A migration that fails and reports success

The seeded script has the preamble. Run it and a migration genuinely fails —
the database error is even printed — and this is the output:

```console
applied 001-create.sql
ERROR: relation already exists
applied 002-index.sql
applied 2 migrations
$ echo $?
0
```

The second migration did not apply. The script says it did, counts it, and exits
0. One line is responsible and it looks like an ordinary assignment.

## `set -e` has more exemptions than most people have heard of

Measured, on this machine. `rc=1` means the script stopped; `rc=0` means it
carried on past a failure:

| Construct | Result |
|---|---|
| `false` | **rc=1** — fires |
| `false \|\| true` | rc=0 — exempt |
| `! false` | rc=0 — exempt |
| `if false; then :; fi` | rc=0 — exempt |
| `while false; do :; done` | rc=0 — exempt |
| `f(){ false; }; f` | **rc=1** — fires |
| `f(){ false; }; if f; then :; fi` | rc=0 — **the failure inside f is exempt too** |
| `( false ) \|\| true` | rc=0 — exempt |
| `false \| true` | rc=0 — exempt |

The sixth and seventh rows are the same function. Calling it normally exits the
script; calling it in an `if` condition suppresses errexit **inside its body**,
so a helper that works standalone behaves differently when tested.

None of this is a bug. `set -e` is suppressed wherever the shell is already
examining the status — otherwise `if grep -q x file` could never be written. The
problem is that the rule is invisible at the call site.

:::predict{question="Under `set -e`, which of these stops the script: `x=$(false)`, or `local x=$(false)` inside a function?"}
:::

## Two constructs that produce the opposite of what you expect

```console
$ bash -c 'set -e; x=$(false); echo reached'          ; echo "rc=$?"
rc=1
$ bash -c 'set -e; f(){ local x=$(false); }; f; echo reached'  ; echo "rc=$?"
reached
rc=0
```

**`local x=$(cmd)` discards the command's exit status.** `local` is itself a
command, and its status is `local`'s — which succeeds. Adding the word `local`
to a working line silently removes the error checking, and it is the most common
way to write a variable inside a function.

And the other direction:

```console
$ bash -c 'set -e; count=0; ((count++)); echo reached' ; echo "rc=$?"
rc=1
$ bash -c 'set -e; count=0; ((count+=1)); echo reached'; echo "rc=$?"
reached
rc=0
```

**`((count++))` ends the script the first time it runs.** `((...))` returns
non-zero when the expression evaluates to zero, and `count++` is a post-increment
whose value is the *old* count — zero. So a counter in a loop kills the script on
iteration one, and `((count+=1))` does not.

## `set -u` is not what people assume either

```console
$ bash -c 'set -u; echo "$UNSET"'; echo "rc=$?"
bash: UNSET: unbound variable
rc=127
```

**127**, not 1 — the status normally meaning "command not found", which makes it
confusing in a log. And it does not object to `${VAR:-default}`, `${VAR-}` or
`"$@"` with no arguments, all of which are safe.

## What this topic covers

- Every context where errexit is exempt, measured rather than listed.
- The two constructs that mask or misreport a status.
- `set -u`, its exit code, and the forms that are deliberately allowed.
- `trap` for cleanup — including why an EXIT plus TERM handler runs **twice**,
  and why the script keeps going after the first one.
- A preamble worth defending, and an honest account of what it cannot catch.

Four labs:

- Generate the exemption table yourself, then explain the two rows that
  contradict each other.
- Find the one line masking a migration's failure, and fix it two ways.
- Watch a cleanup handler run twice and delete a directory the script is still
  using.
- Build a script skeleton and justify every line — including the ones you chose
  not to include.

:::objective{id=OBJ-B08.5.1}
:::

:::objective{id=OBJ-B08.5.2}
:::

---
topic: topic.functions-and-scope
section: production
title: Rules that pay for themselves
order: 5
mode: explain
---

## The convention

Six rules. Each one prevents a specific bug this topic has produced.

**1. Declare every variable `local`, on its own line.**

```bash
process() {
  local file=$1
  local count status=0
  local sum
  sum=$(sha256sum "$file" | cut -d' ' -f1)
  ...
}
```

`local` because a helper reusing `i` or `count` corrupts its caller silently.
On its own line because `local sum=$(cmd)` discards `cmd`'s exit status —
SC2155, from B08.5. Note `local file=$1` is fine: `$1` is not a command, so
there is no status to lose.

**2. Name parameters at the top.** `local file=$1` beats `$1` scattered through
twenty lines, because it documents the signature and it is the only place a
reader has to look to find out what the function takes.

**3. Return a status; print a value.** A function is either a question or a
producer. If it is a question, `return 0`/`return 1` and let the caller write
`if`. If it is a producer, print one thing to stdout — and put diagnostics on
stderr, so `$( )` captures the value and not the commentary.

**4. Never end a function with a bare `echo`** unless you mean "always succeed".
Add an explicit `return` if the status matters.

**5. Wrappers use `command`.** Anything named after a real tool must call it
with `command`, or it calls itself.

**6. `exit` only in `main`, `usage` and `die`.** A library function that exits
takes the caller's cleanup with it.

## What to check in review

A short list that finds most of it:

- `local x=$(...)`, `declare/export/readonly x=$(...)` — masked status.
- Any loop or accumulator inside `cmd | while read` — the result is discarded.
- A function whose last line is `echo` and whose status is then tested.
- A variable used in a helper that the helper never declares — is it a parameter
  the author forgot to pass?
- `exit "$count"` or `return "$count"` — one byte.
- A function named after a tool, without `command`.

`shellcheck` catches the first mechanically (SC2155) and warns on the piped-loop
shape (SC2031). The rest are read.

## Where dynamic scope is actually useful

It is not only a hazard. Two legitimate uses:

**Configuration by convention.** A `log` helper that reads `$LOG_LEVEL` or
`$stage` without being passed them is fine *when that is documented* — it is how
`PS4`, `IFS` and `LC_ALL` work, and threading them through every call would be
worse.

**Scoped overrides.** Because `local` covers everything a function calls, a
caller can change behaviour for one subtree and nothing else:

```bash
run_quietly() {
  local LOG_LEVEL=error
  "$@"                       # every helper below sees the quieter level
}
```

That is genuinely elegant and impossible with lexical scope. The rule is that
the *reading* function must document what it reads — an undocumented read is the
`targt` bug waiting to happen.

## When a function should be a script

A function is the right unit while it stays inside one file's concerns. Reach
for a separate script when:

- Another script needs it — sourcing a library to get one function drags in
  everything else in the file, including its side effects at load time.
- It needs its own `set` options. Options are per-shell, so a function cannot
  turn on `errexit` for itself without changing the caller.
- It should be testable in isolation, or runnable by hand during an incident.
- It is long enough that its `local` declarations no longer fit on one screen.

And the reverse: a *script* should be a function when it is only ever called
from one place and the fork costs more than it buys.

## What to take from this topic

- **Scope is dynamic.** A called function reads and writes its caller's
  variables, however far up. `local` hides a name for the call **and everything
  it calls** — it does not isolate.
- **`$( )`, `( )` and every pipeline stage fork.** Assignments inside them are
  discarded; only output and status come back.
- **`cmd | while read` throws away the loop's work.** Use `< <(cmd)`.
- **A function returns its last command's status** unless told otherwise, so a
  trailing `echo` always succeeds.
- **`return` ends a function; `exit` ends the script**, including from inside a
  function.
- **The exit status is one byte.** `exit 256` is a success; 126, 127 and 128+N
  are already taken.
- **A wrapper without `command` calls itself**, and `FUNCNEST` is unset by
  default.
- **`unset f` removes the variable, not the function.**

:::objective{id=OBJ-B08.6.7}
:::

:::objective{id=OBJ-B08.6.8}
:::

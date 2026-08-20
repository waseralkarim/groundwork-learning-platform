---
topic: topic.set-euo-pipefail
section: internals
title: Cleanup that runs, and runs twice
order: 3
mode: explain
---

A script that creates a temporary directory must remove it — on success, on
failure, and when something kills it. `trap` is how, and it has two behaviours
that surprise people.

## The EXIT trap runs on an errexit abort

```console
$ bash -c 'set -e; trap "echo cleanup ran" EXIT; false; echo NOT reached'
cleanup ran
```

That is the property that makes the pattern work: cleanup happens whether the
script finished, failed a command, or called `exit` itself.

The standard shape:

```bash
WORKDIR=$(mktemp -d)
cleanup() { rm -rf "$WORKDIR"; }
trap cleanup EXIT
```

Three lines, and the temporary directory is gone on every path out. `mktemp -d`
rather than a fixed path, because a predictable name in `/tmp` is both a
collision and a symlink-attack surface.

## Adding signals makes it run twice

```console
$ trap cleanup EXIT INT TERM
...
deploying into /tmp/tmp.yCW
cleanup: removing /tmp/tmp.yCW      ← the TERM handler
deploy complete                      ← the script CARRIED ON
cleanup: removing /tmp/tmp.yCW      ← the EXIT handler
```

Two things went wrong and only one is the double-run.

**The handler ran twice** because `TERM` fired it and then `EXIT` fired it again
on the way out. For `rm -rf` that is harmless; for a handler that releases a
lock, posts a notification or decrements a counter, it is not.

**And the script continued.** A trap handler returns, and execution resumes at
the point of interruption — so the deploy printed `deploy complete` *after* its
working directory had been deleted. Anything the script did next would have been
operating on a directory that no longer existed.

The fix is for the signal handler to exit explicitly, which also gives the right
exit status:

```bash
cleanup() { rm -rf "$WORKDIR"; }
on_signal() { cleanup; exit 143; }     # 128 + 15 for SIGTERM

trap cleanup EXIT
trap on_signal INT TERM
```

Or, if one handler is preferred, make it idempotent and have it exit:

```bash
cleanup() {
  [ -n "${WORKDIR:-}" ] && rm -rf "$WORKDIR"
  WORKDIR=
}
trap cleanup EXIT
trap 'cleanup; exit 143' TERM
```

Blanking the variable makes a second call a no-op, which is the general
technique: **a cleanup handler should be safe to run twice**, because you cannot
always control how many times it fires.

## The ERR trap needs `set -E`

```console
$ bash -c 'set -e;  trap "echo FIRED" ERR; f(){ false; }; f'
                                                  ← nothing
$ bash -c 'set -eE; trap "echo FIRED" ERR; f(){ false; }; f'
FIRED
```

An ERR trap is **not inherited by functions, subshells or command
substitutions** unless `set -E` is given. Without it the trap is silent in
exactly the places where failures are hardest to see — which is the opposite of
useful.

If you use an ERR trap for diagnostics, `set -eE` is the correct preamble:

```bash
set -eEuo pipefail
trap 'echo "failed at line $LINENO: $BASH_COMMAND" >&2' ERR
```

`$BASH_COMMAND` holds the command that failed and `$LINENO` its line, which
turns errexit's silent exit into a message naming the problem. That single line
addresses the most common complaint about `set -e` — that it exits without
saying why.

## What the preamble cannot catch

Being honest about this is what makes it worth using.

**It catches unhandled failures, not wrong behaviour.** A command that succeeds
while doing the wrong thing — `rm` on the wrong path, a `curl` that received an
error page with status 200 — passes every check.

**It cannot see a masked status.** `local x=$(cmd)`, a non-final pipeline stage
without `pipefail`, anything inside an `if` condition.

**It does not make a script idempotent or safe to interrupt.** A script killed
halfway leaves whatever it had done; errexit governs when to stop, not how to
recover.

**And it does not apply to what the script calls.** A child script with its own
shebang runs with its own options, so `set -e` here says nothing about the tool
you just invoked.

Which gives the honest framing: **`set -euo pipefail` converts a class of silent
failure into a loud one.** It is a floor, not a guarantee, and the remaining work
is asserting outcomes — that the file exists and is a plausible size, that the
count is non-zero, that the version now running is the one you deployed.

## Assertions are the other half

```bash
[ -s "$OUT" ]              || { echo "output is empty" >&2; exit 1; }
[ "$count" -gt 0 ]         || { echo "nothing processed" >&2; exit 1; }
[ "$(running_version)" = "$WANT" ] || { echo "deploy did not take" >&2; exit 1; }
```

Every one of those catches something the preamble structurally cannot, and this
course has now met each of them as a real incident: an empty backup that exited
0, a cleanup that processed nothing, a rollback that silently did not happen.

The pattern is always the same. **The command's exit status is its opinion of
itself; the resulting state is evidence.**

:::objective{id=OBJ-B08.5.7}
:::

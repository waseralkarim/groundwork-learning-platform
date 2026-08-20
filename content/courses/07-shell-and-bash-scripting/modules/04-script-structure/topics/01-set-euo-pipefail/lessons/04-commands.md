---
topic: topic.set-euo-pipefail
section: commands
title: The preamble, line by line
order: 4
mode: do
---

## The options

```bash
set -e                 # exit on an unhandled non-zero status
set -u                 # fail on an unset variable (exits 127)
set -o pipefail        # a pipeline's status is its last non-zero one
set -E                 # functions inherit the ERR trap
set -x                 # trace: print each command after expansion
set -n                 # parse only, run nothing

set -euo pipefail      # the usual three
set -eEuo pipefail     # add -E if you use an ERR trap

set +e                 # turn one back off
```

Query and restore, when a section genuinely needs different options:

```bash
set +e
risky_command
status=$?
set -e
```

Better, where possible, is to handle it inline rather than toggling — `command
|| status=$?` keeps the option set intact.

## Checking a status without dying

```bash
if cmd; then ...                 # branch on it
cmd || true                      # ignore it — comment WHY
cmd || status=$?                 # capture it
status=0; cmd || status=$?       # capture, with a defined default

if ! cmd; then                   # the negated branch
  echo "cmd failed" >&2
fi
```

`cmd || true` needs a comment saying which case it covers. Without one, a
reviewer cannot tell "failure is acceptable here" from "somebody silenced a
problem" — the same rule as the deliberate unquoted expansion in B08.1.

## Variables that must exist

```bash
: "${DEPLOY_ENV:?DEPLOY_ENV must be set}"    # fail now, with a message
DIR=${1:?usage: deploy.sh DIR}               # required positional
PORT=${PORT:-8080}                           # optional, with a default
readonly DIR                                  # cannot be reassigned later
```

`${VAR:?message}` at the top beats `set -u` catching it later, because the
message names the variable and the fix.

## Assignments that keep the status

```bash
# WRONG — local succeeds regardless, the failure is discarded
local x=$(cmd)

# RIGHT — declare, then assign
local x
x=$(cmd)
```

The same applies to `declare`, `export`, `readonly` and `typeset`. `shellcheck`
reports it as **SC2155**, which is the single most valuable check it performs on
most codebases.

## Arithmetic that does not kill the script

```bash
count=$((count + 1))     # always safe
: $((count++))           # safe — the : swallows the status
((count += 1))           # safe until the result is genuinely 0
((count++))              # UNSAFE — returns 1 when count was 0
((count++)) || true      # safe, and noisy
```

`count=$((count + 1))` is the form to standardise on. It is an assignment, not a
command, so there is no status to trip over.

## Cleanup

```bash
WORKDIR=$(mktemp -d)
TMPFILE=$(mktemp)

cleanup() {
  [ -n "${WORKDIR:-}" ] && rm -rf "$WORKDIR"
  WORKDIR=
}
trap cleanup EXIT
trap 'cleanup; exit 143' TERM      # 128 + 15
trap 'cleanup; exit 130' INT       # 128 + 2
```

Separate handlers for signals, because a signal handler must **exit** — otherwise
the script resumes after cleanup has already removed what it was using. And make
the handler idempotent, since EXIT will fire after a signal handler has already
run it.

```bash
trap -p              # show the traps currently set
trap - EXIT          # remove one
```

## Diagnostics when errexit fires

```bash
set -eEuo pipefail
trap 'echo "failed at line $LINENO: $BASH_COMMAND" >&2' ERR
```

`set -E` is required or the trap is silent inside functions. `$BASH_COMMAND` is
the command that failed. This turns a silent exit into a message naming the line
and the command, which is the main complaint about `set -e` answered in one line.

```bash
PS4='+ ${BASH_SOURCE##*/}:${LINENO}: '
set -x
```

For tracing, `PS4` makes each traced line say where it came from.

## Checking a script before running it

```bash
bash -n script.sh            # syntax only
bash -x script.sh            # trace it
shellcheck script.sh         # SC2155 and about two hundred others
shellcheck -s bash -S warning script.sh
```

`shellcheck` is not installed on this image, so no lab depends on it — but in a
repository it is the cheapest way to enforce most of this topic mechanically.

## Assertions worth writing

```bash
[ -s "$OUT" ]      || { echo "empty output" >&2; exit 1; }
[ "$n" -gt 0 ]     || { echo "nothing processed" >&2; exit 1; }
[ -d "$DIR" ]      || { echo "not a directory: $DIR" >&2; exit 1; }
command -v jq >/dev/null || { echo "jq is required" >&2; exit 1; }
```

The last one belongs near the top. A missing tool discovered at line 3 is a
message; discovered at line 80, it is a half-finished operation.

:::try{lab=when-errexit-fires}
:::

:::objective{id=OBJ-B08.5.8}
:::

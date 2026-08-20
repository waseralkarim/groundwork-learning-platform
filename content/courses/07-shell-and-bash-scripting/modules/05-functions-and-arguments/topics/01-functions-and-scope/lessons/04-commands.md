---
topic: topic.functions-and-scope
section: commands
title: The forms worth knowing
order: 4
mode: do
---

## Defining and inspecting

```bash
name() { ...; }              # define — POSIX, use this one
type -t name                 # alias | function | builtin | file | (nothing)
declare -f name              # print one function's source
declare -F                   # list every function name
unset -f name                # remove it — plain `unset` removes the VARIABLE
export -f name               # make it visible to child bash processes
```

`declare -f` on a function you did not write is the fastest way to find out what
a wrapper in someone's `.bashrc` is actually doing.

## Bypassing a function

```bash
command ls -l                # skip functions; run the builtin or PATH executable
builtin cd /tmp              # skip functions; run the shell's own cd
\ls                          # skip ALIASES only — does nothing to a function
```

The wrapper form that does not recurse:

```bash
ls() { command ls --color=auto "$@"; }
```

```bash
FUNCNEST=10                  # bound recursion; UNSET by default
```

Set it before testing anything recursive. Without it a self-calling function
runs until bash exhausts memory.

## Returning

```bash
return                       # the status already in $?
return 0                     # success
return 1                     # failure — 1 to 125 are yours
exit 1                       # ends the SCRIPT, not the function

die() { echo "$*" >&2; exit 1; }     # exit is correct here
```

Both `return` and `exit` truncate to one byte, so `return 256` is a success.

## Scope

```bash
local x                      # declare, then assign — keeps the status (SC2155)
x=$(cmd)

local x y z                  # several at once
local -a items               # an array
local -A byname              # an associative array
local -n _out=$1             # a nameref; the _ prefix avoids a circular reference
local -r frozen=value        # read-only for this call
declare -g NAME=value        # assign globally from inside a function
```

`local` is valid in `dash` as well as bash, despite not being POSIX — so it is
safe in `#!/bin/sh` scripts on Debian-family systems. `local -n` and `local -A`
are bash only.

## Keeping an assignment alive

```bash
while read -r line; do ...; done < <(command)    # process substitution
while read -r line; do ...; done < file          # a plain redirect
mapfile -t lines < <(command)                    # read the whole thing at once
shopt -s lastpipe                                # last pipeline stage in this shell

( cd /tmp && do_thing )                          # a subshell ON PURPOSE — the cd
                                                 # is undone when it ends
```

The last one is the case where forking is the feature: anything that changes
directory, sets options or exports variables can be wrapped in `( )` so it
cannot leak.

## Checking a function's status

```bash
if is_healthy "$svc"; then ...          # branch on it
is_healthy "$svc" || return 1           # propagate it
is_healthy "$svc"; status=$?            # capture it
```

Remember B08.5: an `if` condition suppresses errexit for the **whole body** of
the function it calls.

## Diagnostics

```bash
declare -p x                 # show a variable's value AND its attributes
declare -p                   # every variable in scope, with attributes
set -x                       # trace; function calls appear as they run
caller                       # inside a function: the caller's line and source
FUNCNAME[0]                  # the current function's name; [1] is its caller
BASH_LINENO BASH_SOURCE      # parallel arrays — the whole call stack
```

A stack trace in four lines:

```bash
trace() {
  local i
  for ((i = 1; i < ${#FUNCNAME[@]}; i++)); do
    echo "  at ${FUNCNAME[i]} (${BASH_SOURCE[i]}:${BASH_LINENO[i-1]})" >&2
  done
}
```

Called from an ERR trap — with `set -E`, per B08.5 — that turns a silent exit
into the path the shell took to get there.

:::try{lab=where-values-disappear}
:::

:::objective{id=OBJ-B08.6.1}
:::

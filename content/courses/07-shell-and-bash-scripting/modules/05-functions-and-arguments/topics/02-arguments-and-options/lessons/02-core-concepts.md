---
topic: topic.arguments-and-options
section: core-concepts
title: What the shell hands you
order: 2
mode: explain
---

## The positional parameters

```console
$ set -- a "b c" d
$ echo "$#"                          → 3
$ printf '[%s]' "$@"; echo           → [a][b c][d]
$ printf '[%s]' "$*"; echo           → [a b c d]
$ printf '[%s]'  $@ ; echo           → [a][b][c][d]
$ printf '[%s]'  $* ; echo           → [a][b][c][d]
```

Four expansions, three different answers. Only **`"$@"`** reproduces what the
caller actually typed. B08.1 established why — unquoted expansions are word-split
— and the consequence here is the rule: **forward arguments with `"$@"`, always.**

`"$*"` joins them into a single word using the **first character of `IFS`**:

```console
$ ( IFS=:; printf '[%s]' "$*" )      → [a:b c:d]
```

Which makes `"$*"` right for exactly one thing — building a message:

```bash
die() { echo "$0: $*" >&2; exit 1; }      # one string, joined with spaces
```

Slices work too:

```console
$ printf '[%s]' "${@:2}"; echo       → [b c][d]
$ printf '[%s]' "${@: -1}"; echo     → [d]
```

The space in `${@: -1}` is required — `${@:-1}` is the use-a-default form and
means something else entirely.

:::note
**`$0` is not `$1`.** It is the name the shell was invoked with — a path for a
script, `-bash` for a login shell, and whatever the caller chose when a program
`exec`s something. `$#` does not count it and `shift` never touches it. Do not
use it for anything but messages, and use it in `usage` rather than hard-coding
the script's name, so a renamed or symlinked copy still prints something true.
:::

## `shift` is all-or-nothing

```console
$ set -- one two three
$ shift 2; echo "rc=$? \$#=$# [$*]"
rc=0 $#=1 [three]

$ set -- one two three
$ shift 5; echo "rc=$? \$#=$# [$*]"
rc=1 $#=3 [one two three]
```

Asked to shift further than it can, `shift` **returns 1 and does nothing at
all** — it does not shift what it can and stop. So a parser doing `shift 2` to
consume an option and its value leaves *everything* in place when the value is
missing, and the loop reads the same argument again.

Two consequences:

- Under `set -e`, a `shift` past the end **ends the script**, silently, with no
  message. That is B08.5's rule meeting this one.
- A hand-rolled parser must check `$#` before shifting a pair, not after.

```bash
--out) [ $# -ge 2 ] || die "--out needs a value"; out=$2; shift 2 ;;
```

## `--` ends the options

Every argument after `--` is an operand, however it starts:

```bash
grep -- -v file          # search for the literal string "-v"
rm -- -rf                # delete a file called -rf
myscript -- --verbose    # pass --verbose through as an operand
```

This is the only reliable way to handle a filename beginning with a dash, and it
is why `find … -exec rm -- {} +` and `git checkout -- FILE` are written that way.
A parser you write must honour it; `getopts` and `getopt(1)` both do.

## Resetting the list

```bash
set -- x y z          # $1=x $2=y $3=z
set --                # $#=0
set -- "${files[@]}"  # load an array into the positional parameters
eval set -- "$parsed" # the getopt(1) idiom
```

`set --` is how you rebuild the argument list after parsing, and the leading
`--` matters: without it, `set "$@"` would read an argument beginning with `-`
as an option **to `set` itself**.

## Where a script gets its input

Arguments are not the only channel, and choosing well is part of the design:

| Channel | Right for |
|---|---|
| Arguments | what changes per invocation — the target, the flags |
| Environment | ambient context and **secrets** — `DEPLOY_ENV`, tokens |
| stdin | data, especially streamed or large |
| A config file | many settings, versioned, shared between runs |

The strong rule: **a secret goes in a file, or failing that the environment —
never in an argument.** `/proc/PID/cmdline` is world-readable:

```console
$ stat -c '%A %U:%G' /proc/self/cmdline
-r--r--r-- learner:learner
```

so `ps` shows every argument to every user on the machine for as long as the
process runs. The environment is better — B06.4 measured `/proc/PID/environ` as
readable only by the owner — but it still leaks to children and into crash
dumps, so a file with restrictive permissions beats both.

:::objective{id=OBJ-B08.7.1}
:::

:::objective{id=OBJ-B08.7.2}
:::

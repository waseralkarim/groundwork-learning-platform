---
topic: topic.functions-and-scope
section: core-concepts
title: Defining, finding and returning
order: 2
mode: explain
---

## Two syntaxes, one of which is portable

```bash
greet() { echo "hello $1"; }        # POSIX — works everywhere
function greet { echo "hello $1"; } # bash/ksh only
function greet() { ... }            # both, and portable to neither
```

Use the first. The braces need whitespace around them and the last command needs
a terminator, which is why `f() { echo hi; }` has a semicolon before the closing
brace and `f() { echo hi }` is a syntax error.

A definition is not a declaration — it is a **command that runs**. The shell
reads the file top to bottom, and a function called before its definition has
been read does not exist yet. That is one of the arguments for `main "$@"` on
the last line: everything is defined by the time anything runs.

## How a name is resolved

When the shell sees a word in command position it looks, in order:

1. an **alias** (interactive shells only, and not expanded inside functions)
2. a **function**
3. a **builtin** — `cd`, `echo`, `read`, `[`
4. an executable on **`PATH`**

So a function outranks a builtin, and both outrank the real program:

```console
$ echo() { printf 'the FUNCTION ran\n'; }
$ echo hi
the FUNCTION ran
```

Two escapes:

```bash
command ls    # skip functions: run the builtin or the PATH executable
builtin cd    # skip functions: run the shell's own cd
```

`type -t name` reports which kind won: `alias`, `function`, `builtin`, `file`,
or nothing.

:::warning
A wrapper that forgets `command` **calls itself**:

```bash
ls() { ls -l "$@"; }        # infinite recursion
ls() { command ls -l "$@"; }  # correct
```

`FUNCNEST` is **unset by default**, so there is no nesting limit — bash recurses
until it exhausts memory. Set `FUNCNEST=10` before experimenting.
:::

## What a function returns

A function returns an **exit status**, and nothing else. If no `return` is given,
it is the status of the **last command that ran**:

```console
$ f() { true;  }; f; echo $?     → 0
$ f() { false; }; f; echo $?     → 1
$ f() { false; echo done; }; f; echo $?     → 0
```

That third one is the trap. **A function whose last line is an `echo` always
succeeds**, whatever happened above it — which is exactly how B08.5's migration
reported two applied migrations while one failed.

A bare `return` means "return the status I already have":

```console
$ f() { return; }; false; f; echo $?
1
$ false; f() { return; }; f; echo $?
0
```

The same three commands in a different order, with different answers — because
**a function definition is itself a command, and a successful one.** Defining `f`
between the `false` and the call resets `$?` to 0 before `return` ever reads it:

```console
$ false;             echo $?     → 1
$ false; g() { :; }; echo $?     → 0
```

Which is a reason to prefer an explicit `return "$status"` over a bare one:
whatever sits between the thing that failed and the `return` becomes part of the
answer.

## `return` is not `exit`

| | `return` | `exit` |
|---|---|---|
| Ends | the function | **the whole shell** |
| Outside a function | error, status 2 | fine |
| In a sourced script | ends the sourcing | ends the **calling** shell |

```console
$ bash -c 'return 3'
bash: return: can only `return' from a function or sourced script
$ bash -c 'f(){ exit 7; }; f; echo NOT-REACHED'; echo $?
7
```

`exit` inside a function ends the script. That is sometimes what you want in a
`usage` or `die` helper and never what you want in a library function, because
the caller loses the chance to clean up.

## The exit status is one byte

```console
$ bash -c 'exit 256'; echo $?    → 0
$ bash -c 'exit 300'; echo $?    → 44
$ bash -c 'exit -1';  echo $?    → 255
```

The value is taken modulo 256. `return` truncates identically.

And some of those 256 values are already spoken for:

| Status | Meaning |
|---|---|
| 0 | success |
| 1–125 | **yours** — whatever you define |
| 126 | found, but not executable |
| 127 | command not found |
| 128 + N | killed by signal N — 130 `INT`, 143 `TERM`, 137 `KILL` |
| 255 | often "out of range", and what `exit -1` becomes |

```console
$ bash -c '/tmp/not-executable'; echo $?    → 126
$ bash -c 'nosuchcmd';           echo $?    → 127
$ bash -c 'kill -TERM $$';       echo $?    → 143
```

Two consequences worth carrying. **Never `exit` a count** — `exit "$failures"`
is a success at 256 and means "killed by SIGTERM" at 143. Exit 1 and print the
number. And **64–78 are `sysexits.h`** — `EX_USAGE` is 64, which distinguishes
"you called it wrong" from "it went wrong" for a wrapper deciding whether to
retry.

:::note
`sysexits.h` is a convention, not a rule, and its adoption is patchy outside
BSD-derived tools. Using 64 for a usage error is common and defensible; using
the whole table is over-engineering for most scripts.
:::

:::objective{id=OBJ-B08.6.1}
:::

:::objective{id=OBJ-B08.6.2}
:::

:::objective{id=OBJ-B08.6.3}
:::

---
topic: topic.how-a-line-becomes-a-command
section: overview
title: The shell does not run what you typed
order: 1
mode: explain
---

Here is a line that does two different things depending on the contents of a
variable:

```bash
rm $f
```

If `f` is `report.log`, that deletes one file. If `f` is `a file.log` — a name a
web upload will happily produce — it deletes **two** files, called `a` and
`file.log`, and neither of them is the one you meant.

The variable did not change type. The command did not change. **The number of
arguments changed**, because the shell rewrote the line before `rm` ever saw it.

## Eight stages, in a fixed order

Between Enter and `execve`, the shell performs eight expansions in a sequence
that never varies. Two of them are the entire subject of this topic:

- **Word splitting** happens *after* parameter expansion, so the contents of a
  variable decide how many arguments there are.
- **Globbing** happens after that, and its results are *never* re-split.

That asymmetry is why `for f in *.log` is safe and `for f in $files` is not,
and it is not a rule to memorise — it falls out of the order.

:::predict{question="You are in a directory with six files ending in .log, one of which is named 'a file.log'. How many arguments does a command receive from `cmd *.log`? And from `cmd $g` where g='*.log'?"}
:::

## Quoting is the control, not a style

Most people learn quoting as a habit — "quote your variables" — without being
told what it does. It is precise:

| | Suppresses |
|---|---|
| `"..."` | word splitting and globbing |
| `'...'` | every expansion, all eight stages |
| unquoted | nothing |

Double quotes still allow `$var`, `$(cmd)` and `$((...))`. That is why they are
almost always the right answer: you keep the expansions you asked for and lose
the two that were done *to* you.

And the quotes themselves are removed at stage 8. They were never arguments —
they were instructions to the earlier stages.

## Two commands that end every argument

You do not have to reason about this. The shell will show you:

```console
$ f='a file.log'
$ set -x; printf '%s\n' $f
+ printf '%s\n' a file.log
$ set -x; printf '%s\n' "$f"
+ printf '%s\n' 'a file.log'
```

`set -x` prints the command **after expansion**, quoting any word that needs it.
The first line passed two arguments; the second passed one.

```console
$ printf '%q ' $f;   echo
a file.log
$ printf '%q ' "$f"; echo
a\ file.log
```

`printf %q` makes word boundaries visible. In this topic you will use a tiny
script called `argc` that does the same thing more directly — it prints how many
arguments it received and what each one was, which converts an argument about
quoting into a number.

## Filenames are not identifiers

A Linux filename may contain **any byte except NUL and `/`**. That includes
spaces, tabs, newlines, leading hyphens and asterisks. None of that is
theoretical:

```console
$ ls -b
--force   -n   a\ file.log   normal.log   star*.log   two\nlines.log
```

Those arrive from uploads, from Windows, from customer-supplied identifiers, and
from bugs upstream. In this topic's lab directory there is a file whose name
contains a newline — which is legal, and which makes this true:

```console
$ ls *.log | wc -l
7
$ argc *.log
argc = 6
```

**Two counts of the same six files.** `wc -l` says seven because one filename
contains a newline. That is why "don't parse `ls`" is advice rather than
pedantry, and why `find -print0` exists.

## Where this goes wrong in production

**The cleanup that cleaned too much.** A nightly job does `rm $f` in a loop. It
runs for two years against files named `app-2026-08-18.log`, then a service
starts naming logs from a customer-supplied string.

**The script that changed shells.** A working script gets `#!/bin/sh` instead of
`#!/bin/bash` during a container migration. On Debian `/bin/sh` is **dash**,
which has no `[[`, no arrays and no `<<<` — and the failure is a syntax error
pointing at a line that has not changed in years.

**The argument that became an option.** A file named `-n` reaches `echo`, or a
file named `--force` reaches a tool that takes `--force`. The shell has no
concept of "this word is data" — that is what `--` is for.

## What you will do

Four labs, all on a real shell:

- Watch a line change through each stage, using `set -x` and `printf %q`.
- Predict the argument count for fifteen lines, then measure. Four of them
  surprise most people.
- Forward arguments through three layers of wrapper and find the only form that
  survives.
- Fix a real log-archiving script with four separate expansion faults — one of
  which deletes the wrong files and produces no error at all.

:::objective{id=OBJ-B08.1.1}
:::

:::objective{id=OBJ-B08.1.2}
:::

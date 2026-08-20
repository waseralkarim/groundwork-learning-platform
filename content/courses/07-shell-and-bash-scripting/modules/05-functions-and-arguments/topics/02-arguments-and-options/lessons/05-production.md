---
topic: topic.arguments-and-options
section: production
title: A command-line contract
order: 5
mode: explain
---

## Choosing a parser

| | `getopts` | `getopt(1)` | hand-rolled |
|---|---|---|---|
| Long options | no | **yes** | if you write them |
| Dependency | none — builtin | external, util-linux | none |
| Operands after options | stops at the first | **permutes** | your choice |
| `--opt=value` | no | **yes** | if you write it |
| Abbreviations | no | **yes**, unambiguous | no |
| Errors | `?` and `:`, silent mode | message + status | yours |
| Lines of code | ~8 | ~12 plus `eval` | ~12 |

**`getopts` when the script has short options and no external audience.** It is
portable to any POSIX shell, has no dependency, and eight lines is the whole
parser. This is most operational scripts.

**`getopt(1)` when people type the command by hand.** Long options are a real
usability difference — `--dry-run` is self-documenting in a runbook and `-n` is
not — and permutation matches what everyone expects from GNU tools. The cost is
an external dependency and an `eval`.

**Hand-rolled when you want long options and no dependency**, or when the syntax
is unusual (subcommands, `key=value` operands, repeated flags accumulating into
an array). It is not much more code than `getopt(1)` and there is no `eval`;
what you give up is the abbreviation handling and the certainty that the
normalisation is right.

The one that is always wrong is **`getopts` with a long option in the help
text**. Advertising `--dry-run` for a parser that reads it as `d`,`r`,`y`,… is
how a dry run becomes a deletion.

## The contract

Whatever parses it, a script that other people run owes them:

- **A usage line on stderr, and exit 64** when called wrong. `-h` is the
  exception — requested help goes to stdout and exits 0.
- **Errors that name the input.** `--format must be json|text|csv, got 'jsn'`
  beats `invalid format`, and both beat silence.
- **`--` honoured**, so a file called `-rf` can be passed.
- **Validation immediately after parsing**, before any work.
- **A `--dry-run` that is real**, on anything destructive — and tested, because
  an untested dry run is the most dangerous flag in the script.
- **Defaults that are safe.** If a flag turns on deletion, the default is off; if
  a missing value would mean "everything", refuse instead.

That last pair is what the seeded prune script gets wrong twice over: deletion is
a flag rather than a subcommand, and the advertised safety flag enables it.

## Argument, environment, or file

A flag is not always the right channel:

- **An argument** for what changes per invocation — the target, the mode.
- **The environment** for ambient context — `DEPLOY_ENV`, `LOG_LEVEL`. Cheap to
  set once for many calls, and invisible in `ps`.
- **A file** for many settings, or anything versioned and shared.
- **stdin** for data.

And the rule with teeth: **never a secret in an argument.**
`/proc/PID/cmdline` is world-readable, so `ps` shows it to every user on the
machine. `/proc/PID/environ` is readable only by the owner, which makes the
environment better — but a file with restrictive permissions beats both, because
the environment still passes to children and lands in crash dumps.

## Testing a parser

The parser is the part most likely to be wrong and the easiest to test, because
it is pure: arguments in, variables out. Make it a function that prints its
result, and the test is a table:

```bash
parse() { ... ; echo "verbose=$verbose out=$out rest=$*"; }

check '-v -o f.txt a'  'verbose=1 out=f.txt rest=a'
check '--out=f.txt a'  'verbose=0 out=f.txt rest=a'
check '-- -v'          'verbose=0 out=backup.tar rest=-v'
check '"a b"'          'verbose=0 out=backup.tar rest=a b'
```

Seven invocations catch nearly everything: normal, no arguments, `--` alone, a
missing value, an unknown option, `--` followed by a dash-argument, and an
argument containing whitespace. The bats topic later in this course turns this into a
real test suite; the table works without it.

## When to stop

The parser is a good early signal that a script has outgrown shell. Once you
want subcommands, mutually exclusive flags, a repeated flag building a list,
`--format` values validated against an enum, or generated help that stays in
step with the options — you are reimplementing `argparse`, badly, in a language
with no data structures.

B11's `argparse` gives all of that in about the same number of lines as the
`getopts` loop alone, with the help text generated from the definitions so it
cannot drift out of date. **The prune script's whole incident was a help text
that had drifted out of date.**

## What to take from this topic

- **`"$@"` is the only faithful expansion.** `"$*"` joins with `IFS`; unquoted
  forms word-split.
- **`shift N` is all-or-nothing** — returns 1 and shifts nothing if `N > $#`,
  and under `set -e` that ends the script silently.
- **`getopts` has no long options.** It reads `--dry-run` as bundled letters and
  enables any that match.
- **A leading `:` in the optstring** gives silent errors, `?` for unknown and `:`
  for a missing argument, and lets you own the message and the status.
- **`OPTIND` is global.** A parsing function needs `local OPT OPTIND=1`, and the
  bug is invisible until somebody adds a second call.
- **`getopts` stops at the first operand**; `getopt(1)` permutes.
- **`getopt(1)` prints a usable result even when it fails**, so the `|| exit`
  is what tells you.
- **`--` ends options**, and a parser you write must honour it.
- **Never put a secret in an argument.**

:::objective{id=OBJ-B08.7.6}
:::

:::objective{id=OBJ-B08.7.8}
:::

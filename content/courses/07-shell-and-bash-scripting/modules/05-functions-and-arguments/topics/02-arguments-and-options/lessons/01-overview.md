---
topic: topic.arguments-and-options
section: overview
title: The dry run that deleted everything
order: 1
mode: explain
---

A prune script. `-d` deletes, `-n` is a dry run. Its help text also mentions
`--dry-run`, which somebody wrote in the usage block and nobody implemented.

```console
$ prune.sh -n /srv/data
delete=0 dry=1 dir=/srv/data
  would remove export-01.csv
  ...

$ prune.sh --dry-run /srv/data 2>/dev/null
delete=1 dry=1 dir=/srv/data
  removed export-01.csv
  removed export-02.csv
  removed export-03.csv
  removed export-04.csv
```

**`--dry-run` enabled deletion.**

`getopts` does not know what a long option is. It saw a word beginning with `-`
and read the rest of it as **bundled single letters** — `-`, `d`, `r`, `y`, `-`,
`r`, `u`, `n`. The `d` matched the optstring, so `delete=1`. The `n` at the end
matched too, so `dry=1` as well — and which of those the script honours is
decided by the order of its own `if`s.

The unknown letters produced warnings, on **stderr**. Redirect it away — which
is what a cron job keeping only stdout does — and the log shows `delete=1 dry=1`
and four removals, with nothing to indicate the operator asked for the opposite.

:::predict{question="`getopts` is given `-v file -v`. Both `-v` flags are valid. How many does it see?"}
:::

## The other way to lose a flag

```console
$ report.sh
  region=us-east  verbose=1 format=json
  region=eu-west  verbose=0 format=text
  region=ap-south verbose=0 format=text
```

Three regions, called with identical flags. The first is formatted as JSON and
the other two are not.

`OPTIND` — the index of the next argument `getopts` will read — is a **global**,
and nothing resets it between calls. After the first call it is 4, so the second
call starts reading past the end of its own argument list, finds no options, and
falls through to the defaults. `shift $((OPTIND - 1))` then removes the same
number of arguments as last time, so `$1` still lands on the region name.

**Every region is still reported.** That is what makes it survive review: the
output has the right number of lines, in the right order, with the right names.

## What `getopts` does with the arguments it was not designed for

Measured:

| Given | What `getopts` does |
|---|---|
| `-ab` | bundling works — two options |
| `-ofile` | attached value works — `OPTARG` is `file` |
| `-o=file` | `OPTARG` is **`=file`** — the `=` is part of the value |
| `--verbose` | letters `-`,`v`,`e`,`r`,`b`,`o`,`s`,`e` — **silently sets `-v`** |
| `-v file -v` | **stops at `file`** — the second `-v` is never seen |
| `-- -v` | `--` ends options; `-v` becomes an operand |

The last two are the ones that surprise people who use GNU tools all day.
`ls -l /tmp -a` works because GNU **permutes** its arguments; `getopts` stops at
the first non-option and leaves the rest alone.

## There is a second parser, and it is not a builtin

```console
$ getopt -o vo: --long verbose,out: -- --verbose --out=f.txt "a b" c
 -v --out 'f.txt' -- 'a b' 'c'
```

`getopt(1)` from util-linux handles long options, `--opt=value`, **unambiguous
abbreviations** (`--verb` works), and options *after* operands. It emits a
requoted list for `eval set --`, which is why `a b` survives as one argument.

It is a separate program rather than a builtin, and the older BSD `getopt` it
replaced could not do any of this — which is why a generation of advice says
"never use `getopt`". On Linux, that advice is out of date.

## What this topic covers

- What the shell hands a script: `$#`, `$@`, `$*`, `$0`, and what quoting does.
- `shift`, its exit status, and why it is all-or-nothing.
- `getopts` in full — optstring, `OPTARG`, `OPTIND`, and both error modes.
- `getopt(1)`, the `eval set --` idiom, and when it is worth the dependency.
- A command-line contract: usage, `--`, validation, and exit 64.

Four labs:

- Find out exactly what your script received, and why `"$@"` is the only form
  that tells the truth.
- Watch an option-parsing function work once and then silently stop.
- Make `--verbose` work three ways, and pick one.
- Write a CLI that refuses bad input by name.

:::objective{id=OBJ-B08.7.5}
:::

:::objective{id=OBJ-B08.7.7}
:::

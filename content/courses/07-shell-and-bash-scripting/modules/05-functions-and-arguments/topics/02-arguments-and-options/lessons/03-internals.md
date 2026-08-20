---
topic: topic.arguments-and-options
section: internals
title: How getopts actually reads a line
order: 3
mode: explain
---

:::diagram{src=../diagrams/option-parsing.mmd caption="The same command line, three parsers. getopts splits an unrecognised long option into letters; getopt(1) recognises it; a hand-rolled parser does whatever you wrote."}
:::

## The loop

```bash
while getopts ":vo:" OPT; do
  case $OPT in
    v)  verbose=1 ;;
    o)  out=$OPTARG ;;
    :)  die "-$OPTARG requires an argument" ;;
    \?) die "unknown option -$OPTARG" ;;
  esac
done
shift $((OPTIND - 1))
```

`getopts` is called **once per option**. Each call reads one, sets `OPT` and
possibly `OPTARG`, advances `OPTIND`, and returns 0. When there are no options
left it returns non-zero and the loop ends.

Three pieces of state, and all three are variables you can read:

- **`OPT`** (whatever you named it) — the letter found.
- **`OPTARG`** — its argument, or in silent mode the *offending* letter.
- **`OPTIND`** — the index of the next argument to read. `shift $((OPTIND - 1))`
  leaves the operands as `$1`, `$2`, …

## The optstring says two different things

```text
":vo:"
 │ ││└── o takes an ARGUMENT
 │ │└─── o is accepted
 │ └──── v is accepted, no argument
 └────── SILENT error reporting  ← leading colon
```

A colon **after** a letter means that option takes a value. A colon at the
**front of the whole string** switches error reporting. They are unrelated and
they look identical, which is most of why the leading one gets left out.

## The two error modes, measured

Without the leading colon, `getopts` prints its own message and sets `OPT` to
`?`:

```console
$ prog -z          →  prog.sh: illegal option -- z
$ prog -o          →  prog.sh: option requires an argument -- o
```

With it, `getopts` says nothing and tells you through the variables:

```console
$ prog -z          →  OPT=[?] OPTARG=[z]
$ prog -o          →  OPT=[:] OPTARG=[o]
```

Silent mode is the one to use, for three reasons. You can name the option in
your own message; you can distinguish "unknown option" (`?`) from "missing
argument" (`:`), which the noisy mode collapses; and you control the exit
status, so a usage error can be **64** rather than whatever happens next.

The noisy mode's message also names `$0`, so a function inside a large script
reports the whole script's name and not the operation that failed.

## Where it stops

```console
$ prog -v file -v
OPT=[v]
OPTIND=2  remaining=[file -v]
```

**`getopts` stops at the first argument that is not an option.** The second
`-v` is left in the operand list and never parsed.

GNU tools do not behave this way — `ls -l /tmp -a` works, because GNU
**permutes**: it scans the whole line, gathers the options, and moves the
operands to the end. That is a convention of the GNU C library's `getopt_long`,
not a shell feature, and it is why an operator who lives in GNU tools will type
`prune.sh /srv/data -n` and be surprised.

`--` also ends option parsing, and everything after it is an operand.

## What it does with the things it does not understand

| Given | `OPTARG` / effect |
|---|---|
| `-ab` | two options — bundling works |
| `-ofile` | `OPTARG` = `file` — attached values work |
| `-o file` | `OPTARG` = `file` — separated values work |
| `-o=file` | `OPTARG` = **`=file`** |
| `--verbose` | letters `-`,`v`,`e`,`r`,`b`,`o`,`s`,`e` |

Row 4 is a silent wrong value: a caller typing `--out=x` in the short form gets
a filename beginning with `=`. Row 5 is the one that deletes data — every letter
of a long option is tested against the optstring, and any that matches is
**enabled**.

## `OPTIND` is global

This is the defect that survives review, because the output still looks right.

```console
$ run_region -v -f json us-east      → verbose=1 format=json
$ run_region -v -f json eu-west      → verbose=0 format=text
$ run_region -v -f json ap-south     → verbose=0 format=text
```

`OPTIND` is left at 4 by the first call. The second starts reading at index 4 of
its own three-argument list, finds nothing, and falls through to the defaults.
`shift $((OPTIND - 1))` then removes 3 arguments as before — so `$1` still lands
on the region name and **every region is still reported, in order, by name**.

The fix is one word, and it must be `local`, not a bare assignment:

```bash
run_region() {
  local OPT OPTIND=1              # local so a caller's parse is not disturbed
  while getopts ":vf:" OPT; do
    ...
  done
  shift $((OPTIND - 1))
}
```

`local OPTIND=1` both resets it for this call and restores the caller's value on
return — which matters if the caller is itself mid-parse. A bare `OPTIND=1`
resets it and leaves the caller's parse broken instead, which converts one bug
into a harder one.

:::warning
`getopts` at the **top level** of a script needs no reset, because `OPTIND`
starts at 1 in a fresh shell. It is only re-entry — a function called more than
once, or a script that parses twice — that breaks. So the bug is invisible until
somebody adds a second call, which may be months after the parser was written
and reviewed.
:::

## `getopt(1)`: a different program with different rules

```console
$ getopt -o vo: --long verbose,out: -- --verbose --out=f.txt "a b" c
 -v --out 'f.txt' -- 'a b' 'c'
```

It **normalises** — long to short where both exist, attached values separated,
options moved before the `--`, operands after — and **requotes** everything,
which is why `a b` survives. That requoting is what makes `eval` safe here:

```bash
parsed=$(getopt -o vo: --long verbose,out: -n "${0##*/}" -- "$@") || exit 64
eval set -- "$parsed"

while true; do
  case $1 in
    -v|--verbose) verbose=1; shift ;;
    -o|--out)     out=$2;    shift 2 ;;
    --)           shift; break ;;
  esac
done
```

Four properties worth knowing:

- **`|| exit 64`** is required, and for a sharper reason than it looks. On a bad
  option `getopt` returns non-zero *and still prints a usable result*:

  ```console
  $ getopt -o v --long verbose -n demo -- --nope a b
  demo: unrecognized option '--nope'            ← stderr
   -- 'a' 'b'                                    ← stdout, rc=1
  ```

  The offending option has been **silently dropped** and the operands survive.
  So a script without the guard does not crash — it runs, having discarded the
  flag the operator typed, which is this topic's failure mode all over again.
  The status is the only thing that tells you, so you have to check it.
- **`-n NAME`** sets the name in its error messages, which otherwise says
  `getopt`.
- **Unambiguous abbreviations work** — `--verb` matches `--verbose`. That is a
  feature to GNU users and a compatibility hazard: adding a `--verify` option
  later makes an existing `--ver` in someone's cron job ambiguous, and it starts
  failing.
- It **permutes**, so `prog "a b" -v c --out f` parses correctly.

The old advice "never use `getopt`" refers to the **BSD** version, which could
not do long options and mangled anything containing whitespace. The util-linux
version — `getopt --version` says so — is the one described here. Checking which
you have is a one-line portability test, and on a container image you control it
is a non-issue.

:::objective{id=OBJ-B08.7.3}
:::

:::objective{id=OBJ-B08.7.4}
:::

:::objective{id=OBJ-B08.7.6}
:::

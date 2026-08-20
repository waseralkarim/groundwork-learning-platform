---
topic: topic.arguments-and-options
section: commands
title: The forms worth knowing
order: 4
mode: do
---

## Reading what you were given

```bash
"$#"                # how many arguments
"$@"                # all of them, one word each — the only faithful form
"$*"                # all of them joined by the first char of IFS
"$1" "$2"           # individually
"${1:-default}"     # with a default
"${1:?usage: $0 DIR}"   # required, with a message
"${@:2}"            # from the second onwards
"${@: -1}"          # the last — the space is REQUIRED
"$0"                # the invocation name; NOT an argument
"${0##*/}"          # just the basename, for messages
```

## Changing the list

```bash
shift               # drop $1
shift 2             # drop two — returns 1 and drops NOTHING if $# < 2
set -- a b c        # replace the list
set --              # empty it
set -- "${arr[@]}"  # load an array into it
eval set -- "$parsed"   # the getopt(1) idiom
```

Guard a paired shift by count, not by hope:

```bash
[ $# -ge 2 ] || die "--out needs a value"
out=$2; shift 2
```

## `getopts`

```bash
while getopts ":vo:h" OPT; do
  case $OPT in
    v)  verbose=1 ;;
    o)  out=$OPTARG ;;
    h)  usage; exit 0 ;;
    :)  die "-$OPTARG requires an argument" ;;
    \?) die "unknown option -$OPTARG" ;;
  esac
done
shift $((OPTIND - 1))
```

```text
":vo:h"
 │              leading colon  → silent errors, report via ? and :
 │  └── trailing colon on o    → o takes an argument
```

Inside a function, always:

```bash
local OPT OPTIND=1
```

`local` so the caller's parse is restored on return; `=1` so this call starts at
the beginning. A bare `OPTIND=1` fixes this call and breaks the caller's.

## `getopt(1)` — long options

```bash
parsed=$(getopt -o vo: --long verbose,out:,dry-run \
                -n "${0##*/}" -- "$@") || exit 64
eval set -- "$parsed"

while true; do
  case $1 in
    -v|--verbose)  verbose=1; shift ;;
    -o|--out)      out=$2;    shift 2 ;;
    --dry-run)     dry=1;     shift ;;
    --)            shift; break ;;
    *)             die "internal error at $1" ;;
  esac
done
```

`--long a,b:,c` mirrors the short optstring: a trailing `:` means the long option
takes a value. `|| exit 64` is not optional — on a bad option `getopt` exits
non-zero *and still prints a usable list with the bad option removed*.

```bash
getopt --version        # "getopt from util-linux" = the one with long options
```

## A hand-rolled parser

When you want no dependency and full control:

```bash
while [ $# -gt 0 ]; do
  case $1 in
    -v|--verbose)  verbose=1 ;;
    -o|--out)      [ $# -ge 2 ] || die "--out needs a value"; out=$2; shift ;;
    --out=*)       out=${1#*=} ;;
    -h|--help)     usage; exit 0 ;;
    --)            shift; break ;;
    -*)            die "unknown option: $1" ;;
    *)             break ;;
  esac
  shift
done
```

The four lines people leave out are `--out=*`, `--`, the `-*` catch-all, and the
count check before taking `$2`. Each is one line and each is a real defect
without it — the catch-all especially, because without it an unknown option
falls to `*)` and is treated as a **filename**.

## Validating what you got

```bash
[ $# -ge 1 ]        || { usage; exit 64; }
[ -d "$1" ]         || die "not a directory: $1"
[ -r "$FILE" ]      || die "cannot read: $FILE"
case $FORMAT in json|text|csv) ;; *) die "bad --format: $FORMAT" ;; esac
[[ $PORT =~ ^[0-9]+$ ]] || die "--port must be a number: $PORT"
[ "$PORT" -ge 1 ] && [ "$PORT" -le 65535 ] || die "--port out of range"
```

Validate **immediately after parsing**, before anything has happened. A bad
`--format` caught at line 20 is a message; caught at line 200 it is a
half-finished job.

## Usage and exit codes

```bash
usage() {
  cat >&2 <<EOF
usage: ${0##*/} [-v] [-o FILE] DIR...
  -v, --verbose   report each file
  -o, --out FILE  write to FILE (default: backup.tar)
EOF
}
die() { echo "${0##*/}: $*" >&2; exit 1; }

[ $# -ge 1 ] || { usage; exit 64; }     # EX_USAGE
```

Usage on **stderr** and status **64**, so a wrapper can tell "called wrong" from
"went wrong". `-h` is the exception: an explicitly requested help text goes to
**stdout** and exits **0**, because the user asked for it and may be piping it to
`less`.

## Checking a parser by hand

```bash
./prog -v -o f.txt a "b c"      # normal
./prog --                        # no options, no operands
./prog -o                        # missing value
./prog -z                        # unknown option
./prog -- -v                     # -v as an operand
./prog "a b"                     # whitespace survives
./prog                           # no arguments at all
```

Seven invocations, and most parsers fail at least one. Keeping them as a shell
function in the repository turns a class of bug into a test.

:::try{lab=what-the-shell-hands-you}
:::

:::objective{id=OBJ-B08.7.3}
:::

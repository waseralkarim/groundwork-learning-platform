---
topic: topic.how-a-line-becomes-a-command
section: internals
title: Arguments, forwarding, and which shell you are in
order: 3
mode: explain
---

Once you can see argument lists, two things become tractable that otherwise
feel like folklore: passing arguments through wrappers, and knowing which
features you are allowed to use.

## `"$@"` is the only correct way to forward arguments

Three forms, and they are genuinely different. With the arguments `a b` and `c`
— two arguments, the first containing a space:

```console
$ show 'a b' c
    $@:   [a] [b] [c]
    "$@": [a b] [c]
    "$*": [a b c]
```

- **`$@` unquoted** — expands to the arguments and then word-splits each one.
  Two arguments became three. Never what you want.
- **`"$@"`** — expands to each argument as its own word, splitting nothing. This
  is the one.
- **`"$*"`** — joins everything into a **single** word, separated by the first
  character of `IFS`. Occasionally useful for building a message; never for
  passing arguments on.

The special case that makes `"$@"` non-obvious: with *zero* arguments, `"$@"`
expands to **nothing at all** — not to one empty string. That is exactly right
and it is why the shell needed a special rule; `"$*"` with zero arguments gives
you one empty argument, which is usually a bug.

```bash
# a wrapper that works
run_tool() {
  exec /usr/local/bin/tool --config /etc/tool.conf "$@"
}
```

Every argument the caller supplied arrives at `tool` exactly as given, spaces
and all, and nothing is added when there are none.

## `$1` and friends need quoting too

`"$@"` gets the attention, but the same applies one at a time:

```bash
dest=$1          # unquoted assignment is safe — assignments do not word-split
cp "$1" "$2"     # but usage is not
```

Assignment is the one place an unquoted expansion cannot bite you: `x=$f` is
safe even when `f` contains spaces, because no word splitting is performed on
the right-hand side of an assignment. It is still worth quoting for consistency,
because the reader has to know that rule to be sure.

## A word can become an option

The shell has no concept of "this word is data". A file named `-n` reaching
`echo` is a flag:

```console
$ ls
--force   -n   a file.log   normal.log
$ echo *
a file.log normal.log $
```

The `-n` was consumed as an option and suppressed the trailing newline; the
`--force` was printed but a tool that understands `--force` would have obeyed
it.

Two defences, and you want both:

```bash
rm -- "$f"          # -- ends option parsing; everything after is data
rm "./$f"           # a leading ./ means the name cannot start with -
```

`--` is understood by nearly every GNU tool and is the general answer. The
`./` prefix works even with tools that do not support `--`, and has the side
benefit of being obvious to a reader.

:::warning
This is not only about hostile input. Generated identifiers, ticket numbers and
branch names all produce leading hyphens eventually, and the failure mode is a
tool silently doing something else rather than reporting a bad filename.
:::

## Which shell is running your script

`#!/bin/sh` on Debian is **dash**, not bash. Measured on this machine:

| Feature | bash | dash (`/bin/sh`) |
|---|---|---|
| `[[ ... ]]` | yes | **no** |
| arrays — `a=(1 2)` | yes | **no** |
| here-strings — `<<<` | yes | **no** |
| `local` in a function | yes | yes |
| `$(...)`, `${var%x}`, `"$@"` | yes | yes |

`local` is worth noting because it is commonly listed as a bashism and works
fine in dash — it is not POSIX, but every shell you will meet supports it.

The failure mode is specific and it wastes time: a script that has worked for
years gets its shebang changed, or is invoked as `sh script.sh` instead of
`./script.sh`, and produces a **syntax error on a line nobody touched**. The
line number points at working code, because dash rejects `[[` at parse time.

```console
$ dash -c '[[ 1 = 1 ]]'
dash: 1: [[: not found
```

Pick deliberately. `#!/bin/bash` if you want the features — and say so — or
`#!/bin/sh` and restrict yourself to POSIX. What does not work is writing bash
and labelling it `sh`.

:::note
This platform's own lab harness runs walkthroughs under **bash** and `verify`
checks under **dash**, for exactly this reason: a check that silently depended on
a bashism would pass on the author's machine and fail somewhere else.
:::

## Making the invisible visible

Three tools, in increasing order of detail:

```bash
set -x                      # trace: every command after expansion
printf '%q ' "$var"         # exact word boundaries, escapes shown
ls -b                       # filenames with non-printing characters escaped
cat -A                      # every byte: tabs as ^I, line ends as $
```

`ls -b` is the one people do not know, and it is how you find out that a
filename contains a tab rather than spaces. `cat -A` settles the same question
for file contents — trailing whitespace, CRLF line endings, and the tab that is
breaking your `cut -f`.

And the reason `find -print0` and `xargs -0` exist:

```bash
find . -name '*.log' -print0 | xargs -0 rm --
```

NUL is the only byte that cannot appear in a filename, so it is the only safe
separator. Every other approach — newline-separated, space-separated — is a
guess about what filenames will not contain, and this topic's lab directory
contains a counterexample to each.

:::objective{id=OBJ-B08.1.5}
:::

:::objective{id=OBJ-B08.1.7}
:::

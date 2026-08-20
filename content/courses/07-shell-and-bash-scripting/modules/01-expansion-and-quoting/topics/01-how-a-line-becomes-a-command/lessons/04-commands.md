---
topic: topic.how-a-line-becomes-a-command
section: commands
title: Seeing what the command received
order: 4
mode: do
---

The whole skill here is refusing to reason about a line when you could measure
it. These are the tools.

## Show the expansion

```bash
set -x                      # trace on
set +x                      # trace off
( set -x; cmd args )        # trace one command, in a subshell
bash -x script.sh           # trace a whole script without editing it
```

`set -x` prints each command **after expansion**, quoting any word that needs
it:

```console
$ f='a file.log'
$ ( set -x; argc $f )
+ argc a file.log
$ ( set -x; argc "$f" )
+ argc 'a file.log'
```

The quotes bash adds in the trace are the answer: it quotes a word when the word
contains something that would need quoting. No quotes means no spaces.

Make the trace more useful by putting the source location in it:

```bash
PS4='+ ${BASH_SOURCE##*/}:${LINENO}: '
set -x
```

## Show the exact words

```bash
printf '%q ' "$var"; echo       # one value, escaped
printf '[%s]\n' "$@"            # one line per argument, bracketed
printf '%s\0' "$@" | od -c | head # the bytes, if you suspect something invisible
```

`printf` with more arguments than format specifiers **repeats the format**,
which is why `printf '[%s]\n' "$@"` prints one bracketed line per argument. That
is the shortest argument-list dump available and needs no helper script.

```console
$ set -- 'a b' c
$ printf '[%s]\n' "$@"
[a b]
[c]
```

## Show what is in a filename

```bash
ls -b                     # escape non-printing characters
ls -Q                     # quote every name
find . -maxdepth 1 -print0 | od -c | head  # the bytes
cat -A file               # tabs as ^I, line ends as $, CR as ^M
```

`ls -b` answers "is that a space or a tab" in one keystroke, and `cat -A` finds
the CRLF line endings that make a config file behave strangely.

## Control globbing

```bash
shopt -s nullglob         # unmatched pattern -> nothing
shopt -s failglob         # unmatched pattern -> error
shopt -s dotglob          # * also matches dotfiles
shopt -u nullglob         # back to the default: pattern stays literal
shopt -p nullglob         # what is it now?
set -f                    # disable globbing entirely (set +f to restore)
```

Default is all four off. That means `*` does **not** match `.bashrc`, and a
pattern with no matches stays literal — the two glob behaviours that surprise
people most.

## Control word splitting

```bash
IFS=: read -r a b c <<< "$line"     # for one command only — the safe form
while IFS= read -r line; do ...     # IFS= keeps leading/trailing whitespace
```

`while IFS= read -r line` is the canonical line-reading idiom and every part of
it earns its place: `IFS=` stops leading and trailing whitespace being trimmed,
and `-r` stops backslashes being interpreted. Without `-r`, a line containing
`C:\new` loses the backslash and gains a newline.

## Handle filenames safely

```bash
rm -- "$f"                                  # -- ends option parsing
rm "./$f"                                   # or make it not start with -
find . -name '*.log' -print0 | xargs -0 rm --
find . -name '*.log' -exec rm -- {} +       # no pipe, no xargs
```

`find -exec ... +` is worth knowing as the no-pipeline alternative: it batches
arguments like `xargs` does, needs no NUL handling because nothing is parsed,
and returns a sensible exit status.

## Check a script before running it

```bash
bash -n script.sh          # parse only — syntax check, runs nothing
dash -n script.sh          # does it parse as POSIX sh?
```

`bash -n` catches the unclosed quote that would otherwise be discovered halfway
through a deployment. `dash -n` answers "is this really POSIX" without waiting
for the migration that changes the shebang.

```console
$ dash -n script.sh
script.sh: 12: Syntax error: "(" unexpected
```

## The helper used in these labs

`argc` prints the argument list a command really received:

```console
$ argc $f
argc = 2
  $1 = [a]
  $2 = [file.log]
```

It is nine lines and worth having on any machine you debug on:

```bash
#!/bin/bash
printf 'argc = %d\n' "$#"
i=0
for a in "$@"; do
  i=$((i + 1))
  printf '  $%d = [%s]\n' "$i" "$a"
done
```

:::try{lab=watch-the-line-change}
:::

:::objective{id=OBJ-B08.1.6}
:::

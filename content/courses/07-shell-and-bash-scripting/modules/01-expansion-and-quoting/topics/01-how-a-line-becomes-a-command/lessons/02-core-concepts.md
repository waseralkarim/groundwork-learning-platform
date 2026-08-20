---
topic: topic.how-a-line-becomes-a-command
section: core-concepts
title: The order, stage by stage
order: 2
mode: explain
---

:::diagram{src=../diagrams/expansion-order.mmd caption="Eight stages, fixed order. Word splitting applies only to the results of stages 3–5, and globbing results are never re-split."}
:::

## Brace expansion is first, so variables do not work in it

```console
$ n=3
$ echo {1..3}
1 2 3
$ echo {1..$n}
{1..3}
```

The second line produced the literal text `{1..3}`. Brace expansion happens at
**stage 1**, before `$n` has been substituted at stage 3 — so when the brace
stage looked at the line, it saw `{1..$n}`, which is not a valid range, and left
it alone. By the time `$n` became `3` it was too late.

This is the clearest possible demonstration that the order is real rather than
descriptive. If you need a variable range, use `seq` or a C-style `for`.

## Parameter expansion produces text, not values

```console
$ f='a file.log'
$ argc $f
argc = 2
  $1 = [a]
  $2 = [file.log]
```

The shell substituted the variable's *text* into the line, and then stage 6 —
word splitting — treated that text like any other. There is no type system here:
a variable holds a string, and the string becomes part of the command line.

## Command substitution strips trailing newlines

```console
$ v=$(printf 'line\n\n\n')
$ printf '%s' "$v" | wc -c
4
```

Six bytes went in, four came out. **All** trailing newlines are removed — always,
and there is no option to keep them. That is usually what you want and
occasionally not; the workaround when you need them is to append a sentinel:

```bash
v=$(printf 'line\n\n\n'; printf x)
v=${v%x}
```

And the result is word-split like anything else:

```console
$ argc $(echo one two)
argc = 2
$ argc "$(echo one two)"
argc = 1
```

## Word splitting: the stage that changes the argument count

Stage 6 splits the *results of stages 3, 4 and 5* at any character in `IFS` —
space, tab and newline by default.

It does **not** re-split the literal text you typed. Words you type are already
words; splitting exists only to decide how many words an *expansion* produced.

```console
$ argc a file.log
argc = 2
$ f='a file.log'
$ argc $f
argc = 2
```

The same two arguments — but for different reasons, and only the second one is
under the control of whatever set `f`. That is the whole risk: a line whose
argument count is decided by data rather than by what you wrote.

`IFS` is a variable, so splitting is configurable:

```console
$ line="root:x:0:0:root:/root:/bin/bash"
$ IFS=: read -r user pw uid rest <<< "$line"
$ echo "$user $uid"
root 0
```

Setting `IFS` for a single command like that is the safe form. Setting it
globally changes how every subsequent unquoted expansion splits, which is a
long-range action at a distance.

## Globbing runs after splitting, and its results are never split

This is the asymmetry that makes globs safe:

```console
$ for f in *.log; do printf '[%s] ' "$f"; done
[a file.log] [normal.log] [star*.log] ...
```

`a file.log` came back as **one word**, with its space intact, because glob
results are not re-split. Compare:

```console
$ v="a file.log normal.log"
$ for f in $v; do printf '[%s] ' "$f"; done
[a] [file.log] [normal.log]
```

Same filenames, three words. **The glob is safe and the variable is not**, and
that is a consequence of the order rather than a rule anyone had to decide.

It also means a variable *containing* a pattern gets globbed:

```console
$ g='*.log'
$ argc $g        # split into one word, then globbed
argc = 6
$ argc "$g"      # neither
argc = 1
```

## An unmatched glob becomes itself

```console
$ argc *.nomatch
argc = 1
  $1 = [*.nomatch]
```

By default bash leaves a non-matching pattern as literal text. This is the cause
of a specific and common bug:

```bash
for f in /var/log/app/*.log; do
  rm "$f"          # runs once with f='/var/log/app/*.log' when the dir is empty
done
```

The loop body executes once, with a filename that does not exist. `rm` then
fails with a confusing message about a file whose name contains an asterisk.

```console
$ shopt -s nullglob     # unmatched pattern expands to nothing; loop runs zero times
$ shopt -s failglob     # unmatched pattern is an error
```

`nullglob` is the option you usually want in a script, and it is off by default
for compatibility.

:::warning
`nullglob` changes behaviour globally for the rest of the script, including in
functions and sourced files. Set it deliberately near the top, or guard the loop
with `[ -e "$f" ] || continue` instead — which is uglier and has no reach.
:::

## Quote removal is last, and it explains everything

The quotes you typed are deleted at stage 8. They never reach the command:

```console
$ set -x; argc "a file.log"
+ argc 'a file.log'
```

`argc` received one argument whose value contains a space and no quotes. The
quotes were instructions to stages 6 and 7 — and once those have run, the
instructions have been obeyed and are discarded.

Which gives the summary worth memorising:

| Form | Expansions | Word splitting | Globbing |
|---|---|---|---|
| `$f` | yes | **yes** | **yes** |
| `"$f"` | yes | no | no |
| `'$f'` | **no** | no | no |

The middle row is what you want almost every time.

:::objective{id=OBJ-B08.1.3}
:::

:::objective{id=OBJ-B08.1.4}
:::

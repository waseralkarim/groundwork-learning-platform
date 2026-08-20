---
topic: topic.where-output-goes
section: internals
title: What a pipeline really is
order: 3
mode: explain
---

:::diagram{src=../diagrams/pipeline-anatomy.mmd caption="Each stage is a separate process with its own copy of every variable. The pipe is a kernel buffer, and stdio picks its buffering mode from what stdout is connected to."}
:::

## Every stage is its own process

`a | b` does not run `a` and then `b`. The shell creates a pipe, forks a process
for each stage, and runs them **simultaneously** — `b` starts consuming while `a`
is still producing. That is what makes a pipeline able to process a file larger
than memory.

The cost is that each stage is a **subshell** with its own copy of the shell's
variables:

```console
$ count=0
$ printf 'a\nb\nc\n' | while read -r l; do count=$((count + 1)); done
$ echo $count
0
```

The loop ran three times and incremented a `count` that belonged to a child
process. That process exited, and its memory went with it. Nothing was lost or
overwritten — the parent's `count` was never touched.

Three fixes, in order of preference:

```bash
# 1. process substitution — no pipeline, so no subshell for the loop
while read -r l; do count=$((count + 1)); done < <(printf 'a\nb\nc\n')

# 2. redirect from a file
while read -r l; do count=$((count + 1)); done < input.txt

# 3. bash's lastpipe — runs the LAST stage in the parent
shopt -s lastpipe; set +m
printf 'a\nb\nc\n' | while read -r l; do count=$((count + 1)); done
```

All three give `count=3`. Process substitution is the general answer: `< <(cmd)`
presents a command's output as a file, so the loop is not part of a pipeline at
all.

`lastpipe` works and has two conditions worth knowing — it is bash-only, and it
requires job control to be off, which it is in scripts but not in an interactive
shell. That is why the example includes `set +m`, and why testing it interactively
can make you think it does not work.

## Exit status, and which stage failed

A pipeline's exit status is the status of its **last** command:

```console
$ false | true; echo $?
0
```

The failure is invisible, which matters because the first stage is usually the
one that does the real work — `curl`, `pg_dump`, `find`.

```console
$ set -o pipefail
$ false | true; echo $?
1
```

`pipefail` makes the status the last **non-zero** one. And when you need to know
*which* stage:

```console
$ false | true
$ echo "${PIPESTATUS[@]}"
1 0
```

`PIPESTATUS` is an array, one entry per stage, and it is only valid immediately
after the pipeline — the next command overwrites it, including an `echo`. Copy
it first if you need it twice:

```bash
cmd_a | cmd_b | cmd_c
status=("${PIPESTATUS[@]}")
```

:::warning
`PIPESTATUS` is bash-only, and `pipefail` is not POSIX either — though dash and
most shells support it. In a `#!/bin/sh` script, neither is guaranteed, and the
portable workaround is to restructure so the important command is not in a
pipeline at all.
:::

## SIGPIPE, and why `head` can stop `yes`

When a reader closes its end, the kernel sends **SIGPIPE** to the next writer.
That is how a pipeline terminates early instead of running forever:

```console
$ yes | head -2
y
y
$ echo "${PIPESTATUS[@]}"
141 0
```

`yes` was killed by signal 13, reported as `128 + 13 = 141`. This is normal and
correct — it is the mechanism that makes `find / | head` cheap instead of a full
filesystem walk.

It also means a program that ignores SIGPIPE keeps running after its reader has
gone, and one that treats a write error as fatal will report a failure that is
not one. If you have ever seen `BrokenPipeError` from a Python script piped into
`head`, that is this.

The practical consequence: **with `pipefail` on, a pipeline ending in `head` can
report failure** because the first stage was killed by SIGPIPE. That is a real
interaction between two things you were told to enable, and it is why a script
using both sometimes needs `|| true` on a specific line, with a comment saying
why.

## Buffering is chosen by what is downstream

The C standard library picks a buffering mode when a stream is first used:

| stdout connected to | mode | flushes |
|---|---|---|
| a terminal | line-buffered | at every newline |
| a pipe or file | **block-buffered** | when the buffer fills (4–8 KB), or at exit |

The program is identical. The behaviour is not.

```console
$ drip 3 | grep . | stamp
arrived +3s : line 1 emitted at +0s
arrived +3s : line 2 emitted at +1s
arrived +3s : line 3 emitted at +2s
```

Every line was emitted on time and all three arrived together at the end, when
`grep` exited and flushed its buffer. The same command run without the second
pipe behaves perfectly, because then `grep`'s stdout is a terminal.

Fixes, depending on what you control:

```bash
grep --line-buffered ERROR log      # the tool has an option
awk '{print; fflush()}' log         # flush explicitly
sed -u '...'                        # GNU sed's unbuffered mode
stdbuf -oL cmd                      # force line buffering on any stdio program
stdbuf -o0 cmd                      # unbuffered
```

`stdbuf` is the general answer, and its limitation is worth knowing exactly: it
works by preloading a library that changes stdio's defaults, so it cannot affect
a program that does not use stdio — a Go binary, for instance — or one that sets
its own buffering. `tee` is the documented example of the second case; its own
man page notes that a command adjusting its streams overrides `stdbuf`.

:::callback{to=topic.user-space-and-the-kernel}
A01.4 measured why buffering exists — a syscall costs hundreds of nanoseconds
and writing a megabyte one byte at a time is a million crossings. This is the
operational consequence of that optimisation: the library is being *correct*
about efficiency and the result is a log that arrives late.
:::

## Here-docs, here-strings, and process substitution

Three ways to feed input that is not a file:

```bash
cmd <<EOT            # here-doc: expands $vars and $(cmd)
value is $v
EOT

cmd <<'EOT'          # quoted delimiter: NOTHING is expanded
literal $v
EOT

cmd <<< "$var"       # here-string: one line, bash only

cmd < <(other)       # process substitution: another command's output as a file
```

**Quoting the delimiter is the important distinction.** `<<EOT` expands
variables and command substitutions inside the body, which is what you want for
a templated config and exactly what you do not want when the body is a script,
an SQL statement or anything containing a literal `$`.

`<<-EOT` allows the closing delimiter to be indented with **tabs** — only tabs,
which is a genuine nuisance in a file otherwise indented with spaces.

Process substitution is the one that solves problems nothing else does:

```bash
diff <(sort a.txt) <(sort b.txt)          # compare two transformations
while read -r l; do ...; done < <(cmd)    # loop without a subshell
cmd > >(tee log) 2> >(tee err >&2)        # send each stream through a filter
```

It is bash-only, and it works by giving the command a path like `/dev/fd/63` —
which is why a tool that needs to seek within its input, or to open the file
twice, will fail on it.

:::objective{id=OBJ-B08.2.2}
:::

:::objective{id=OBJ-B08.2.5}
:::

:::objective{id=OBJ-B08.2.7}
:::

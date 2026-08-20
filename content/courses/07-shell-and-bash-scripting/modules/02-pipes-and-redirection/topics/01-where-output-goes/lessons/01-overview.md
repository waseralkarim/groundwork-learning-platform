---
topic: topic.where-output-goes
section: overview
title: Three failures that produce no error
order: 1
mode: explain
---

Every one of these lines is wrong, and none of them prints a warning you would
notice:

```bash
sort data.txt > data.txt              # data.txt is now empty
cmd 2>&1 > deploy.log                 # errors went to the terminal, not the log
count=0; find . | while read f; do count=$((count+1)); done   # count is 0
```

The first destroys a file. The second hides exactly the output you were trying
to capture. The third silently produces the wrong answer. All three are about
one question — **where does output actually go** — and all three follow from
rules that are simple once stated.

## Redirection is applied left to right

`2>&1` does not mean "send stderr to stdout". It means **make descriptor 2 a
copy of wherever descriptor 1 points right now**. It copies the current target,
not the name, and nothing links them afterwards.

So the order decides the outcome:

```console
$ cmd >file 2>&1      # 1 → file, then 2 = copy of 1 → file.   Both captured.
$ cmd 2>&1 >file      # 2 = copy of 1 → terminal, then 1 → file. Errors escape.
```

Measured, those produce visibly different results — the second prints the error
message to your screen while the file contains only stdout. It is the single
most common redirection bug, and it looks correct.

## `>` truncates before the command runs

The shell sets up redirections *before* starting the program. So by the time
`sort` opens `data.txt` to read it, the shell has already emptied it:

```console
$ printf 'c\nb\na\n' > data.txt
$ sort data.txt > data.txt
$ wc -c < data.txt
0
```

Zero bytes, exit status 0, no message. Some tools do notice — GNU `grep` says
`input file is also the output` and exits 2 — but the file is destroyed either
way, and most tools say nothing at all.

:::predict{question="A pipeline stage increments a counter: `printf 'a\\nb\\nc\\n' | while read l; do count=$((count+1)); done`. What is `count` afterwards, and why?"}
:::

## A pipeline is several processes

`a | b` runs both at once, connected by a kernel buffer, **each in its own
subshell**. That is what makes pipelines fast, and it is why a variable set
inside the loop above is gone when the loop ends — it was incremented in a child
process that has since exited.

It also explains the exit status. A pipeline reports the status of its **last**
command only:

```console
$ false | true; echo $?
0
```

A failing first stage is invisible. `set -o pipefail` fixes it, and
`${PIPESTATUS[@]}` tells you which stage failed.

## And output can be produced without appearing

This is the subtlest of the four and the one that ruins incidents. The C library
chooses a buffering mode based on **what stdout is connected to**: line-buffered
to a terminal, block-buffered to a pipe. Same program, same code, different
behaviour depending on what is downstream.

Watch it happen — a producer emitting one line per second, through `grep`:

```console
$ drip 3 | grep . | stamp
arrived +3s : line 1 emitted at +0s
arrived +3s : line 2 emitted at +1s
arrived +3s : line 3 emitted at +2s
```

Every line was **emitted** on time and every line **arrived** three seconds
late, together, when `grep` exited and flushed. Add `--line-buffered` and the
arrival times match the emission times exactly.

That is why `tail -f app.log | grep ERROR` can show nothing for minutes and then
produce a burst — and why it does the right thing when you run it by hand
without the pipe, which makes it maddening to diagnose.

## What you will do

Four labs:

- Look at your own process's file descriptors, then make output land in four
  different places on purpose — including both orderings of `2>&1`.
- Destroy a config file with a redirection, then find the ways to do it that
  work and say what each costs.
- Find why a counter stays zero, read a pipeline's real exit status, and watch
  `head` kill `yes` with SIGPIPE.
- Take a job whose output arrives minutes late and make it stream — then decide
  what a scheduled job's logging should actually look like.

:::objective{id=OBJ-B08.2.1}
:::

:::objective{id=OBJ-B08.2.3}
:::

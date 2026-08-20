---
topic: topic.where-output-goes
section: core-concepts
title: Descriptors, order, and truncation
order: 2
mode: explain
---

## Three descriptors you did not open

Every process starts with three file descriptors already open, and you can see
what they point at:

```console
$ ls -l /proc/self/fd/
lr-x------ 0 -> pipe:[52947108]
l-wx------ 1 -> pipe:[52950029]
l-wx------ 2 -> /dev/null
```

- **0, stdin** — where input is read from.
- **1, stdout** — results.
- **2, stderr** — diagnostics.

The split between 1 and 2 is the useful part and it is a design decision, not an
accident: **errors are kept out of the data stream** so that `cmd | process`
does not feed an error message into `process`, and so that `cmd > file` captures
results while you still see what went wrong.

A program that writes errors to stdout has broken that contract, and it is worth
recognising because the symptom is confusing — error text appearing inside a
data file, or a pipeline that processes an error message as though it were a
record.

:::note
`/proc/self/fd` is worth knowing for a second reason: it answers "what is this
process actually reading and writing" for a *running* process, by PID. That is
how you find out which file a daemon has open, or that it is writing to a
deleted file — the case A01.5 covered from the filesystem side.
:::

## Redirection order, precisely

:::diagram{src=../diagrams/redirection-order.mmd caption="2>&1 copies the current target of descriptor 1. It does not create a link, so the order of the two redirections changes the outcome."}
:::

The rule is one sentence: **`2>&1` makes descriptor 2 a copy of wherever
descriptor 1 points at that moment.** It duplicates the target, and afterwards
the two descriptors are independent.

```console
$ mk() { echo "to stdout"; echo "to stderr" >&2; }

$ mk >a.txt 2>&1
$ cat a.txt
to stdout
to stderr

$ mk 2>&1 >b.txt
to stderr                 # printed on the terminal
$ cat b.txt
to stdout
```

Both lines contain the same two redirections. The first captures everything; the
second sends errors to the terminal and puts only stdout in the file.

Which means `2>&1` at the end is almost always what you want, and `&>file` is
bash's shorthand for exactly that:

```bash
cmd >file 2>&1          # portable, works in sh
cmd &>file              # bash only, identical effect
cmd >>file 2>&1         # append instead of truncate
```

The second ordering is not useless — `cmd 2>&1 >file | grep ...` is a real idiom
for piping *stderr* while stdout goes to a file. But it is deliberate, and worth
a comment when you write it.

## `>` truncates first

The shell performs redirections **before** it runs the command. So this sequence
happens:

1. The shell opens `data.txt` for writing, truncating it to zero bytes.
2. The shell starts `sort` with descriptor 1 attached to the now-empty file.
3. `sort` opens `data.txt` to read, and finds nothing.

```console
$ printf 'c\nb\na\n' > data.txt
$ sort data.txt > data.txt
$ wc -c < data.txt
0
```

Silent, exit status 0. Some tools detect it:

```console
$ grep -v DEBUG app.conf > app.conf
grep: app.conf: input file is also the output
$ wc -c < app.conf
0
```

`grep` warns and exits 2 — **and the file is still empty**, because the shell
truncated it before `grep` ran and had the chance to object. The warning tells
you what happened; it does not prevent it.

Three ways to do it correctly, with different costs:

```bash
# 1. a temporary file, then rename. atomic, safest, needs disk space.
grep -v DEBUG app.conf > app.conf.tmp && mv app.conf.tmp app.conf

# 2. sponge, which reads all input before opening the output
#    (from moreutils - not installed on every machine, including this one)

# 3. in-place editing, where the tool supports it
sed -i '/DEBUG/d' app.conf
```

The first is the one that always works and the one to reach for by default. The
`&&` matters: without it a failed `grep` still renames a truncated temp file
over your config.

`sed -i` is convenient and worth knowing precisely — it writes a new file and
renames it, so it is not really "in place", and it breaks hard links and can
change the inode. That matters when something is watching the file by inode, or
when the file is a bind-mounted config in a container.

## `noclobber`, and when it helps

```console
$ set -o noclobber
$ echo y > existing.txt
bash: existing.txt: cannot overwrite existing file
$ echo y >| existing.txt      # >| forces it
```

`noclobber` makes `>` refuse to overwrite. It is a useful interactive safety net
and a poor script-wide policy, because it changes the meaning of every `>` in
everything you source. In scripts, prefer being explicit about the temp-file
pattern; interactively, it has saved a lot of people's afternoons.

Note what it does **not** protect: it stops `>` clobbering an existing file, and
does nothing about `>>`, about `tee`, or about a tool writing the file itself.

## Where the output can go

```bash
cmd > file                # stdout to a file, truncating
cmd >> file               # stdout appended
cmd 2> errors.log         # stderr to its own file
cmd > out.log 2> err.log  # separated, which is often what you want
cmd > /dev/null 2>&1      # discard everything
cmd 2>/dev/null           # keep results, discard complaints
cmd | tee file            # to a file AND onward down the pipe
cmd | tee -a file         # appending
cmd | tee /dev/stderr     # to stderr and onward, for tracing a pipeline
```

`tee` is the answer whenever you want output in two places, and `tee -a` inside
a loop is how you build a log while still watching progress.

**Separating out and err into two files** deserves more use than it gets. It
makes "did this produce results, and did it complain" two independent questions,
which is exactly what you want when reading a job's output the next morning.

:::objective{id=OBJ-B08.2.4}
:::

---
topic: topic.finding-files
section: overview
title: Four ways to act on the wrong files
order: 1
mode: explain
---

A retention job, running weekly for two years:

```bash
find "$DIR" -name '*.log' -mtime +7 -exec rm {} \;
echo "cleanup complete"
```

It reports success every week. It has four separate faults, and none of them
produces an error.

## `-mtime +7` does not mean "older than 7 days"

It means **strictly more than seven whole 24-hour periods**, truncated. Measured
against files of known age:

```console
$ find archive -mtime +7 -printf '%f\n'
age-8d.log  age-10d.log  age-30d.log

$ find archive -mtime +6 -printf '%f\n'
age-7d.log  age-7d2h.log  age-8d.log  age-10d.log  age-30d.log
```

A file **seven days old is not matched by `+7`**. It is matched by `+6`. So a
policy of "delete anything older than seven days" written as `-mtime +7` keeps
everything for eight, and the discrepancy is invisible until somebody counts.

## `-exec cmd \;` throws away every failure

```console
$ find app -name '*.log' -exec false \; ; echo $?
0
$ find app -name '*.log' -exec false {} + ; echo $?
1
```

Identical intent, opposite reporting. With `\;` find runs the command once per
file and **ignores its exit status entirely** — every `rm` could fail and find
still exits 0. With `+` a failure reaches find.

The two forms also differ in cost: twelve files gave **twelve processes** with
`\;` and **one** with `+`.

:::predict{question="A directory inside the search path cannot be read. What does `find` return, and what does `find … | xargs rm` return?"}
:::

## A permission error does not stop anything

```console
$ find . -name '*.log' >/dev/null; echo $?
1
$ find . -name '*.log' | wc -l >/dev/null; echo $?
0
```

find reports 1 when it could not read part of the tree — and in a pipeline that
status is replaced by the last command's, so `find | xargs rm` proceeds happily
having skipped a whole subdirectory. The files it could not see are simply never
deleted, and nothing says so.

## `xargs` runs your command even with no input

```console
$ find . -name 'nomatch' -print0 | xargs -0 echo RAN
RAN
```

Nothing matched, and the command ran anyway with no arguments. For `echo` that
is harmless; for a command with a default target, or one that treats "no
arguments" as "everything", it is not. `xargs -r` suppresses it.

## And a fifth, which is about testing

Copying a directory to test a retention job destroys the thing being tested:

```console
$ cp -r archive copy   # every mtime is now today
$ cp -a archive copy   # mtimes preserved
```

`cp -r` gives every copy the current time, so a retention job run against it
correctly deletes nothing — and the test passes for the wrong reason.

## What you will do

Four labs on a seeded tree with files of known age:

- Predict which files four time predicates select, then measure — and find the
  one that excludes a file it was meant to include.
- Compare `-exec \;`, `-exec +` and two `xargs` forms on process count and on
  what happens when the command fails.
- Find out what `-prune` does that filtering afterwards does not, with a timing
  difference you can measure.
- Fix the retention job, and build a bulk-delete pattern that is reviewable
  before it runs.

:::objective{id=OBJ-B08.4.1}
:::

:::objective{id=OBJ-B08.4.2}
:::

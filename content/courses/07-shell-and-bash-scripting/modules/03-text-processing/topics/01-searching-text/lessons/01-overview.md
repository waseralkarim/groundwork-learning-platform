---
topic: topic.searching-text
section: overview
title: The tools you already use
order: 1
mode: explain
---

`grep` has appeared in fifty-eight lessons of this curriculum. `awk` in
twenty-two. Neither has ever been explained, which is exactly how most people
meet them — copied from an answer, adjusted until the output looked right, and
never read.

That works until one of three things happens.

## A successful search ends your script

```bash
set -euo pipefail
grep ' 401 ' access.log      # there are no 401s. good.
echo "all checks complete"   # never runs
```

`grep` returns **1 when it finds nothing**. That is not an error — it is the
answer — and `set -e` cannot tell the difference. The script exits 1 having
found exactly the good news it was looking for.

Run the seeded health check against a log with no server errors at all and it
fails immediately, printing one line. **The healthier the system, the sooner it
dies.**

There is a third status people forget: **2 means a real error** — the file could
not be read, the pattern was invalid. So `grep` distinguishes "no" from "broken"
and almost nobody uses the distinction.

## The same pattern means two things

```console
$ grep    'a+' file      # matches nothing — '+' is literal in BRE
$ grep -E 'a+' file      # matches 'a', 'aa', 'aaa' — '+' is an operator
$ grep    'a\+' file     # matches 'a', 'aa', 'aaa' — escaped, so it IS an operator
```

`grep` and `sed` default to **basic** regular expressions, where `+`, `?`, `|`
and `(` are literal characters. `grep -E`, `sed -E` and `awk` use **extended**
ones, where they are operators. The escaping is inverted between the two
dialects, so a pattern moved from one tool to another silently changes meaning
rather than erroring.

:::predict{question="A pattern is read from a config file. It is the literal text `[warn]`. You run `grep \"$pattern\" haystack.txt` against 16 lines. How many match?"}
:::

## Splitting a line is not one operation

```console
$ cut -d' ' -f2 access.log
                              # empty, for every line
$ awk '{print $2}' access.log
10.2.0.14
10.2.0.9
```

`cut -d' '` splits on **exactly one space**. Real command output — `ps`, `df`,
`ls -l`, any log with aligned columns — separates fields with *runs* of spaces,
so field 2 is the empty string between the first and second space.

`awk`'s default splitting treats a run of whitespace as one separator, which is
why it works on the output `cut` was reached for first. The failure is silent:
you get empty strings, not an error, and a downstream comparison against an
empty value usually succeeds at doing nothing.

## What this topic covers

The rules behind three tools you have been using without them:

- **grep** — its three exit statuses, the `set -e` interaction, the two regex
  dialects, and when a pattern must be matched literally.
- **awk** — field splitting that works on real output, plus `NR`, `NF` and
  `$NF`.
- **sed** — enough to substitute safely, and why its dialect matches grep's.

`find` and `xargs` are the next topic in this module; this one is about text
that is already in front of you.

## What you will do

Four labs:

- Watch a health check fail because the system is healthy, and fix it three
  different ways.
- Run the same pattern through four dialects and record where it changes
  meaning — including a pattern that matches every line in the file.
- Extract fields from ragged real output, find where `cut` returns nothing, and
  use `$NF` to survive a column being added.
- Build a report from a log using the right tool for each step, and defend each
  choice.

:::objective{id=OBJ-B08.3.1}
:::

:::objective{id=OBJ-B08.3.2}
:::

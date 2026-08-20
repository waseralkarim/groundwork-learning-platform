---
topic: topic.searching-text
section: internals
title: Splitting a line into fields
order: 3
mode: explain
---

Extracting a column is the most common thing anybody does to command output, and
the two obvious tools disagree about what a column is.

## `cut` counts separators; `awk` counts fields

```console
$ cat access.log
2026-08-17T02:14:01Z  10.2.0.14    GET   /api/orders   200   14ms
2026-08-17T02:14:07Z  10.2.0.9     POST  /api/orders   500 1204ms

$ cut -d' ' -f2 access.log
                        # empty. every line.
$ awk '{print $2}' access.log
10.2.0.14
10.2.0.9
```

`cut -d' '` splits on **exactly one space**, so two consecutive spaces produce an
empty field between them. Column-aligned output is full of runs of spaces, so
field 2 is the empty string.

`awk` with its default separator treats a **run** of whitespace — spaces, tabs,
any mixture — as a single separator, and ignores leading whitespace entirely.
That is why it works on the output people reach for `cut` to handle.

**The failure is silent.** You get empty strings rather than an error, and a
downstream `[ "$x" = "500" ]` quietly does nothing.

| Use | When |
|---|---|
| `cut -d,` / `cut -d:` | a real delimited format — CSV, `/etc/passwd` |
| `cut -c` | fixed-width columns, by character position |
| `awk '{print $2}'` | whitespace-separated output from any command |
| `awk -F,` | a delimited format where you also need logic |

The rule that survives: **`cut` for data files, `awk` for command output.**

## `$NF` survives a column being added

```console
$ awk '{print $NF}' access.log
14ms
1204ms
```

`NF` is the number of fields on the current line, so `$NF` is the last one and
`$(NF-1)` the one before. Counting from the right is more stable than counting
from the left, because new columns are usually added on the left — a timestamp,
a request ID, a pod name.

`NR` is the record number:

```bash
awk 'NR > 1 { print $3 }' services.csv    # skip a header row
awk 'NR == 1 { next } { total += $2 } END { print total }' file
```

`END` runs once after the last line, which is where sums and counts belong.
`BEGIN` runs before the first, which is where `FS` and headers go.

## An awk program is a set of pattern-action pairs

```awk
pattern { action }
```

Either half can be omitted. A pattern with no action prints the line; an action
with no pattern runs on every line. That is the whole language structure:

```bash
awk '/ERROR/'                       # like grep
awk '$5 == 500'                     # a field comparison grep cannot do
awk '$5 >= 500 { print $4 }'        # a numeric comparison, then a projection
awk -F: '$3 >= 1000 { print $1 }'   # a different separator
awk '{ n[$4]++ } END { for (k in n) print n[k], k }'   # count by field
```

The third line is the reason to reach for awk at all. `grep` matches text; awk
can compare a **field** numerically, which text matching cannot do —
`grep ' 500 '` also matches a 500-millisecond duration, and `$5 == 500` does not.

:::warning
`awk '$5 == 500'` compares numerically when the field looks numeric and as a
string otherwise. `$5 == "500"` is always a string comparison. Being explicit
avoids the case where `0500` and `500` disagree with your expectations.
:::

## Two ways to be wrong about whitespace

Setting `FS` to a single space is not the same as leaving it alone:

```bash
awk '{print $2}'          # default: runs of whitespace, leading trimmed
awk -F' ' '{print $2}'    # bash quotes it, awk still treats ' ' as the default
awk -F'[ ]' '{print $2}'  # a literal single space — behaves like cut
```

The middle form catches people out: a single space as `FS` is special-cased back
to the default behaviour. To genuinely split on one space you need the bracket
form — which is almost never what you want.

And tabs:

```bash
awk -F'\t' '{print $2}'   # a real tab-delimited file
```

The default separator already handles tabs mixed with spaces, so `-F'\t'` is
only for files where an **empty field** between two tabs is meaningful.

## sed, minimally and safely

`sed` earns its place for substitution on a stream. The parts worth knowing:

```bash
sed 's/old/new/'         # first occurrence on each line
sed 's/old/new/g'        # every occurrence
sed 's/old/new/2'        # only the second
sed -E 's/[0-9]+/N/g'    # ERE, so + works
sed -n '5,10p'           # print only lines 5-10; -n suppresses default printing
sed '/^#/d'              # delete comment lines
sed 's|/usr/local|/opt|' # any delimiter works — use | when the text has /
```

Two things that cause real damage.

**Greedy matching.** `.*` takes as much as it can:

```console
$ echo 'a "one" and "two" b' | sed -E 's/".*"/X/'
a X b
```

One replacement spanning both quoted strings, because `.*` ran to the *last*
quote. `[^"]*` is the fix: `s/"[^"]*"/X/g`.

**The delimiter is whatever follows `s`.** That is a feature — `s|a|b|` avoids
escaping slashes in paths — and it means a variable containing the delimiter
breaks the command, or worse, injects extra fields. Substituting untrusted text
with `sed` is not safe; use a tool that takes data as data.

## Choosing between them

- **grep** — does this line contain / match this? Fast, and the exit status is
  the answer.
- **awk** — I need a *field*, a comparison, or a total. Anything involving
  columns or arithmetic.
- **sed** — I need to change the text as it passes.
- **`cut`** — a genuinely delimited file, and nothing else.

The most common mistake is a chain that does all four badly:
`grep x | grep -v y | awk '{print $3}' | sed 's/,//'` is usually one awk program,
and the awk version is both faster and easier to read six months later.

:::objective{id=OBJ-B08.3.6}
:::

:::objective{id=OBJ-B08.3.7}
:::

---
topic: topic.finding-files
section: core-concepts
title: Predicates, time and pruning
order: 2
mode: explain
---

## find is an expression, not a command with flags

Everything after the starting path is one boolean expression evaluated against
each path. Adjacent tests are **ANDed implicitly**:

```bash
find /var/log -name '*.log' -type f -mtime +7
#              └── these three are ANDed
```

`-o` is OR and binds **more loosely** than the implicit AND, which is the source
of most surprising results:

```bash
find . -name '*.log' -o -name '*.txt' -delete     # deletes only the .txt files
find . \( -name '*.log' -o -name '*.txt' \) -delete   # both
```

In the first, the expression parses as `(-name '*.log')` OR `(-name '*.txt' AND
-delete)`. The `.log` files are matched and nothing is done to them; the `.txt`
files are deleted. **Always parenthesise an `-o`** when an action follows.

The other rule worth knowing: if you supply **no** action, `-print` is implied.
If you supply one — `-delete`, `-exec` — it is **not**, which is why adding
`-delete` to a working `find` makes the output disappear.

## Time predicates truncate to whole days

`-mtime n` compares **whole 24-hour periods, truncated**:

| Form | Means |
|---|---|
| `-mtime +7` | strictly more than 7 whole days — so 8 or more |
| `-mtime 7` | exactly 7 whole days — between 7 and 8 |
| `-mtime -7` | fewer than 7 whole days |

Measured on files of known age:

```console
$ find archive -mtime +7 -printf '%f '
age-8d.log age-10d.log age-30d.log

$ find archive -mtime +6 -printf '%f '
age-7d.log age-7d2h.log age-8d.log age-10d.log age-30d.log
```

**A file exactly seven days old is excluded by `+7` and included by `+6`.**
So "older than seven days" is `-mtime +6` if you mean "has lived seven full
days", and `+7` if you mean "has lived eight". Neither reading is wrong; writing
one and meaning the other is.

The way out is to stop using days:

```bash
find archive -mmin +10080        # 7 days, in minutes — no truncation surprise
find archive -newermt '-7 days'  # newer than a moment; negate for older
find archive ! -newermt '-7 days'
```

`-mmin` still truncates, to whole minutes, which almost never matters.
`-newermt` compares against an actual timestamp and is the clearest form when
the boundary matters — a retention policy, a compliance window, an audit.

:::warning
`-mtime` uses **modification** time. `-atime` is access time, which many
filesystems are mounted `relatime` or `noatime` to avoid updating, so it may be
meaningless. `-ctime` is inode-change time, which a `chmod` or a `chown`
updates — so a permission fix can make a file look recently touched to a
retention job.
:::

## `-prune` stops find descending

Two ways to exclude a directory, and they are not equivalent:

```bash
find . -not -path '*/node_modules/*' -name '*.log'      # filters afterwards
find . -path '*/node_modules' -prune -o -name '*.log' -print   # never enters
```

Both produce the same files. The first **walks the entire excluded tree** and
discards each path; the second never opens those directories.

Measured on a tree of 2,649 paths where the excluded subtree holds most of them:

```text
-not -path : 4ms
-prune     : 1ms
```

Four times, on a small tree. A real `node_modules`, `.git` or `vendor` directory
holds tens or hundreds of thousands of entries, and the difference scales with
it — which is why a `find` over a source tree can take minutes without pruning
and be instant with it.

The syntax deserves reading carefully:

```bash
find . -path '*/node_modules' -prune -o -name '*.log' -print
#      └── if it is node_modules, prune (and stop)
#                                  └── otherwise, if it matches, print
```

`-prune` is an **action** that returns true, so the `-o` short-circuits and the
rest is never evaluated for that path. And the explicit `-print` is required —
because you supplied an action, the implicit one is gone.

## The two `-exec` forms differ in three ways

```bash
find . -name '*.log' -exec gzip {} \;    # one process per file
find . -name '*.log' -exec gzip {} +     # batched, like xargs
```

| | `\;` | `+` |
|---|---|---|
| Processes for 12 files | **12** | **1** |
| `{}` position | anywhere, repeatable | must be last |
| Command fails → find's status | **ignored, find exits 0** | **propagated, find exits 1** |

The third row is the one nobody knows and it is the important one. A job that
does `-exec rm {} \;` will report success when every single `rm` failed.

Use `+` unless you specifically need one invocation per file — because the
command cannot take multiple arguments, or because you need `{}` in the middle
of the command line.

## xargs, and what it does when there is nothing to do

```bash
find . -name '*.log' -print0 | xargs -0 gzip
```

`-print0` and `-0` are the only safe pairing for arbitrary filenames — NUL is
the one byte a filename cannot contain. Without them, `xargs` splits on
whitespace **and interprets quotes**, so `a file.log` becomes two arguments and
`it's.log` produces an error about an unmatched quote.

Three flags that change behaviour materially:

```bash
xargs -r cmd        # do not run at all if input is empty (GNU)
xargs -n 20 cmd     # at most 20 arguments per invocation
xargs -I{} cmd {}   # substitute into a template — implies ONE item per command
xargs -P 4 cmd      # four in parallel
```

`-I` is the trap. It silently sets one item per invocation, so a pipeline
written for batching quietly becomes one process per file — the same twelve-to-one
difference as `\;` versus `+`, arrived at by accident.

And `-r` matters more than it looks. Without it:

```console
$ find . -name 'nomatch' -print0 | xargs -0 echo RAN
RAN
```

The command ran with no arguments. Whether that is harmless depends entirely on
the command.

:::objective{id=OBJ-B08.4.3}
:::

:::objective{id=OBJ-B08.4.4}
:::

---
topic: topic.searching-text
section: core-concepts
title: Exit status, dialects, literals
order: 2
mode: explain
---

## grep's three answers

| Status | Meaning |
|---|---|
| **0** | at least one line matched |
| **1** | no lines matched — a **result**, not a failure |
| **2** | an actual error: unreadable file, invalid pattern |

Most scripts treat anything non-zero as failure, which conflates "the thing you
searched for is not there" with "the search could not be performed". Those are
opposite findings.

```bash
if grep -q ' 500 ' access.log; then
  echo "server errors present"
fi
```

`-q` is the right form when you only want the answer: it exits at the first
match without printing, which is also faster on a large file.

And when you genuinely need to know which of the three happened:

```bash
if grep -q PATTERN "$f"; then
  found=yes
elif [ $? -eq 1 ]; then
  found=no
else
  echo "grep failed on $f" >&2; exit 1
fi
```

That is more code than most searches deserve — but on a file that might not
exist, the difference between "no matches" and "no file" is the whole finding.

## Why `set -e` makes this urgent

`set -e` exits on any command returning non-zero. `grep` returning 1 is the
normal outcome of a search that found nothing, so:

```bash
set -euo pipefail
grep ' 401 ' access.log     # no 401s — good news — script dies here
echo "clean"                # unreachable
```

**The healthier the system, the sooner the script exits.** And because `set -e`
exits silently, the symptom is a script that stops partway with no message and a
status of 1.

Three correct forms, depending on what you mean:

```bash
grep ' 401 ' access.log || true          # I do not care about the result
count=$(grep -c ' 401 ' access.log || true)   # I want the number, zero is fine

if grep -q ' 401 ' access.log; then      # I want to branch on it
  echo "auth failures found" >&2
  exit 1
fi
```

The third is usually what a health check actually meant. The first two are
honest about not caring, and the `|| true` deserves a comment saying which case
it is covering — the same rule as the deliberate unquoted expansion in B08.1.

:::warning
`|| true` on a whole pipeline also hides a status **2**. If the file might be
missing, check for it explicitly rather than swallowing every failure mode
together.
:::

## Two dialects, inverted escaping

:::diagram{src=../diagrams/regex-dialects.mmd caption="Which dialect a pattern is interpreted in depends on the tool and the flag. The escaping is inverted between BRE and ERE, so a copied pattern changes meaning silently."}
:::

| Dialect | Tools | How `+ ? ( ) { }` and alternation behave |
|---|---|---|
| **BRE** — basic | `grep`, `sed` (default) | literal characters |
| **ERE** — extended | `grep -E`, `sed -E`, `awk` | operators |
| **fixed** | `grep -F` | nothing is special |

Measured on one file containing `aa`:

```console
$ grep -c 'a\+' file      # 1  — escaped, so it is an operator
$ grep -c 'a+'  file      # 0  — literal '+', and there is no '+' in the file
$ grep -cE 'a+' file      # 1  — operator
```

`sed` behaves identically, which is at least consistent:

```console
$ echo aaa | sed 's/a\+/X/'      # X
$ echo aaa | sed 's/a+/X/'       # aaa   (unchanged)
$ echo aaa | sed -E 's/a+/X/'    # X
```

**Use `-E` by default.** Its dialect is the one you already know from every
other language, and the patterns are readable. The only reason to write BRE is
portability to a `sh` script that must run somewhere ancient — and `-E` has been
in POSIX since 2001.

What is *not* in either: `\d`, `\w` as you know them from Perl, and lookaround.
`grep -P` provides them where it is compiled in, and it is not portable. The
POSIX spellings are `[0-9]` and `[[:digit:]]`, and the bracket forms work
everywhere.

## A pattern from data is not a pattern

This is the one that produces silent wrong answers rather than errors.

```console
$ pattern='[warn]'
$ grep -c "$pattern" haystack.txt
16
$ grep -cF "$pattern" haystack.txt
1
```

Sixteen out of sixteen lines. `[warn]` is a **character class** matching any one
of `w`, `a`, `r`, `n` — and almost every English line contains one of those.
There is no error; the search simply answers a different question.

Other metacharacters that arrive from real data:

| Text | Also matches |
|---|---|
| `1.2.3.4` | `1x2y3z4` — `.` is any character |
| `v1.0.0` | `v1a0b0` |
| `cost: $5.00` | `$` is an anchor; the pattern may match nothing |
| `GET /api/orders?id=1` | `?` makes the preceding character optional (in ERE) |
| `C:\Users\app` | `\U` is an escape; behaviour varies |

**If the pattern came from a variable, a config file, a filename or a user, use
`grep -F`.** If you need part of it to be a pattern and part literal, build it
deliberately and escape the literal half — do not hope.

`grep -w` is the other one worth knowing:

```console
$ grep -w dev hosts       # matches 'dev' as a word
$ grep    dev hosts       # also matches 'device', 'devops', 'sandbox-dev2'
```

Half the "why is this matching that" questions are solved by `-w` or by anchors.

## Anchors and where matching starts

`^` and `$` bind a pattern to the start and end of a **line**, not of a field:

```bash
grep '^ERROR'        # lines beginning with ERROR
grep 'ERROR$'        # lines ending with it
grep -x 'ERROR'      # lines that are exactly that
```

A grep with no anchors matches anywhere in the line, which is why searching for
a short string in a log finds it inside timestamps, paths and IDs. Anchoring is
usually cheaper than making the pattern cleverer.

:::objective{id=OBJ-B08.3.3}
:::

:::objective{id=OBJ-B08.3.5}
:::

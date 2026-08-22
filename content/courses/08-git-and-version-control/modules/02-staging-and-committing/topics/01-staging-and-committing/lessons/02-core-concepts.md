---
topic: topic.staging-and-committing
section: core-concepts
title: One question, asked of three copies
order: 2
mode: explain
---

Every command in this topic is one of two things: a **comparison** between two
of the three copies, or a **move** of content from one to another. Once you can
name which pair or which direction, none of them need remembering separately.

## The comparisons

There are three pairs, and each has exactly one command.

| Pair | Command | Answers |
|---|---|---|
| working ↔ index | `git diff` | "what have I changed since I staged?" |
| index ↔ `HEAD` | `git diff --cached` | "what will this commit contain?" |
| working ↔ `HEAD` | `git diff HEAD` | "what have I changed since the last commit?" |

`--staged` is a synonym for `--cached`. The duplication exists because the index
is also called the cache, which is the same reason `git rm --cached` and
`git ls-files` sound like they belong to different tools.

:::warning
The command people reach for by reflex — plain `git diff` — is the *narrowest*
of the three. It cannot see anything you have staged. "I ran `git diff` and it
looked fine" is not a statement about what you are about to commit.
:::

## Status is those same three pairs, in two columns

```console
$ git status --short
MM config.py
 M notes.txt
A  newfile.py
?? scratch.log
```

Column one is **index vs `HEAD`** — staged. Column two is **working vs index** —
not staged. Read that way, the codes stop being a vocabulary list:

- `MM` — staged a change, then changed it again. **What you are about to commit
  is not what is on your disk.**
- `' M'` — modified, nothing staged
- `'A '` — newly added to the index, and disk matches it
- `'??'` — untracked. Not in the index at all, which is a different state from
  modified rather than a milder one

:::objective{id=OBJ-B10.2.2}
:::

:::objective{id=OBJ-B10.2.3}
:::

## The moves

```text
working  ──git add──▶  index  ──git commit──▶  HEAD
```

Content only ever moves right by those two commands, and `git add` is the one
that surprises people: **it writes a blob into the object store immediately.**
It is not a note to read the file later.

Three consequences, all of which are really the same one:

**Staged work survives losing the file.** The blob exists. `git checkout --
<path>` restores it from the index, and `git cat-file -p :<path>` reads it with
no commit involved.

**Editing after staging does not change the commit.** The index already holds
the earlier version by id.

**Staging over something does not erase it.** Each `git add` replaces the
*index entry*, but the previous blob is still an object — unreferenced, and
still there until `gc` runs.

## Moving left again

```text
HEAD  ──reset --mixed──▶  index  ──checkout -- <path>──▶  working
```

Moving content leftward is `git reset` with the amount of movement chosen by
flag, and this is the whole of it:

| | Moves | Can it lose work? |
|---|---|---|
| `--soft` | `HEAD` | No |
| `--mixed` | `HEAD` + index | No |
| `--hard` | all three | **Yes** — overwrites the working tree |

The modern spellings say what they do, and are worth preferring:

```console
$ git restore --staged <path>    # unstage, keep your edit    (was: git reset <path>)
$ git restore <path>             # discard your edit          (was: git checkout -- <path>)
```

`git checkout` was overloaded to mean both "switch branch" and "throw away my
changes to this file", which is a genuinely dangerous ambiguity — one of those
is trivially reversible and the other is not. `restore` and `switch` split it.

:::note
Only `--hard` and `git restore <path>` can destroy anything, and both destroy
the same thing: edits that were never staged and therefore never became an
object. Everything else moves pointers. That is why "reset is dangerous" is a
misleading summary — two of its three modes cannot lose a byte.
:::

## Why a commit can be a lie

Put the two halves together and the failure this topic exists for is obvious in
hindsight:

- `git commit` builds a tree from **the index**
- your tests, your editor, and your eyes are looking at **the working tree**

Nothing keeps those in step. Stage a fix, think again, edit, commit — and the
commit contains the version you staged while you carry on believing in the one
you can see.

```console
$ git cat-file -p :config.txt      # what will be committed
timeout = 60
$ cat config.txt                   # what you have been testing
timeout = 90
```

:::predict{question="Which single command, run before committing, would show you that these two disagree?"}
:::

Plain `git diff`. It compares working against index, so **empty means they
agree** and anything at all means they do not. That is the entire check, and it
is the one command most people already run — just not for this reason.

:::objective{id=OBJ-B10.2.1}
:::

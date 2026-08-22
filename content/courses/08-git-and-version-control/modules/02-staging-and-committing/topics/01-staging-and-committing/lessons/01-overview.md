---
topic: topic.staging-and-committing
section: overview
title: Why there is a step between editing and committing
order: 1
mode: explain
---

Most tools that version files have two states: what you have, and what you
saved. Git has three, and the extra one is the single most common source of
day-to-day confusion — *"I fixed it, but the fix isn't in the commit"*, *"why
does `git diff` show nothing when `git status` says modified?"*, *"what is the
difference between `--cached` and `--staged`?"*

None of those are quirks. They are all the same fact, seen from different
angles:

```console
$ git rev-parse HEAD:balance.txt      # what is committed
b2875d05c18a0346f39ce90365511f8a721e8410
$ git rev-parse :balance.txt          # what is staged
1098d6349b7e09de45963725179f89e1bf3c54e4
$ git hash-object balance.txt         # what is on disk
1fba146e9906555b51bad0ec80296e71d569c23f
```

**Three ids, one path, at the same moment.** One file, three versions of it,
all real and all addressable right now. Every command in this topic either
*reports* on differences between those three or *moves* content between them.

:::predict{question="If a file has three different versions at once, which one does `git commit` use?"}
:::

The staged one — always, without exception, and regardless of what is on disk.
That single rule explains the first complaint at the top of this lesson
completely: you staged, then you edited, then you committed the thing you
staged.

## The three copies, and where they live

| Copy | Lives in | Made of |
|---|---|---|
| **committed** | the object store, via `HEAD`'s tree | objects |
| **staged** | `.git/index` | an object id, plus cached stat data |
| **working** | the filesystem | ordinary files |

Two of the three are already objects. This is the part that surprises people:
**`git add` writes a blob immediately.** It does not mark a file to be saved
later — it hashes the contents, writes them into the object store, and records
the id in the index. `git commit` then builds a tree from the index and writes a
commit pointing at it.

:::note
So a commit is assembled from the index, not from your files. That is not a
gotcha — it is the *purpose*. The index exists so you can build the next commit
deliberately, a piece at a time, rather than being forced to commit whatever
happens to be on disk at that second.
:::

A useful consequence falls out immediately: **staged work survives losing the
file.** Once you have run `git add`, the content is a blob. Delete the file,
overwrite it, break your editor — the staged version is still in the object
store and still recoverable.

## Why the extra step earns its keep

The index is genuinely unusual, and the honest case for it is not "Git is
special":

**A commit should be one idea.** An afternoon's work often contains three —
a bug fix, a rename, and a stray debug line. Staging lets you commit the fix
alone, so the history reads as decisions rather than as a diary.

**Review works on commits.** A reviewer reading one focused change is doing
something different from a reviewer reading everything you touched since
Tuesday.

**And it is a real hazard**, which the rest of this topic takes seriously.
Because the commit comes from the index, you can commit a state that has never
existed on disk and has therefore never been run, never been tested, and never
been seen by anything except the diff you approved hunk by hunk.

```console
$ git cat-file -p :f.txt        # what will be committed
GOOD
BAD
$ cat f.txt                     # what is on disk and passing your tests
GOOD
BAD-fixed
```

That is not a hypothetical — it is what a `git add` followed by one more edit
produces, and it is measured in this topic's second lab.

:::objective{id=OBJ-B10.2.1}
:::

## Everything else is a comparison

Once three copies exist, the commands stop needing to be memorised
individually. `git status` compares all three and reports in two columns.
`git diff` compares a *pair*, and which pair depends on the flag. `git reset`
moves a pointer and then optionally drags the index and working tree along with
it.

:::diagram{src=../diagrams/three-copies.mmd caption="The three copies and the commands that move or compare them. add moves right to centre; commit moves centre to left; the three diffs each compare a different pair."}

That is the whole topic. The rest is making each of those precise enough that
you can predict the outcome before you press enter.

## What this topic covers

- Reading all three copies of a file directly, by object id
- `git status`, including both columns of the short form
- Which pair each of `diff`, `diff --cached` and `diff HEAD` compares
- What `git add` writes, and when
- `reset --soft`, `--mixed` and `--hard` as one question about how far to move
- When partial staging is worth its risk, and what to check before you commit

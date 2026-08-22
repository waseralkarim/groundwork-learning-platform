---
topic: topic.rebase-and-replay
section: core-concepts
title: Replay, and what changes when you replay
order: 2
mode: explain
---

## One commit, replayed

Rebasing a range is the same operation repeated. For each commit, in order:

1. Compute the change that commit made — its tree against its parent's tree.
2. Apply that change to the new base.
3. Write a **new commit** with the original message and author, the new parent,
   and a new committer timestamp.
4. Use that as the base for the next one.

Step 3 is where the id changes, and it changes for three independent reasons at
once: different parent, different tree, different committer timestamp. Any one
of them would be enough.

:::note
**Author and committer are different fields, and rebase is where the difference
becomes visible.** The author is who wrote the change and when; the committer is
who created *this object* and when. A rebase preserves the author and rewrites
the committer — which is why `git log` after a rebase still shows the original
dates, while the commits themselves are minutes old.
:::

## What survives and what does not

| Preserved | Replaced |
|---|---|
| the change itself | the commit id |
| message | the parent link |
| author name, email, date | the committer date |
| | the tree, if the base differed |

**"The tree, if the base differed"** is the one that surprises people. A
replayed commit's tree is *the new base plus this commit's change*, not the
original tree. So a rebased commit can contain a state that never existed on
your machine — and if the change interacts badly with what the new base
contains, that commit is broken even though it was fine where it was written.

This is why "each commit should build" is much harder to guarantee after a
rebase than before, and why CI running only on the final tip can pass over a
branch whose intermediate commits do not compile.

:::objective{id=OBJ-B10.4.1}
:::

## Ours and theirs are swapped

B10.3 flagged this as a warning. Here is why it happens.

During a rebase, Git checks out the **new base** and applies your commits to it
one at a time. So `HEAD` is the branch you are rebasing *onto* — and stage 2,
"ours", is that branch. Your own commit is stage 3, "theirs".

```text
merge   ours = the branch you are on = your work
rebase  ours = the branch you are moving onto = the other work
```

Nothing is inconsistent: "ours" always means `HEAD`, and a rebase moves `HEAD`
somewhere unexpected. But the practical effect is that `--ours` during a rebase
discards the change you were replaying, which is rarely what anyone wants at
that moment.

```console
$ git status
interactive rebase in progress; onto a1b2c3d
```

Reading that line before resolving is the habit worth having. It names the
operation, and the operation determines what the words mean.

:::objective{id=OBJ-B10.4.4}
:::

## Why the conflict comes back

A merge asks one question per conflicting region, between two finished states.

A rebase asks it once **per commit**, because each replay is a separate
application onto a different tree:

```text
merge     base ─────────────────► one resolution
rebase    D onto main ─► D'       resolve
          E onto D'   ─► E'       resolve again — different starting tree
```

Whether resolving `D'` helps `E'` depends on **how** you resolved it, and this
is worth measuring rather than assuming:

| Resolution of `D'` | What happens to `E'` |
|---|---|
| take your change | `E'` applies cleanly — the tree now matches what it expects |
| take the new base's value | `E'` conflicts **again**, on the same region |

Measured: with `main` at 99 and a branch bumping 1 → 2 → 3, resolving the first
conflict to `99` produces a second conflict of `ours=99, theirs=3`. Resolving it
to `2` produces no second conflict at all.

So the repetition is not automatic — it is what happens when each resolution
leaves the region still disagreeing with the next commit's expectation. On a
long branch that is easy to fall into, and it is why a ten-commit rebase can
present the same region ten times.

Two things help, and they are not the same thing:

**`git rerere`** records each resolution and replays it when the same conflict
appears again. It makes the repetition cheap. It does not make it stop, and it
replays an answer that may no longer be correct.

**Fewer commits to replay** makes the repetition stop. Squashing a branch before
rebasing, or simply keeping branches short, removes the condition rather than
the symptom.

:::objective{id=OBJ-B10.4.3}
:::

## Interactive rebase

```console
$ git rebase -i main
```

The replay list is opened for editing, and every line is an instruction:

| | |
|---|---|
| `pick` | replay it unchanged |
| `reword` | replay it, edit the message |
| `edit` | stop after replaying so you can amend |
| `squash` | fold into the previous commit, combining messages |
| `fixup` | fold into the previous commit, discarding this message |
| `drop` | do not replay it at all |

Reordering the lines reorders the commits. Deleting a line drops that commit.

All of it is still replay: **every surviving commit gets a new id**, including
the ones marked `pick`. There is no "leave this one alone" — a commit whose
ancestors changed must change, because its parent is part of its identity.

:::warning
`drop` and deleting a line do not delete anything. The commit becomes
unreachable, exactly like the originals in any rebase, and the reflog still
records where the branch was. Every mistake in an interactive rebase is
recoverable — which is worth knowing *before* you are staring at a list of
twelve commits deciding whether to press enter.
:::

## Undoing a rebase

```console
$ git reset --hard ORIG_HEAD
```

`ORIG_HEAD` is written before any operation that moves `HEAD` substantially, so
immediately after a rebase it names exactly where the branch was. One command,
and the original commits are reachable again.

If something else has happened since, the reflog holds the same information with
more history:

```console
$ git reflog
a1b2c3d HEAD@{0}: rebase (finish): returning to refs/heads/feature
9f8e7d6 HEAD@{5}: commit: the last commit before I started
$ git reset --hard HEAD@{5}
```

The rebased commits then become unreachable in turn — nothing is deleted in
either direction. B10.7 makes a topic of this; the point here is that the
recovery exists and is cheap, which should change how nervous the command makes
you.

:::objective{id=OBJ-B10.4.5}
:::

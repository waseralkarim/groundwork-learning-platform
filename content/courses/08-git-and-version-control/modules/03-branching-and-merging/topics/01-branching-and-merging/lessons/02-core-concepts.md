---
topic: topic.branching-and-merging
section: core-concepts
title: The base, the two sides, and the rule
order: 2
mode: explain
---

## Switching a branch moves three things

`git switch` is usually described as "changing branch", which hides what it
touches:

| | What changes |
|---|---|
| `HEAD` | now names the other ref |
| index | rewritten to that commit's tree |
| working tree | files updated to match |

All three, together. That is why switching with uncommitted changes is
sometimes refused — Git will not silently overwrite work that has no object
behind it. It is also why switching is *fast* regardless of how much history
exists: it is a checkout of one tree, not a replay of anything.

:::note
Git allows the switch when your changes do not collide with the difference
between the two trees, and carries them across. That is a convenience, not a
promise, and the moment a file differs on both sides it refuses. `git stash` or
a commit is the reliable answer.
:::

:::objective{id=OBJ-B10.3.1}
:::

## Finding the base

The **merge base** is the most recent commit reachable from both branches.

```text
        ╭─ D ─ E          (feature)
A ─ B ─ C
        ╰─ F ─ G          (main)
```

Both `E` and `G` can reach `C`, `B` and `A`. The most recent of those is `C`, so
`C` is the base. Git computes it from parent links alone:

```console
$ git merge-base main feature
```

Nothing recorded where `feature` started. The answer is derived, every time,
which is why branches can be created, deleted and renamed freely without
damaging anything.

:::predict{question="If `feature` has not moved since it was created, what is the merge base of `main` and `feature`?"}
:::

`feature` itself — the branches' most recent common commit is the tip of
`feature`. That is precisely the fast-forward condition seen from the other
side: **when the base equals one branch's tip, that branch has nothing to
contribute**, and the merge is a pointer move.

## The three-way rule

With a base, each side's change is knowable. For every region of every file:

| base → ours | base → theirs | Result |
|---|---|---|
| unchanged | unchanged | unchanged |
| **changed** | unchanged | **ours** |
| unchanged | **changed** | **theirs** |
| changed | changed, identically | that change |
| **changed** | **changed, differently** | **conflict** |

That table is the whole algorithm. Note what it does *not* need: any knowledge
of which branch is more important, which is newer, or who wrote what. A change
is taken because exactly one side made it.

Two things follow that surprise people:

**A deletion is a change.** If you edited a file and the other side deleted it,
that is row five — a conflict, and Git asks rather than guessing.

**Identical changes are not a conflict.** Two people fixing the same typo the
same way produces the same bytes, and there is nothing to decide.

:::objective{id=OBJ-B10.3.4}
:::

## Fast-forward, and the argument about it

```console
$ git merge feature          # base == main's tip → pointer moves
$ git merge --no-ff feature  # merge commit anyway
```

```text
fast-forward   A ─ B ─ C ─ D ─ E         history is linear; the branch vanishes

--no-ff        A ─ B ─ C ───────╮
                     ╰─ D ─ E ──M       the branch is visible forever
```

Both are legitimate and they optimise different things.

**Fast-forward** gives a linear history that is easy to read, easy to bisect,
and free of merge commits that record nothing interesting.

**`--no-ff`** keeps the fact that a set of commits belonged together. When
reverting a feature means reverting five commits, having one merge commit to
revert is worth a lot.

The rule worth applying: **fast-forward for a single commit, `--no-ff` for a
feature.** What you are really deciding is whether "this group of commits was
one piece of work" is information you want to keep.

:::objective{id=OBJ-B10.3.3}
:::

## What a merge commit is

```console
$ git cat-file -p HEAD
tree 226d1601...
parent ab899f59...      ← the branch you were on
parent d7e867a9...      ← the branch you merged
author ...
committer ...

Merge branch 'feature'
```

Two parents, and a tree that is the combined result. Both halves matter:

- The **tree** is the answer — a complete snapshot like any other commit, not a
  diff and not a pair of references.
- The **parents** are the record — which is what makes the branch visible in
  history and what `git log --graph` draws.

There is no third kind of object and no special-casing. A merge commit is an
ordinary commit that happens to have two parents, which is why every command
that walks history handles it without knowing it is special.

## Conflicts live in the index

When the rule's last row fires, Git writes all three versions into the index:

```console
$ git ls-files --stage conflicted.txt
100644 <base-blob>   1	conflicted.txt
100644 <ours-blob>   2	conflicted.txt
100644 <theirs-blob> 3	conflicted.txt
```

| Stage | Version |
|---|---|
| 1 | the merge base |
| 2 | ours — the branch you are on |
| 3 | theirs — the branch being merged |

**The markers in your file are a rendering of this**, produced so you have
something to edit. The authoritative state is the index, which is why:

- `git checkout --ours <path>` and `--theirs <path>` work — they pull stage 2 or
  stage 3 out directly.
- `git commit` refuses while any path has non-zero stages. There is no single
  version, so there is no tree.
- `git add <path>` *is* the resolution. It replaces the three entries with one.

:::warning
Stage 2 is "the branch you are on", not "your work". During a **rebase** your
commits are being replayed onto the other branch, so `HEAD` is the other branch
and **ours and theirs are swapped** relative to what you would expect. This
catches experienced people, and it catches them while they are already resolving
a conflict.
:::

:::objective{id=OBJ-B10.3.5}
:::

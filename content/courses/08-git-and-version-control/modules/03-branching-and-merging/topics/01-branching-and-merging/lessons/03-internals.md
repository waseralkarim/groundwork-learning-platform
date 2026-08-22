---
topic: topic.branching-and-merging
section: internals
title: How the base is chosen when there is more than one
order: 3
mode: explain
---

The three-way rule assumes there is *a* merge base. Usually there is. Sometimes
there are two, and what Git does about that is the reason its default strategy
is called `ort` — and was called `recursive` for the twenty years before that.

## Criss-cross history

```text
        ╭─ D ───── F        (main)
A ─ B ─ C    ╳
        ╰─ E ───── G        (feature)
```

If `D` was merged into the feature branch and `E` into `main` — each side
pulling from the other at different times — then both `D` and `E` are reachable
from both tips. Neither is an ancestor of the other, so **neither is more
recent**. There are two merge bases and no way to pick between them.

```console
$ git merge-base --all main feature
d4c1a9...
e77b02...
```

Picking one arbitrarily produces a merge that is subtly wrong: changes already
reconciled through the other base can reappear as conflicts, or worse, be
silently reverted.

## What the strategy actually does

The recursive answer is in the name. **Merge the bases with each other**,
producing a synthetic commit, and use *that* as the base for the real merge.
If those bases themselves have several bases, recurse again.

The result is a base that already accounts for the reconciliations both sides
have done, so previously-resolved conflicts do not come back.

:::note
`ort` — "Ostensibly Recursive's Twin" — replaced `recursive` as the default in
Git 2.34. Same algorithm, reimplemented to work on the index and object store
directly rather than by checking trees out to disk. It is faster and it fixes
several rename-detection bugs; the model this topic teaches is unchanged.
:::

## Renames are detected, not recorded

Git stores no rename information. A commit that renames a file is a tree with
one entry gone and another added, and the blob is unchanged — because content
addressing means moving a file cannot change its id.

So a merge that must combine "you renamed it" with "they edited it" *infers*
the rename:

- A path present on one side and absent on the other, plus
- a path added on that side whose blob is identical or highly similar

Identical content makes this exact. **Similar** content makes it a heuristic,
governed by a similarity threshold, and heuristics have failure modes: rename a
file and rewrite most of it in the same commit and Git may see a delete plus an
add, and drop the other side's edits into a file nobody will look at again.

That is worth knowing precisely because the fix is procedural: **rename in one
commit, rewrite in the next.** The intermediate commit costs nothing and makes
the rename unmissable.

:::objective{id=OBJ-B10.3.2}
:::

## Rerere: recording a resolution

```console
$ git config --global rerere.enabled true
```

**Re**use **re**corded **re**solution. When enabled, Git records the conflict
and the resolution you chose, keyed by the conflict's content. Meet the same
conflict again — replaying a rebase, merging a long-lived branch repeatedly —
and it applies your earlier answer automatically.

Two things to hold about it:

**It is a mitigation, not a fix.** The reason you are seeing the same conflict
repeatedly is usually a stale merge base, and back-merging solves that
permanently while rerere just makes the symptom cheaper.

**It replays an answer that may no longer be right.** The resolution was correct
for the code as it was. If both sides have moved on, applying it silently is
exactly the wrong outcome — so a recorded resolution deserves the same review a
fresh one would get.

## Why a merge cannot be "just a diff and apply"

It is tempting to think a merge could take `base..theirs` as a patch and apply
it to `ours`. That is what `git cherry-pick` does, and the difference is
instructive.

A patch describes *changes to specific lines in a specific context*. If `ours`
has moved that context, the patch may fail to apply, or apply in the wrong
place. A three-way merge instead asks a question about each region — *who
changed this?* — which does not depend on line numbers surviving.

```text
patch application     "put these lines here"        breaks when context moves
three-way merge       "who changed this region?"    works from content
```

Which is why cherry-picking the same change onto two branches and then merging
them can conflict, even though the change is "the same": the two applications
produced different commits, and relative to the base both sides changed the
region — differently, because context differed.

:::objective{id=OBJ-B10.3.4}
:::

## What none of this can see

Everything above operates on text. The merge base makes attribution possible,
recursion makes it correct with multiple bases, rename detection extends it
across moves — and none of it knows what the code *means*.

A rename of `send_email` to `send_notification` on one branch and a new call to
`send_email` on the other are, textually, two independent additions to different
regions of different files. Every mechanism in this lesson works perfectly and
the result does not run.

That is the boundary of the tool, and it is worth locating precisely: **Git
guarantees that no two edits to the same region were silently discarded. It
guarantees nothing about the combination.** Tests are the only thing that can,
and they have to run on the merge result.

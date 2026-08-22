---
topic: topic.rebase-and-replay
section: internals
title: How a replay is actually performed
order: 3
mode: explain
---

"Apply the change to the new base" is not one operation. Git has two ways to do
it, they fail differently, and knowing which one is running explains most
surprising rebase behaviour.

## Patch application, and its limits

The historical implementation turns each commit into a patch and applies it —
essentially `format-patch` piped into `am`. A patch says *"replace these lines,
which look like this, at roughly here"*, and applying it is a search for that
context in the target.

That works well and it has a specific failure mode: **the context has to be
findable.** If the new base rewrote the surrounding lines, the patch does not
apply, and you get a conflict even though nothing semantically incompatible
happened. Move the same code somewhere else in the file and the patch may apply
in the wrong place, or fail on a hunk that is really fine.

Patch application also cannot see renames, because a patch is per-file. A commit
touching `old_name.py`, replayed onto a base where it has become `new_name.py`,
finds no file to patch.

## Merge-based replay

The modern default replays each commit as a **three-way merge** instead, with:

| | |
|---|---|
| base | the commit's own parent |
| ours | the new base you are replaying onto |
| theirs | the commit being replayed |

That is exactly B10.3's rule, applied once per commit — and it inherits all of
its properties. It works from content rather than line positions, so moved code
does not defeat it. It detects renames, so a replayed commit follows a file that
was renamed underneath it. And it produces the same *kind* of conflict, with the
same three index stages you can read.

**This is also the mechanical answer to why "ours" is the other branch.** Ours
is `HEAD`, `HEAD` is the new base during the replay, so your commit is theirs.
Not an inconsistency — a consequence of which side the algorithm is standing on.

:::note
`git rebase --apply` selects the older patch-based path. It is occasionally
faster on long, simple ranges, and it is worth knowing that the flag exists so
that an unexpected `does not apply` error is recognisable as a *strategy*
symptom rather than a real conflict.
:::

## The trees are new, and that has consequences

Each replayed commit's tree is **the new base's tree with this commit's change
applied**. It is not the original tree, and it may be a state that has never
existed anywhere.

```text
original    D's tree = C's tree + D's change
replayed    D' tree  = main's tree + D's change     ← never existed before
```

Three consequences worth holding:

**A replayed commit can be broken while the original was fine.** If `main` added
something that interacts badly with `D`'s change, `D'` contains the combination
and nobody has ever run it. The conflict machinery sees nothing, because no
region was changed by both sides — B10.3's semantic conflict, arriving one
commit at a time.

**Intermediate commits are less trustworthy after a rebase.** "Every commit
builds" is a property of the commits as written; after replay it is a property
of combinations nobody tested. `git rebase -x 'make test'` runs a command after
each replayed commit and is the only way to actually establish it.

**Identical changes can collide.** If `main` already contains a change
equivalent to one you are replaying, the replay produces an empty commit. Git
notices and drops it, which is usually right — and is worth knowing about when a
commit you expected to see is not in the result.

:::objective{id=OBJ-B10.4.1}
:::

## Why the reflog makes all of this safe

Rebase moves a branch ref many times — once per replayed commit — and every one
of those moves is recorded:

```console
$ git reflog
a1b2c3d HEAD@{0}: rebase (finish): returning to refs/heads/feature
9f8e7d6 HEAD@{1}: rebase (pick): the second commit
5c4b3a2 HEAD@{2}: rebase (pick): the first commit
e1d2c3b HEAD@{3}: rebase (start): checkout main
7a6b5c4 HEAD@{4}: commit: where I actually was
```

The entry before `rebase (start)` is where the branch was, which is also what
`ORIG_HEAD` holds. Nothing in the sequence deletes an object — every original
commit is still in the store, unreferenced.

The window is `gc.reflogExpire`, ninety days by default for reachable entries
and thirty for unreachable ones. That is a long time, and it is not forever:
"recoverable" has an expiry, and it is worth knowing the number rather than
assuming it is infinite.

:::objective{id=OBJ-B10.4.5}
:::

## What none of this changes

A rebase produces different objects with the same content. It does not, and
cannot, change:

- **What the code does.** The changes are the same changes.
- **Whether the result is correct.** A clean rebase carries the same semantic
  risk as a clean merge, applied once per commit instead of once.
- **What other people have.** Their objects are on their machines, and no
  operation of yours reaches them.

That third one is the whole of the golden rule, stated as a fact about storage
rather than as advice.

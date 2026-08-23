---
topic: topic.undoing-things
section: internals
title: What each undo writes, and what it only reads
order: 3
mode: explain
---

Every command in this topic is built from operations B10.1 to B10.4 already
established. Sorting them by *what they write* makes the differences structural
rather than memorised.

| | Writes objects | Moves a ref | Reads |
|---|---|---|---|
| `restore <path>` | no | no | a tree, into files |
| `reset` | no | **yes** | a tree, when `--mixed`/`--hard` |
| `revert` | **yes** — one commit | yes, forward | two trees, to compute an inverse |
| `cherry-pick` | **yes** — one commit | yes, forward | two trees, to compute a change |

**Only two of them create anything.** Reset and restore write no objects at all
— reset moves 41 bytes, restore rewrites files. Nothing new enters the store,
which is exactly why neither can be "undone" by recovering an object: there is
no new object, only a pointer that used to be somewhere else.

## Revert and cherry-pick are the same machinery

Both compute a change between two trees and apply it to a third. They differ in
sign:

```text
cherry-pick   apply   (commit^ → commit)   to HEAD
revert        apply   (commit → commit^)   to HEAD
```

That is the whole difference. Which is why they share behaviour people find
surprising in one and expect in the other:

- **Both can conflict**, because both apply a change whose context may have
  moved. A revert conflicting is exactly as ordinary as a cherry-pick
  conflicting.
- **Both use the three-way machinery** from B10.3, so both produce index stages
  1, 2 and 3, and both are resolved with `git add` followed by `--continue`.
- **Both produce an empty result** when the change is already present, and both
  stop and ask rather than committing nothing.

:::note
This is why `git revert --continue` and `git cherry-pick --continue` exist and
behave identically, and why `git status` during either one reads much like a
merge. They are merges — of a computed change rather than of a branch.
:::

## Why cherry-pick can produce an identical object

Measured in the lab: cherry-picking onto a branch that has not moved since the
source's parent yields **the same id**.

Work through the inputs. A commit object contains its tree, its parent, its
author with timestamp, its committer with timestamp, and its message. In that
case:

- **parent** — the same, because the target is that parent
- **tree** — the same, because the same change applied to the same base
- **author, committer, timestamps, message** — copied unchanged

Every input identical, so the SHA-1 is identical, so the object already exists
and nothing is written. Git does not detect this and deduplicate; there is
nothing to detect. Writing an object that already exists is a no-op by
construction.

**A revert never does this**, because its message differs (`Revert "..."`) and
its tree is the pre-change state at a point after the change — so at minimum the
message input differs.

:::objective{id=OBJ-B10.5.3}
:::

## What "already merged" means to a revert

The reverted-merge behaviour has a structural explanation, not a special case.

A merge is a commit with two parents. Reverting it produces an ordinary commit
whose change is the inverse of what the merge introduced. **The merge commit
itself is untouched**, still in history, still naming the branch's tip as its
second parent.

So when you later ask Git to merge that branch again, the question it answers is
*what is reachable from the branch that is not reachable from here?* The answer
is nothing — the merge commit still reaches all of it.

```console
$ git merge feat
Already up to date.
```

Correct, and unhelpful. Reachability is unchanged; only the *content* changed,
via a later commit. Merge does not look at content, so the way back is to undo
the commit that changed it.

:::objective{id=OBJ-B10.5.5}
:::

## Why reset cannot be recovered by object id alone

Everything reset removes is still an object — B10.4 measured that. But note what
is *not* recoverable from the objects: **which commit the branch pointed at.**

A commit does not record which branches contained it. So after a reset, finding
the old tip means consulting something that records ref history:

```console
$ git reflog                     # every position HEAD has held
$ git reflog show <branch>       # every position that branch has held
$ git fsck --unreachable         # objects nothing leads to, unordered
```

The first two are ordered and labelled; the third is a pile. That difference
matters when recovering: the reflog tells you *where you were*, while `fsck`
tells you *what exists*, and only one of those answers the question you have.

And the reflog is per-repository and local. A colleague's clone has its own,
which is why the person who lost work is usually the only one who can recover
it — a point the B10.4 troubleshooting scenario turns on.

## The one asymmetry worth remembering

```text
objects        append-only, content-addressed, never modified
refs           mutable, and the only record of their history is the reflog
```

Every undo in this topic is an operation on the second line. That is why
recovery always reduces to the same question — *what did this ref point at
before?* — and why the reflog, rather than the object store, is the thing that
expires.

---
topic: topic.undoing-things
section: production
title: Undoing things while people are watching
order: 5
mode: explain
---

Undo commands are used most under time pressure, by the person least able to
reason carefully at that moment. So the useful preparation is not knowing more
commands — it is having already decided which one you will reach for.

## The incident sequence

Production is broken and a specific commit is responsible.

**Revert it. Now.** Not reset, not a fix-forward commit, not a discussion about
history shape.

```console
$ git revert --no-edit <bad-commit>
$ git push
```

It adds a commit, so nobody else has to do anything. It works on `main`. It
needs no force-push and no coordination, and it is reversible by the same
mechanism if you get the wrong commit.

**Two things to expect while doing it:**

**It may conflict.** A revert is an inverse patch, and if the surrounding lines
have changed since, the context it needs is gone. That is a merge, under
pressure. It is a reason to revert promptly rather than eventually.

**If the target is a merge commit, you need `-m 1`.** Git refuses without it
rather than guessing which parent is the mainline. Knowing this in advance turns
a confusing error into a keystroke.

:::warning
And the consequence to write down at the time: **re-merging that branch later
will not bring the work back.** Git still considers it merged, so you will get
`Already up to date` at precisely the moment someone expects a large diff. The
way back is to revert the revert. The person merging the fix next week is rarely
the person who reverted it.
:::

## Fix-forward versus revert

Reverting is not always right. The honest comparison:

| | Revert | Fix forward |
|---|---|---|
| Time to safe | one command | as long as the fix takes |
| Confidence | high — restores a known-good state | depends on the fix |
| Cost | the feature is out until re-landed | none, if the fix works |

**Revert when** you do not yet know the cause, the blast radius is large, or the
fix will take more than a few minutes. Restoring a known-good state is almost
always faster than reasoning correctly while alarms are firing.

**Fix forward when** the cause is understood, the change is small and obvious,
and reverting would itself be disruptive — reverting a database migration is
frequently worse than the bug.

The failure mode is choosing fix-forward because reverting feels like an
admission. That is not an engineering criterion.

:::objective{id=OBJ-B10.5.6}
:::

## What revert cannot undo

A revert changes the code. It does not change what has already happened.

**A leaked secret stays leaked.** B10.1 measured this: the blob is in every
clone, fork and CI cache that fetched it, and a later commit removing the file
does nothing to it. Rotate the credential first. Every Git operation afterwards
is hygiene.

**A released artefact stays released.** Reverting the commit does not unpublish
the package, roll back the deployment, or reach the customers who already
downloaded it. Reverting is one step of an incident response, not the whole of
it.

**A destructive migration stays run.** If the commit dropped a column, reverting
the code leaves the column dropped. Undoing data requires a data operation, and
the revert may make things worse by pointing code at a schema that no longer
exists.

The general shape: **revert undoes a change to the repository, and the
repository is only one of the places the change went.**

## Cherry-pick as a release practice

The common pattern — fix on `main`, cherry-pick onto the release branch — is
also the reliable way to produce the same change as two unrelated commits, with
the consequences the troubleshooting scenario covers.

The alternative is worth adopting deliberately:

**Commit the fix on the oldest branch that needs it, and merge forward.**
`release-4.2` → `release-4.3` → `main`. The change exists once. Every branch
acquires it by merging, so `git branch --contains` is meaningful, a later revert
is visible to every merge that follows, and there is no duplicate to reconcile.

When you genuinely must pick — the release branch will never be merged back —
use `-x`. It appends the source id to the message and is the only record Git
will keep.

:::objective{id=OBJ-B10.5.4}
:::

## What to standardise

**Worth standardising:**

- **Revert as the default incident response**, so nobody is deciding under
  pressure.
- **Branch protection on `main` and release branches.** Every force-push
  incident happens on a team that already understood the convention. A
  convention is not a control.
- **Merge-forward over cherry-pick** between branches that will meet.
- **`--force-with-lease` never `--force`**, on the branches where forcing is
  allowed at all.

**Not worth standardising:**

- **Banning `reset`.** It is correct for local work, and rules that forbid safe
  things get ignored — which weakens the rules that matter.
- **History aesthetics.** No incident in this topic was caused by the log
  looking untidy.

## Three sentences to keep

**Revert adds, everything else replaces** — which is why revert is the only undo
that costs other people nothing.

**"The commit is in history" and "the change is in the tree" are different
claims**, and only the second one determines whether the bug is back.

**Revert undoes a change to the repository**, and the repository is only one of
the places the change went.

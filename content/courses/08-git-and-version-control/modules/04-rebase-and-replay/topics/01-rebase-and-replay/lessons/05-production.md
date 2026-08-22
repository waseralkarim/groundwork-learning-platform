---
topic: topic.rebase-and-replay
section: production
title: The rule is about other people, not about you
order: 5
mode: explain
---

Almost every rebase argument is conducted as a matter of taste, and almost every
rebase *incident* has the same cause. Separating those two things is the useful
part of this topic.

## The only irreversible operation here

Everything a rebase does to your own repository is undone by one command.
`ORIG_HEAD` names where you were; the original commits are still objects; the
reflog holds the trail. You cannot lose committed work by rebasing.

**Force-pushing a rebased shared branch is different in kind**, and the
difference is not that it is more destructive locally — it is that what it
destroys is not local at all:

- Colleagues holding the old commits now have a history that disagrees with the
  remote, and nothing tells them why.
- Work they built on top of your old commits is now based on commits that no
  branch reaches.
- Their recovery involves rebasing *their* work onto your new commits, which
  they did not choose and may not understand.
- Open pull requests, CI runs and review comments anchored to the old ids point
  at objects the remote no longer reaches.

None of that is recoverable by you, because none of it is on your machine. That
is the whole asymmetry, and it is why the rule is stated as *"do not rebase
commits anyone else has"* rather than *"be careful with rebase"*.

:::warning
`git push --force` overwrites the remote unconditionally. `git push
--force-with-lease` refuses if the remote moved since you last fetched, which
catches exactly the case where somebody else pushed while you were rebasing.
There is no reason to prefer the first, and the second has saved more work than
any policy about history shape.
:::

:::objective{id=OBJ-B10.4.6}
:::

## When rebasing is unambiguously fine

Stated as facts about who holds the commits, so the answer does not depend on
anyone's preference:

**Nobody else has them.** A local branch you have never pushed. Rebase freely,
reorder, squash, reword — there is nobody to disagree with.

**Only you have them, on a branch that is yours by convention.** A pushed
feature branch that the team treats as one person's. Rebasing and
force-with-leasing is normal, and the convention is doing the work — which means
it has to be an actual convention, not an assumption.

**Everyone involved agreed just now.** Two people on one branch can rebase it as
long as the second one knows. This works and it does not scale, which is a
reason to prefer short branches rather than a reason to ban it.

And the case that is never fine: **a branch other people build on** — `main`, a
release branch, a long-lived integration branch. Not because rebasing them is
technically different, but because the number of people who must repair their
own repositories is large and they did not choose it.

## Rebase before review, merge after

The practice that avoids most of the argument:

**Before a pull request is opened**, rebase as much as you like. Tidy the
commits, squash the "wip" ones, rewrite the messages you wrote at 6pm. Nobody
else has them, so nothing is at stake.

**Once review has started**, stop rewriting. Reviewers anchor comments to
commits and diffs; rebasing invalidates that, and a reviewer who has read three
of your five commits has to start over. Add fixup commits instead, and squash at
merge time if the team wants a tidy result.

That split gets the readable history rebasing is wanted for, and pays none of
the cost — because the rewriting happens while the commits are still private.

## The interaction with CI

A rebase produces commits whose trees never existed before, so **what CI tested
before the rebase is not what exists after it.** If your pipeline runs on the
branch, a rebase invalidates its result completely — the ids are different and
the trees may be too.

Two consequences:

**Re-run CI after any rebase**, and treat a green run against pre-rebase ids as
evidence about nothing.

**A branch that must be rebased onto `main` before merging is being tested
twice, or not enough.** This is what merge queues address: rather than each
author rebasing and hoping, the queue builds the exact tree that will land, in
order.

## The honest summary of the taste argument

**For rebasing:** history reads as a sequence of considered changes rather than
a diary of what happened. `git log` is genuinely more useful. `bisect` lands on
commits that are meant to be coherent.

**Against rebasing:** the linear history is a fiction. Work *was* parallel, and
a merge records that. The commits you get are ones nobody ever tested in that
form.

Both are true, and the question is which fiction serves the reader better —
which is a team decision, not a correctness one.

What is **not** a matter of taste, and is where the incidents come from:

**Rewriting commits other people hold.** No history-shape preference makes that
safe, and no argument about readability has ever been the cause of a bad
afternoon. The bad afternoons are always somebody force-pushing a branch that
somebody else had.

:::objective{id=OBJ-B10.4.6}
:::

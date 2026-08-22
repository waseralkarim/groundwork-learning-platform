---
topic: topic.branching-and-merging
section: production
title: Why long branches are the only real problem
order: 5
mode: explain
---

Almost every merge pathology teams complain about has one underlying cause, and
it is not the merge algorithm.

> **The merge base gets older, and everything gets worse at once.**

Conflicts multiply, resolutions get harder to judge, semantic conflicts get more
likely, and the window a mistake can span grows. Fixing the branch length fixes
all four; fixing any of the four individually fixes none of the others.

## What branch age actually costs

A merge only has to reason about work done since the base. So the amount of
divergence a merge must handle is proportional to how long ago the two sides
last agreed — and that number is entirely under your control.

| Branch age | What the merge must reconcile |
|---|---|
| 1 day | one day of `main` against one day of yours |
| 4 weeks | four weeks of everyone's work against yours |

The second is not four times harder than the first. It is worse than that,
because conflicts interact: resolving one changes the context for the next, and
a resolver who has been at it for an hour is making worse decisions than one who
started five minutes ago.

**Back-merging advances the base.** Merge `main` into your branch and commit it,
and everything reconciled is permanently reconciled — the next merge starts from
there. Weekly back-merges turn one large merge into several small ones, and the
small ones are individually easier than the large one is per-conflict.

:::objective{id=OBJ-B10.3.7}
:::

## A clean merge is not a passing test

This bears repeating because it is the failure that reaches production.

Git guarantees exactly one thing: **no two edits to the same region were
silently discarded.** It does not know what the code means, so it cannot see
that a renamed function and a new caller of the old name are incompatible.

Which gives the rule about where CI runs:

```text
CI on the feature branch   tests a tree nobody will ship
CI on the merge result     tests the tree that will land
```

If `main` has moved since you branched, those are different trees. Both branches
being individually green is precisely the condition that produces a broken
`main`, and it is why merge queues exist — they build the exact tree that is
about to become `main`, one at a time.

:::warning
A merge queue tests the combination against `main` **at that moment**. Two
changes landing close together can still interact in a way neither test saw.
Shorter branches narrow that window; nothing closes it entirely, which is an
argument for being able to revert quickly rather than for more gates.
:::

## Resolve regions, not files

The most damaging merge mistake is not a badly-judged conflict. It is a
resolution taken at the wrong granularity.

`git checkout --ours <path>` and a merge tool's "use my version" replace the
**entire file** with one side's copy — including every region that side never
changed. Against a recent base that is nearly harmless. Against a four-week-old
base it silently reverts four weeks of the other side's work in that file, and
reports nothing, because nothing conflicted in those regions.

The two safeguards are the same ones as above: resolve at region granularity,
and keep the base recent enough that a mistake cannot span much.

:::objective{id=OBJ-B10.3.6}
:::

## What to standardise, and what not to

Teams reach for policy after a bad merge, and usually reach for the wrong lever.

**Worth standardising:**

- **Branch lifetime.** Days, not weeks. This is the one that fixes multiple
  problems at once.
- **Where CI runs.** On the merge result.
- **Resolution granularity.** Regions, and never a whole-file take on a stale
  branch.
- **`--no-ff` for features, fast-forward for single commits.** Cheap, and it
  makes `git revert -m 1` available when you need it most.

**Not worth standardising:**

- **History shape as an aesthetic.** Linear-versus-merges is a real trade, but
  it is not what broke your build, and `git log --first-parent` gives the linear
  *view* without discarding anything.
- **More approvals.** A reviewer looking at a feature's diff cannot see a
  semantic conflict with a change on another branch. Adding reviewers adds
  latency against a defect they cannot detect.

The distinction worth carrying: the first list changes **what gets tested and
how much divergence exists**. The second changes how things look and who signs
off. Only the first reaches the defects.

## Three sentences to keep

**A merge is defined relative to the base**, so the base's age is the single
number that predicts how hard a merge will be.

**No conflict means no two edits touched the same region** — nothing more, and
in particular nothing about whether the result works.

**Whole-file resolutions discard regions nobody was arguing about**, which is
how a merge silently removes work that never conflicted.

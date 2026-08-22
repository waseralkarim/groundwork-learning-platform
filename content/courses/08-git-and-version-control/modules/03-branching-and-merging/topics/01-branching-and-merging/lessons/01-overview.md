---
topic: topic.branching-and-merging
section: overview
title: The question a merge is actually answering
order: 1
mode: explain
---

Two people change the same file. One adds a function at the top, the other
fixes a typo at the bottom. Git combines them without asking anyone anything.

Two people change the same *line*. Git stops and demands a decision.

Both of those look obvious once you have seen them, and neither is explained by
"Git compares the two versions". Comparing two versions cannot tell you which
side did what:

```text
  yours:  timeout = 90
  theirs: timeout = 30
```

Which is the change and which is the original? You cannot tell. One of you
raised it and the other left it alone, or one of you lowered it, or you both
edited it — and the correct outcome is different in each case.

:::predict{question="What extra piece of information would let you decide which side actually changed that line?"}
:::

The version it was **before either of you touched it**. If the original said
`30`, then one side changed it and the other did not, and the answer is `90`
with nothing to ask. If the original said `60`, both sides changed it and there
is a genuine decision to make.

That third version is called the **merge base**, and supplying it is the entire
trick:

> A merge does not compare two branches. It compares **each branch against the
> commit they last had in common.**

Everything else in this topic is a consequence of that sentence.

## Why the model makes this cheap

B10.1 established that a commit records its parents, which makes history a
graph rather than a list. The merge base is a question about that graph: *the
most recent commit reachable from both branches.* No extra bookkeeping, no
record of "where this branch came from" — the parent links already contain the
answer.

And B10.1 established that a branch is a file holding one commit id. So:

- **Creating a branch** writes 41 bytes and no objects.
- **Committing on it** rewrites those 41 bytes.
- **Merging** finds the base, combines, and writes a commit with *two* parents.

None of that requires a branch to know about any other branch. A branch does not
record where it diverged, because the graph already knows.

:::note
This is why "branching is expensive, avoid it" is advice from a different era of
tooling that outlived its reason by about fifteen years. In a system that copied
the tree, it was true. Here a branch is a pointer, and the thing people are
actually afraid of — merging — got easier the moment the base could be computed
rather than remembered.
:::

## Fast-forward is not a kind of merge

If nothing has happened on your branch since you left it, there is nothing to
combine. Git moves the pointer forward and stops:

```text
before        A ─ B ─ C          (main)
                    ╰─ D ─ E     (feature)

fast-forward  A ─ B ─ C ─ D ─ E  (main, feature)
```

No merge commit, because no merging happened. `main` was an *ancestor* of
`feature`, so the combined result already existed — and the merge base of the
two branches was `main` itself.

That is the case worth recognising, because the argument about `--no-ff` is
entirely about whether you want history to record that a branch existed at all.
Neither answer is wrong; they are different things to want.

## What a conflict actually is

A conflict is not "Git got confused". It is a precise condition:

> **Both sides changed the same region, relative to the base.**

When that happens Git does something more interesting than printing markers into
your file. It puts *all three versions* into the index at once — base, ours,
theirs — and refuses to write a tree until one of them is left. B10.2 met those
non-zero stages in passing; this is the topic where they matter.

Which is why `git add` is how you resolve a conflict. It replaces the three
competing entries with one, and once a path has a single version again there is
a tree to commit.

:::objective{id=OBJ-B10.3.4}
:::

## The merges that hurt do not conflict

The dangerous case is the opposite of the frightening one.

```text
  branch A:  renames  send_email()  ->  send_notification()
  branch B:  adds a new caller of   send_email()
```

Different files, different lines, no overlap. Git merges them cleanly and
reports nothing, and the result does not run. That is a **semantic conflict**,
and no version control system can catch it — the tool compares text and this is
a fact about meaning.

Worth stating plainly now rather than discovering later: **"it merged cleanly"
is not "it works".** A clean merge means no two edits touched the same region.
It says nothing about whether the combined result is correct, which is what the
test suite is for and why CI runs on the merge result rather than on either
branch.

## What this topic covers

- What switching a branch does to `HEAD`, the index and the working tree
- Reading a history's shape from parent links, and finding a merge base
- Fast-forward versus a true merge, and what each does to the graph
- The three-way merge, done by hand, so the attribution rule is visible
- Conflicts read from the index's stages rather than from the markers
- A merge that resolved cleanly and was wrong, and what would have caught it

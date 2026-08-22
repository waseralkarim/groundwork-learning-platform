---
topic: topic.staging-and-committing
section: production
title: The gap between what you ran and what you shipped
order: 5
mode: explain
---

Everything in this topic reduces to one sentence with operational consequences:

> **You test the working tree. You ship the index.**

Nothing keeps those in step, and every failure below is the same gap seen from a
different part of the pipeline.

## CI tests the commit, and that is not reassurance

A green build tells you something precise and narrower than people read it as:
**this commit does not break anything we test.** It does not say the commit does
what its message claims.

That distinction stops being pedantic the moment a commit is incomplete:

- The engineer's local run passed, against the working tree, which had the fix.
- CI passed, against the commit, which did not.
- Both results were correct. Neither was about the same code.

:::warning
"It worked locally and CI is green" describes two tests of two different files.
When those two are the same — which is the normal case — the phrase means what
people think. When they are not, it is exactly the situation that produces a
"fix" that changes nothing in production.
:::

The organisational version of this: **no test asserts that a change was made.**
Tests assert behaviour, and a commit that silently omits the fix leaves the old
behaviour in place, which the old tests are perfectly happy with. This is why
the check has to happen before the commit — nothing downstream is looking for
it.

## Pre-commit hooks usually lint the wrong copy

A pre-commit hook that runs `eslint .` or `black .` reads **the working tree**,
because that is what those tools read. The commit is built from the index. So a
hook can pass while the commit it approved contains something the hook never
saw — or fail on a file you deliberately left unstaged.

The fix is for the hook to check staged content specifically:

```console
$ git diff --cached --name-only --diff-filter=ACM
```

and lint those paths from the index rather than from disk. Frameworks that do
this properly stash unstaged changes for the duration of the hook, which is
`--keep-index` applied automatically — and is worth recognising as the same idea
rather than as framework magic.

:::objective{id=OBJ-B10.2.5}
:::

## Partial staging is worth it, with one condition

The case for it is real and gets stronger as a codebase ages. Commits that are
one idea are easier to review, easier to `revert` cleanly, and dramatically
better for `bisect` — which degrades badly when the commit it lands on does
three things, because you then have to work out which of the three.

The condition is that **the hunks are independent**. Splitting a fix from a
debug line is safe. Splitting a function from its only caller produces a commit
that cannot even parse, and the first person to check it out gets a broken tree.

Two practices make that judgement cheap:

**Run `git diff` before committing.** Empty means the commit matches your disk.
Non-empty means you are shipping something you have not run, and you should be
able to say why that is fine.

**Test the staged state when it matters.** `git stash push --keep-index` leaves
only what you staged on disk. Run the suite, then `git stash pop`.

## Reviewing for completeness, not just correctness

The failure mode this topic keeps producing is invisible to a reviewer asking
*"is this diff correct?"* — because it is. A one-line deletion is a perfectly
correct one-line deletion.

The question that catches it is *"does this diff do what the title says?"*

Cheap signals, in order of cost:

```console
$ git show --stat <commit>
 config.py | 1 -
 1 file changed, 1 deletion(-)
```

A change that raises a value must **add** a line. A pure deletion under the
title "raise pool timeout" is a mismatch you can see without reading the diff at
all. Reviewers are reliable at spotting incorrect changes and much weaker at
spotting incomplete ones, so it is worth making completeness an explicit
question rather than hoping.

## Where the index costs you at scale

On a very large repository, `git status` has to decide whether each tracked file
changed. The stat cache makes that cheap per file, but "cheap per file" times a
million files is still slow, and the usual symptoms are `status` taking seconds
and editors that run it constantly feeling sluggish.

The mitigations all reduce how much of the tree is examined — a filesystem
monitor so Git is told what changed instead of asking, index version 4 for a
smaller file, or a sparse index so untouched directories are not enumerated.
Each is a different way of avoiding the same per-file work.

The point worth carrying is that **`git status` is not free**, and it is not free
for a comprehensible reason: it is a three-way comparison over every tracked
path, and the index is what makes it merely fast rather than impossible.

## What to carry forward

**You test the working tree and ship the index.** One command closes the gap,
and it costs a second.

**A green build is evidence about the commit**, not about your intent. Both can
be true and unrelated.

**Partial staging buys a readable history and owes a check.** Take the trade —
and pay the check.

:::objective{id=OBJ-B10.2.7}
:::

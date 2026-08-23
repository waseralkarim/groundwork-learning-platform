---
topic: topic.undoing-things
section: core-concepts
title: Sorted by what they touch
order: 2
mode: explain
---

## The table that decides everything

| | History | Index | Working tree | Safe when shared |
|---|---|---|---|---|
| `restore <path>` | — | optional | **rewritten** | yes |
| `reset --soft` | **shorter** | — | — | no |
| `reset --mixed` | **shorter** | rewritten | — | no |
| `reset --hard` | **shorter** | rewritten | **rewritten** | no |
| `revert` | **longer** | — | change undone | **yes** |
| `cherry-pick` | **longer** | — | change applied | yes |

Two columns matter most. **History** — does the branch gain or lose entries? And
**safe when shared** — which is entirely determined by the first: losing entries
means other people's commits are no longer in your history.

## Reset: one command, three amounts

B10.2 measured this. Restating it here because it is half of "undo":

```text
--soft    HEAD                        work stays staged
--mixed   HEAD + index                work stays, unstaged   (the default)
--hard    HEAD + index + working      work is overwritten
```

The thing worth re-stating is what reset does *not* do: it does not remove a
commit from the middle. It moves the branch to a position, and everything past
that position stops being reachable.

```text
before   A ─ B(bad) ─ C          reset --hard to A
after    A                        ← C went too
```

Measured: three commits became one. If the mistake is not the most recent thing
you did, reset takes the good work after it as well, and that is usually the
reason to reach for revert instead — before any argument about shared history
comes into it.

:::objective{id=OBJ-B10.5.1}
:::

## Revert: an inverse patch, which can conflict

A revert computes the change a commit made and applies the opposite. That makes
it a **patch application**, with everything that implies:

```console
$ git revert <commit>
Auto-merging app.txt
CONFLICT (content): Merge conflict in app.txt
```

Measured, and worth expecting. If later commits changed the lines around the one
you are reverting, the inverse patch may not fit — the context it needs is gone.
Reverting something from three weeks ago in a file that has moved on will
frequently ask you a question.

That is not a failure. It is Git declining to guess, exactly as in a merge, and
the resolution is the same: fix the file, `git add`, `git revert --continue`.

:::note
This is worth knowing *before* an incident. "Revert the bad commit" sounds like
a single atomic action, and if the file has changed since, it is a merge you
will be doing under time pressure. Reverting promptly is easier than reverting
eventually.
:::

## Cherry-pick: a copy with no link

```console
$ git cherry-pick <commit>
```

Applies that commit's change to your branch and commits it. What it does *not*
do is record any relationship — no parent link, no reference, nothing in the
object.

So `git log` shows two commits with the same message and no indication they are
the same work. The only way to leave a record is `-x`, which appends
`(cherry picked from commit …)` to the message.

:::predict{question="You cherry-pick a commit onto a branch that has not moved since the source commit's parent. What is the new commit's id?"}
:::

**The same id.** Parent, tree, message, author and committer timestamp are all
identical, so every input to the hash is the same and the output is too. The
"copy" is the original object, and nothing new gets written.

Which separates two claims people run together: *cherry-pick creates a new
commit object* is always true; *cherry-pick creates a new id* is only true when
some input differs. Content addressing, behaving consistently.

:::objective{id=OBJ-B10.5.3}
:::

## Why revert is the only safe one

Everything above reduces to one distinction:

```text
adds to history      revert, cherry-pick      others receive a commit
replaces history     reset, rebase, amend     others must repair their clone
```

When you add, a colleague's `git pull` does what it always does — brings in a
commit. When you replace, their branch points at commits your history no longer
contains, and Git offers to merge two divergent histories that contain the same
work twice.

You cannot fix that from your machine, because the repositories needing repair
are not yours. That is the same sentence as B10.4's golden rule, and it is the
same sentence because it is the same mechanism.

:::objective{id=OBJ-B10.5.2}
:::

## The commit is in history; the change may not be in the tree

The last idea, and the one that catches experienced people:

```console
$ git branch --contains <fix-commit>
  main
$ git show main:validator.py | grep validate
def validate(batch):
    return batch.rows          ← the fix is not here
```

Both outputs are correct. `--contains` answers *is this commit reachable?*
Reading the file answers *is this change present?* A later revert, an
overwriting commit, or a merge that resolved toward a side without it will make
those two answers differ.

**Only the second question determines behaviour.** When a fixed bug comes back,
check the file before concluding anything — `git log -S '<string>' -- <path>`
then lists every commit that added or removed that text, which usually names the
culprit outright.

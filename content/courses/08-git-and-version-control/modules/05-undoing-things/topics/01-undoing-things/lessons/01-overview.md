---
topic: topic.undoing-things
section: overview
title: Four undos, and the question that picks between them
order: 1
mode: explain
---

"Undo the last thing" is four different requests, and Git has a command for
each. The reason people reach for the wrong one is that the commands are usually
learned as a list of recipes rather than as answers to a question.

The question is: **what do you want to have happened?**

| You want | Command | History |
|---|---|---|
| this file back how it was | `git restore <path>` | untouched |
| that commit not to be there | `git reset` | loses an entry |
| the *effect* of that commit gone | `git revert` | **gains** an entry |
| that commit's change here too | `git cherry-pick` | gains a copy |

Two of those change history's shape and two do not, and that distinction decides
which are safe to use on a branch other people have.

## Reset removes, revert adds

This is the pair people confuse, and the difference is not subtle once stated:

```text
reset   A ─ B ─ C ─ D          →   A ─ B ─ C
                                   D is unreachable; history is shorter

revert  A ─ B ─ C ─ D          →   A ─ B ─ C ─ D ─ D'
                                   D is still there; D' undoes its effect
```

**Reset** moves the branch pointer backwards. The commit is not deleted — B10.4
established that thoroughly — but it is no longer part of the branch, and anyone
else holding it now has a history yours disagrees with.

**Revert** leaves everything and adds a commit whose change is the inverse.
History gets longer. Nobody's existing commits move.

:::predict{question="Your colleague has already pulled the commit you want to undo. Which of the two can you use without anyone else having to repair their repository?"}
:::

Only revert. It adds; it does not replace. Every existing commit stays exactly
where it was, so nobody's history disagrees with yours — they simply receive one
more commit, which is what pulling is for.

That is the whole rule, and it is the same rule as B10.4's golden rule seen from
a different angle: **operations that add are always safe to share; operations
that replace are only safe while you are the sole holder.**

## Revert does not erase, and that is the point

A revert leaves the original commit in the log, visible, with its message. People
sometimes find this unsatisfying — the mistake is still there, in the record.

That is not a limitation. It is provenance:

- The change was made, for a reason, by someone.
- It was undone, for a reason, by someone.

Both facts are true and both are worth keeping. A history that shows a fix, a
revert, and a re-application tells a much more useful story than one where the
first two never appear — particularly to whoever is trying to work out why the
code looks the way it does eighteen months later.

:::objective{id=OBJ-B10.5.2}
:::

## Cherry-pick copies, and copies are not links

`git cherry-pick <commit>` applies that commit's change to your current branch
and makes a commit for it.

The word that matters is **applies**. Nothing links the new commit to the old
one. There is no record that they are related, no back-reference, nothing
`git log` can show you. You have two commits containing the same change, and Git
regards them as two commits.

Which produces the failure mode this topic exists to prevent: cherry-pick a fix
onto a release branch, later merge that branch back, and the change is now in
history twice. Sometimes that merges cleanly and the duplicate is harmless.
Sometimes it conflicts with itself, and the conflict is between two copies of
your own work — with nothing in the log explaining why.

:::note
There is a surprise here, measured rather than assumed. Cherry-picking does not
always produce a *different* id. If the target branch has not moved since the
source's parent, then the parent, tree, message, author and committer timestamp
are all identical — so the "copy" hashes to the same forty characters and **is**
the original object.

That is content addressing being consistent, and it means "cherry-pick makes a
new commit object" and "cherry-pick makes a new id" are different claims. Lab 2
measures both cases.
:::

:::objective{id=OBJ-B10.5.3}
:::

## The one that catches people: reverting a merge

```console
$ git revert -m 1 <merge-commit>
```

`-m 1` is required, because "undo this" is ambiguous when a commit has two
parents — you have to say which side to return to.

And then the part nobody expects: **you cannot simply re-merge that branch
later.** As far as Git is concerned the branch is still merged; its commits are
still reachable, so a second merge has nothing to contribute. You get "Already
up to date" and none of your work.

The change was undone by a *later* commit, not by unmerging anything. So the way
to bring it back is to revert the revert — which is why that phrase, which
sounds like a joke, is the standard answer.

:::objective{id=OBJ-B10.5.5}
:::

## What this topic covers

- The four undos, sorted by what they touch rather than by name
- Why revert is the only one safe on shared history
- What a cherry-pick actually produces, including when the copy is identical
- Diagnosing a change that appears twice, or that vanished after a merge
- Reverting a merge, and getting the work back afterwards
- Choosing between them by who holds the commits and what history should say

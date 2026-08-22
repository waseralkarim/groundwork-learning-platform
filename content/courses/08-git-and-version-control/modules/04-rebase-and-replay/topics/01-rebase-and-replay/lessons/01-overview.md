---
topic: topic.rebase-and-replay
section: overview
title: The word "rebase" is doing you a disservice
order: 1
mode: explain
---

The name suggests moving something. Take these commits, put them on a different
base, carry on. Nothing was created or destroyed — they were *moved*.

That is not what happens, and almost every confusion about rebase comes from
believing it.

## What actually happens

B10.1 established that a commit's id is a hash of its contents, and that those
contents include **the parent**. So a commit sitting on a different parent is,
necessarily, a different object:

```text
before                    after rebasing onto main

A ─ B ─ C  (main)         A ─ B ─ C ─ D' ─ E'   (main, feature)
     ╰─ D ─ E (feature)        ╰─ D ─ E          ← still here, unreachable
```

`D'` and `E'` are **new commits**. They contain the same changes, the same
messages and the same author — and different ids, different parents, and a new
committer timestamp. `D` and `E` are not modified and not deleted. They are
abandoned: still in the object store, still readable by id, reachable by nothing.

:::predict{question="If D and E still exist after a rebase, what would happen to a colleague who had already pulled them?"}
:::

Nothing, immediately — and that is the problem. They keep `D` and `E`, because
those commits are perfectly valid and their branch still points at them. You now
have `D'` and `E'`. Both histories contain the same *changes* as different
*commits*, and Git has no way to know they are related.

When they next pull, they get a history containing both. Their merge produces
every change twice, and the conflicts are between two copies of their own work.

**That is the entire content of the golden rule.** Not "rebasing is dangerous" —
it is completely safe on commits nobody else has. The rule is about who is
holding the objects you are about to orphan.

## Rebase and merge answer different questions

Both combine work. They record different things:

| | Merge | Rebase |
|---|---|---|
| Existing commits | untouched | replaced by copies |
| New objects | one merge commit | one new commit per replayed commit |
| History shape | records that a branch existed | linear, as if written in order |
| What it discards | nothing | the fact that the work was parallel |
| Conflicts | once, against the base | potentially once **per commit** |
| Safe on shared branches | yes | no |

The last row is not a matter of degree. A merge adds to history; a rebase
replaces part of it, and replacement is only safe while you are the only person
holding the originals.

:::note
"Rebase gives a cleaner history" is true and is a claim about *reading*.
"Rebase discards the fact that work happened in parallel" is the same claim from
the other side. Whether that fact is worth keeping is a real question with no
universal answer — which is why this topic argues about *when*, not *whether*.
:::

## Why conflicts can repeat

A merge resolves once: two finished states, one base, one decision per
conflicting region.

A rebase replays commits **one at a time**. Each replayed commit lands on a
different tree from the one it was written against, so each can conflict — and
resolving `D'` does not help `E'`, which is a separate application onto a
different starting point. A ten-commit branch can present the same conflict ten
times.

This is the practical reason `git rerere` matters more here than anywhere else,
and the reason a long branch is much worse to rebase than to merge.

:::objective{id=OBJ-B10.4.3}
:::

## Nothing here can lose work

Worth saying early, because rebase frightens people more than it should.

Every commit involved still exists as an object. The reflog records where the
branch pointed before the rebase, and `ORIG_HEAD` names it directly. A rebase
you dislike is undone with one command, and this is exactly B10.1's finding
applied: **unreachable is not gone.**

The genuine hazards are narrower and worth naming precisely:

- **Uncommitted work**, which has no object behind it — the same hazard as
  `reset --hard`, and the same fix: commit or stash first.
- **A force-push of a rebased shared branch**, which is not dangerous to you at
  all. It is dangerous to everyone else, and it is the only irreversible thing
  in this topic — because what it destroys lives on their machines and in their
  pending work.

## What this topic covers

- Watching a rebase produce new ids while the originals stay readable
- Rebase versus merge, by what each records and discards
- Why a conflict can come back once per commit, and what to do about it
- Which side is "ours" during a rebase, and why it is the opposite of a merge
- Recovering a branch you rebased away
- When rebasing is safe, stated in terms of who holds the commits

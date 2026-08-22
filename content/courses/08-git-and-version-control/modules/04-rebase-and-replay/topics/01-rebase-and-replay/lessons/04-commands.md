---
topic: topic.rebase-and-replay
section: commands
title: The commands, and the one that saves you
order: 4
mode: explain
---

## Rebasing

```console
$ git rebase main                    # replay this branch onto main
$ git rebase -i main                 # same, with the list opened for editing
$ git rebase --onto main old new     # replay new, taking old as the old base
$ git rebase --abort                 # back to where you started
$ git rebase --continue              # after resolving
$ git rebase --skip                  # drop the commit being replayed
```

`--onto` is the form worth learning, because it makes the operation general.
Plain `git rebase main` infers what to replay from the merge base; `--onto`
states the new base and the range separately, which is the only way to express
"move these commits somewhere else entirely":

```console
$ git rebase --onto main topic-a topic-b
```

Replay the commits on `topic-b` that are not on `topic-a`, onto `main`. That is
how you detach a branch that was accidentally started from the wrong place — a
common situation with no other clean answer.

:::warning
`--skip` discards the commit currently being replayed. During a conflict it is
easy to reach for when `--continue` is meant, and the discarded commit becomes
unreachable with no prompt. It is recoverable from the reflog, but you have to
notice it happened.
:::

## Seeing what will be replayed, first

```console
$ git log --oneline main..HEAD       # exactly the commits that will be replayed
$ git rev-list --count main..HEAD    # how many times a conflict could recur
```

`main..HEAD` is the range rebase will replay. Running it beforehand turns "this
might be unpleasant" into a number, and the number is the upper bound on how
many times you can meet the same conflict.

If it is large, the useful move is usually to reduce it — squash first, or merge
instead — rather than to start and find out.

## During a rebase

```console
$ git status                         # names the operation in progress
$ git ls-files --stage <path>        # the three competing entries
$ git cat-file -p :2:<path>          # ours — the branch you are replaying ONTO
$ git cat-file -p :3:<path>          # theirs — your own commit
$ git diff --diff-filter=U           # only the unresolved paths
```

Reading `git status` first is not ceremony. It prints `rebase in progress`, and
that line is what tells you `--ours` currently means the *other* branch. The
same command during a merge would mean the opposite.

:::note
`git checkout --ours <path>` during a rebase discards the change you are
replaying — your own work — which is almost never the intent. If you find
yourself reaching for it, check `git status` and confirm which operation you are
in before pressing enter.
:::

## Recording resolutions

```console
$ git config --global rerere.enabled true
$ git rerere status                  # what it is tracking right now
$ git rerere forget <path>           # discard a recorded resolution
```

More valuable during rebases than anywhere else, because a rebase can present
the same conflict once per replayed commit. `rerere forget` matters too: a
recorded resolution that is now wrong will be replayed silently, and forgetting
it is how you get asked again.

## Undoing

```console
$ git reset --hard ORIG_HEAD         # immediately after a rebase
$ git reflog                         # the fuller history of where HEAD was
$ git reset --hard HEAD@{5}          # back to a specific earlier point
$ git branch rescue <sha>            # give an abandoned commit a ref
```

`git branch rescue <sha>` is the gentler recovery. Rather than moving your
current branch, it gives the abandoned commits a name — so both histories exist
and you can compare them before deciding.

That is usually what you want after a rebase you are unsure about: not "undo",
but "let me see both".

:::objective{id=OBJ-B10.4.5}
:::

## Pushing a rebased branch

```console
$ git push --force-with-lease        # refuses if the remote moved
$ git push --force                   # overwrites unconditionally
```

**Use `--force-with-lease`.** It compares the remote's current tip against what
you last fetched and refuses if they differ — which is exactly the case where
somebody else pushed while you were rebasing, and exactly the work `--force`
would silently destroy.

The habit that makes it reliable is to `git fetch` immediately before pushing,
so the lease reflects reality rather than a stale idea of it.

:::warning
`--force-with-lease` protects against a *concurrent* push. It does not protect a
colleague who pulled your branch an hour ago and is working on it locally —
nothing on the remote records that. Only a convention about who owns a branch
covers that case.
:::

## The two commands to remember

```console
$ git log --oneline main..HEAD       # what am I about to replay?
$ git reset --hard ORIG_HEAD         # put it back
```

The first prevents most bad rebases. The second undoes the rest.

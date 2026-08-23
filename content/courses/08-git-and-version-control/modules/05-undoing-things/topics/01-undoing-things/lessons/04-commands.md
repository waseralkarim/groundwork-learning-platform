---
topic: topic.undoing-things
section: commands
title: The commands, and the ones whose names mislead
order: 4
mode: explain
---

## Undoing a file

```console
$ git restore <path>                    # discard working-tree changes
$ git restore --staged <path>           # unstage, keep the edit
$ git restore --staged --worktree <p>   # both
$ git restore --source=HEAD~3 <path>    # take the version from three back
```

`--source` is the one people miss. It turns `restore` into "give me this file as
it was at that commit", which is frequently what someone means when they reach
for something much heavier.

:::warning
`git restore <path>` with no `--staged` **overwrites your working-tree changes
with no confirmation and no recovery.** The edit was never staged, so no object
exists for it. This and `reset --hard` are the two commands in the topic that
can destroy work permanently.
:::

## Undoing a commit

```console
$ git revert <commit>                   # add a commit that undoes it
$ git revert --no-edit <commit>         # ...without opening an editor
$ git revert -m 1 <merge-commit>        # a merge: keep the first parent
$ git revert -n <commit>                # apply the inverse, do not commit yet
$ git revert --continue                 # after resolving a conflict
$ git revert --abort                    # give up
```

`-n` (`--no-commit`) is useful for reverting several commits into one commit:
apply each inverse without committing, then commit once with a message that
explains the whole rollback.

## Undoing a position

```console
$ git reset --soft <commit>             # move HEAD only
$ git reset <commit>                    # ...and the index (the default)
$ git reset --hard <commit>             # ...and the working tree
$ git reset --hard ORIG_HEAD            # undo the last big move
```

Worth stating once more because the name suggests otherwise: **reset does not
remove a commit from the middle of history.** It moves the branch to a position
and everything past that position stops being reachable, including good work
that came after the mistake.

## Copying a commit

```console
$ git cherry-pick <commit>              # apply its change here
$ git cherry-pick -x <commit>           # ...and record the source in the message
$ git cherry-pick A..B                  # a range, exclusive of A
$ git cherry-pick --continue            # after resolving
$ git cherry-pick --abort               # back to before
```

**Use `-x` by default.** Git records no link between a cherry-pick and its
source, so the message is the only place that information can live — and the
absence of it turns a two-minute diagnosis into an investigation.

## Names that mislead

| Command | What it suggests | What it does |
|---|---|---|
| `reset` | undoing a change | moving a branch pointer |
| `revert` | going back | going *forward*, with an inverse |
| `checkout -- <path>` | switching something | overwriting a file, destructively |
| `cherry-pick` | picking, i.e. selecting | copying, with no link to the original |

`git checkout` is the worst of these, which is why 2.23 split it into `switch`
and `restore`. Prefer the new names: the command that can destroy uncommitted
work should not be a typo away from the one that changes branches.

## Finding out what actually happened

```console
$ git show <commit>:<path>              # the file as of that commit
$ git log -S '<string>' -- <path>       # commits that added or removed that text
$ git log -G '<regex>' -- <path>        # commits whose diff matches
$ git branch --contains <commit>        # which branches reach it
$ git log --oneline --graph --all       # the shape
```

**`git log -S` is the single most useful command here.** When a fixed bug comes
back, it lists every commit that added or removed the relevant text, in order,
which usually names the culprit without any guessing.

:::note
`git branch --contains` answers *is this commit reachable* — not *is this change
present*. A revert, an overwrite, or a merge resolved toward the other side will
make those differ. Read the file with `git show <branch>:<path>` before
concluding anything.
:::

:::objective{id=OBJ-B10.5.4}
:::

## Recovering from the undo

```console
$ git reflog                            # every position HEAD has held
$ git reflog show <branch>              # every position that branch has held
$ git reset --hard ORIG_HEAD            # straight after a big move
$ git branch rescue <sha>               # name an abandoned commit
$ git fsck --unreachable                # objects nothing leads to
```

`git branch rescue <sha>` remains the gentlest option: it makes abandoned
commits reachable without moving your current branch, so both states exist and
can be compared before you commit to either.

## The three to memorise

```console
$ git show <branch>:<path>       # what the code actually says
$ git log -S '<string>' -- <p>   # who changed it
$ git revert <commit>            # undo it safely, wherever it is
```

The first two answer "is the fix really there and what happened to it". The
third is the only undo that costs nobody else anything.

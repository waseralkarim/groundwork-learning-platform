---
topic: topic.remotes-and-collaboration
section: commands
title: The commands, and the ones worth making reflexes
order: 4
mode: explain
---

## Looking without changing anything

```console
$ git remote -v                      # the names and their URLs
$ git ls-remote origin               # what the remote has, right now
$ git branch -vv                     # local branches and their upstreams
$ git config --get remote.origin.fetch
```

`git ls-remote` is the one people never learn. It asks the remote for its refs
and writes nothing — no objects, no ref updates, no change to your repository at
all. When you want the truth about a remote and are not ready to update your
notes, this is it.

## Fetching

```console
$ git fetch                          # the default remote
$ git fetch --all                    # every remote
$ git fetch --prune                  # drop refs for branches deleted remotely
$ git fetch origin main              # one branch
```

`--prune` is worth turning on permanently:

```console
$ git config --global fetch.prune true
```

Without it, `origin/feature-x` lingers for months after the branch is gone, and
tab-completion keeps offering branches nobody can check out.

## Integrating

```console
$ git merge origin/main              # explicit, after a fetch
$ git rebase origin/main             # explicit, replaying your work
$ git pull                           # fetch + whichever of the above is configured
$ git pull --rebase                  # fetch + rebase, this once
$ git pull --ff-only                 # fetch + refuse unless it fast-forwards
```

The first two are what `pull` does; running them separately is how you see the
divergence before deciding.

:::note
`git pull` with no upstream configured does nothing useful and says so. That is
usually the answer when someone reports pull "not working" on a new branch —
`git push -u origin <branch>` sets the upstream and fixes both directions at
once.
:::

## Pushing

```console
$ git push                           # to the configured upstream
$ git push -u origin <branch>        # push and set the upstream
$ git push --force-with-lease        # replace, if the remote is where I last saw it
$ git push --force                   # replace regardless
$ git push origin --delete <branch>  # remove a branch from the remote
```

**`--force-with-lease` compares the remote against your remote-tracking ref**, so
fetch immediately before using it or you are checking a question you already
know the answer to. And it protects only against a concurrent push — nothing on
the remote records a colleague who pulled an hour ago and is working locally.

:::warning
Pushing to a **non-bare** repository's checked-out branch is refused by default:

```console
remote: error: refusing to update checked out branch: refs/heads/main
remote: error: ...it will make the index and work tree inconsistent
```

Which is why servers hold bare repositories. It is not a permissions problem and
`--force` does not help.
:::

## Reading the situation

```console
$ git status -sb                                     # ## main...origin/main [ahead 1, behind 1]
$ git rev-list --left-right --count origin/main...HEAD
$ git log --oneline HEAD..origin/main                # what they have that I lack
$ git log --oneline origin/main..HEAD                # what I have that they lack
$ git log --graph --oneline --all
```

Note the **three dots** in `rev-list`: `A...B` is "reachable from either but not
both", which is what makes `--left-right` able to split the counts. Two dots is a
one-directional range and gives a different answer.

## Evidence about rewrites

```console
$ git reflog show origin/main
7d54e50 refs/remotes/origin/main@{0}: fetch: forced-update
62462da refs/remotes/origin/main@{1}: fetch
```

**This is the durable record.** The `(forced update)` line in fetch output
scrolls past in a second; the remote-tracking reflog keeps it, along with the
pre-rewrite id — which is what you need to rescue anything that was on the old
history.

:::objective{id=OBJ-B10.6.5}
:::

## Recovering after someone rewrote a shared branch

```console
$ git fetch origin
$ git reset --hard origin/main                       # no local work of your own
$ git rebase --onto origin/main <old-upstream> HEAD  # you had real commits
```

Choose by what your local commits actually *are*. If they are just the old
version of somebody else's work, take theirs. If they are yours, replay them onto
the new history rather than merging — merging drags the abandoned commits back
in, silently and successfully.

## The four to make reflexes

```console
$ git fetch                                # free, safe, and always first
$ git status -sb                           # where am I relative to what I know
$ git log --oneline HEAD..origin/main      # what is coming
$ git log --oneline origin/main..HEAD      # what I am about to send
```

Every diagnosis in this topic begins with those. The first one costs nothing and
makes the other three honest.

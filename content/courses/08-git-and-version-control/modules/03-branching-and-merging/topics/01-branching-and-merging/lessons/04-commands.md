---
topic: topic.branching-and-merging
section: commands
title: The commands, and the ones that lie about their names
order: 4
mode: explain
---

## Branching

```console
$ git switch <branch>            # move HEAD, index and working tree
$ git switch -c <new>            # create from HEAD and move to it
$ git switch -c <new> <start>    # create from somewhere else
$ git switch -                   # back to the previous branch
$ git branch -d <branch>         # delete, refusing if unmerged
$ git branch -D <branch>         # delete regardless
$ git branch --merged main       # which branches are fully contained in main
```

`git branch --merged` is the one worth adopting. It answers "what can I safely
delete?" from the graph rather than from memory — a branch listed there has
every one of its commits reachable from `main`, so deleting the ref discards
nothing.

`-d` applies the same test and refuses when it fails. `-D` skips it. Since a
branch is 41 bytes and the commits survive as unreachable objects either way,
`-D` is far less destructive than it looks — but `-d` telling you "not fully
merged" is genuine information about the graph.

## Inspecting the shape

```console
$ git log --graph --oneline --all        # draw the DAG
$ git log --first-parent                 # follow only merge first parents
$ git merge-base main feature            # where they last agreed
$ git merge-base --all main feature      # every base, when there are several
$ git rev-list --count base..main        # how far one side has moved
$ git diff --name-only base..main        # what one side touched
```

**`--first-parent` deserves more use than it gets.** On a history built with
`--no-ff`, it shows one entry per merged feature and hides the commits inside —
exactly the view squashing is usually adopted to produce, available on demand
and without destroying anything.

Sizing a merge before attempting it is two commands: compare
`diff --name-only base..main` with `base..feature`, and the intersection is the
only place conflicts can occur.

:::objective{id=OBJ-B10.3.2}
:::

## Merging

```console
$ git merge <branch>             # fast-forward if possible, else a merge commit
$ git merge --no-ff <branch>     # always a merge commit
$ git merge --ff-only <branch>   # fast-forward or fail
$ git merge --abort              # back to before the merge began
$ git merge --continue           # after resolving
```

`--ff-only` is the useful one in scripts and hooks: it turns "this might create
a merge commit" into a refusal you can act on rather than a surprise in the log.

:::warning
`-X ours` and `-X theirs` are **strategy options** that resolve conflicting
regions in favour of one side. They are not the same as `--ours` / `--theirs` in
`git checkout`, which replace an entire file. The similar names hide a
difference in blast radius, and the whole-file version is what silently reverts
work that never conflicted.
:::

## During a conflict

```console
$ git status --short                     # UU = unmerged, both changed
$ git ls-files --stage <path>            # the three competing entries
$ git cat-file -p :1:<path>              # the base
$ git cat-file -p :2:<path>              # ours
$ git cat-file -p :3:<path>              # theirs
$ git diff --diff-filter=U               # only the unresolved paths
$ git checkout --ours <path>             # take stage 2 wholesale
$ git checkout --theirs <path>           # take stage 3 wholesale
$ git add <path>                         # collapse to stage 0 — the resolution
```

Reading stages 1, 2 and 3 is the habit worth building. The markers show you
*ours* and *theirs*; only the index shows you the **base**, and the base is what
tells you which side actually changed something.

:::note
`ours` is the branch you are **on**. During a rebase your commits are being
replayed onto the other branch, so `HEAD` is the other branch and the two are
swapped relative to intuition. Check `git status` — it names the operation in
progress — before reaching for either.
:::

:::objective{id=OBJ-B10.3.5}
:::

## Undoing a merge

```console
$ git merge --abort                      # before committing
$ git reset --hard ORIG_HEAD             # immediately after, if not pushed
$ git revert -m 1 <merge-commit>         # after it is shared
```

`-m 1` means "keep the first parent" — the branch you were on. Reverting a merge
needs it because a merge has two parents, and "undo this" is ambiguous without
saying which side to return to.

Worth knowing: a reverted merge cannot simply be re-merged later. Git sees the
branch as already merged, and the revert as a subsequent change, so a second
merge brings nothing. Reverting the revert is the usual answer, and it is the
kind of thing that is much easier to reason about knowing the graph is
append-only.

## The two-line summary

```console
$ git merge-base main feature    # what a merge will be reasoned against
$ git log --first-parent         # what your history looks like to a stranger
```

The first is what every merge outcome is defined relative to. The second is what
your branching policy actually produced.

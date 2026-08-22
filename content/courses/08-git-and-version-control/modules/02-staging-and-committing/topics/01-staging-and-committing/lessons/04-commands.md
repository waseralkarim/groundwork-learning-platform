---
topic: topic.staging-and-committing
section: commands
title: The commands, sorted by what they move
order: 4
mode: explain
---

Git's staging commands accumulated over twenty years, and it shows. The same
operation has several spellings, one command was overloaded to mean four things,
and the newer replacements are better but not yet in most people's fingers.

Sorted by what they actually do, it is a short list.

## Putting content into the index

```console
$ git add <path>          # stage the whole file as it is on disk
$ git add -A              # everything: modified, new and deleted
$ git add -u              # tracked files only — no new files
$ git add -p              # choose hunk by hunk
$ git add -N <path>       # record the path with no content ("intent to add")
```

`-A` versus `-u` is the distinction worth keeping: `-u` will not pick up a file
Git has never seen. That is also the gap in `git commit -a`, which stages
tracked modifications and silently ignores your new file.

`-N` is the useful obscure one. It makes an untracked file visible to `git diff`
and to `add -p` without staging its contents, which is how you review a brand
new file hunk by hunk.

## Taking content out of the index

```console
$ git restore --staged <path>     # unstage; your edit is untouched
$ git reset <path>                # the same thing, older spelling
$ git reset --mixed HEAD~1        # unstage a whole commit's worth
```

Both restore the index entry from `HEAD`. The working tree is not touched by
either, which is worth saying plainly because "reset" sounds like it should be.

## Throwing away edits

```console
$ git restore <path>              # discard working-tree changes
$ git checkout -- <path>          # the same thing, older spelling
$ git restore --source=HEAD --staged --worktree <path>   # both copies at once
```

:::warning
These are the genuinely destructive commands in this topic, alongside
`reset --hard`. They overwrite the working tree with content from the index or
`HEAD`, and an edit that was never staged has no object anywhere — so there is
nothing to recover it from. Git will not ask you to confirm.
:::

## Why `restore` and `switch` exist

`git checkout` used to mean, depending on its arguments:

- switch to a branch
- create and switch to a branch
- restore one file from the index, discarding your edits
- restore one file from an arbitrary commit

The first two are trivially reversible. The third destroys uncommitted work.
Having them share a name — distinguished by whether you remembered `--` — was a
genuine design problem, and Git 2.23 split it:

| Old | New | Job |
|---|---|---|
| `git checkout <branch>` | `git switch <branch>` | move `HEAD` |
| `git checkout -b <new>` | `git switch -c <new>` | create and move |
| `git checkout -- <path>` | `git restore <path>` | discard edits |
| `git reset <path>` | `git restore --staged <path>` | unstage |

Prefer the new ones. `checkout` is not deprecated and every existing document
uses it, so you must still read it — but the command that can destroy your work
should not be a typo away from the one that cannot.

:::objective{id=OBJ-B10.2.6}
:::

## Setting work aside

```console
$ git stash push -m "half-done"      # stash tracked modifications
$ git stash push -u                  # include untracked files
$ git stash push --keep-index        # stash, but leave the staged state on disk
$ git stash list
$ git stash pop
```

`--keep-index` is the one that matters here. It leaves **only what you staged**
in the working tree, so you can run the tests against exactly what is about to
be committed rather than against what you happen to have. It is the direct
answer to the risk that partial staging creates.

:::note
A stash is not a special format — it is commits, stored under `refs/stash`.
Which means a dropped stash is recoverable exactly like any other orphaned
commit: it is unreachable, not gone, until `gc` runs.
:::

## Inspecting before committing

```console
$ git status --short            # both columns, compactly
$ git diff                      # what is NOT going in
$ git diff --cached             # what IS going in
$ git ls-files --stage          # the index itself
$ git cat-file -p :<path>       # the exact staged bytes
$ git commit -v                 # commit, with the staged diff in the editor
```

The last one is worth configuring permanently:

```console
$ git config --global commit.verbose true
```

It puts the staged diff below your message every time you commit. Writing a
message directly above the diff it describes turns "remember to check" into
something you would have to actively ignore — which is the difference between a
rule and a habit.

## The one-line summary

```console
$ git diff            # empty ⇒ the commit matches your disk
```

Every other command in this lesson is a way of getting into or out of a state.
That one tells you whether the state you are about to commit is the one you have
been testing.

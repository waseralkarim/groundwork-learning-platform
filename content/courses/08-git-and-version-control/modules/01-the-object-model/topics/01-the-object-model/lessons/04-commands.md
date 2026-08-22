---
topic: topic.the-object-model
section: commands
title: The commands that show you the store
order: 4
mode: explain
---

Git's commands split into two groups, and the split has a name.

**Porcelain** is the everyday interface — `add`, `commit`, `log`, `status`,
`diff`. Built for humans, and free to change its output between versions.

**Plumbing** is the layer underneath — `cat-file`, `hash-object`, `rev-parse`,
`ls-tree`, `rev-list`. Built for scripts, with output that is stable on purpose.

This topic has been plumbing throughout, because plumbing is what shows you the
objects. It is also the right layer to script against: **porcelain output is not
a stable interface**, and a pipeline parsing `git status` will break on an
upgrade in a way that one parsing `git rev-parse` will not.

## Naming an object

`git rev-parse` turns anything human into an object id, and it is the command
worth knowing best.

```console
$ git rev-parse HEAD                 # the commit
$ git rev-parse HEAD^{tree}          # its tree
$ git rev-parse HEAD:balance.txt     # a blob, by path
$ git rev-parse HEAD~2               # two first-parents back
$ git rev-parse :balance.txt         # the staged version, from the index
```

| Syntax | Means |
|---|---|
| `HEAD~n` | follow **first** parents `n` times |
| `HEAD^n` | the `n`th **parent** of one commit |
| `HEAD^{tree}` | dereference until you get a tree |
| `HEAD:path` | the object at `path` in that commit |
| `:path` | the object at `path` in the **index** |

:::warning
`~` and `^` are different, and the difference only shows at a merge. `HEAD~2` is
two steps back along first parents; `HEAD^2` is the *second parent* of `HEAD` —
the branch that was merged in. In a linear history they coincide, which is why
the distinction is usually learned during an incident.
:::

## Reading an object

```console
$ git cat-file -t <id>       # type:  blob, tree, commit, tag
$ git cat-file -s <id>       # size in bytes
$ git cat-file -p <id>       # pretty-print the contents
```

`-p` is the one to reach for. On a tree it formats the entries; on a commit it
prints the raw object; on a blob it gives you the file. Since loose objects are
zlib-compressed, this is also the only sensible way to read one at all.

For bulk work there is a batch mode, which is what makes auditing a large
repository practical:

```console
$ git cat-file --batch-all-objects --batch-check='%(objectsize) %(objecttype) %(objectname)'
```

One process, every object, no fork per lookup.

## Making an object

```console
$ printf 'hello\n' | git hash-object --stdin        # compute only
$ printf 'hello\n' | git hash-object -w --stdin     # compute AND write
```

**`-w` is the difference between asking and doing.** Without it, Git tells you
what the id *would* be and writes nothing — which is why the first lab can
compute ids all day without touching the object store.

## Listing and walking

```console
$ git ls-tree HEAD                   # one level
$ git ls-tree -r HEAD                # recurse into subtrees
$ git ls-tree -r --name-only HEAD    # just paths

$ git rev-list HEAD                  # every commit reachable from HEAD
$ git rev-list --all                 # from every ref
$ git rev-list --objects --all       # every object, with its path
```

`git rev-list --objects --all` is the one that answers "which path is this
enormous blob?", by printing an id and the path it was seen at.

## Checking the whole store

```console
$ git fsck
$ git fsck --unreachable
$ git count-objects -vH
```

`fsck` verifies that every object's contents still hash to its own name and that
every reference resolves. Because ids are content hashes, this is a genuine
integrity check rather than a checksum somebody stored alongside the data — silent
disk corruption shows up here.

:::note
`--unreachable` lists objects no ref leads to, and it is quieter than people
expect after an amend or a reset — because the **reflog counts**. While the
reflog still mentions a commit, `fsck` does not consider it unreachable:

```console
$ git commit --amend -m "reworded"
$ git fsck --unreachable                     # ← prints nothing

$ git reflog expire --expire=now --all
$ git fsck --unreachable
unreachable commit b7238fcaba52d04ee9b079aa5205109e84f362b3
```

The commit was orphaned by the amend either way. The reflog was holding it, and
that is precisely the mechanism keeping your "lost" work alive — so an empty
listing is good news, not evidence that nothing was orphaned.
:::

:::objective{id=OBJ-B10.1.7}
:::

## A worked question

*"Which commit first introduced this line, and is the file still identical to
that version?"*

```console
$ git log -S 'payable' --oneline -- balance.txt     # commits changing that string
$ git rev-parse <that-commit>:balance.txt           # the blob then
$ git rev-parse HEAD:balance.txt                    # the blob now
```

If the two ids match, the file has not changed since — no diff needed, no
content compared. **Comparing ids is comparing contents**, and that is the habit
this topic is really trying to install.

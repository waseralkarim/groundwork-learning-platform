---
topic: topic.staging-and-committing
section: internals
title: What is actually in .git/index
order: 3
mode: explain
---

The index is one file, and it is not a directory of staged copies:

```console
$ file -b .git/index
Git index, version 2, 3 entries
```

Binary, versioned, and with a count that matches the number of *tracked* files —
not the number of changed ones. `git ls-files --stage` renders it readably:

```console
$ git ls-files --stage
100644 2044b72a0a12177872b807d2a836716e0f483a27 0	LICENSE
100644 a2dca04b903f1e51c50c0b7363c4b4d9180f52fd 0	accounts/payable.txt
100644 b2875d05c18a0346f39ce90365511f8a721e8410 0	balance.txt
```

**mode, object id, stage number, path.** No file contents — the content is a
blob in the object store, and the index only names it. This is why staging is
cheap regardless of file size: it writes one object and one index entry.

## The stat cache, and why `status` is fast

Each entry also carries data the readable form does not show: size, mtime, ctime,
device and inode. Together these are the **stat cache**, and they exist to answer
one question quickly — *has this file plainly not changed?*

Without it, `git status` in a repository with 50,000 files would have to read and
hash all 50,000. With it, Git compares the cheap metadata first and only hashes
files whose stat data has moved.

It is an optimisation, never the source of truth:

```console
$ touch balance.txt          # mtime changes, contents do not
$ git status --short
                             # ← nothing
```

The `touch` invalidated the cached stat data, so Git re-hashed the file, found
the same id, and reported no change. **A stale cache costs time, not
correctness** — and it quietly refreshes the entry so the next `status` is fast
again.

:::note
The historical exception is the "racy git" problem: a file modified in the same
second the index was written can have identical size and mtime despite different
contents. Git handles it by treating entries whose mtime matches the index's own
timestamp as suspect and re-hashing them. It is worth knowing this exists, mostly
so you recognise that "compare mtime and size" is not a safe shortcut in your own
tooling.
:::

## Stage numbers, and the one time they are not zero

That third column is `0` for every entry above, and stays `0` for the entire life
of a normal repository. It becomes interesting during a conflicted merge, where
one path genuinely has several competing versions at once:

```console
$ git merge other
CONFLICT (content): Merge conflict in balance.txt

$ git ls-files --stage balance.txt
100644 c2014ddafd932a7cf468dbe4dbffae4a27fdcf6a 1	balance.txt
100644 0da944013e9f0eee6b53d4b3e71bc8e407ad2a03 2	balance.txt
100644 a2d63f80842f84223bfe0996f3089cb3ea3c7577 3	balance.txt
```

Three entries, one path:

| Stage | Is |
|---|---|
| 1 | the **common ancestor** — what both sides started from |
| 2 | **ours** — the version on the branch you are on |
| 3 | **theirs** — the version being merged in |

This is what a conflict *is*. Not a file with markers in it — that is only how
Git renders the situation into your working tree so you can edit it. The real
state is the index holding three versions and refusing to produce a tree.

And it explains the resolution procedure exactly: `git add` on a conflicted path
replaces those three entries with a single stage-0 entry, which is why staging is
how you declare a conflict resolved. Until then there is no single version to
commit, so Git will not let you commit.

:::objective{id=OBJ-B10.2.1}
:::

## The index is not optional

It is tempting to read the index as a feature you could turn off with `commit
-a`. You cannot, because it is load-bearing:

- **Merges resolve into it.** The three-way state above lives nowhere else.
- **`git add` is an index operation** — so `commit -a`, which stages tracked
  modifications for you, is using it too.
- **`git status` and `git diff` are defined in terms of it.** Both of their
  "what changed" answers are comparisons against index entries.

Avoiding the index in your workflow does not remove it; it only means you first
meet it during a conflict, which is the worst possible moment to be introduced.

## What this buys you when reading commands

Almost every confusing flag in this area resolves to "which part of the index
does this touch":

```console
$ git rm --cached <path>      # remove from the index, keep the file on disk
$ git diff --cached           # compare the index against HEAD
$ git ls-files --stage        # print the index
$ git reset <path>            # rewrite that index entry from HEAD
$ git restore --staged <path> # the same thing, named after what it does
```

They look like unrelated flags on unrelated commands. They are all the same
noun.

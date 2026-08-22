---
topic: topic.the-object-model
section: core-concepts
title: Four objects, and the rule that names them
order: 2
mode: explain
---

Everything Git stores is one of four things. That is not a simplification for
teaching — it is the whole list.

| Object | Holds | Points at |
|---|---|---|
| **blob** | file contents | nothing |
| **tree** | a directory listing | blobs and trees |
| **commit** | a snapshot plus provenance | one tree, and its parents |
| **tag** | a name and a message for an object | usually a commit |

And one rule names all of them:

```text
id = sha1( <type> <byte-length> \0 <contents> )
```

## Why that rule is the whole design

Once an object's name is derived from its contents, several properties stop
being features and start being consequences you could not remove if you wanted
to.

**Identical content is one object.** Not deduplicated later — *never duplicated*.
Two files with the same bytes produce the same id and therefore the same object,
whatever they are called and wherever they live.

**Objects cannot be edited.** Change a byte and you have computed a different
name, which means you have made a *different object*. The original is untouched
because you never touched it. Everything that looks like editing in Git —
amending, rebasing, reverting — is creating new objects and moving a pointer.

**Tampering cannot hide.** A tree's contents include its children's ids, and a
commit's contents include its tree's id. So an id at the top covers everything
underneath it, all the way down. Change one byte in one file, and the blob id,
the tree id, every enclosing tree id, and every commit id from that point
forward are different.

:::note
This is A04.1's content addressing, applied to a whole data structure rather
than a single file. The same construction gives a container image its
`sha256:…` digest, and for the same reason: you can hand someone a name and they
can verify they got the right bytes without trusting you.
:::

## A blob has no name

This is the fact people find hardest, so it is worth stating flatly: **a blob
contains file contents and nothing else.** No filename. No path. No permissions.
No timestamp. No author.

```console
$ git hash-object a.txt        # contains "same contents\n"
9b0d6e7d2b6fea685ca530b22246c3e22fb055f7
$ git hash-object b.txt        # also contains "same contents\n"
9b0d6e7d2b6fea685ca530b22246c3e22fb055f7
```

Same object. A repository with a thousand copies of the same licence file
stores it once.

So where does the name live? One level up.

```console
$ git cat-file -p HEAD^{tree}
100644 blob 2044b72a…    LICENSE
040000 tree 1ec22a97…    accounts
100644 blob b2875d05…    balance.txt
```

A tree entry is **mode, type, id, name** — which makes a tree precisely a
directory listing, with subdirectories as nested trees.

:::warning
`100644` and `100755` are the only file modes Git records. Not the owner, not
the group, not the rest of the mode. A file committed as `0600` comes back as
`0644`. Anyone treating a repository as a backup of a filesystem is relying on
something Git never promised.
:::

## A commit is a snapshot with a parent

```console
$ git cat-file -p HEAD
tree 781f3a7a26ba85a6d51f58181a9a9a47033935b7
parent 5b1ffa8652f090804d0d4e4822c4da86ad5ca596
author Lab Learner <learner@lab.invalid> 1787390494 +0000
committer Lab Learner <learner@lab.invalid> 1787390494 +0000

Add accounts payable
```

Read what is *not* there. No list of changed files. No diff. No "modified
balance.txt". A commit records the complete state of the project and a link to
what came before, and nothing whatsoever about what changed.

**"What changed" is computed, not stored.** When you run `git diff`, Git
compares two trees entry by entry. Identical id means identical content, so an
unchanged file is dismissed without reading it — and an unchanged *directory* is
dismissed without descending into it at all. That is why diffing a repository
with half a million files is fast.

:::predict{question="A commit records its parent. What does the very first commit in a repository record in that field?"}
:::

Nothing — it has no parent line at all. The first commit is not a special case
needing special handling; it simply has zero parents, in the same way a merge
commit has two.

```console
$ git cat-file -p HEAD          # a merge
tree 226d1601c130d8fa0d999d642258a02ec099f8ed
parent ab899f59d60c2a938513c1d8c45d75f6b5f939a5
parent d7e867a949b4b0c5404f9a223aca27da6885a23b
```

Zero, one or many parents is what makes history a **directed acyclic graph**
rather than a list. It is directed because parents point backwards, and acyclic
because a commit's id depends on its parents' ids — so a cycle would require an
object to be named before it existed.

:::diagram{src=../diagrams/object-graph.mmd caption="Three commits over the seeded ledger. Each commit names one tree; the trees share the LICENSE blob because its contents never changed. Nothing points forward — parents point back."}

## Refs: the only mutable thing

Objects never change. Something has to, or the repository could never move
forward, and that something is a **ref**: a small file containing an object id.

```console
$ cat .git/refs/heads/main
f40047a87fc93b938ac7614acc4dd9bbdbc85de0
$ cat .git/HEAD
ref: refs/heads/main
```

A branch is that file. There is no branch object and no branch record anywhere
else, which is why creating one costs nothing and deleting one destroys nothing.

`HEAD` is a second file naming *which ref you are on*. That indirection is the
entire difference between working on a branch — where committing moves the
branch — and a detached `HEAD`, where `HEAD` holds an id directly and there is
no branch to move.

:::objective{id=OBJ-B10.1.2}
:::

:::objective{id=OBJ-B10.1.5}
:::

## Reachable, and the thing people call "losing work"

A commit is **reachable** if you can get to it by starting at some ref and
following parent links. Reachability is not a property of the commit — it is a
property of what currently points at it, and that is why it can change without
the commit changing at all.

This is the single most useful idea in the course:

> Git does not delete commits when you move a pointer. It makes them
> unreachable. **Unreachable is not gone.**

`--amend`, `reset --hard`, a deleted branch, an abandoned rebase — all of them
move or remove pointers. The objects stay exactly where they were, still
readable by id, and the reflog records where each pointer used to be. That is
why almost every Git disaster is recoverable, and why B10.7 can teach recovery
as a short topic rather than a dark art.

The genuine exception is `git gc`, which eventually collects objects nothing
points at. The window is weeks by default — long enough that "recoverable" is
usually true, and short enough that it is not a promise.

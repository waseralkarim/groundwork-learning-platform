---
topic: topic.the-object-model
section: internals
title: Where the objects actually live
order: 3
mode: explain
---

The object store is a directory. You can look at it, and nothing about it is
clever.

```console
$ find .git/objects -type f | head -3
.git/objects/20/44b72a0a12177872b807d2a836716e0f483a27
.git/objects/b2/875d05c18a0346f39ce90365511f8a721e8410
.git/objects/e6/9de29bb2d1d6434b8b29ae775ad8c2e48c5391
```

One object, one file. The path is the object's own id, split after two
characters — `2044b72a…` becomes `20/44b72a…`. The split exists because some
filesystems slow down badly with tens of thousands of entries in one directory,
and 256 subdirectories spreads them out. That is the entire reason.

## Why you cannot `cat` an object

```console
$ file -b .git/objects/20/44b72a0a12177872b807d2a836716e0f483a27
zlib compressed data
```

Every loose object is zlib-compressed on disk, which is why `git cat-file -p`
exists and `cat` produces line noise. Two consequences worth holding on to:

**The id is computed before compression, not after.** The hash covers
`<type> <length>\0<contents>` — the uncompressed form. If it covered the
compressed bytes, a different zlib version or compression level would produce a
different id for identical content, and nothing would ever agree across machines.

**The header is inside the compressed data.** So the file on disk is
self-describing: decompress it and the first bytes tell you what kind of object
it is and how long it is, with no external index needed.

## Loose objects and packfiles

Writing one file per object is fine for a few thousand and poor for a few
million. Git therefore has a second representation:

| | Loose | Packed |
|---|---|---|
| Layout | one file per object | many objects in one `.pack` |
| Compression | zlib, each object alone | zlib **plus deltas between objects** |
| Written by | ordinary commits | `git gc`, `git repack`, and every fetch/push |
| Lookup | path from the id | binary search in a `.idx` file |

Packing is where Git *does* store deltas — a version of a file expressed as
changes against another. This is the point at which people conclude the
"snapshots, not diffs" claim was a lie, so it is worth being exact:

:::note
Deltas in a packfile are a **storage encoding**, not the data model. A packed
object still has the same id, still decompresses to the same bytes, and is still
reachable in the same way. The delta base is chosen by heuristics on size and
name similarity, not by commit order — Git will happily delta against a version
from a different branch, or in the "wrong" chronological direction. Nothing
about a commit's meaning depends on any of it, and the packing can be redone
differently tomorrow without changing a single id.
:::

That is the difference that matters. In a diff-based system, the diffs *are* the
history and reconstructing an old state means replaying them. Here, deltas are a
compression detail beneath an unchanged model, and any object can be produced
without consulting any other commit.

:::diagram{src=../diagrams/loose-and-packed.mmd caption="The same object graph in both representations. Ids, reachability and meaning are identical; only the bytes on disk differ."}

## What `git gc` actually collects

Objects that nothing points at are not removed when they become unreachable.
They are removed when `gc` next runs *and* they are older than a grace period —
`gc.pruneExpire`, two weeks by default.

```console
$ git count-objects -vH
count: 12              ← loose objects
size: 48.00 KiB
in-pack: 0             ← nothing packed yet
packs: 0
size-pack: 0 bytes
prune-packable: 0
garbage: 0
size-garbage: 0 bytes
```

That is a freshly-created repository, and the zeros are the point: **packing is
not something commits do.** Objects arrive loose and stay loose until `gc`,
`repack`, or a fetch or push produces a pack. A repository you have only ever
committed to locally can be entirely loose.

Two practical readings of that grace period:

**It is why recovery works.** The commit you "lost" to a `reset --hard` an hour
ago is still there, and will be for a fortnight. B10.7 turns that into a
procedure.

**It is why recovery is not guaranteed.** "Unreachable is not gone" is true with
an expiry date attached. An aggressive `git gc --prune=now` collapses the window
to zero, which is exactly why that command deserves more caution than the one
people are actually frightened of.

## The index, and why staging exists at all

There is a third thing in `.git`, and it is neither an object nor a ref:

```console
$ file -b .git/index
Git index, version 2, 3 entries
```

The **index** is a binary file listing the paths that will go into the next
commit, each with a blob id and cached stat data. `git add` writes a blob into
the object store *immediately* and records it in the index; `git commit` turns
the index into a tree and writes a commit pointing at it.

Two things follow that explain otherwise-baffling behaviour:

**Staged content is already an object.** `git add` a file, edit it again, and
the version you staged is safely in the object store — which is why staged work
survives mistakes that lose the working copy.

**The commit is built from the index, not from your files.** This is the whole
explanation for "I fixed it but the fix is not in the commit": you edited after
staging, and the commit faithfully recorded what you staged. Not a bug, and not
really a gotcha once staging is understood as *building the next tree
incrementally* rather than as a confirmation step.

:::objective{id=OBJ-B10.1.4}
:::

## SHA-1, and whether it still matters

Git's default object hash is SHA-1, which has been broken for collision
resistance since 2017 — SHAttered produced two different PDFs with the same
SHA-1.

The honest position is neither "it does not matter" nor "Git is insecure":

- Git added **SHA-1DC**, a variant that detects the known collision-attack
  pattern and refuses. The published collisions do not work against it.
- An attacker needs a *chosen-prefix* collision against real content that also
  survives review — very much harder than the demonstration.
- Repositories using SHA-256 exist and are supported, but interoperability is
  still limited, which is why almost nothing has moved.

The transferable point is about content addressing generally: **its guarantees
are exactly as strong as the hash underneath it.** The same is true of a
container digest and a package checksum, and each of them will need the same
migration eventually.

---
topic: topic.the-object-model
section: production
title: What the model costs you when it is real
order: 5
mode: explain
---

Everything in this topic has been a property of a data structure. Three of those
properties become operational problems the first time a repository is shared,
and all three are the *same* property seen from different angles: **objects are
never modified, and nothing that has been committed goes away by being deleted
later.**

## A committed secret is not removed by deleting it

This is the one to internalise, because the instinct is exactly wrong.

```console
$ echo "AWS_SECRET=hunter2" > creds.env
$ git add -A && git commit -m "oops"
$ git rm creds.env && git commit -m "remove the secret"

$ ls creds.env
ls: cannot access 'creds.env': No such file or directory

$ git cat-file -p e64df7de
AWS_SECRET=hunter2
```

The file is gone from the working tree and gone from the current tree. The blob
is exactly where it was, readable by anyone with a clone, and the commit that
introduced it is still in the history where anyone can find it.

:::warning
**Deleting a leaked credential in a later commit does nothing to protect it.**
The blob is still in every clone, every fork, every CI cache and every mirror
that fetched before you noticed. Treat it as disclosed the moment it was pushed.
:::

The correct order is not negotiable:

1. **Rotate the credential.** First, before anything else, and regardless of what
   you plan to do to the repository. This is the only step that actually revokes
   the attacker's access.
2. Remove it from history with a rewriting tool, if the repository is private
   and the rewrite is worth its coordination cost.
3. Add it to `.gitignore` and add a scanner to CI, so the next one is caught
   before it is pushed.

Step 1 is the fix. Steps 2 and 3 are hygiene. Teams routinely do 2 and 3, feel
finished, and never do 1 — which is the failure this lesson exists to prevent.

:::objective{id=OBJ-B10.1.6}
:::

## Repository size is a policy problem, not a Git problem

A repository that takes an hour to clone is nearly always a repository somebody
committed build output to. The model explains why it cannot be fixed by
deleting things now:

- Every version of that artefact is a distinct blob, because its bytes differed
  each time. Content addressing shares only what is **identical**.
- Deleting the files today removes them from the current tree and from no
  history at all.
- Truncating history removes *references*, and the objects go only when they are
  unreachable and `gc` has run past its grace period.

Locate the cost by measuring rather than guessing:

```console
$ git count-objects -vH
$ git cat-file --batch-all-objects --batch-check='%(objectsize) %(objecttype) %(objectname)' \
    | sort -rn | head -20
```

Then map the large ids back to paths with `git rev-list --objects --all`. The
answer is almost always a handful of paths, and the real remedy is a policy one:
artefacts belong in artefact storage, large assets in LFS, and `.gitignore`
belongs in the repository before the first commit rather than after the first
complaint.

## Rewriting history is a coordination cost, not a technical one

Rewriting is easy to do and expensive to have done, and the object model is why:
change anything and every id downstream changes, so every clone now disagrees
with the remote about what happened.

Everyone else must re-clone or reset. Anything that pinned a commit id — a
deployment record, a changelog, an incident timeline, a code review link — now
points at an object no branch reaches. Open pull requests may need rebuilding.

:::note
This is the same property that makes tampering detectable, met from the other
side. You cannot have "any change to history is visible to everyone" without
also having "any change to history is disruptive to everyone". They are one
mechanism.
:::

Which makes the practical rule easy to state and worth stating precisely:
**rewrite freely before you push; treat rewriting after you push as an incident
with a communication plan.**

## Identify a build by its tree, not its commit

A useful trick that falls out of the model. Pipelines usually record the commit
id, which answers *"which commit did we build?"* — but not *"is this the same
code?"*, because a commit id also covers the author, the committer and their
timestamps.

```console
$ git rev-parse HEAD              # changes on amend, rebase, cherry-pick
$ git rev-parse HEAD^{tree}       # changes only when the content does
```

Record both. The commit id is the provenance; the **tree id** is the content
identity, and it is identical across a rebase that changed nothing. It is the
honest answer to "the pipeline ran twice and produced two different build ids
for the same source".

:::objective{id=OBJ-B10.1.4}
:::

## What to carry into the rest of the course

Three sentences, and every later topic in B10 is an application of one of them:

**Objects are immutable and named by their contents.** So nothing is edited,
only added — and any change to history is visible to anyone holding the old ids.

**Refs are pointers, and they are the only thing that moves.** So branching is
free, and every frightening command is a pointer move over a store that is not
being destroyed.

**Reachable is a property of pointers, not of commits.** So work is lost only
when nothing points at it *and* `gc` has run — which is why recovery is usually
possible, and why it has a deadline.

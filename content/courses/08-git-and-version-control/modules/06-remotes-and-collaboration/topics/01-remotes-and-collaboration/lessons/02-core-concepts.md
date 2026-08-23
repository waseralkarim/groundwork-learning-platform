---
topic: topic.remotes-and-collaboration
section: core-concepts
title: Three sets of refs, and which ones move
order: 2
mode: explain
---

Every clone holds three kinds of ref, and knowing which command moves which is
the whole of this topic.

| Ref | Lives in | Moved by |
|---|---|---|
| **local branch** | `refs/heads/main` | your commits, merge, rebase, reset |
| **remote-tracking** | `refs/remotes/origin/main` | fetch, and only fetch |
| **the remote's own** | on the other machine | your push, and other people |

The third one you never see directly. You only ever see the second — your record
of what the third said last time.

```console
$ git branch -a
* main
  remotes/origin/main
```

Two files, both local, both 41 bytes. `git status` compares them, and every
count it reports is a fact about those two files.

## What upstream configures

```console
$ git branch -vv
* main a1b2c3d [origin/main: ahead 1] add retry
```

That `[origin/main]` is the **upstream** — recorded in `.git/config`, and it is
what makes three things work without arguments:

- `git push` knows where to push
- `git pull` knows what to fetch and integrate
- `ahead`/`behind` have something to be measured against

```console
$ git push -u origin main        # set it while pushing
$ git branch --set-upstream-to=origin/main
```

A branch with no upstream reports no counts at all — not "up to date", just
nothing. That is usually the answer when someone says their status "stopped
showing ahead/behind".

:::objective{id=OBJ-B10.6.1}
:::

## The refspec

The mapping between their refs and yours is configuration, not magic:

```console
$ git config --get remote.origin.fetch
+refs/heads/*:refs/remotes/origin/*
```

Read it as *"take everything under `refs/heads/` on the remote and write it
under `refs/remotes/origin/` here"*. Their `main` becomes your `origin/main` —
which is why your remote-tracking refs are named after the remote and cannot
collide with your branches.

**The leading `+` means "allow a non-fast-forward update".** Without it, a fetch
would refuse to move `origin/main` backwards or sideways after someone rewrote
history — and you would be unable to see the rewrite at all. With it, the fetch
succeeds and reports `(forced update)`, which is your only notification.

:::note
Push uses a refspec too, and by default it is *not* forced — which is exactly
the asymmetry you want. Fetching a rewrite is safe, because it only updates your
notes. Pushing one is destructive, because it changes what everyone else will
fetch.
:::

## Fetch, pull, push in one picture

```text
                fetch ──▶  refs/remotes/origin/*        (your notes)
                              │
                              │ merge / rebase          (the second half of pull)
                              ▼
                           refs/heads/*                 (your branches)
                              │
                              │ push
                              ▼
                        the remote's refs
```

**Fetch only ever writes into the middle box.** It cannot conflict, cannot touch
a file, and cannot lose work — there is no situation where fetching is the risky
choice.

**Pull is fetch plus the downward arrow**, and that arrow runs on whatever you
have checked out. Merges, conflicts and unasked-for merge commits all live
there.

**Push is the upward arrow**, and it is the only one that changes what other
people will see.

:::objective{id=OBJ-B10.6.2}
:::

## Ahead and behind, precisely

```console
$ git rev-list --left-right --count origin/main...HEAD
1       2
```

Three dots, not two. `A...B` means *commits reachable from either but not both*,
and `--left-right` splits them: left is `origin/main`'s side (**behind**), right
is yours (**ahead**).

| | Meaning | Resolution |
|---|---|---|
| `0 n` | only you have commits | push fast-forwards |
| `n 0` | only they do | pull fast-forwards |
| `n m` | both — **diverged** | merge or rebase |

**These counts are computed from your stale record.** Measured: with a
colleague's commit already on the remote and no fetch since, the same repository
reports `behind=0`, then `behind=1` after fetching. Nothing on the remote
changed between the readings.

So "behind" cannot appear until a fetch makes it appear — which is why a push
can be rejected by a repository that had just claimed to be up to date.

:::objective{id=OBJ-B10.6.3}
:::

## Why pushes are refused

The rule is B10.3's fast-forward rule, applied to the remote's ref:

> An update is allowed when the old tip is an **ancestor** of the new one.

If it is, nothing that was reachable stops being reachable, and the push is
accepted. If it is not, accepting it would strand commits — so it is refused.

```console
$ git push
 ! [rejected]  main -> main (fetch first)
```

`(fetch first)` means the remote holds commits you have never seen.
`(non-fast-forward)` means you have them and are trying to replace them anyway.
Two messages, one rule.

**The rejection protects other people.** Your commits are on your machine and
nothing has happened to them. What is at stake is somebody else's work becoming
unreachable on the shared remote — which is why `--force` is spelled the way it
is.

:::objective{id=OBJ-B10.6.4}
:::

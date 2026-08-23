---
topic: topic.remotes-and-collaboration
section: overview
title: There is no connection to the server
order: 1
mode: explain
---

Most confusion about remotes comes from a picture that feels obviously right and
is wrong: that your repository is somehow *attached* to a server, and that
`origin/main` shows you what is on it.

Nothing is attached. There is no session, no connection, and no live view.

```console
$ git remote -v
origin  /srv/git/project.git (fetch)
origin  /srv/git/project.git (push)
```

A remote is **a name for a URL**, written in `.git/config`. That is the whole of
it. The name is used when you run a command that talks to the URL, and between
those moments nothing is happening at all.

## So what is `origin/main`?

A file.

```console
$ cat .git/refs/remotes/origin/main
c7b696d43f5c9e2a1b8d0f7e6a5c4b3d2e1f0a9b
```

Forty hex characters and a newline — the same 41 bytes as any branch, in a
different directory. It records **where `origin`'s `main` was the last time you
asked**, and it is updated by exactly one thing: a fetch.

:::predict{question="A colleague pushes to `main`. You run `git status` and it says nothing about it. Why not?"}
:::

Because `git status` compares your branch against `origin/main`, and
`origin/main` is a local file that has not been touched. Nothing told your
repository anything happened. `git status` is not out of date — it is exactly as
current as your last fetch, and it has no way to be more current than that.

That single fact explains most of this topic:

- **"Your branch is up to date with origin/main"** means *up to date with what I
  last heard*, not *up to date with the server*.
- **"Your branch is ahead by 3 commits"** is a comparison between two local
  files.
- **A push rejected as non-fast-forward** is the remote telling you that your
  local record of it is stale.

## Fetch and pull are different sizes

```text
git fetch    update remote-tracking refs, download objects
             ─ touches no local branch, no file in your working tree

git pull     git fetch, then integrate into your current branch
             ─ merges by default, or rebases if configured
```

Measured: after a colleague pushes and you `git fetch`, `origin/main` moves and
your `main` does not.

```console
$ git fetch
$ git rev-parse --short main origin/main
786e3f8        ← unchanged
c7b696d        ← moved
```

**Fetch is always safe.** It writes remote-tracking refs and objects, and it
cannot touch your work, produce a conflict, or change a file you are editing.
There is no situation in which fetching is the risky option.

**Pull is fetch plus a second operation you may not have thought about.** That
second half is where merges appear, conflicts happen, and unexpected merge
commits get created — and it runs on whatever you have checked out.

:::note
The habit worth building is **fetch, look, then decide**:

```console
$ git fetch
$ git log --oneline HEAD..origin/main     # what they did that I do not have
$ git log --oneline origin/main..HEAD     # what I have that they do not
```

Two commands, and you know exactly what a pull would do before it does it.
:::

:::objective{id=OBJ-B10.6.2}
:::

## Ahead, behind, diverged

These are not moods. They are a comparison between two refs and their merge
base:

```text
ahead 3, behind 0     you have 3 they lack        push fast-forwards
ahead 0, behind 2     they have 2 you lack        pull fast-forwards
ahead 2, behind 3     both — diverged             something must reconcile them
```

**And they are computed from the stale ref.** Measured: with a colleague's commit
already on the remote but not yet fetched, `git status` reports `ahead 1,
behind 0` — no divergence at all. After `git fetch` the same repository reports
`ahead 1, behind 1`.

Nothing changed on the remote between those two readings. What changed is what
this repository had been told. "Behind" cannot appear until a fetch makes it
appear, which is why a push can be rejected by a repository that a moment
earlier claimed to be perfectly up to date.

Diverged is the only interesting case, and it is not an error. It means both
sides committed since the merge base, which is the normal result of two people
working. It has to be resolved by a merge or a rebase, because there is no
single line of history any more.

:::objective{id=OBJ-B10.6.3}
:::

## Why a push gets rejected

```console
$ git push
 ! [rejected]        main -> main (fetch first)
hint: Updates were rejected because the remote contains work that you do not
hint: have locally.
```

Git says `(fetch first)` when the remote holds commits you have not fetched, and
`(non-fast-forward)` when you have them and are still trying to replace them.
Two messages, one rule.

The rule is exactly the one from B10.3: an update is a **fast-forward** when the
old tip is an ancestor of the new one. If it is, nothing on the remote becomes
unreachable and the push is allowed. If it is not, accepting it would strand
commits — so it is refused.

**The rejection is protecting other people's work**, not yours. Your commits are
safe on your machine. What it prevents is your push making somebody else's
commits unreachable on the shared remote, which is the same harm B10.4's golden
rule describes.

Which is why `--force` is spelled the way it is: you are asking to do the thing
the check exists to prevent.

:::objective{id=OBJ-B10.6.4}
:::

## What this topic covers

- What a remote actually is, read out of `.git/config` and `.git/refs/remotes`
- Fetch versus pull, measured by which refs move
- Ahead, behind and diverged as facts about two refs
- Why a push is rejected, and what the rejection protects
- Two clones of one repository, and what happens when they disagree
- Choosing pull and integration settings by the history they produce

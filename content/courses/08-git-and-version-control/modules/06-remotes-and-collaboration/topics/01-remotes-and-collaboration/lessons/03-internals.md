---
topic: topic.remotes-and-collaboration
section: internals
title: What actually travels between two repositories
order: 3
mode: explain
---

A fetch is not a file sync. Both sides negotiate, and what crosses the wire is
decided by the same reachability rules everything else in this course uses.

## The negotiation

1. Your side asks what refs the remote has. It answers with a list of names and
   ids — cheap, and it is all `git ls-remote` does.
2. Your side works out which of those ids it already has, and offers what it
   knows.
3. The remote computes the objects reachable from what you want but *not*
   reachable from what you already have.
4. Those objects are sent as a packfile.

**Step 3 is why a second fetch transfers almost nothing.** It is not caching —
the remote genuinely computes a smaller set, because reachability from your
existing commits excludes everything you already hold.

It is also why an unrelated history costs a full transfer. Nothing is shared, so
nothing can be excluded.

:::note
`git ls-remote origin` performs only step 1. It is the cheapest possible way to
ask "what does the remote actually have right now?" without touching your
repository at all — useful when you want the truth but do not want to update
your refs yet.
:::

## Objects arrive before refs move

The order matters, and explains an otherwise odd behaviour:

```text
1. packfile written into .git/objects
2. refs/remotes/origin/* updated
```

If a fetch is interrupted between those, you have objects nothing points at —
harmless, invisible, and collected by `gc` eventually. What you never get is a
ref pointing at an object you do not have, which is what keeps the repository
consistent under interruption.

The same ordering applies on push, in reverse: the remote receives objects,
verifies it can reach everything the new ref needs, and only then moves the ref.
**A push that fails partway leaves the remote's branch exactly where it was.**

## Why a push is refused, mechanically

The remote applies one test to each ref update:

> Is the current value an **ancestor** of the proposed value?

That is a graph query, not a comparison of who is newer. If the answer is yes,
accepting cannot make anything unreachable. If no, some commits reachable from
the current value would stop being reachable — so it refuses unless the refspec
is forced.

```console
 ! [rejected]  main -> main (fetch first)
```

The message differs by what your side knows — `(fetch first)` when the remote
holds commits you have never seen, `(non-fast-forward)` when you have them and
are replacing them anyway — but the test is identical.

:::objective{id=OBJ-B10.6.4}
:::

## What `--force-with-lease` actually compares

`--force` skips the test entirely. `--force-with-lease` replaces it with a
different one:

> Is the remote's current value equal to **my remote-tracking ref**?

That is why it protects against a concurrent push: if somebody pushed after your
last fetch, the remote's value has moved past your `origin/main` and the lease
fails.

And it is why it does **not** protect a colleague who pulled an hour ago and is
working locally. Nothing on the remote records that they exist. The lease is a
statement about *staleness of your information*, not about who holds what.

:::warning
`git fetch` immediately before a lease-push makes the lease reflect reality. A
lease taken against a fetch from this morning is checking a question you already
know the answer to.
:::

## Remote-tracking refs and the reflog

Remote-tracking refs have their own reflog, and it is the record that survives a
rewrite:

```console
$ git reflog show origin/main
7d54e50 refs/remotes/origin/main@{0}: fetch: forced-update
62462da refs/remotes/origin/main@{1}: fetch
```

`forced-update` in that log is durable evidence, unlike the fetch output that
scrolled past. When someone asks *"did that branch get rewritten, and when?"*,
this answers it — and it also gives you the pre-rewrite id, which is what you
need to rescue anything that was on it.

:::objective{id=OBJ-B10.6.5}
:::

## Bare repositories and why pushing to a checkout fails

A bare repository is one with no working tree — no checked-out branch, so no
files that a ref move could invalidate.

Push to a non-bare repository's *current* branch and Git refuses by default,
because moving that ref would leave the working tree and index describing a
commit that is no longer `HEAD`. The repository would be internally consistent
and the person sitting in front of it would see `git status` reporting changes
they did not make.

That is the entire reason servers hold bare repositories. Nothing else about
them is special — the lab builds one with `git init --bare` and no daemon, no
network and no configuration at all.

## What none of this needs

Worth stating explicitly, because it shapes what is possible:

- **No server process.** A remote can be a filesystem path.
- **No persistent connection.** Every command that talks to a remote opens,
  transfers and closes.
- **No central authority.** "The remote" is a convention. Every clone holds the
  full object graph and can serve as one.

Which is why the labs in this topic run with no network at all, and why the
things that go wrong between two people are never about connectivity — they are
about which local file was last updated, and when.

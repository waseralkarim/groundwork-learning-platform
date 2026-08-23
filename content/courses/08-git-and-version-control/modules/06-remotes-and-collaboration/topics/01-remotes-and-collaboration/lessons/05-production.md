---
topic: topic.remotes-and-collaboration
section: production
title: What everyone else has, and cannot be reached from here
order: 5
mode: explain
---

One asymmetry runs through every collaboration failure in this course:

> **You can change the remote. You cannot change anyone's clone.**

A rewrite, a deletion, a cleanup — all of them operate on a repository you can
reach. The copies on other people's machines are untouched, and the only thing
that ever brings them into line is somebody running a command there.

## History rewrites are two operations

Removing a commit from a shared branch looks like one action and is two:

1. Rewrite the remote's history. You can do this.
2. Get every existing clone off the old history. **You cannot do this.**

The troubleshooting scenario is what happens when only the first is done: a
developer with a two-week-old clone pulls, Git merges their old history with the
new one, and the removed commit is back on `main` — under a merge commit that
was a legitimate fast-forward and broke no rule.

So the announcement matters as much as the rewrite:

```text
poor      "we cleaned up main this morning"
better    "we rewrote main. before your next push, run:
             git fetch origin && git reset --hard origin/main
           if you have local work, rebase it onto the new origin/main instead."
```

The second version names the operation people must perform. The first leaves
them to work it out, and the default — `git pull` — is exactly wrong.

:::warning
And when the rewrite was to remove a secret: **it was disclosed the moment it was
pushed.** It sat in every clone and CI cache in the meantime. Rotate first; the
history work is hygiene, and this failure mode is why it is only that.
:::

:::objective{id=OBJ-B10.6.5}
:::

## Protect the branch, do not rely on the convention

The push that reintroduced the removed commit was a **fast-forward**. No
protection applied because none was being violated, and no amount of care about
force-pushing would have caught it.

That is the general shape: conventions cover the cases people remember, and
incidents come from the cases they do not.

**Worth configuring on the host:**

- **Require pull requests** for `main` and release branches, so nothing lands
  without a second pair of eyes on what it contains.
- **Block force-pushes** on those branches. It is the one rule that cannot be
  forgotten under pressure.
- **Require linear history** if the team wants it — better as a server-side
  check than as a habit everyone has to maintain.

**Worth configuring locally:**

```console
$ git config --global pull.rebase true          # or pull.ff only
$ git config --global push.default simple
$ git config --global fetch.prune true
```

`fetch.prune` is the quiet one. Without it, `origin/feature-x` sticks around
after the branch is deleted on the remote, and your tab-completion offers
branches that no longer exist for months.

## Why `pull.rebase` is a real decision

With it unset, `git pull` merges when the branch has diverged. That produces
commits titled `Merge branch 'main' of github.com:...`, which record nothing
about the work — they are an artefact of two people committing on the same
afternoon.

The stronger argument is not about shape, though:

> **With `pull.rebase` unset, the same command does different things on
> different machines, and nobody can tell from the command which happened.**

A team's history then depends on whose laptop ran the command. That is a
variable nobody is tracking and nobody wants. Setting it either way removes it;
leaving it unset is the only genuinely bad option.

:::note
`pull.ff = only` is the third choice and it suits people who would rather be
told than have something happen. It fetches, then refuses if the branch has
diverged — which pairs naturally with the fetch-look-decide habit rather than
replacing it.
:::

:::objective{id=OBJ-B10.6.6}
:::

## Fetch is free; make it a reflex

Every diagnostic in this topic starts the same way, because remote information
is only ever as fresh as your last fetch:

```console
$ git fetch
$ git log --oneline HEAD..origin/main     # what they have that I lack
$ git log --oneline origin/main..HEAD     # what I have that they lack
$ git status -sb
```

Fetch writes remote-tracking refs and objects and nothing else. It cannot
conflict, cannot touch a file you are editing, and cannot lose work. There is no
situation in which it is the risky option, and there is no state in which the
answer to "what is going on?" does not begin with it.

## What to carry forward

**Nothing is connected.** A remote is a name for a URL, and `origin/main` is a
local file with an age. Every count Git reports about a remote is a fact about
that file.

**You can change the remote and not anyone's clone**, which is why rewriting
shared history is a coordination problem with a technical component rather than
the other way round.

**A rejection protects the other person**, not you — and `--force` is a request
to do exactly what it prevented.

**Divergence caused by a rewrite reads identically to parallel work**, and
merging it silently reintroduces what was removed. The fetch output's
`(forced update)` is the only thing that distinguishes them, and it scrolls past
in a second.

---
topic: topic.the-object-model
section: overview
title: The problem nobody states out loud
order: 1
mode: explain
---

Before Git, and still on plenty of machines today:

```console
$ ls
deploy.sh
deploy.sh.bak
deploy.sh.bak2
deploy.sh.working
deploy.sh.old-DO-NOT-DELETE
deploy.sh.2024-11-03-before-riz-changed-it
```

Everybody laughs at this directory and almost everybody has made one. It is
worth asking what it is actually failing at, because the answer is the
specification for every version control system ever written.

It cannot tell you **what changed** between two of those files without you
running `diff` by hand. It cannot tell you **why** any of them exist — the
reason lived in someone's head, or in a Slack message that has scrolled away.
It cannot tell you **who** made the change, or **when**, except by a filename
somebody typed and a timestamp the filesystem will happily lose on a copy. And
it cannot tell you **which one is real**, which is why the fifth file is shouting.

:::predict{question="Two engineers each fix a different bug in deploy.sh on the same afternoon, working from the same starting copy. With this scheme, what happens to one of the fixes?"}
:::

The honest answer is that one of them is gone, and nobody finds out until the
bug comes back. The last person to copy their file over the shared one wins,
silently. There is no record that a decision was made, because no decision was
made — a file was overwritten.

## What a version control system has to promise

Strip away the tooling and there are four promises:

**Nothing is lost.** Any state the project has been in can be recovered, whether
or not anyone thought it was important at the time. This is the one the `.bak`
scheme fails hardest, and the one people are most surprised Git keeps so
literally — as you will measure later in this topic, even work you have
apparently thrown away is still sitting in the repository.

**Every change has provenance.** Who, when, and — the part that pays for itself
years later — *why*. A change without a reason is a change nobody dares touch.

**History cannot be quietly rewritten.** Not "must never change" — sometimes
history genuinely needs editing. The promise is weaker and more useful: it
cannot change *without that being detectable*. Nobody can alter what happened
last March and have the record still look untouched.

**Parallel work can be reconciled.** Two people changing different things must
both keep their work, and two people changing the *same* thing must be told, not
silently resolved.

:::note
Only the fourth promise is about collaboration. The other three are worth having
on a project with exactly one person on it, which is why "I work alone, I do not
need Git" does not follow.
:::

## Why this course starts underneath the commands

Most Git teaching starts with `git add`, `git commit`, `git push` — the three
commands that get you to a working day — and leaves the model for later. It is a
reasonable-looking choice and it produces a predictable outcome: people who are
fluent until something goes wrong, and then paste a command from a search result
into a repository they care about and hope.

The reason it fails is that Git's *interface* is genuinely inconsistent — `git
checkout` did four unrelated jobs for years, `reset` means something different
with each flag — while Git's *model* is small and almost boringly regular. Four
kinds of object. A pointer. A rule for naming things. Every command is a move
over that structure, and the frightening ones stop being frightening when you
can see what they move.

So this topic does not teach a single command for getting work done. It answers
one question:

> When you commit, where does that go, and what is it?

By the end you will have computed a commit's name yourself, with `sha1sum`, and
watched Git agree with you.

:::objective{id=OBJ-B10.1.1}
:::

## Where this connects

You have met the central idea already. **A04.1** taught content addressing —
naming a thing by the hash of its contents so the name changes whenever the
contents do — and used a Git commit id as its example without explaining it.
This topic is where that debt is paid.

The relationship runs the other way too. Once you have seen a repository as
content-addressed storage, **C14's** container image layers are recognisably the
same design, and `sha256:9f2a…` in an image reference stops being noise.

:::diagram{src=../diagrams/the-four-promises.mmd caption="The four promises, and the object-model property that delivers each one. Content addressing does most of the work: it is why nothing is lost and why tampering is detectable."}

## What this topic covers

- What the four object types are, and what each one holds
- How an object id is computed, done by hand and checked against Git
- Why Git stores snapshots rather than diffs, and what that costs
- What a branch is on disk, and what `HEAD` points at
- What `--amend` really does to the commit it appears to replace

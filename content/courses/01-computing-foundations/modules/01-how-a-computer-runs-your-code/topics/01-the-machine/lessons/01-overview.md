---
topic: topic.the-machine
section: overview
title: Why start here
order: 1
mode: explain
---

Every production incident you will ever debug comes down to one of four things
running out, going wrong, or being slower than someone assumed:

- **CPU** — the thing that executes instructions
- **Memory** — the fast, volatile place where running work lives
- **Storage** — the slow, persistent place where data survives
- **Network** — the connection to everything else

That is not a simplification for beginners. It is the actual shape of the
problem, and senior engineers use exactly this list. When a Kubernetes pod is
`OOMKilled`, that is memory. When a deploy takes twenty minutes, that is usually
storage or network. When a service is fast for ten users and unusable for a
thousand, that is CPU or memory or a queue in front of one of them.

This topic covers the first three. Network gets its own course, because it is
the one that behaves least like the others.

## Why not skip to the interesting part

Most DevOps material starts at Docker. You can get quite far that way — far
enough to be hired, in a good market. The ceiling shows up later, and it shows
up in a specific and recognisable way.

You will be able to write a `Dockerfile` but not explain why your image is
900MB. You will know `kubectl describe pod` shows `OOMKilled` but not what the
kernel actually did, or why the pod died at 512MB when your app "only uses
300MB". You will read `exec format error` and search for the string instead of
recognising it on sight. You will look at `free -h`, see 200MB free out of 32GB,
and file a ticket about a memory leak that does not exist.

Every one of those is a gap in this topic, not a gap in Docker.

:::note
There is a reason this curriculum teaches mechanism before interface. An
interface changes every few years. `docker run` replaced `lxc-start`, and
something will replace `docker run`. The mechanism underneath — processes,
memory, the kernel boundary — has been essentially stable since the 1970s. Learn
the part with the longer half-life first.
:::

## What you will be able to do

By the end of this topic you will be able to walk up to an unfamiliar Linux
machine, work out what it is made of, decide whether a given workload will fit
on it, and — when it is misbehaving — tell whether the bottleneck is CPU,
memory or disk, and say which line of output proves it.

That last skill is the one that separates people who fix production from people
who restart it.

## What you need first

Nothing. This is the first topic in the curriculum. You need to be able to open
a terminal and type a command; if you can do that, you are ready.

You do **not** need to know any programming language, what Linux is, or what a
container is. Everything is defined before it is used.

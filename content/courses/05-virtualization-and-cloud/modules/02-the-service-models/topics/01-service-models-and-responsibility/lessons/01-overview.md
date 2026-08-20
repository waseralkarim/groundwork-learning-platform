---
topic: topic.service-models-and-responsibility
section: overview
title: Fourteen, eleven, eight, three
order: 1
mode: explain
---

IaaS, PaaS and SaaS are usually introduced as three product categories, which
makes them sound like three different things to buy. They are not. They are
**one stack with the boundary drawn in different places**, and the useful way to
understand them is to count.

In the first lab you take one application — an HTTP API with a PostgreSQL
database — deployed four ways, and count the layers you are responsible for:

```text
colocation   yours: 14    provider: 3
IaaS         yours: 11    provider: 7
PaaS         yours:  8    provider: 12    shared: 3
SaaS         yours:  3    provider: 14
```

Same application, same data, same traffic. Fourteen down to three, and every
step is a trade rather than an improvement.

## The three that never move

Compute the intersection — which layers are yours in *all four* deployments —
and you get exactly three:

```text
data
access control
configuration
```

That is not a claim you have to accept. It falls out of `comm` across the four
files, and you will run it.

Those three are where nearly every cloud breach actually happens. A publicly
readable bucket. An IAM role granting `*` on `*`. A database with the password
`postgres`. **No service model takes any of them from you**, including SaaS,
where you have given up everything else.

:::note
This is the practical answer to "is the cloud secure". The provider's layers are
run by people who do nothing else, at a scale you cannot match. Your three are
run by you, and they are the three that show up in the breach reports.
:::

## The band in the middle

The PaaS row is the interesting one, because it is the only one with a **shared**
column — three layers where both parties must act:

- The provider publishes an OS patch; **you** choose when to roll it.
- The provider patches the database; **you** pick the maintenance window.
- The provider takes backups; **you** verify a restore works.

"Shared" is the category that fails most often, and for a predictable reason:
it is read as "theirs". A maintenance window left at its default means "any
time", which is a decision made by not deciding — and one of the incidents in
this topic is exactly that.

## What you will do

**Compute the boundary** for four deployments and find the irreducible three
yourself, with `diff` and `comm` rather than with a diagram.

**Assign twelve security advisories** arriving in one week. Some are clearly
yours, some clearly the provider's, and the interesting ones are neither.

**Assign five outages.** One of them has no satisfying answer, and finding out
which is the point of the exercise — it is the one where fault and
preventability come apart.

**Read a vendor's shared-responsibility page** for what it omits. It will not
say anything false.

## The question this topic is really about

Not "which model is best" — that depends on the situation and mostly on how many
people you have. The question is:

> **When I move up a model, what exactly am I handing over, and what am I
> keeping?**

Answering it as a list rather than an impression is the skill. And the answer
always contains those same three items, which is why a team that moves to SaaS
and stops thinking about security has misunderstood the trade rather than
completed it.

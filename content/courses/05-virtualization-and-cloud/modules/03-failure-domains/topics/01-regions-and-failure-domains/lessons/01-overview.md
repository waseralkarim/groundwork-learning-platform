---
topic: topic.regions-and-failure-domains
section: overview
title: Three replicas is not redundancy
order: 1
mode: explain
---

Three application replicas, placed by a scheduler with no constraints, all
landing on the same node. Three database nodes, all in one availability zone.
Nine replicas across three zones, all reading their secrets from a vault cluster
in one of them.

Every one of those is described by its owners as highly available, and each has
a single event that takes the whole thing down.

**Counting replicas tells you nothing. Counting failure domains does.**

## What this topic computes

Two pieces of arithmetic, and both produce results people do not expect.

**Composition.** Components all required — in *series* — multiply, so every
dependency makes the system worse:

```text
managed k8s (99.95) + postgres (99.95) + LB (99.99) + secrets (99.99)
  = 99.880046%   →   about 52 minutes a month
```

Four managed services, each promising better than 99.9%, composing to worse than
any of them individually. That number is not on any vendor page, and it is your
actual availability.

Components where any one suffices — in *parallel* — multiply their
*un*availability instead, so nines arrive fast:

```text
two components at 99%     → 99.99%
three components at 99%   → 99.9999%
```

Which looks wonderful and is true only when the failures are independent. They
almost never are, and the rest of the topic is about that word.

**Quorum placement.** Three nodes across two zones, quorum of two:

```text
lose the zone holding 2 nodes → 1 left → QUORUM LOST
lose the zone holding 1 node  → 2 left → quorum held
```

So a quorum system "redundant across two availability zones" survives a random
zone loss **half the time**. Across three zones it survives any single zone
loss. That is a computable difference between a design that works and one that
looks like it does, and adding a fourth node to two zones does not fix it.

:::note
This is why every distributed system's documentation says three zones and most
deployments use two. Two zones feels redundant, costs less, and provides no
fault tolerance at all for anything quorum-based.
:::

## The word the arithmetic depends on

Parallel redundancy multiplies unavailability *if the failures are
independent*. Things that break independence, all of which are ordinary:

- Replicas on the same node, rack, or zone
- A shared control plane, vault, or DNS zone
- The same bad deployment reaching every replica
- A dependency every replica has that is not itself replicated

The last one is the seeded incident in this topic: a service with replicas in
three zones went completely down during an outage **in a zone it was not in**,
because the load balancer's health check read from a single-zone vault. Sixty
minutes of user-facing impact from a facility the service did not run in.

## What you will do

**Compose real numbers** from a provider's published figures and find out what
your stack actually promises.

**Take a census of failure domains** — the same "what shares a fate" question as
A04.4's blast radius, asked about infrastructure.

**Compute quorum survival** for placements across two and three zones, and find
why adding nodes to two zones does not help.

**Find the correlated failure** in four topologies described as redundant. One
of the four is genuinely well placed and has a different problem, which is the
more interesting finding.

## The question underneath

Not "are we highly available" — which is unanswerable and produces meetings — but:

> **What single event takes this down, and how do we know?**

It has a specific answer, it is computable, and the answer is frequently
something nobody listed as a dependency.

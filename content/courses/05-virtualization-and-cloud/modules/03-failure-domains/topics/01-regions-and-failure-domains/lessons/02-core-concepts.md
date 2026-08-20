---
topic: topic.regions-and-failure-domains
section: core-concepts
title: Boundaries, and the arithmetic across them
order: 2
mode: explain
---

## Regions and zones are boundaries against specific things

**An availability zone** is one or more datacentres with independent power,
cooling and network, close enough to its siblings for synchronous replication —
single-digit milliseconds apart. It is the boundary against a **facility
failure**: a power event, a cooling failure, a fire, a flood, a fibre cut into
one building.

**A region** is a set of zones in a geographic area. It is the boundary against
a **regional disaster** and, increasingly importantly, against a **regional
control-plane failure** — which is the more common event by a wide margin.

The distinction that matters operationally: zones are close enough that you can
run one system across them synchronously. Regions are not, so multi-region is a
different design rather than more of the same.

**Most cloud services are regional.** A load balancer, a managed database, a
Kubernetes cluster — each lives in one region and spans zones within it. That
means a region is usually your largest single failure domain, and it is the one
most deployments have exactly one of.

## Series: every dependency makes it worse

Components that are all required multiply:

```text
A = a₁ × a₂ × a₃ × …
```

```bash
/tmp/avail series 0.9995 0.9995 0.9999 0.9999
# 99.880046%
```

That is managed Kubernetes, managed PostgreSQL, a load balancer and a secrets
manager — four services each promising 99.95% or better, composing to **99.88%**,
about 52 minutes a month.

Two things follow, and both are worth saying out loud in design reviews:

**Adding a dependency always lowers availability.** There is no exception. A
feature that adds one more required service has made the whole system less
available, and that cost is rarely counted.

**Your number is never the best number on the page.** Vendors publish
per-service figures. Nobody publishes the product, and the product is what your
users get.

## Parallel: nines arrive fast, conditionally

Components where any one suffices multiply their *unavailability*:

```text
A = 1 − (1−a₁)(1−a₂)…
```

```bash
/tmp/avail parallel 0.99 0.99        # 99.99%
/tmp/avail parallel 0.99 0.99 0.99   # 99.9999%
```

Two mediocre components in parallel beat one excellent one. Three are better
than almost anything you can buy.

Which is why redundancy is the standard answer, and why the arithmetic is so
often wrong in practice: **it assumes the failures are independent**.

:::warning
`(1−a₁)(1−a₂)` is only valid when the two failures have nothing in common. Two
replicas on the same node have a shared fate, and the correct model for them is
not parallel at all — it is one component with a slightly different failure
rate. Calculated availability that assumes independence is an upper bound, and
usually a distant one.
:::

## What breaks independence

All of these are ordinary rather than exotic:

- **Same node, rack or zone.** The scheduler will do this unless told not to.
- **A shared dependency** every replica needs — a vault, a config service, a
  DNS zone, a certificate authority.
- **The same deployment.** A bad release reaches every replica within minutes,
  and no amount of parallelism helps.
- **A shared control plane.** Every replica in a cluster depends on one API
  server for scheduling and healing.
- **Correlated load.** When one replica fails, its traffic goes to the others,
  which may then fail for the same reason. That is a cascade, and redundancy can
  make it faster.

The census that finds these is the same question as A04.4's blast radius, asked
about infrastructure: **what does this take with it when it fails?**

## Quorum: where the nodes sit decides what survives

A distributed system needing majority agreement — etcd, Consul, ZooKeeper,
a Raft database — needs `floor(n/2)+1` nodes to accept writes.

Three nodes, quorum two. Place them across two zones and one zone necessarily
holds two:

```text
AZ-a: node1, node2      AZ-b: node3

lose AZ-a → 1 node left  → QUORUM LOST → the system is read-only or down
lose AZ-b → 2 nodes left → quorum held
```

:::diagram{src=../diagrams/quorum.mmd caption="Both are 'redundant across zones'. Only one of them tolerates a zone failure."}
:::

**A random zone loss is survived half the time.** Across three zones, any single
zone loss leaves two nodes and quorum holds — always.

The correction people reach for makes it **worse**. Add a fourth node — two per
zone — and quorum becomes three, so losing either zone leaves two:

```text
3 nodes over 2 zones (2/1):  survives 1 of 2 zone failures
4 nodes over 2 zones (2/2):  survives 0 of 2 zone failures
```

More nodes in two zones never produces zone fault tolerance, and an even number
is actively harmful. The number of **zones** is what matters, and for a majority
quorum it has to be at least three.

:::predict{question="Five etcd nodes across two zones — three in AZ-a, two in AZ-b. Quorum is 3. Which zone failures does this survive?"}

Only the loss of AZ-b.

Lose AZ-b and three nodes remain, which is exactly quorum — it holds, with no
margin. Lose AZ-a and two remain against a quorum of three, so writes stop.

Five nodes feels considerably more redundant than three and buys nothing at all
for zone failure, because the constraint is the number of zones rather than the
number of nodes. Five nodes across three zones (2/2/1) survives any single zone
loss and is the configuration that actually helps.

This is the most common serious mistake in the topic, and it is entirely
arithmetic.

## Static stability

The property worth naming, because it explains why some outages are survivable
and some are not: **can the system keep working during a failure without
anything having to act?**

A load balancer already configured with healthy targets in two zones keeps
serving when a third zone dies — no decision, no control plane, no failover. A
system that needs the control plane to reschedule pods before it recovers is
depending on that control plane during exactly the event most likely to have
disturbed it.

This is why the A05.2 incident — a 45-minute control-plane outage where pods
kept serving — was survivable. The data plane was statically stable. Losing the
ability to deploy and scale was a real cost and not an outage.

Designing for it means: pre-provisioned capacity rather than scale-on-failure,
health checks that do not depend on remote services, and no control-plane call
on a request path.

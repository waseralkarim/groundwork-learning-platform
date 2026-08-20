---
topic: topic.regions-and-failure-domains
section: internals
title: Finding what shares a fate
order: 3
mode: explain
---

## The census

Counting replicas is the wrong measurement. The right one is: **for each thing
that could fail, what goes with it?**

Work outward, and write the list down:

| Domain | What shares it | Typical blind spot |
|---|---|---|
| Process | one container | — |
| Node | every pod scheduled there | no anti-affinity set, so all replicas land together |
| Rack | nodes sharing power and a switch | invisible from the API; the provider knows |
| Zone | everything in that facility | a single-zone dependency the rest of the stack uses |
| Region | every zonal service, and the regional control plane | the whole account, usually |
| Provider | everything you run | one console, one identity system, one billing account |
| Global | DNS, certificate authority, package registries | rarely enumerated at all |

The rows people skip are **rack** — which you cannot see and which makes
"different nodes" less independent than it looks — and the last two, which
almost nobody lists as dependencies.

## The dependency that is not replicated

The most common correlated failure has a specific shape: **N replicas, each
depending on one instance of something else.**

```text
9 app replicas across 3 zones      ← looks excellent
    ↓ every one of them
1 vault cluster in AZ-a            ← the actual availability
```

The composite is not the replicas' availability. It is the vault's, because the
vault is in series with all of them. Nine replicas in three zones with a
single-zone dependency is a single-zone system wearing nine copies.

This is exactly the seeded incident: a service with replicas in three zones went
fully down during an outage **in a zone it was not in**, because the load
balancer's health check called an endpoint that read from a single-zone vault.
All targets marked unhealthy, all traffic dropped, sixty minutes.

The lesson generalises past vaults: **anything on a health check path is a hard
dependency of the whole service**, and health checks are written casually.

## Where the arithmetic stops being a model

Independence is the assumption everything rests on, and there are four ordinary
ways it fails.

**Shared infrastructure.** Same node, rack, power feed, top-of-rack switch.
Anti-affinity handles the node; racks are usually invisible to you, which is
part of what a zone abstraction is buying.

**Shared dependencies.** The vault case, plus DNS, certificate authorities,
config services, and the container registry every node pulls from.

**Shared change.** A bad deployment reaches every replica in minutes. This one is
worth dwelling on because redundancy provides *no* protection at all against it —
which is why progressive rollout, canaries and fast rollback are availability
controls rather than release conveniences.

**Correlated load.** One replica fails, its traffic redistributes, the others
fail for the same reason. Redundancy makes the cascade faster rather than
slower, and the mitigations are load shedding, circuit breakers and capacity
headroom rather than more replicas.

## Multi-region: a different design, not more of the same

Zones are close enough for synchronous replication. Regions are not — tens to
hundreds of milliseconds apart — so multi-region forces choices that
multi-zone does not.

**Synchronous across regions** means every write pays the round trip. Usually
unacceptable.

**Asynchronous** means the standby lags, so a failover loses whatever had not
replicated. That lag *is* your RPO, and it is a number to measure rather than
assume.

**Active-active** means resolving conflicting writes in two places, which is a
data-model problem rather than an infrastructure one, and it is the hardest of
the three by a large margin.

What multi-region buys is survival of a regional failure — including a regional
control-plane failure, which is far more common than a datacentre being
destroyed. What it costs is a second copy of everything, a data model that
tolerates lag or conflict, and a failover procedure.

:::warning
**An untested failover is a plan, not a capability**, and failover is itself a
common cause of outages: a standby that was never receiving replication, DNS
that will not propagate quickly enough, a secondary sized for a fraction of real
traffic, or a split brain when both sides think they are primary.

The honest question before building multi-region is not "can we fail over" but
"when did we last fail over, deliberately, in business hours". If the answer is
never, the capability is unproven regardless of what has been built.
:::

Most organisations get better value from **static stability within one region**
than from a second region they have never used. Three zones, pre-provisioned
capacity, no control-plane dependency on the request path, and a tested restore
covers the overwhelming majority of real incidents.

## Reading published numbers

Provider figures are per-service and per-region and are *upper bounds on a
component*, not on your system. Three habits:

**Compose everything required.** `avail series` over every dependency, including
the ones that are not in the architecture diagram — secrets, DNS, registry,
identity.

**Do not credit redundancy you have not verified is independent.** Two replicas
that might be on one node are not parallel.

**Treat 100% claims carefully.** A managed DNS service published at 100% is a
statement about the service's design, not a promise that name resolution never
fails for you — resolver caches, registrar problems and your own zone
configuration are all outside it.

## The four questions

On any system, and they have specific answers:

```text
1. What single event takes this down?
2. Which dependencies are in series that we did not list?
3. Where is the quorum, and does it survive one zone?
4. When did we last test the failover or the restore?
```

Question 2 finds the most, because the answer is nearly always something on a
health check path or a secrets fetch. Question 4 finds the most serious, for the
same reason it did in the previous module: an untested recovery path is a claim.

---
topic: topic.regions-and-failure-domains
section: production
title: Choosing what to survive, and proving you do
order: 5
mode: explain
---

## Decide what you are protecting against, then price it

"Highly available" is not a target. These are:

| Survive | Needs | Roughly costs |
|---|---|---|
| A process dying | more than one replica | nothing |
| A node failing | anti-affinity across nodes | nothing |
| A zone failing | ≥3 zones, quorum placed correctly, no single-zone dependency | ~nothing extra in cloud |
| A region failing | a second region, replicated data, tested failover | 2× infrastructure and a large amount of complexity |
| A provider failing | a second provider | usually more than it is worth |

The first three are cheap and are the ones most often not done. **Spreading
across three zones costs approximately nothing in a cloud region** and is
skipped constantly, while multi-region gets discussed because it sounds like
the serious answer.

The honest ordering: get zone-level right, make it statically stable, test your
restore. Then consider a second region, knowing it doubles your infrastructure
and adds a failover procedure that is itself a source of outages.

## What zone-level right looks like

- **Three zones**, not two, for anything quorum-based. Two zones gives a quorum
  system no zone fault tolerance, and four nodes across two zones gives less
  than three did.
- **Topology spread constraints** rather than hoping. Schedulers pack by
  default; three replicas without a constraint is three processes, not three
  domains.
- **No single-zone dependency.** Vault, config service, registry mirror,
  anything on a health check path.
- **Pre-provisioned capacity.** If losing a zone requires scaling up, you depend
  on the control plane during the event most likely to have disturbed it. Run
  enough that `n−1` zones carry full load.
- **Health checks that are local.** A readiness probe calling a remote service
  puts that service in series with yours, and a load balancer will remove every
  replica when it goes down.

That last point is the seeded incident, and it is worth stating as a rule:
**anything a readiness probe touches is a hard dependency of the whole
service.**

## The numbers to write down

Three, and they are decisions rather than observations:

**Availability target.** Composed from real dependencies with `avail series`,
not taken from the best vendor figure. If four managed services give you 99.88%,
promising 99.95% to anyone is promising something you cannot deliver.

**RPO** — how much data you may lose. Nightly backups with no point-in-time
recovery means 24 hours. Async cross-region replication means whatever the lag
is, which is measurable with one query and usually is not measured.

**RTO** — how long recovery may take. Measured by doing it, not estimated. A
large database restore takes hours and that is your RTO whether or not anyone
has written it down.

Unstated, all three default to whatever the system happens to do, and everyone
discovers them together during an incident.

## What actually causes outages

Worth keeping in proportion, because effort follows attention:

Zone failures are real and uncommon. Region failures are rarer still. **Most
outages are changes** — a deployment, a configuration edit, a certificate
expiring, a dependency deprecated on schedule.

Redundancy provides no protection against any of those. A bad release reaches
all nine replicas in minutes; multi-region gives you a second region running the
same bad release.

So the controls that reduce real downtime most are progressive rollout,
canaries, fast rollback, and change freezes during risky windows — none of which
appears in an availability calculation, and all of which matter more than a
second region for most organisations.

The arithmetic in this topic is for the failures redundancy *does* address. It
is worth doing precisely, and it is not the largest term.

## Testing it

An untested failure path is a claim. Cheap tests in ascending order of nerve:

**Kill a pod.** Does traffic notice? This should be routine and boring.

**Cordon and drain a node.** Do replicas move, and is there capacity for them?

**Simulate a zone loss** by cordoning every node in one zone. This is the test
almost nobody runs and it finds single-zone dependencies immediately — including
the ones on health check paths.

**Restore a backup** into a scratch environment and assert the application
starts. Count restores, not backups.

**Fail over deliberately**, in business hours, with everyone watching. If this
has never been done, the capability is unproven no matter what has been built.

Each of these has found something real in systems that were confident. The zone
simulation in particular is a half-day of work that regularly finds a dependency
nobody had listed.

## The review questions

For any design claiming high availability:

```text
1. What single event takes this down?
2. Which dependencies are in series that are not on the diagram?
3. Where is the quorum, and does it survive one zone?
4. Does anything on the health check path leave this failure domain?
5. If a zone fails, does anything have to act — or does it just keep working?
6. When did we last test that?
```

Question 4 is the one that finds the seeded incident, and it is not on anybody's
standard checklist. Question 5 is static stability, and it separates designs
that survive a control-plane outage from ones that need rescuing during it.

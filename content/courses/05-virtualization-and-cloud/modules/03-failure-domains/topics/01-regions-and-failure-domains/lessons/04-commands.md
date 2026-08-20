---
topic: topic.regions-and-failure-domains
section: commands
title: Computing availability, and finding placement
order: 4
mode: explain
---

## The calculator

`bc` is not in this image, so the labs ship a small helper. The arithmetic is
awk underneath and worth being able to write yourself.

```bash
/tmp/avail series   0.9995 0.9995 0.9999 0.9999    # all required
/tmp/avail parallel 0.99 0.99 0.99                 # any one suffices
/tmp/avail downtime 0.997003                       # per month and per year
```

By hand:

```bash
# series — multiply
awk 'BEGIN{ printf "%.6f%%\n", 0.9995*0.9995*0.9999*0.9999*100 }'

# parallel — multiply the unavailabilities
awk 'BEGIN{ printf "%.6f%%\n", (1-(1-0.99)^3)*100 }'

# availability → downtime per month
awk -v a=0.9988 'BEGIN{ s=30*24*3600*(1-a); printf "%dh %dm\n", s/3600, (s%3600)/60 }'
```

:::try{lab=compose-the-numbers run="bash /opt/lab/seed-domains.sh >/dev/null; /tmp/avail series 0.9995 0.9995 0.9999 0.9999; /tmp/avail downtime 0.99880046"}
Four managed services, each promising 99.95% or better, composing to 99.88% —
about 52 minutes a month. Every dependency you add makes this worse, and no
vendor page shows you the product.
:::

## Quorum survival

```bash
# quorum for n nodes
awk -v n=5 'BEGIN{ print int(n/2)+1 }'

# does a placement survive losing each zone?
for z in 2 1; do
  awk -v n=3 -v z=$z 'BEGIN{
    q=int(n/2)+1; left=n-z
    printf "lose zone of %d: %d left, quorum %d -> %s\n",
      z, left, q, (left>=q ? "HELD" : "LOST")
  }'
done
```

Run it for the placements that matter and the pattern is stark:

```text
3 nodes / 2 zones (2,1)   survives 1 of 2
4 nodes / 2 zones (2,2)   survives 0 of 2      ← adding a node made it worse
3 nodes / 3 zones (1,1,1) survives 3 of 3
5 nodes / 2 zones (3,2)   survives 1 of 2
5 nodes / 3 zones (2,2,1) survives 3 of 3
```

## Finding out where things actually are

On a real cluster, the placement you asked for and the placement you got are
different questions:

```bash
# which node and zone is each replica on?
kubectl get pods -l app=api -o wide

# what zone is each node in?
kubectl get nodes -L topology.kubernetes.io/zone

# both at once — the census that matters
kubectl get pods -l app=api -o json \
  | jq -r '.items[] | .spec.nodeName' \
  | sort | uniq -c
```

If that last command prints one line, every replica is on one node and you have
one replica with extra cost.

```bash
# is anything actually spreading them?
kubectl get deploy api -o yaml | grep -A20 'topologySpreadConstraints\|affinity'
```

An absent result is the finding. Schedulers pack by default, and "three
replicas" without a constraint is a request for three processes rather than for
three failure domains.

## Enumerating dependencies you did not list

The series composition is only as good as the list, and the list is usually
short by several entries:

```bash
# what does this workload actually talk to at startup?
kubectl get deploy api -o yaml | grep -E 'env:|secretKeyRef|configMapKeyRef' -A3

# what does the health check call?
kubectl get deploy api -o yaml | grep -A10 'readinessProbe'
```

The readiness probe is the one to read carefully. **Anything on a health check
path is a hard dependency of the entire service** — if the probe calls a remote
service, that service's availability is in series with yours, and a load
balancer will remove every healthy replica when it goes down.

## Checking a failover is real

```bash
# is the standby actually receiving data, and how far behind?
# (postgres example; every system has an equivalent)
psql -c 'SELECT client_addr, state, replay_lag FROM pg_stat_replication;'
```

`replay_lag` is your RPO for an unplanned failover, measured rather than
assumed. A standby with no rows in that table is not a standby.

And the question no command answers: **when was the failover last performed
deliberately?** If the answer is never, it is a plan rather than a capability.

## The five worth keeping

```bash
/tmp/avail series ...                                   # what your stack really promises
awk -v n=5 'BEGIN{print int(n/2)+1}'                    # quorum
kubectl get pods -o wide | awk '{print $7}' | sort | uniq -c   # where they really are
kubectl get deploy X -o yaml | grep -A10 readinessProbe # what the probe depends on
psql -c 'SELECT replay_lag FROM pg_stat_replication;'   # the RPO you actually have
```

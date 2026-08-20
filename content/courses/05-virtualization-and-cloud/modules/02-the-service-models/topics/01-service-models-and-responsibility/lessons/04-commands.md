---
topic: topic.service-models-and-responsibility
section: commands
title: Computing a boundary instead of drawing one
order: 4
mode: explain
---

There is no instrument for a service model. What there is instead is a text file
per deployment and the ordinary tools for comparing text — which turns out to be
enough to make the boundary countable.

## Count what is yours

```bash
grep -c 'YOU' 2-iaas.txt        # layers you own
grep -c 'provider' 2-iaas.txt   # layers they own
grep -c 'SHARED' 3-paas.txt     # layers needing both
```

Run it across all four and the progression appears:

```text
colocation   yours 14   provider  3   shared 0
IaaS         yours 11   provider  7   shared 0
PaaS         yours  8   provider 12   shared 3
SaaS         yours  3   provider 14   shared 0
```

:::try{lab=diff-the-boundary run="bash /opt/lab/seed-responsibility.sh >/dev/null; cd /tmp/deployments; for f in 1-colocation 2-iaas 3-paas 4-saas; do printf '%-14s yours=%-3s provider=%s\n' $f $(grep -c YOU $f.txt) $(grep -c provider $f.txt); done"}
Four numbers that make "IaaS versus PaaS" concrete. Fourteen to three, and the
shared column exists in exactly one row.
:::

## See exactly which layers moved

```bash
diff 2-iaas.txt 3-paas.txt
```

The output is the boundary shift itself — every line that changed is a
responsibility that moved, and the ones that changed from `YOU` to `SHARED` are
the ones worth the most attention.

## Find what never moves

```bash
# the layers you own, per deployment, one per line
for f in 1-colocation 2-iaas 3-paas 4-saas; do
  awk '/^  / && /YOU/ { split($0, a, "  +"); print a[2] }' "$f.txt" | sort > "/tmp/y-$f"
done

# intersect all four
comm -12 /tmp/y-1-colocation /tmp/y-2-iaas > /tmp/i
comm -12 /tmp/i /tmp/y-3-paas > /tmp/i2
comm -12 /tmp/i2 /tmp/y-4-saas
```

```text
access control
configuration
data
```

Three lines, computed rather than asserted. `comm -12` prints only what appears
in both sorted inputs, so chaining it across four files gives the intersection —
and the intersection is the answer to "what does no service model take from me".

## Reading an SLA as time

```bash
# downtime allowed per 30-day month, for a given percentage
awk -v sla=99.9 'BEGIN { s = 30*24*3600 * (100-sla)/100;
  printf "%dh %dm %ds\n", s/3600, (s%3600)/60, s%60 }'
```

And the number people forget — dependencies in series multiply:

```bash
# three components at 99.9%, all required
awk 'BEGIN { c = 0.999^3; printf "combined %.4f%%  -> %.0f min/month\n",
  c*100, 30*24*60*(1-c) }'
# combined 99.7003%  -> 129 min/month
```

Two hours nine minutes, against the 43 minutes each component promises. Counting
your dependencies and multiplying takes a minute and is almost never done.

## The audit, as commands

On a real system rather than a lab file, the same questions have real sources:

```bash
# what version are the managed nodes on, and how old is that image?
kubectl get nodes -o wide

# when is the database's maintenance window — or is it still "any"?
# (provider CLI; the default is the finding)

# when did a restore last actually run?
# (not "when did a backup last succeed" — those are different questions)
```

The third has no command because it is usually not automated, and that absence is
the finding. A backup nobody has restored is a file of unknown quality, and
"backup succeeded" means a file was written.

## The four worth keeping

```bash
diff model-a.txt model-b.txt              # what moved
comm -12 a.txt b.txt                      # what never moves
awk 'BEGIN{printf "%.4f", 0.999^3}'       # what your dependencies really give you
kubectl get nodes -o wide                 # is the shared layer actually being done
```

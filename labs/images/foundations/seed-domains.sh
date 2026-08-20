#!/bin/bash
# Seeds the A05.3 failure-domain labs.
#
# Like A05.2 this topic has no instrument — you cannot fail an availability zone
# from inside a container. What it has instead is arithmetic, and the arithmetic
# produces results people do not expect:
#
#   * three nodes across two AZs loses quorum when the AZ holding two fails, so
#     a "redundant" two-AZ quorum system survives a random AZ loss half the time
#   * parallel redundancy adds nines very fast and only if failures are
#     independent, which is the assumption that is almost always wrong
#
# So the labs compute rather than describe, and the topologies below are data to
# be analysed rather than prose to be read.
#
# A small calculator ships with them because `bc` is not in this image and the
# awk incantations are not what the topic is teaching.
set -euo pipefail

export LC_ALL=C

# ---------------------------------------------------------------- calculator

cat > /tmp/avail <<'HELPER'
#!/bin/bash
# avail series  0.999 0.999 0.999      -> all required, multiply
# avail parallel 0.99 0.99             -> any one suffices
# avail downtime 0.997003              -> per month and per year
#
# bc is not in this image; awk does exponentiation with ^ and is enough.
export LC_ALL=C
mode=$1; shift
case "$mode" in
  series)
    awk -v n=$# "BEGIN{ a=1 }" </dev/null >/dev/null
    a=1
    for x in "$@"; do a=$(awk -v a="$a" -v x="$x" 'BEGIN{printf "%.10f", a*x}'); done
    awk -v a="$a" 'BEGIN{printf "%.6f%%\n", a*100}'
    ;;
  parallel)
    f=1
    for x in "$@"; do f=$(awk -v f="$f" -v x="$x" 'BEGIN{printf "%.10f", f*(1-x)}'); done
    awk -v f="$f" 'BEGIN{printf "%.6f%%\n", (1-f)*100}'
    ;;
  downtime)
    awk -v a="$1" 'BEGIN{
      m=30*24*3600*(1-a); y=365*24*3600*(1-a)
      printf "per month: %dh %dm %ds\n", m/3600, (m%3600)/60, m%60
      printf "per year:  %dd %dh %dm\n", y/86400, (y%86400)/3600, (y%3600)/60
    }'
    ;;
  *) echo "usage: avail series|parallel|downtime ..." >&2; exit 2 ;;
esac
HELPER
chmod 0755 /tmp/avail

# ----------------------------------------------------------------- topologies

T=/tmp/topologies
rm -rf "$T"; mkdir -p "$T"

cat > "$T/README.txt" <<'EOF'
Four deployments, each described by its owners as "highly available" and each
with a correlated failure that redundancy does not cover.

For each, work out:

  - what fails together, and why
  - what the redundancy actually protects against
  - what single event takes the whole thing down

One of the four is genuinely well placed and has a different problem.
EOF

cat > "$T/alpha.txt" <<'EOF'
topology: alpha — order service
  3 application replicas
  placement: no constraints set; scheduler placed all 3 on node-7
  3 database nodes, quorum-based, all in AZ-a
  load balancer: single, in AZ-a
  region: eu-west-1
  claim: "three replicas, three database nodes, fully redundant"
EOF

cat > "$T/bravo.txt" <<'EOF'
topology: bravo — payments service
  6 application replicas, 3 in AZ-a and 3 in AZ-b
  database: managed postgres, primary in AZ-a, synchronous standby in AZ-b
  3 etcd nodes for the cluster: 2 in AZ-a, 1 in AZ-b
  load balancer: managed, spans both AZs
  region: eu-west-1
  claim: "everything is doubled across two availability zones"
EOF

cat > "$T/charlie.txt" <<'EOF'
topology: charlie — reporting API
  4 application replicas across AZ-a, AZ-b, AZ-c (2/1/1)
  database: managed postgres, multi-AZ, 3 replicas one per AZ
  load balancer: managed, spans three AZs
  region: eu-west-1
  secrets: fetched at startup from a vault cluster in AZ-a only
  claim: "three availability zones, no single point of failure"
EOF

cat > "$T/delta.txt" <<'EOF'
topology: delta — customer portal
  9 application replicas across 3 AZs (3/3/3)
  database: managed postgres, multi-AZ, 3 replicas one per AZ
  load balancer: managed, spans three AZs
  secrets: replicated across all three AZs
  region: eu-west-1  (single region)
  DNS: single provider, single zone
  deploys: 20+ per day via one CI system in the same region
  claim: "no single point of failure within the region"
EOF

# ------------------------------------------------------------ published SLAs

cat > /tmp/slas.txt <<'EOF'
# Figures a provider publishes for the services this platform depends on.
# All required to serve a request unless noted.

compute (per instance)          0.995
compute (across 2+ AZs)         0.9999
managed kubernetes control      0.9995
managed postgres (single AZ)    0.999
managed postgres (multi AZ)     0.9995
managed load balancer           0.9999
object storage                  0.99999
managed DNS                     1.0        (published as 100%)
secrets manager                 0.9999
EOF

# ---------------------------------------------------------------- an incident

cat > /tmp/az-incident.txt <<'EOF'
# Post-incident summary from a provider, and what we observed.

PROVIDER
  2026-06-14 09:12 UTC  AZ eu-west-1b: power event affecting one datacentre
  2026-06-14 09:12 UTC  instances in eu-west-1b became unreachable
  2026-06-14 11:40 UTC  service restored
  Note: eu-west-1a and eu-west-1c were unaffected throughout.

US
  09:12  all traffic errors, 100%
  09:13  paged
  09:20  confirmed our replicas in 1a and 1c were healthy and serving nothing
  09:24  found the load balancer had marked all targets unhealthy
  10:05  found the health check calls an endpoint that reads from the vault
         cluster, which is single-AZ in 1b
  10:12  pointed health checks at a local endpoint; traffic restored
  Total user-facing impact: 60 minutes, in a zone we were not in.
EOF

echo "Seeded: /tmp/topologies, /tmp/slas.txt, /tmp/az-incident.txt, /tmp/avail."

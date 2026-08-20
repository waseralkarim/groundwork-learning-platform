#!/bin/bash
# Seeds the A05.1 layers labs.
#
# Most of this topic is measured live — the container can read its own
# hypervisor flag, its borrowed kernel version and the gap between what /proc
# reports and what its cgroup allows. That is the good half and it needs no
# seeding.
#
# What it cannot do is stand on a different layer. A container cannot show you
# bare metal, cannot boot its own kernel, and cannot cold-start a function. So
# those come from captures taken on real systems, clearly labelled as captures,
# in the same style A03 used for routing tables the sandbox cannot produce.
#
# The comparison figures are the honest kind: measured where we could measure
# them, cited where we could not, and never presented as though we had run them
# here.
#
# One of them changed while writing this. "Containers start in 5-50 ms" is the
# quoted figure and it describes the runtime creating a process. Timing
# `docker run --rm image true` on this host gave ~760 ms, and `docker exec` into
# an already-running container ~245 ms. Both are in the table, because the gap
# between the quoted number and the observed one is more instructive than either
# number alone.
set -euo pipefail

export LC_ALL=C

C=/tmp/captures
rm -rf "$C"; mkdir -p "$C"

# ------------------------------------------------------------- bare metal

cat > "$C/bare-metal.txt" <<'EOF'
# Captured on a physical server. Note what is present and what is absent.

$ grep -o hypervisor /proc/cpuinfo | head -1
(no output — the flag is not set)

$ cat /sys/class/dmi/id/sys_vendor
Dell Inc.
$ cat /sys/class/dmi/id/product_name
PowerEdge R650

$ uname -r
6.1.0-18-amd64

$ lscpu | grep -E 'Model name|Hypervisor|Virtualization'
Model name:            Intel(R) Xeon(R) Gold 6338 CPU @ 2.00GHz
Virtualization:        VT-x

$ ls /.dockerenv
ls: cannot access '/.dockerenv': No such file or directory

$ nproc
64
$ cat /sys/fs/cgroup/cpu.max
max 100000
EOF

# --------------------------------------------------------------------- vm

cat > "$C/virtual-machine.txt" <<'EOF'
# Captured inside a cloud VM. It has its own kernel and its own virtual
# firmware, and it knows it is virtualised.

$ grep -o hypervisor /proc/cpuinfo | head -1
hypervisor

$ cat /sys/class/dmi/id/sys_vendor
Amazon EC2
$ cat /sys/class/dmi/id/product_name
m6i.xlarge

$ uname -r
6.5.0-1018-aws

$ lscpu | grep -E 'Hypervisor vendor|Virtualization type'
Hypervisor vendor:     KVM
Virtualization type:   full

$ ls /.dockerenv
ls: cannot access '/.dockerenv': No such file or directory

$ systemd-detect-virt
kvm

$ nproc
4
$ cat /sys/fs/cgroup/cpu.max
max 100000
EOF

# -------------------------------------------------------------- boot times

cat > "$C/startup-costs.txt" <<'EOF'
# Startup cost by layer.
#
# READ THE SOURCE COLUMN. Only two of these numbers were measured for this
# course, and they are not the ones usually quoted.

layer            start time          source        memory overhead   isolation boundary
---------------  ------------------  ------------  ----------------  ------------------
bare metal       60-300 s            published     none              none between
                 (POST + firmware                                    tenants
                 + boot)

virtual machine  10-60 s             published     256 MB - 1 GB     hypervisor,
                                                   per guest kernel  hardware-assisted

microVM          ~125 ms             published     ~5 MB             hypervisor
(Firecracker)

container        5-50 ms             published     none - it shares  kernel: namespaces
  (runtime work only)                              the host kernel   + cgroups + seccomp

container        ~760 ms             MEASURED      as above          as above
  (docker run, end to end)           on this host

container        ~245 ms             MEASURED      as above          as above
  (docker exec into a running one)   on this host

function         cold: 100 ms-10 s   published     varies            usually a microVM
                 warm: ~0 ms                                         underneath


# Why the two container rows disagree by more than an order of magnitude:
#
# "Containers start in milliseconds" describes the container runtime creating a
# process — the 5-50 ms row. It is true and it is not what anyone waits for.
# End to end you also pay the CLI, the daemon round trip, image and snapshot
# setup, and network attachment.
#
# The measured figures here are from Docker Desktop on WSL2, which adds a layer
# of its own; a Linux host running containerd directly is faster. They are
# reported anyway, because the gap between the quoted number and the observed
# one is the point — and it is why "why is my pod taking eight seconds" is a
# question with a real answer rather than a broken cluster.
#
# Reproduce it: time `docker run --rm <image> true` in a loop.
EOF

# ------------------------------------------------------------- the workloads

W=/tmp/workloads
rm -rf "$W"; mkdir -p "$W"

cat > "$W/alpha.txt" <<'EOF'
workload: alpha — customer-facing HTTP API
traffic: steady 400 req/s, 24 hours a day, latency budget p99 < 150 ms
tenancy: our code only
state: stateless; all state in a managed database
constraint: the team deploys 20+ times a day
EOF

cat > "$W/bravo.txt" <<'EOF'
workload: bravo — runs code submitted by our customers
traffic: unpredictable, 0 to 2000 concurrent executions
tenancy: HOSTILE — customers may submit anything, deliberately
state: none; each execution is independent and short
constraint: must not be able to reach other customers' executions
EOF

cat > "$W/charlie.txt" <<'EOF'
workload: charlie — nightly financial reconciliation
traffic: one run per night, 40 minutes, 60 GB of memory at peak
tenancy: our code only
state: reads and writes a large working set on local disk
constraint: must complete before 06:00; runs on a fixed schedule
EOF

cat > "$W/delta.txt" <<'EOF'
workload: delta — webhook receiver for a partner integration
traffic: 0 to 40 req/s, bursty, often silent for hours
tenancy: our code only
state: stateless; writes to a queue
constraint: partner tolerates up to 3 s for the first request after idle
EOF

cat > "$W/README.txt" <<'EOF'
Four workloads. Choose a layer for each — bare metal, VM, container or function
— and justify it by what the alternatives would have cost.

One of these has a constraint that eliminates every layer but one, and it is
not the one with the largest resource requirement.
EOF

echo "Seeded: /tmp/captures (bare metal, VM, startup costs), /tmp/workloads."

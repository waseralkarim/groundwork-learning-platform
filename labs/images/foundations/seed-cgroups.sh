#!/bin/bash
# Seeds two cgroup trees for the A02 cgroup labs.
#
# A tier-2 sandbox mounts /sys/fs/cgroup read-only and re-roots it, which is
# correct and is itself a lesson — but it means a learner cannot walk a node's
# hierarchy or read the limits above their own. So the hierarchy is reproduced
# here as real directories with real interface files, taken from a Kubernetes
# node with cgroup v2 and the systemd driver.
#
# Everything written is inert data under the session's own tmpfs. Nothing here
# executes anything the learner writes.
set -euo pipefail

# put <path> <file>=<value> ...
put() {
  local dir="$1"; shift
  mkdir -p "$dir"
  local kv
  for kv in "$@"; do
    printf '%s
' "${kv#*=}" > "$dir/${kv%%=*}"
  done
}

# ---------------------------------------------------------------- lab 3 tree ---
# A quiet node. The interesting property is structural: one container's own
# memory.max is `max` while the pod slice above it is not.
N=/tmp/node/sys/fs/cgroup
put "$N" memory.max=max cpu.max=max cpu.weight=100

put "$N/system.slice" memory.max=max cpu.weight=100 cpu.max=max
put "$N/kubepods.slice"   memory.max=30064771072 cpu.max=max cpu.weight=100 memory.current=19327352832

# checkout — Guaranteed, so it sits directly under kubepods.slice
P=$N/kubepods.slice/kubepods-pod3f1a.slice
put "$P" memory.max=2147483648 cpu.max="200000 100000" cpu.weight=79 memory.current=1503238553
put "$P/cri-containerd-a1b2.scope"   memory.max=2147483648 cpu.max="200000 100000" cpu.weight=79   memory.current=1503238553 memory.peak=1610612736
printf 'low 0
high 0
max 0
oom 0
oom_kill 0
' > "$P/cri-containerd-a1b2.scope/memory.events"

# reports — Burstable. The sidecar has no limit of its own.
B=$N/kubepods.slice/kubepods-burstable.slice
put "$B" memory.max=max cpu.max=max cpu.weight=100 memory.current=901775360
P=$B/kubepods-burstable-pod7c2b.slice
put "$P" memory.max=536870912 cpu.max=max cpu.weight=20 memory.current=524288000
put "$P/cri-containerd-c3d4.scope"   memory.max=469762048 cpu.max=max cpu.weight=20   memory.current=440401920 memory.peak=463470592
printf 'low 0
high 0
max 41
oom 0
oom_kill 0
' > "$P/cri-containerd-c3d4.scope/memory.events"
put "$P/cri-containerd-e5f6.scope"   memory.max=max cpu.max=max cpu.weight=20   memory.current=83886080 memory.peak=94371840
printf 'low 0
high 0
max 0
oom 3
oom_kill 3
' > "$P/cri-containerd-e5f6.scope/memory.events"

# scratch — BestEffort
E=$N/kubepods.slice/kubepods-besteffort.slice
put "$E" memory.max=max cpu.max=max cpu.weight=1
P=$E/kubepods-besteffort-pod9e44.slice
put "$P" memory.max=max cpu.max=max cpu.weight=1 memory.current=134217728
put "$P/cri-containerd-9a8b.scope"   memory.max=max cpu.max=max cpu.weight=1 memory.current=134217728 memory.peak=201326592

# ------------------------------------------------------------ lab 4 incident ---
# Three containers pulled off a node during an incident. Each is a different
# problem, and one of them is not a problem at all.
I=/tmp/incident

put "$I/alpha"   cpu.max="20000 100000" cpu.weight=4   memory.max=1073741824 memory.current=241172480 memory.peak=268435456
printf 'usage_usec 1180043221
nr_periods 214880
nr_throttled 211944
throttled_usec 8801244930
' > "$I/alpha/cpu.stat"
printf 'some avg10=61.44 avg60=59.80 avg300=58.11 total=1904772311
full avg10=61.40 avg60=59.77 avg300=58.09 total=1903991044
' > "$I/alpha/cpu.pressure"
printf 'low 0
high 0
max 0
oom 0
oom_kill 0
' > "$I/alpha/memory.events"

put "$I/bravo"   cpu.max=max cpu.weight=39   memory.max=268435456 memory.current=262406144 memory.peak=268435456
printf 'usage_usec 40118822
nr_periods 0
nr_throttled 0
throttled_usec 0
' > "$I/bravo/cpu.stat"
printf 'some avg10=0.11 avg60=0.09 avg300=0.07 total=4112893
full avg10=0.09 avg60=0.08 avg300=0.06 total=3990114
' > "$I/bravo/cpu.pressure"
printf 'some avg10=44.20 avg60=41.03 avg300=39.88 total=903118442
full avg10=43.90 avg60=40.81 avg300=39.60 total=901004221
' > "$I/bravo/memory.pressure"
printf 'low 0
high 0
max 88214
oom 12
oom_kill 12
' > "$I/bravo/memory.events"
printf 'anon 249561088
file 4194304
shmem 0
kernel 8650752
' > "$I/bravo/memory.stat"

put "$I/charlie"   cpu.max="400000 100000" cpu.weight=157   memory.max=4294967296 memory.current=1932735283 memory.peak=2147483648
printf 'usage_usec 918442110
nr_periods 214880
nr_throttled 24
throttled_usec 1880422
' > "$I/charlie/cpu.stat"
printf 'some avg10=1.02 avg60=0.94 avg300=0.88 total=21884320
full avg10=0.61 avg60=0.55 avg300=0.51 total=13004221
' > "$I/charlie/cpu.pressure"
printf 'low 0
high 0
max 0
oom 0
oom_kill 0
' > "$I/charlie/memory.events"

echo "Seeded: a node's cgroup tree at /tmp/node, and three containers at /tmp/incident."

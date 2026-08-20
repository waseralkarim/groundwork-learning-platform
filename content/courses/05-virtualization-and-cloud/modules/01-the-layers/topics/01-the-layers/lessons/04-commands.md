---
topic: topic.the-layers
section: commands
title: Taking the census, and reading the true numbers
order: 4
mode: explain
---

## Where am I

```bash
grep -o hypervisor /proc/cpuinfo | head -1     # virtualised, or no output
lscpu | grep -iE 'hypervisor|virtualization'   # which hypervisor, and the type
lscpu | grep 'Model name'                      # the real silicon underneath
uname -r                                       # whose kernel
[ -f /.dockerenv ] && echo containerised
cat /sys/class/dmi/id/sys_vendor 2>/dev/null   # what the firmware claims to be
```

Six commands and you have the whole stack. Two of them are informative when they
*fail*: no hypervisor flag means bare metal, and a missing `/sys/class/dmi`
means you are in a container rather than directly on the guest.

:::try{lab=count-your-layers run="grep -o hypervisor /proc/cpuinfo | head -1; lscpu | grep -i 'hypervisor vendor'; uname -r; ls /.dockerenv"}
Four layers in four lines: virtualised, by Microsoft's hypervisor, on a kernel
whose name says WSL2, inside a container. None of that is in any manifest.
:::

## What am I actually allowed

```bash
cat /sys/fs/cgroup/cpu.max        # quota period, in microseconds
cat /sys/fs/cgroup/memory.max     # bytes, or "max"
cat /sys/fs/cgroup/pids.max
```

The CPU arithmetic, done properly:

```bash
awk '{ if ($1=="max") print "unlimited"; else printf "%.2f cores\n", $1/$2 }' \
    /sys/fs/cgroup/cpu.max
```

And memory in units a person can read:

```bash
awk '{ if ($1=="max") print "unlimited"; else printf "%.0f MiB\n", $1/1048576 }' \
    /sys/fs/cgroup/memory.max
```

Compare against what the standard interfaces claim:

```bash
nproc                                    # the machine's CPUs
awk '/MemTotal/ {printf "%.1f GiB\n", $2/1048576}' /proc/meminfo
```

:::try{lab=the-numbers-that-lie run="echo \"nproc: $(nproc)\"; awk '{printf \"cpu.max: %.2f cores\\n\", $1/$2}' /sys/fs/cgroup/cpu.max" title="Two answers to one question"}
One of these is what a thread pool will size itself from and the other is what
the kernel will actually let it use. The ratio is how much throttling the
process is about to discover.
:::

## Is it being throttled

```bash
cat /sys/fs/cgroup/cpu.stat
# nr_periods, nr_throttled, throttled_usec
```

`nr_throttled` rising is the counter that tells the truth when CPU utilisation
looks comfortable. Watch it change:

```bash
before=$(awk '/^nr_throttled/{print $2}' /sys/fs/cgroup/cpu.stat)
# ...run the workload...
after=$(awk '/^nr_throttled/{print $2}' /sys/fs/cgroup/cpu.stat)
echo "throttled $((after - before)) more periods"
```

And the per-cgroup pressure, which is the honest replacement for load average:

```bash
cat /sys/fs/cgroup/cpu.pressure
cat /sys/fs/cgroup/memory.pressure
```

## Sizing things correctly

```bash
CORES=$(awk '{ if ($1=="max") print 0; else printf "%d", ($1/$2)+0.5 }' /sys/fs/cgroup/cpu.max)
[ "$CORES" -lt 1 ] && CORES=$(nproc)      # unlimited: fall back to the host
export GOMAXPROCS=$CORES
```

That snippet is worth keeping. It reads the limit, rounds sensibly, and falls
back to the host count only when there genuinely is no limit.

For the JVM, prefer a percentage over a fixed size:

```bash
JAVA_OPTS="-XX:MaxRAMPercentage=75"     # of the container's limit
```

rather than `-Xmx3g`, which is a number that stops being right the moment
somebody changes the memory limit and does not tell anybody.

## Which cgroup version

```bash
[ -f /sys/fs/cgroup/cgroup.controllers ] && echo v2 || echo v1
```

v1 uses different names — `cpu.cfs_quota_us`, `cpu.cfs_period_us`,
`memory.limit_in_bytes` — and a script that reads only v2 paths finds nothing
and silently falls back to the host values, which is the exact failure it was
written to prevent.

## Timing a start

```bash
for i in 1 2 3 4 5; do
  t0=$(date +%s%N)
  docker run --rm alpine true
  t1=$(date +%s%N)
  echo "$(( (t1-t0)/1000000 )) ms"
done
```

Worth running once against your own environment, because the number you get is
usually nothing like the quoted one — ~760 ms on the machine these labs run on,
against the 5–50 ms that describes the runtime's own work. If a scale-up feels
slow, this is where the time is, and it is measurable rather than mysterious.

## The five worth keeping

```bash
grep -o hypervisor /proc/cpuinfo | head -1              # am I virtualised
uname -r                                                # whose kernel
awk '{printf "%.2f\n", $1/$2}' /sys/fs/cgroup/cpu.max   # what I actually get
awk '/nr_throttled/{print $2}' /sys/fs/cgroup/cpu.stat  # am I being stopped
awk '{printf "%.0f MiB\n", $1/1048576}' /sys/fs/cgroup/memory.max
```

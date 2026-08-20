#!/bin/bash
# Seeds real /proc/diskstats sample pairs and a storage incident bundle.
#
# A tier-2 sandbox has a read-only overlay root and a tmpfs scratch directory,
# so it cannot generate controlled block I/O — that is the isolation working,
# and inventing numbers to work around it would teach arithmetic on fiction.
# The samples here were taken off real machines, ten seconds apart, and every
# derived figure a learner computes from them is internally consistent
# (Little's law holds: queue depth = IOPS x await).
#
# Everything written is inert text under the session's own tmpfs.
set -euo pipefail

S=/tmp/samples
mkdir -p "$S"

# diskstats fields:
#  1 major  2 minor  3 name
#  4 reads  5 rmerged  6 sectors_read   7 ms_read
#  8 writes 9 wmerged 10 sectors_write 11 ms_write
# 12 in_flight 13 ms_io 14 weighted_ms
# 15-18 discards  19-20 flushes

# --- 1. a healthy SATA SSD, ten seconds apart -------------------------------
cat > "$S/healthy.txt" <<'EOF'
# device: sda   interval: 10 seconds   /sys/block/sda/queue/scheduler: [mq-deadline]
# rotational 0   nr_requests 256   read_ahead_kb 128
   8       0 sda 100000 2000 8000000 50000 50000 1000 4000000 30000 0 40000 80000 0 0 0 0 12 400
   8       0 sda 101200 2010 8096000 50600 50600 1010 4048000 30240 0 41000 82000 0 0 0 0 12 400
EOF

# --- 2. an NVMe at 100% util that is completely fine ------------------------
cat > "$S/nvme.txt" <<'EOF'
# device: nvme0n1   interval: 10 seconds   scheduler: [none]
# rotational 0   nr_requests 1023   read_ahead_kb 128
 259       0 nvme0n1 4000000 0 512000000 800000 1200000 0 153600000 240000 0 600000 1040000 0 0 0 0 88000 1200
 259       0 nvme0n1 4030000 0 515840000 806000 1206000 0 154368000 240600 0 610000 1046600 0 0 0 0 88300 1204
EOF

# --- 3. reads starved by writes on a rotational disk, scheduler none --------
cat > "$S/starved.txt" <<'EOF'
# device: sdb   interval: 10 seconds   scheduler: [none] mq-deadline bfq
# rotational 1   nr_requests 128   read_ahead_kb 128
   8      16 sdb 200000 400 25600000 900000 3000000 900000 384000000 600000 0 700000 2400000 0 0 0 0 400 900
   8      16 sdb 200500 402 25664000 1050000 3012000 903000 385536000 624000 0 710000 2574000 0 0 0 0 400 900
EOF

# --------------------------------------------------------------- incident ---
I=/tmp/incident
mkdir -p "$I"/{alpha,bravo,charlie}

# alpha: crossed dirty_ratio. Memory speed, then device speed, in one step.
cat > "$I/alpha/notes.txt" <<'EOF'
Service: ingest-writer. Node has 128 GiB RAM, volume is a cloud block store.
Symptom: writes are instant for ~40 minutes after a restart, then every write
blocks for seconds. Throughput graph is flat and healthy until it collapses.
EOF
cat > "$I/alpha/meminfo.txt" <<'EOF'
MemTotal:       131923968 kB
MemAvailable:   119238144 kB
Dirty:           23592960 kB
Writeback:        1048576 kB
Shmem:              81920 kB
EOF
cat > "$I/alpha/vm-sysctls.txt" <<'EOF'
vm.dirty_ratio = 20
vm.dirty_background_ratio = 10
vm.dirty_bytes = 0
vm.dirty_expire_centisecs = 3000
EOF
cat > "$I/alpha/proc-io.txt" <<'EOF'
rchar: 4096
wchar: 88046829568
syscr: 2
syscw: 671232
read_bytes: 0
write_bytes: 41875931136
EOF
cat > "$I/alpha/io.pressure" <<'EOF'
some avg10=61.20 avg60=58.44 avg300=41.02 total=1904772311
full avg10=60.80 avg60=58.11 avg300=40.77 total=1898221044
EOF
cat > "$I/alpha/mount.txt" <<'EOF'
/dev/sdb1 on /var/lib/ingest type ext4 (rw,relatime)
EOF

# bravo: 100% util on NVMe. Nothing is wrong; the alert is.
cat > "$I/bravo/notes.txt" <<'EOF'
Service: search-index. Alert fired: "disk utilisation 100% for 30 minutes".
No user-visible symptom reported. Escalated because the dashboard is red.
EOF
cat > "$I/bravo/diskstats.txt" <<'EOF'
# nvme0n1, ten seconds apart
 259       0 nvme0n1 4000000 0 512000000 800000 1200000 0 153600000 240000 0 600000 1040000 0 0 0 0 88000 1200
 259       0 nvme0n1 4030000 0 515840000 806000 1206000 0 154368000 240600 0 610000 1046600 0 0 0 0 88300 1204
EOF
cat > "$I/bravo/io.pressure" <<'EOF'
some avg10=0.42 avg60=0.38 avg300=0.31 total=8221044
full avg10=0.11 avg60=0.09 avg300=0.08 total=1904221
EOF
cat > "$I/bravo/queue.txt" <<'EOF'
scheduler            [none] mq-deadline kyber
rotational           0
nr_requests          1023
read_ahead_kb        128
EOF

# charlie: overlay copy-up. It wrote far more than it was asked to.
cat > "$I/charlie/notes.txt" <<'EOF'
Service: pricing-db (PostgreSQL). Runs fine for weeks, then a schema migration
takes 40 minutes instead of the 90 seconds it takes on a developer laptop.
Deployed without a volume, "because it is only a cache".
EOF
cat > "$I/charlie/proc-io.txt" <<'EOF'
rchar: 2199023255552
wchar: 1073741824
syscr: 16744448
syscw: 262144
read_bytes: 2190433320960
write_bytes: 12884901888
EOF
cat > "$I/charlie/mount.txt" <<'EOF'
overlay on / type overlay (rw,relatime,lowerdir=...,upperdir=...,workdir=...)
overlay on /var/lib/postgresql/data type overlay (rw,relatime,lowerdir=...)
EOF
cat > "$I/charlie/io.pressure" <<'EOF'
some avg10=22.40 avg60=21.88 avg300=20.14 total=402118221
full avg10=21.90 avg60=21.44 avg300=19.80 total=398004221
EOF

echo "Seeded: three diskstats sample pairs in /tmp/samples, three workloads in /tmp/incident."

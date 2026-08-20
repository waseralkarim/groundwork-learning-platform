#!/bin/bash
# Seeds three workloads' per-task scheduler evidence for the A02 scheduler
# challenge.
#
# The sandbox can produce contention on demand — the guided labs do exactly
# that — but it cannot produce a Kubernetes node with a wrapper script inherited
# from an old VM fleet and an unrelated service blocked on a slow database. So
# those arrive as captured /proc readings, laid out the way
# `for t in /proc/PID/task/*` would have printed them.
#
# All three captures cover the same 600-second window (6000 periods of 100ms),
# so the per-thread totals, the cgroup counters and the quotas agree with each
# other. A learner who checks the arithmetic should find it holds.
#
# Everything here is inert text under the session's own tmpfs.
set -euo pipefail

W=/tmp/workloads
mkdir -p "$W"/{alpha,bravo,charlie}

# ------------------------------------------------------------------ alpha ---
# Throttled by its own 1-CPU quota, and running 32 threads inside it.
cat > "$W/alpha/schedstat-per-thread.txt" <<'EOF'
# for t in /proc/1/task/*; do printf '%s %s
' "$(basename $t)" "$(cat $t/schedstat)"; done
1     17013493344 19927750000 28109
14    17073400010 19864687500 28146
15    17133306676 19801625000 28183
16    17193213342 19738562500 28220
17    17253120008 19675500000 28257
18    17313026674 19612437500 28294
19    17372933340 19549375000 28331
20    17432840006 19486312500 28368
21    17492746672 19423250000 28405
22    17552653338 19360187500 28442
23    17612560004 19297125000 28479
24    17672466670 19234062500 28516
25    17732373336 19171000000 28553
26    17792280002 19107937500 28590
27    17852186668 19044875000 28627
28    17912093334 18981812500 28664
29    17972000000 18918750000 28701
30    18031906666 18855687500 28738
31    18091813332 18792625000 28775
32    18151719998 18729562500 28812
33    18211626664 18666500000 28849
34    18271533330 18603437500 28886
35    18331439996 18540375000 28923
36    18391346662 18477312500 28960
37    18451253328 18414250000 28997
38    18511159994 18351187500 29034
39    18571066660 18288125000 29071
40    18630973326 18225062500 29108
41    18690879992 18162000000 29145
42    18750786658 18098937500 29182
43    18810693324 18035875000 29219
44    18870599990 17972812500 29256
EOF

cat > "$W/alpha/cpu.stat" <<'EOF'
usage_usec 575104000
nr_periods 6000
nr_throttled 5768
throttled_usec 178402100000
EOF

echo "100000 100000" > "$W/alpha/cpu.max"

cat > "$W/alpha/sched-main.txt" <<'EOF'
policy                                       :                    0
prio                                         :                  120
se.load.weight                               :              1048576
se.slice                                     :              3000000
nr_switches                                  :               918442
nr_voluntary_switches                        :                 1140
nr_involuntary_switches                      :               917302
EOF

cat > "$W/alpha/notes.txt" <<'EOF'
Service: checkout-api (Go). Capture window 600s.
Node: 32 CPUs, node-wide utilisation 44% throughout.
Startup log: "starting checkout-api GOMAXPROCS=32"
EOF

# ------------------------------------------------------------------ bravo ---
# Not a scheduling problem at all. Blocked on something external.
cat > "$W/bravo/schedstat-per-thread.txt" <<'EOF'
# for t in /proc/1/task/*; do printf '%s %s
' "$(basename $t)" "$(cat $t/schedstat)"; done
1     7452980000 27205166 40301
22    7477990000 27115083 40338
23    7503000000 27025000 40375
24    7528010000 26934917 40412
EOF

cat > "$W/bravo/cpu.stat" <<'EOF'
usage_usec 30012000
nr_periods 6000
nr_throttled 2
throttled_usec 41220
EOF

echo "400000 100000" > "$W/bravo/cpu.max"

cat > "$W/bravo/sched-main.txt" <<'EOF'
policy                                       :                    0
prio                                         :                  120
se.load.weight                               :              1048576
se.slice                                     :              3000000
nr_switches                                  :              1884221
nr_voluntary_switches                        :              1881044
nr_involuntary_switches                      :                 3177
EOF

cat > "$W/bravo/notes.txt" <<'EOF'
Service: reporting-api (Python). p99 4.1s, p50 90ms. Capture window 600s.
Node: 32 CPUs, node-wide utilisation 44% throughout.
Traces put almost all of the time inside one span named "db.query".
EOF

# ---------------------------------------------------------------- charlie ---
# Correct quota, no throttling, starving anyway — the weight is wrong.
cat > "$W/charlie/schedstat-per-thread.txt" <<'EOF'
# for t in /proc/1/task/*; do printf '%s %s
' "$(basename $t)" "$(cat $t/schedstat)"; done
1     787370634 62462760666 21979
31    790012817 62255930333 22016
32    792655000 62049100000 22053
33    795297183 61842269667 22090
EOF

cat > "$W/charlie/cpu.stat" <<'EOF'
usage_usec 3170620
nr_periods 6000
nr_throttled 4
throttled_usec 88220
EOF

echo "200000 100000" > "$W/charlie/cpu.max"

cat > "$W/charlie/sched-main.txt" <<'EOF'
policy                                       :                    0
prio                                         :                  139
se.load.weight                               :                15360
se.slice                                     :              3000000
nr_switches                                  :                88214
nr_voluntary_switches                        :                 1022
nr_involuntary_switches                      :                87192
EOF

cat > "$W/charlie/notes.txt" <<'EOF'
Service: pricing-api (Java). Capture window 600s.
Latency is fine at night and terrible during the working day.
Node: 32 CPUs, node-wide utilisation 44% throughout.
Deployed via a wrapper inherited from the old VM fleet. Its entrypoint is:
  exec nice -n 19 java -jar /srv/pricing.jar
EOF

echo "Seeded: three workloads' scheduler evidence under /tmp/workloads."

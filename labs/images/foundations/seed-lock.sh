#!/bin/bash
# Seeds the B08.8 concurrency-and-locking labs.
#
# What is seeded is what needs to be a real script:
#
#   - `job`, a slow task that logs its own start and finish, so two overlapping
#     runs are visible as interleaved lines rather than described
#   - report.sh, which takes no lock at all
#   - guarded.sh, which takes a lock and removes the lock FILE on exit
#   - watchdog.sh, which uses timeout without -k
#   - charge.sh, a non-idempotent action wrapped in a naive retry loop
set -euo pipefail

export LC_ALL=C

S=/tmp/lock
rm -rf "$S"; mkdir -p "$S"

cat > "$S/README.txt" <<'EOF'
Material for the concurrency-and-locking labs.

  job          a slow task that announces its start and finish
  report.sh    no lock. Run two at once and watch them interleave.
  guarded.sh   takes a lock, and removes the lock FILE in its cleanup trap
  watchdog.sh  uses timeout without -k, on a child that ignores TERM
  charge.sh    a non-idempotent action inside a retry loop

Run two of them at once. That is the whole topic.
EOF

# ---------------------------------------------------------------------- job

cat > "$S/job" <<'JOB'
#!/bin/bash
# A slow task. Announces itself so overlapping runs are visible.
name=${1:-job}
secs=${2:-1}
echo "  [$name] start   $(date +%H:%M:%S.%2N)"
echo "$name started" >> /tmp/lock/audit.log
sleep "$secs"
echo "$name finished" >> /tmp/lock/audit.log
echo "  [$name] finish  $(date +%H:%M:%S.%2N)"
JOB
chmod 0755 "$S/job"

# --------------------------------------------------------------- report.sh

cat > "$S/report.sh" <<'REP'
#!/bin/bash
# Build the nightly report. Takes no lock.
set -uo pipefail

NAME=${1:-report}
OUT=/tmp/lock/report.csv

echo "  [$NAME] reading"
rows=$(seq 1 5)
sleep 0.4
echo "  [$NAME] writing"
for r in $rows; do
  echo "$NAME,row-$r" >> "$OUT"
  sleep 0.05
done
echo "  [$NAME] done"
REP
chmod 0755 "$S/report.sh"

# -------------------------------------------------------------- guarded.sh

cat > "$S/guarded.sh" <<'GUA'
#!/bin/bash
# Build the nightly report, guarded by a lock.
# Cleans up after itself, which is where the problem is.
set -uo pipefail

NAME=${1:-guarded}
LOCK=/tmp/lock/guarded.lock

exec 9>"$LOCK"
if ! flock -n 9; then
  echo "  [$NAME] another run holds the lock - exiting"
  exit 0
fi

cleanup() { rm -f "$LOCK"; }      # tidy up the lock file on the way out
trap cleanup EXIT

echo "  [$NAME] start"
sleep "${HOLD_SECONDS:-1}"
echo "  [$NAME] finish"
GUA
chmod 0755 "$S/guarded.sh"

# ------------------------------------------------------------- watchdog.sh

cat > "$S/watchdog.sh" <<'WD'
#!/bin/bash
# Run the importer with a time limit, so it cannot hang the pipeline.
set -uo pipefail

LIMIT=${1:-1}

timeout "$LIMIT" /tmp/lock/importer
status=$?

if [ "$status" -eq 0 ]; then
  echo "importer finished cleanly"
else
  echo "importer did not finish in ${LIMIT}s - terminated (rc=$status)"
fi
exit "$status"
WD
chmod 0755 "$S/watchdog.sh"

cat > "$S/importer" <<'IMP'
#!/bin/bash
# Stands in for a real importer. Installs a TERM handler that logs and keeps
# going, which is a thing real importers do to avoid corrupting a half-written
# batch. The work is a loop, so an interrupted sleep does not end it.
trap 'echo "importer: ignoring TERM, batch in progress" >> /tmp/lock/importer.log' TERM
echo "importer: started pid $$" >> /tmp/lock/importer.log
i=0
while [ "$i" -lt "${IMPORT_BATCHES:-6}" ]; do
  sleep 0.5
  i=$((i + 1))
  echo "importer: batch $i written" >> /tmp/lock/importer.log
done
echo "importer: FINISHED WRITING ALL BATCHES" >> /tmp/lock/importer.log
IMP
chmod 0755 "$S/importer"

# ---------------------------------------------------------------- charge.sh

cat > "$S/charge.sh" <<'CHG'
#!/bin/bash
# Charge a customer, with retries for reliability.
set -uo pipefail

LEDGER=/tmp/lock/ledger.txt

charge_once() {
  # the charge is applied...
  echo "charged $1" >> "$LEDGER"
  # ...and then the response is lost. the money moved; we never heard back.
  return 1
}

customer=${1:-cust-001}
for attempt in 1 2 3; do
  if charge_once "$customer"; then
    echo "charged $customer on attempt $attempt"
    exit 0
  fi
  echo "  attempt $attempt failed, retrying"
  sleep 0.1
done

echo "giving up on $customer after 3 attempts" >&2
exit 1
CHG
chmod 0755 "$S/charge.sh"

: > "$S/audit.log"
: > "$S/importer.log"
: > "$S/ledger.txt"

cat > "$S/notes.txt" <<'EOF'
# Four questions, each answered by running something twice.
#
# report.sh
#   Start two at once:  report.sh A & report.sh B & wait
#   Read report.csv. Whose rows are where?
#
# guarded.sh
#   This one takes a lock, so two at once is safe. Start one, wait a moment,
#   then look at what its cleanup trap does — and start a third run after the
#   first has exited but while a second still holds the lock.
#
# watchdog.sh
#   Run it with a 1-second limit. It reports that it terminated the importer.
#   Then read importer.log a few seconds later.
#
# charge.sh
#   Run it once. Count the lines in ledger.txt.
EOF

echo "Seeded: /tmp/lock (a slow job, and four scripts that need running twice)."

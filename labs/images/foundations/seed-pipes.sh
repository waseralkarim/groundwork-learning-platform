#!/bin/bash
# Seeds the B08.2 pipes and redirection labs.
#
# The shell supplies nearly everything here: redirection order, truncation,
# subshells, exit status and SIGPIPE are all one line each to demonstrate.
#
# What is seeded is what needs to happen SLOWLY, because the buffering lesson
# is about latency and cannot be shown with instantaneous output:
#
#   - `drip`, which emits a line every second, so a learner can watch output
#     arrive at the wrong time and timestamp it
#   - a config file worth destroying, so the truncation lesson costs something
#   - a log pipeline with a masked failure
#
# `drip` deliberately uses printf and a sleep loop rather than any tool that
# might buffer differently. Its own output is unbuffered because printf from
# bash writes immediately; the buffering under test belongs to whatever the
# learner pipes it through.
set -euo pipefail

export LC_ALL=C

P=/tmp/pipes
rm -rf "$P"; mkdir -p "$P"

cat > "$P/README.txt" <<'EOF'
Material for the pipes and redirection labs.

  drip            emits one line per second, with a timestamp
  stamp           reads lines and prints how long after start each arrived
  app.conf        a config file to destroy, and then to destroy safely
  collect.sh      a log pipeline whose failure does not reach the exit status

Everything else you will do with one line of shell.
EOF

# ---------------------------------------------------------------- producers

cat > "$P/drip" <<'DRIP'
#!/bin/bash
# Emit one line per second. Defaults to 5 lines.
n=${1:-5}
start=${DRIP_START:-$(date +%s)}
i=0
while [ "$i" -lt "$n" ]; do
  i=$((i + 1))
  printf 'line %d emitted at +%ds\n' "$i" "$(( $(date +%s) - start ))"
  sleep 1
done
DRIP
chmod 0755 "$P/drip"

cat > "$P/stamp" <<'STAMP'
#!/bin/bash
# Read lines and report how many seconds after start each one ARRIVED.
start=${STAMP_START:-$(date +%s)}
while IFS= read -r line; do
  printf 'arrived +%ds : %s\n' "$(( $(date +%s) - start ))" "$line"
done
STAMP
chmod 0755 "$P/stamp"

# ------------------------------------------------------------------- config

cat > "$P/app.conf" <<'EOF'
# ledger service configuration
listen = 0.0.0.0:8080
workers = 8
log_level = info
DEBUG_TRACE = on
database = postgres://ledger@db.internal/production
timeout = 30
DEBUG_SQL = on
retention_days = 90
EOF

cp "$P/app.conf" "$P/app.conf.pristine"

cat > "$P/config-task.txt" <<'EOF'
# The task: remove every line containing DEBUG from app.conf.
#
# The obvious command is:
#
#     grep -v DEBUG app.conf > app.conf
#
# Predict what that leaves in the file before you run it. Then run it, and
# compare against app.conf.pristine.
#
# Then find at least two ways to do it that work, and say what each one costs.
EOF

# -------------------------------------------------------------- the pipeline

cat > "$P/collect.sh" <<'COLLECT'
#!/bin/bash
# Summarise yesterday's errors and write a report.
# Runs from cron. Has never reported a failure.

LOG=${1:-/tmp/pipes/app.log}
OUT=${2:-/tmp/pipes/report.txt}

count=0
grep ERROR "$LOG" | sort | uniq -c | while read -r n rest; do
  count=$((count + n))
done

echo "total errors: $count" > "$OUT"

grep ERROR "$LOG" | wc -l >> "$OUT"

echo "report written to $OUT"
COLLECT
chmod 0755 "$P/collect.sh"

cat > "$P/app.log" <<'EOF'
2026-08-17 02:14:01 INFO  started
2026-08-17 02:14:07 ERROR upstream timeout
2026-08-17 02:15:22 ERROR upstream timeout
2026-08-17 02:16:03 WARN  retry scheduled
2026-08-17 02:19:41 ERROR checksum mismatch
2026-08-17 02:31:08 INFO  recovered
EOF

cat > "$P/collect-notes.txt" <<'EOF'
# collect.sh has three separate problems and reports success for all of them.
#
#   1. `count` is always 0, no matter what is in the log.
#   2. If the log file does not exist, the script still exits 0 and writes a
#      report saying there were no errors.
#   3. It reads the log twice, and the two numbers can disagree if the log is
#      being written to.
#
# Find each one, say which shell behaviour causes it, and fix them.
#
# Test with:
#     bash collect.sh /tmp/pipes/app.log /tmp/pipes/out.txt
#     bash collect.sh /tmp/pipes/does-not-exist /tmp/pipes/out.txt ; echo "rc=$?"
EOF

echo "Seeded: /tmp/pipes (drip, stamp, a config to destroy, a masked pipeline)."

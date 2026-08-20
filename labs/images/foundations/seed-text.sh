#!/bin/bash
# Seeds the B08.3 text-searching labs.
#
# grep, sed and awk are all present, so every rule in this topic is one command
# to demonstrate. What needs seeding is realistic INPUT — text whose shape is
# the reason the naive approach fails:
#
#   - a log with variable-width columns, because that is what breaks cut and
#     what every real command produces
#   - a health-check script that dies on a successful search, so the set -e
#     interaction is something the learner watches happen
#   - a small set of patterns containing regex metacharacters, to be matched
#     literally
#
# The column widths in access.log are deliberately ragged. Aligned sample data
# is the reason people write `cut -d' '` and believe it works.
set -euo pipefail

export LC_ALL=C

T=/tmp/text
rm -rf "$T"; mkdir -p "$T"

cat > "$T/README.txt" <<'EOF'
Material for the text-searching labs.

  access.log      ragged columns, as real output is
  services.csv    a proper delimited file, for contrast
  healthcheck.sh  a script that stops on a search that found nothing
  patterns.txt    strings containing regex metacharacters

Everything else is one command.
EOF

# --------------------------------------------------------------- ragged log

cat > "$T/access.log" <<'EOF'
2026-08-17T02:14:01Z  10.2.0.14    GET   /api/orders        200   14ms
2026-08-17T02:14:07Z  10.2.0.9     POST  /api/orders        500  1204ms
2026-08-17T02:15:22Z  10.2.0.14    GET   /api/orders/8821   200    31ms
2026-08-17T02:16:03Z  192.168.4.2  GET   /health            200     2ms
2026-08-17T02:19:41Z  10.2.0.9     POST  /api/payments      500  3021ms
2026-08-17T02:22:10Z  10.2.0.31    GET   /api/orders        404     8ms
2026-08-17T02:31:08Z  10.2.0.14    GET   /health            200     1ms
2026-08-17T02:44:52Z  172.16.0.7   POST  /api/payments      200   882ms
EOF

cat > "$T/services.csv" <<'EOF'
name,port,replicas,owner
orders,8080,4,payments-team
payments,8081,2,payments-team
search,8082,6,discovery-team
health,8083,1,platform
EOF

# -------------------------------------------------------- the failing script

cat > "$T/healthcheck.sh" <<'HC'
#!/bin/bash
# Pre-deploy health check. Exits non-zero if anything is wrong.
set -euo pipefail

LOG=${1:-/tmp/text/access.log}

echo "checking for server errors..."
grep ' 500 ' "$LOG"

echo "checking for auth failures..."
grep ' 401 ' "$LOG"

echo "all checks complete"
HC
chmod 0755 "$T/healthcheck.sh"

cat > "$T/healthcheck-notes.txt" <<'EOF'
# healthcheck.sh never prints "all checks complete", and its exit status is 1.
#
# It is not broken in the way it looks. Run it and read carefully:
#
#     bash /tmp/text/healthcheck.sh ; echo "rc=$?"
#
# Questions:
#   1. Which line stops it, and did that line do anything wrong?
#   2. What does grep return when it finds nothing, and is that an error?
#   3. What would this script do on a PERFECTLY HEALTHY system?
#   4. Rewrite it so a clean log is a pass and an unreadable log is a failure.
#
# Question 3 is the one that matters. Work out what the current script reports
# for a system with no errors at all, before you fix anything.
EOF

# ------------------------------------------------------------- literal text

cat > "$T/patterns.txt" <<'EOF'
# Strings to search for LITERALLY. Every one contains at least one character
# that means something to a regular expression.
#
# For each, work out what a naive `grep "$pattern"` would also match.

  1.2.3.4
  v1.0.0
  cost: $5.00
  a+b
  GET /api/orders?id=1
  [warn]
  C:\Users\app
  (deprecated)
EOF

cat > "$T/haystack.txt" <<'EOF'
connect 1.2.3.4 ok
connect 1x2y3z4 ok
release v1.0.0 shipped
release v1a0b0 shipped
cost: $5.00 charged
cost: $5900 charged
formula a+b applied
formula aab applied
GET /api/orders?id=1 200
GET /api/ordersXid=1 200
[warn] disk low
Xwarn] disk low
C:\Users\app installed
CXUsersXapp installed
(deprecated) removed
Xdeprecated) removed
EOF

echo "Seeded: /tmp/text (a ragged log, a csv, a failing health check, literal patterns)."

#!/bin/bash
# Seeds the B08.5 script-structure labs.
#
# Almost nothing needs seeding: every behaviour in this topic is a one-line
# bash invocation, and the labs are better for having the learner run them.
#
# What is seeded is what benefits from being a real script rather than a
# one-liner:
#
#   - `probe`, a helper that runs a snippet under a given set of shell options
#     and reports the exit status. Turns "does errexit fire here?" into a table
#     the learner generates rather than reads.
#   - a migration script whose failure is masked by one ordinary-looking line,
#     so the diagnosis is a real one rather than a demonstration
#   - a deploy script whose cleanup runs twice
set -euo pipefail

export LC_ALL=C

S=/tmp/strict
rm -rf "$S"; mkdir -p "$S"

cat > "$S/README.txt" <<'EOF'
Material for the script-structure labs.

  probe          run a snippet under shell options and report its exit status
  migrate.sh     a migration whose failure is masked by one ordinary line
  deploy.sh      a deploy whose cleanup handler runs twice

Everything else is a one-line bash invocation. Run them yourself — the point
of this topic is the gap between what the preamble looks like it does and what
it does.
EOF

# ------------------------------------------------------------------- probe

cat > "$S/probe" <<'PROBE'
#!/bin/bash
# Run a snippet under given shell options and report the exit status.
#
#   probe 'set -e' 'false; echo reached'
#
# Prints the status and whether the snippet got to its end.
opts=$1
code=$2
out=$(bash -c "$opts; $code" 2>&1); rc=$?
printf 'rc=%-4s %s\n' "$rc" "$(printf '%s' "$out" | tr '\n' ' ' | cut -c1-52)"
PROBE
chmod 0755 "$S/probe"

cat > "$S/cases.txt" <<'EOF'
# Predict the exit status of each under `set -e`, before running it.
# "fires" means the script exits at that command; "exempt" means it continues.
#
#    1.  false
#    2.  false || true
#    3.  ! false
#    4.  if false; then :; fi
#    5.  while false; do :; done
#    6.  f(){ false; }; f
#    7.  f(){ false; }; if f; then :; fi
#    8.  ( false ) || true
#    9.  false | true
#   10.  x=$(false)
#   11.  f(){ local x=$(false); }; f
#   12.  count=0; ((count++))
#   13.  count=0; ((count+=1))
#
# Two pairs differ from each other in ways almost nobody predicts: 10 against
# 11, and 12 against 13. Score yourself honestly before reading anything.
EOF

# ------------------------------------------------------------ the migration

cat > "$S/migrate.sh" <<'MIG'
#!/bin/bash
# Apply pending database migrations, then record the new schema version.
# Runs on every deploy. Has never reported a failure.
set -euo pipefail

SCHEMA_DIR=${1:-/tmp/strict/schema}

apply_migration() {
  local file=$1
  # capture the output so we can log it on failure
  local output=$(fake_psql < "$file")
  echo "applied $(basename "$file")"
}

count=0
for f in "$SCHEMA_DIR"/*.sql; do
  apply_migration "$f"
  count=$((count + 1))
done

echo "applied $count migrations"
MIG
chmod 0755 "$S/migrate.sh"

mkdir -p "$S/schema"
cat > "$S/schema/001-create.sql" <<'EOF'
CREATE TABLE orders (id int);
EOF
cat > "$S/schema/002-index.sql" <<'EOF'
CREATE INDEX orders_id ON orders (id);
EOF

cat > "$S/fake_psql" <<'PSQL'
#!/bin/bash
# Stands in for psql. Fails on anything mentioning INDEX, to simulate a
# migration that cannot be applied.
input=$(cat)
if printf '%s' "$input" | grep -qi index; then
  echo "ERROR: relation already exists" >&2
  exit 1
fi
exit 0
PSQL
chmod 0755 "$S/fake_psql"

cat > "$S/migrate-notes.txt" <<'EOF'
# migrate.sh has set -euo pipefail at the top and still reports success when a
# migration fails.
#
# Run it (fake_psql must be on PATH — add /tmp/strict to it) and observe:
#
#     PATH=/tmp/strict:$PATH bash /tmp/strict/migrate.sh ; echo "rc=$?"
#
# Questions:
#   1. Does it report the right number of migrations applied?
#   2. The second migration FAILS inside fake_psql, and its error is even
#      printed. Why does the script not stop, with set -e at the top?
#   3. Exactly one line is responsible, and it looks like an ordinary
#      assignment. Which one, and what is it really?
#   4. Fix it two different ways, and say which you would ship.
EOF

# --------------------------------------------------------------- the deploy

cat > "$S/deploy.sh" <<'DEP'
#!/bin/bash
# Deploy with cleanup. The cleanup handler runs more times than it should.
set -euo pipefail

WORKDIR=$(mktemp -d)

cleanup() {
  echo "cleanup: removing $WORKDIR"
  rm -rf "$WORKDIR"
}
trap cleanup EXIT INT TERM

echo "deploying into $WORKDIR"
touch "$WORKDIR/artifact"
sleep "${DEPLOY_SECONDS:-0}"
echo "deploy complete"
DEP
chmod 0755 "$S/deploy.sh"

echo "Seeded: /tmp/strict (probe, a masked migration, a double-cleanup deploy)."

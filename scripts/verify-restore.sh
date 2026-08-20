#!/usr/bin/env bash
# Restore a backup into a scratch database and prove the data survived.
#
# This is the whole point of the backup script. An untested backup is a
# hypothesis, and the failure mode is not "the file was corrupt" — it is
# discovering, on the worst day of the quarter, that the dump was 8 KB of schema
# with no rows, or that it restored cleanly and every learner's progress now
# points at content ids that no longer exist.
#
# So this does not check that pg_restore exits 0. It restores into a scratch
# database, counts what came back, and then asserts the one property this whole
# platform depends on: that a progress row still resolves to the topic it was
# recorded against.
#
#   bash scripts/verify-restore.sh                 # newest backup
#   bash scripts/verify-restore.sh backups/x.dump  # a specific one
set -uo pipefail

cd "$(dirname "$0")/.."
[ -f .env ] && set -a && . ./.env && set +a

COMPOSE="${COMPOSE:-docker compose}"
DB_USER="${POSTGRES_USER:-groundwork}"
DB_NAME="${POSTGRES_DB:-groundwork}"
SCRATCH="groundwork_restore_test"

GREEN=$'\033[32m'; RED=$'\033[31m'; DIM=$'\033[2m'; RESET=$'\033[0m'
fail=0
pass() { echo "  ${GREEN} ok ${RESET}  $1"; }
note() { echo "  ${RED}FAIL${RESET}  $1"; fail=$((fail + 1)); }

sql() { $COMPOSE exec -T db psql -qtAX -U "$DB_USER" -d "$1" -c "$2" 2>/dev/null | tr -d '\r'; }

# With no argument, take a fresh dump and verify that one. Comparing an older
# file against the live database is a false failure waiting to happen: a backup
# is a point in time, and the live database moves on the moment anyone signs up.
#
# Given an explicit file, row counts are checked for plausibility rather than
# equality — and the integrity assertions below, which are the real test, hold
# for a dump of any age.
compare_live=1
if [ $# -gt 0 ]; then
  dump="$1"
  compare_live=0
else
  echo "Taking a fresh backup to verify"
  bash "$(dirname "$0")/backup.sh" >/dev/null || { echo "backup failed" >&2; exit 1; }
  dump="$(ls -1t ./backups/groundwork-*.dump 2>/dev/null | head -1)"
fi

if [ -z "${dump:-}" ] || [ ! -f "${dump}" ]; then
  echo "No backup found. Make one first: task db:backup" >&2
  exit 2
fi

echo "Restore check: ${dump}"

live_users=$(sql "$DB_NAME" "SELECT count(*) FROM users")
live_progress=$(sql "$DB_NAME" "SELECT count(*) FROM user_progress")
live_topics=$(sql "$DB_NAME" "SELECT count(*) FROM topics")
if [ "$compare_live" = "1" ]; then
  echo "  ${DIM}live: ${live_users} users, ${live_progress} progress rows, ${live_topics} topics${RESET}"
else
  echo "  ${DIM}older dump — checking it is usable, not that it matches the live database${RESET}"
fi

# --- restore into a scratch database -----------------------------------------
# Never into the live one. A verification script that can destroy production is
# a verification script nobody will run.
$COMPOSE exec -T db psql -qtAX -U "$DB_USER" -d postgres \
  -c "DROP DATABASE IF EXISTS ${SCRATCH}" -c "CREATE DATABASE ${SCRATCH}" >/dev/null 2>&1

if $COMPOSE exec -T db pg_restore --username="$DB_USER" --dbname="$SCRATCH" --no-owner \
     < "$dump" >/tmp/gw-restore.log 2>&1; then
  pass "pg_restore completed"
else
  # pg_restore warns about extensions and comments it cannot recreate as a
  # non-superuser. Those are noise; missing tables are not.
  if grep -qiE "error.*(relation|table|column)" /tmp/gw-restore.log; then
    note "pg_restore reported errors on real objects"
    grep -iE "error" /tmp/gw-restore.log | head -3 | sed 's/^/        /'
  else
    pass "pg_restore completed (with ignorable warnings)"
  fi
fi

# --- did the rows come back? --------------------------------------------------
r_users=$(sql "$SCRATCH" "SELECT count(*) FROM users")
r_progress=$(sql "$SCRATCH" "SELECT count(*) FROM user_progress")
r_topics=$(sql "$SCRATCH" "SELECT count(*) FROM topics")

for pair in "users:${live_users}:${r_users}" "user_progress:${live_progress}:${r_progress}" "topics:${live_topics}:${r_topics}"; do
  name=${pair%%:*}; rest=${pair#*:}; expected=${rest%%:*}; got=${rest#*:}
  if [ -z "$got" ]; then
    note "${name}: table missing or unreadable in the restore"
  elif [ "$compare_live" = "1" ] && [ "$got" != "$expected" ]; then
    note "${name}: restored ${got}, live has ${expected}"
  elif [ "$got" = "0" ] && [ "${expected:-0}" != "0" ]; then
    note "${name}: restored 0 rows — the dump has the schema but not the data"
  else
    pass "${name}: ${got} rows restored"
  fi
done

# --- the property that actually matters ---------------------------------------
# Row counts prove the file was not empty. This proves the data is still
# *usable*: a progress row that no longer joins to its topic is a row that will
# never be shown to the learner it belongs to, and the platform is keyed on
# deterministic content UUIDs precisely so this cannot happen.
orphans=$(sql "$SCRATCH" "
  SELECT count(*) FROM user_progress p
  WHERE p.entity_type = 'topic'
    AND NOT EXISTS (SELECT 1 FROM topics t WHERE t.id = p.entity_id)")
if [ "${orphans:-x}" = "0" ]; then
  pass "every restored topic-progress row still resolves to its topic"
else
  note "${orphans} progress rows point at topics that do not exist in the restore"
fi

# Sessions are hashed tokens with expiry; they are expected to survive as rows.
# Password hashes must survive too, or every account is locked out.
hashes=$(sql "$SCRATCH" "SELECT count(*) FROM users WHERE password_hash LIKE '\$argon2%'")
if [ -n "$hashes" ] && [ "$hashes" = "$r_users" ] && [ "${r_users:-0}" -gt 0 ]; then
  pass "every restored account kept a usable password hash"
else
  note "password hashes did not survive: ${hashes:-0} of ${r_users:-0}"
fi

# --- clean up -----------------------------------------------------------------
$COMPOSE exec -T db psql -qtAX -U "$DB_USER" -d postgres \
  -c "DROP DATABASE IF EXISTS ${SCRATCH}" >/dev/null 2>&1

echo
if [ "$fail" -ne 0 ]; then
  echo "${RED}Restore check FAILED — this backup would not have saved you.${RESET}" >&2
  exit 1
fi
echo "${GREEN}Restore check passed.${RESET}"

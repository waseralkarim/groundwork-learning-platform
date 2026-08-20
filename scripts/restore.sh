#!/usr/bin/env bash
# Restore a backup over a database. Destructive by design.
#
#   bash scripts/restore.sh                          # newest backup, dry run
#   bash scripts/restore.sh --yes                    # newest backup, for real
#   bash scripts/restore.sh backups/x.dump --yes
#   bash scripts/restore.sh backups/x.dump --into groundwork_drill --yes
#
# Three safeguards, each of which exists because of a specific way people lose
# data during a restore:
#
# 1. It refuses to run without --yes, and prints exactly what it would replace.
#    Restores happen under stress, and "I thought it was pointing at staging" is
#    the most common way a bad hour becomes a bad week.
# 2. It takes a safety dump of the current contents first. If the backup turns
#    out to be the wrong one, the thing you just destroyed is still on disk.
# 3. It stops the services that hold connections. A restore against a live
#    application either fails on open connections or races the application
#    writing rows into a half-restored schema.
set -uo pipefail

cd "$(dirname "$0")/.."
[ -f .env ] && set -a && . ./.env && set +a

COMPOSE="${COMPOSE:-docker compose}"
DB_USER="${POSTGRES_USER:-groundwork}"
DB_NAME="${POSTGRES_DB:-groundwork}"

GREEN=$'\033[32m'; RED=$'\033[31m'; YELLOW=$'\033[33m'; DIM=$'\033[2m'; RESET=$'\033[0m'

dump=""
target="$DB_NAME"
confirmed=0

while [ $# -gt 0 ]; do
  case "$1" in
    --yes) confirmed=1 ;;
    --into) target="${2:?--into needs a database name}"; shift ;;
    -*) echo "unknown option: $1" >&2; exit 2 ;;
    *) dump="$1" ;;
  esac
  shift
done

[ -z "$dump" ] && dump="$(ls -1t ./backups/groundwork-*.dump 2>/dev/null | head -1)"
if [ -z "$dump" ] || [ ! -f "$dump" ]; then
  echo "No backup found. Make one first: task db:backup" >&2
  exit 2
fi

sql() { $COMPOSE exec -T db psql -qtAX -U "$DB_USER" -d "$1" -c "$2" 2>/dev/null | tr -d '\r'; }

exists=$(sql postgres "SELECT 1 FROM pg_database WHERE datname = '${target}'")
current_users="?"
[ -n "$exists" ] && current_users=$(sql "$target" "SELECT count(*) FROM users")

echo "Restore"
echo "  from:   ${dump}"
echo "  into:   ${target}$([ -z "$exists" ] && echo ' (will be created)')"
echo "  ${DIM}that database currently holds ${current_users} user accounts${RESET}"

if [ "$confirmed" -ne 1 ]; then
  echo
  echo "${YELLOW}Dry run.${RESET} Nothing has changed."
  echo "Re-run with --yes to replace the contents of '${target}'."
  exit 0
fi

# --- 2: safety dump -----------------------------------------------------------
if [ -n "$exists" ]; then
  mkdir -p ./backups
  safety="./backups/pre-restore-$(date -u +%Y%m%dT%H%M%SZ).dump"
  if $COMPOSE exec -T db pg_dump -U "$DB_USER" -d "$target" -Fc --clean --if-exists > "$safety" 2>/dev/null \
     && [ "$(wc -c < "$safety" | tr -d ' ')" -gt 1024 ]; then
    echo "  ${GREEN} ok ${RESET}  safety dump of the current contents: ${safety}"
  else
    echo "  ${RED}FAIL${RESET}  could not take a safety dump — refusing to continue" >&2
    rm -f "$safety"
    exit 1
  fi
fi

# --- 3: stop the writers ------------------------------------------------------
# Not the database itself, obviously. Just everything holding a connection to it.
echo "  ${DIM}stopping api, worker and migrate${RESET}"
$COMPOSE stop api worker >/dev/null 2>&1

# Terminate whatever is left, or CREATE/DROP will fail on an open connection.
sql postgres "
  SELECT pg_terminate_backend(pid) FROM pg_stat_activity
  WHERE datname = '${target}' AND pid <> pg_backend_pid()" >/dev/null

if [ -z "$exists" ]; then
  $COMPOSE exec -T db psql -qtAX -U "$DB_USER" -d postgres -c "CREATE DATABASE ${target}" >/dev/null
fi

# --- restore ------------------------------------------------------------------
# --clean --if-exists is in the dump itself, so existing objects are dropped as
# it goes rather than needing the database recreated.
if $COMPOSE exec -T db pg_restore -U "$DB_USER" -d "$target" --no-owner --clean --if-exists \
     < "$dump" >/tmp/gw-restore-run.log 2>&1; then
  echo "  ${GREEN} ok ${RESET}  restored"
elif grep -qiE "error.*(relation|table|column|constraint)" /tmp/gw-restore-run.log; then
  echo "  ${RED}FAIL${RESET}  pg_restore reported errors on real objects:" >&2
  grep -iE "error" /tmp/gw-restore-run.log | head -5 | sed 's/^/        /' >&2
  echo "  ${DIM}the safety dump above still has what was there before${RESET}" >&2
  $COMPOSE start api worker >/dev/null 2>&1
  exit 1
else
  echo "  ${GREEN} ok ${RESET}  restored (with ignorable warnings)"
fi

restored_users=$(sql "$target" "SELECT count(*) FROM users")
restored_progress=$(sql "$target" "SELECT count(*) FROM user_progress")
echo "  ${GREEN} ok ${RESET}  ${restored_users} accounts, ${restored_progress} progress rows"

$COMPOSE start api worker >/dev/null 2>&1
echo "  ${DIM}restarted api and worker${RESET}"

echo
echo "${GREEN}Restore complete.${RESET}"
echo "${DIM}Content is not in this dump by design — re-run an ingest if the curriculum"
echo "has moved on since the backup: docker compose exec api python -m app.content.cli ingest${RESET}"

#!/usr/bin/env bash
# Back up the database.
#
# What is actually at risk here is narrow and irreplaceable: accounts, progress,
# quiz attempts, hypotheses. The curriculum is in git and can be rebuilt with one
# ingest, so a backup that captured only content would be theatre.
#
# Custom format (-Fc) rather than plain SQL: it is compressed, it restores
# selectively, and pg_restore can list its contents without a database — which
# matters when you are trying to work out whether a file is worth restoring.
set -euo pipefail

cd "$(dirname "$0")/.."
[ -f .env ] && set -a && . ./.env && set +a

COMPOSE="${COMPOSE:-docker compose}"
DB_USER="${POSTGRES_USER:-groundwork}"
DB_NAME="${POSTGRES_DB:-groundwork}"
DIR="${BACKUP_DIR:-./backups}"
KEEP="${BACKUP_KEEP:-14}"

GREEN=$'\033[32m'; RED=$'\033[31m'; DIM=$'\033[2m'; RESET=$'\033[0m'

mkdir -p "$DIR"
stamp=$(date -u +%Y%m%dT%H%M%SZ)
target="${DIR}/groundwork-${stamp}.dump"

echo "Backing up ${DB_NAME}"

# --clean --if-exists so the dump can be restored over an existing database
# without a manual drop. No --no-owner: the roles are the same on both sides here.
if ! $COMPOSE exec -T db pg_dump \
      --username="$DB_USER" \
      --dbname="$DB_NAME" \
      --format=custom \
      --clean --if-exists \
      --compress=9 \
      > "$target" 2>/tmp/gw-backup-err; then
  echo "${RED}pg_dump failed:${RESET}" >&2
  cat /tmp/gw-backup-err >&2
  rm -f "$target"
  exit 1
fi

size=$(wc -c < "$target" | tr -d ' ')
if [ "$size" -lt 1024 ]; then
  echo "${RED}Backup is only ${size} bytes — that is not a database.${RESET}" >&2
  rm -f "$target"
  exit 1
fi

# Read it back immediately. A dump nobody has opened is a guess, and pg_restore
# --list is the cheapest possible proof that the file is structurally intact.
if ! objects=$($COMPOSE exec -T db pg_restore --list < "$target" 2>/dev/null | grep -c "TABLE DATA"); then
  echo "${RED}The dump could not be read back by pg_restore.${RESET}" >&2
  exit 1
fi

echo "  ${GREEN} ok ${RESET}  ${target}"
echo "  ${DIM}$(( size / 1024 )) KiB, ${objects} tables with data${RESET}"

# Retention. Deliberately count-based rather than age-based: on a machine that
# has been off for a month, an age-based policy deletes everything you have.
mapfile -t old < <(ls -1t "${DIR}"/groundwork-*.dump 2>/dev/null | tail -n +$((KEEP + 1)))
if [ ${#old[@]} -gt 0 ]; then
  for file in "${old[@]}"; do rm -f "$file"; done
  echo "  ${DIM}pruned ${#old[@]} backup(s), keeping the newest ${KEEP}${RESET}"
fi

echo
echo "A backup you have not restored is a hypothesis. Test it: task db:verify-restore"

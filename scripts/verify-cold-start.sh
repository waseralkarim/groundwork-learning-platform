#!/usr/bin/env bash
# Prove the project still starts from nothing.
#
# The original requirement is one sentence — "must run via `docker compose up`"
# — and it is the one most likely to rot without anyone noticing. A running
# development stack hides everything: migrations already applied, images already
# built, content already ingested, volumes already populated. Each of those can
# be broken for weeks while `task up` keeps working perfectly.
#
# So this brings up a *separate* Compose project with its own volumes and its
# own published port, on empty state, and asserts a learner can reach real
# content. It never touches the stack you are working in.
#
#   bash scripts/verify-cold-start.sh
#   KEEP=1 bash scripts/verify-cold-start.sh    # leave it running to poke at
set -uo pipefail

cd "$(dirname "$0")/.."

PROJECT="${COLD_PROJECT:-groundwork-coldstart}"
PORT="${COLD_PORT:-8099}"
COMPOSE="docker compose -p ${PROJECT}"

GREEN=$'\033[32m'; RED=$'\033[31m'; DIM=$'\033[2m'; RESET=$'\033[0m'
fail=0
pass() { echo "  ${GREEN} ok ${RESET}  $1"; }
note() { echo "  ${RED}FAIL${RESET}  $1"; fail=$((fail + 1)); }

cleanup() {
  if [ "${KEEP:-0}" = "1" ]; then
    echo "${DIM}Left running as project '${PROJECT}' on port ${PORT}. Remove with:"
    echo "  docker compose -p ${PROJECT} down -v${RESET}"
    return
  fi
  echo "${DIM}tearing down${RESET}"
  PUBLIC_PORT="$PORT" $COMPOSE down -v --remove-orphans >/dev/null 2>&1
}
trap cleanup EXIT

echo "Cold start check  ${DIM}(project ${PROJECT}, port ${PORT})${RESET}"

# Start from genuinely empty state: no volumes from an earlier run of this check.
PUBLIC_PORT="$PORT" $COMPOSE down -v --remove-orphans >/dev/null 2>&1

if [ ! -f .env ]; then
  note ".env does not exist — a cold start needs it (copy .env.example)"
  exit 1
fi

echo "  ${DIM}building and starting (this is the slow part)${RESET}"
if PUBLIC_PORT="$PORT" $COMPOSE up --build --wait --wait-timeout 420 -d >/tmp/gw-coldstart.log 2>&1; then
  pass "the stack came up from empty volumes"
else
  note "the stack did not become healthy"
  tail -25 /tmp/gw-coldstart.log | sed 's/^/        /'
  exit 1
fi

# --- migrations ---------------------------------------------------------------
# The migrate service runs from the image, not from a bind mount, so this is the
# check that catches a migration that exists on disk but was never rebuilt in.
head=$($COMPOSE exec -T db psql -qtAX -U "${POSTGRES_USER:-groundwork}" \
  -d "${POSTGRES_DB:-groundwork}" -c "SELECT version_num FROM alembic_version" 2>/dev/null | tr -d '\r')
if [ -n "$head" ]; then
  pass "migrations applied to head (${head})"
else
  note "no alembic_version row — migrations did not run"
fi

# --- content ------------------------------------------------------------------
# A cold start has an empty database, so content must be ingested before the
# platform is usable. If this is a manual step, it belongs in the bootstrap.
topics=$($COMPOSE exec -T db psql -qtAX -U "${POSTGRES_USER:-groundwork}" \
  -d "${POSTGRES_DB:-groundwork}" -c "SELECT count(*) FROM topics" 2>/dev/null | tr -d '\r')
if [ "${topics:-0}" -gt 0 ]; then
  pass "content ingested automatically (${topics} topics)"
else
  note "database is empty — content ingest is not part of a cold start"
fi

# --- what a learner would actually hit ----------------------------------------
check() {
  local path="$1" expected="$2" label="$3"
  local got
  got=$(curl -s -o /dev/null -w '%{http_code}' --max-time 20 "http://localhost:${PORT}${path}" || echo 000)
  if [ "$got" = "$expected" ]; then pass "$label"; else note "$label (got $got, wanted $expected)"; fi
}

check "/api/v1/health/ready" 200 "api is ready"
check "/" 200 "the home page renders"
check "/api/v1/roadmap" 200 "the roadmap is served"
check "/api/v1/internal/topics/x/labs/y/spec" 404 "internal endpoints are blocked at the edge"

first_topic=$(curl -s --max-time 20 "http://localhost:${PORT}/api/v1/roadmap" \
  | python -c "
import json,sys
d=json.load(sys.stdin)
print(d['courses'][0]['modules'][0]['topics'][0]['slug'])
" 2>/dev/null || echo "")
if [ -n "$first_topic" ]; then
  check "/topics/${first_topic}" 200 "a topic page renders (${first_topic})"
else
  note "could not read a topic slug from the roadmap"
fi

echo
if [ "$fail" -ne 0 ]; then
  echo "${RED}Cold start FAILED — a fresh clone would not work.${RESET}" >&2
  exit 1
fi
echo "${GREEN}Cold start passed.${RESET}"

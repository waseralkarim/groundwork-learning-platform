#!/usr/bin/env bash
# Verify the observability plane end to end.
#
# Not "are the containers up" — that proves nothing. This asserts that a signal
# produced by the platform actually arrives in the backend that is supposed to
# store it, that the alert rules parse, and that the dashboards are provisioned.
#
# The check that matters most is the last one: a log line's trace_id resolving
# to a real trace. That is the whole point of the pipeline, and it is the part
# that silently breaks — a regex that matches nothing, a handler cleared by
# logging configuration — while every container stays green.
set -uo pipefail

BASE="${BASE:-http://localhost:8080}"
GRAFANA="${GRAFANA:-http://localhost:3000}"
COMPOSE="${COMPOSE:-docker compose}"

GREEN=$'\033[32m'; RED=$'\033[31m'; DIM=$'\033[2m'; RESET=$'\033[0m'
fail=0
pass() { echo "  ${GREEN} ok ${RESET}  $1"; }
note() { echo "  ${RED}FAIL${RESET}  $1"; fail=$((fail + 1)); }
info() { echo "  ${DIM}$1${RESET}"; }

# Everything runs through the prometheus container: it sits on the observability
# network and has wget, so no backend needs a published port for this to work.
inside() { $COMPOSE exec -T prometheus wget -qO- "$1" 2>/dev/null; }

echo "Observability check"

if ! $COMPOSE ps --services --filter status=running 2>/dev/null | grep -q '^otel-collector$'; then
  echo "The observability profile is not running. Start it with: task obs:up" >&2
  exit 2
fi

# --- the signals get produced -------------------------------------------------
for _ in 1 2 3 4 5 6 7 8; do
  curl -s -o /dev/null "${BASE}/api/v1/roadmap"
  curl -s -o /dev/null "${BASE}/api/v1/search?q=kernel"
done
info "generated traffic; waiting for the 15s export interval"
sleep 20

# --- metrics ------------------------------------------------------------------
targets=$(inside 'http://localhost:9090/api/v1/targets' \
  | python -c "import json,sys; d=json.load(sys.stdin)['data']['activeTargets']; print(sum(1 for t in d if t['health']=='up'))" 2>/dev/null || echo 0)
if [ "${targets:-0}" -ge 2 ]; then pass "prometheus targets healthy ($targets up)"; else note "only $targets prometheus targets up"; fi

names=$(inside 'http://localhost:9090/api/v1/label/__name__/values' || echo '{}')
for metric in http_server_request_duration_seconds_count search_queries_total; do
  if printf '%s' "$names" | grep -q "\"$metric\""; then
    pass "metric present: $metric"
  else
    note "metric missing: $metric"
  fi
done

# The stable HTTP semantic convention, in seconds. The instrumentation ships the
# legacy millisecond names unless OTEL_SEMCONV_STABILITY_OPT_IN is set, and every
# dashboard query returns nothing when that happens.
if printf '%s' "$names" | grep -q '"http_server_request_duration_seconds_bucket"'; then
  pass "stable HTTP semconv in use (seconds, not milliseconds)"
else
  note "only legacy http_server_duration_milliseconds found — check OTEL_SEMCONV_STABILITY_OPT_IN"
fi

# --- alert rules --------------------------------------------------------------
rules=$(inside 'http://localhost:9090/api/v1/rules' \
  | python -c "import json,sys; print(sum(len(g['rules']) for g in json.load(sys.stdin)['data']['groups']))" 2>/dev/null || echo 0)
if [ "${rules:-0}" -ge 6 ]; then pass "alert rules loaded ($rules)"; else note "expected 6 alert rules, found ${rules:-0}"; fi

# --- traces -------------------------------------------------------------------
traces=$(inside 'http://tempo:3200/api/search?limit=5' \
  | python -c "import json,sys; print(len(json.load(sys.stdin).get('traces') or []))" 2>/dev/null || echo 0)
if [ "${traces:-0}" -gt 0 ]; then pass "traces reaching tempo ($traces recent)"; else note "no traces found in tempo"; fi

# --- logs ---------------------------------------------------------------------
services=$(inside 'http://loki:3100/loki/api/v1/label/service_name/values' || echo '{}')
if printf '%s' "$services" | grep -q 'groundwork-api'; then
  pass "logs reaching loki from groundwork-api"
else
  note "no groundwork-api logs in loki"
fi

# --- the join: a log line's trace id resolves to a real trace -----------------
query='%7Bservice_name%3D%22groundwork-api%22%7D%20%7C%20trace_id%20!%3D%20%22%22'
trace_id=$(inside "http://loki:3100/loki/api/v1/query_range?query=${query}&limit=1" \
  | python -c "
import json,sys
r=json.load(sys.stdin)['data']['result']
print(r[0]['stream']['trace_id'] if r else '')
" 2>/dev/null || echo "")

if [ -z "$trace_id" ]; then
  note "no log line carried a trace_id — logs and traces cannot be correlated"
else
  found=$(inside "http://tempo:3200/api/traces/${trace_id}" \
    | python -c "import json,sys; print(1 if json.load(sys.stdin).get('batches') else 0)" 2>/dev/null || echo 0)
  if [ "$found" = "1" ]; then
    pass "log → trace correlation works (${trace_id:0:16}…)"
  else
    note "log carried trace_id ${trace_id:0:16}… but tempo has no such trace"
  fi
fi

# --- dashboards ---------------------------------------------------------------
dashboards=$(curl -s --max-time 10 "${GRAFANA}/api/search?type=dash-db" \
  | python -c "import json,sys; print(len(json.load(sys.stdin)))" 2>/dev/null || echo 0)
if [ "${dashboards:-0}" -ge 4 ]; then
  pass "grafana dashboards provisioned ($dashboards)"
else
  note "expected 4 provisioned dashboards, found ${dashboards:-0}"
fi

sources=$(curl -s --max-time 10 "${GRAFANA}/api/datasources" \
  | python -c "import json,sys; print(','.join(sorted(d['type'] for d in json.load(sys.stdin))))" 2>/dev/null || echo "")
if [ "$sources" = "loki,prometheus,tempo" ]; then
  pass "grafana datasources provisioned ($sources)"
else
  note "unexpected datasources: '${sources}'"
fi

echo
if [ "$fail" -ne 0 ]; then
  echo "Observability check FAILED" >&2
  exit 1
fi
echo "Observability check passed."

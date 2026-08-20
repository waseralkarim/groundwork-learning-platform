#!/usr/bin/env bash
#
# End-to-end smoke test against a running stack.
#
# Exercises the full chain the way a browser would: through the proxy only.
# Nothing here talks to a service directly, because nothing in production could.

set -euo pipefail

BASE="${BASE:-http://localhost:8080}"
fail=0

note() { printf '  \033[31mFAIL\033[0m  %s\n' "$1"; fail=1; }
pass() { printf '  \033[32m ok \033[0m  %s\n' "$1"; }

check_status() {
  local path="$1" expected="$2" label="$3"
  local got
  got=$(curl -s -o /dev/null -w '%{http_code}' --max-time 10 "${BASE}${path}" || echo "000")
  if [ "$got" = "$expected" ]; then pass "$label ($path -> $got)"; else note "$label ($path -> $got, expected $expected)"; fi
}

check_json() {
  local path="$1" key="$2" expected="$3" label="$4"
  local got
  got=$(curl -s --max-time 10 "${BASE}${path}" \
    | python -c "import json,sys; print(json.load(sys.stdin).get('$key',''))" 2>/dev/null || echo "")
  if [ "$got" = "$expected" ]; then pass "$label ($key=$got)"; else note "$label ($key=$got, expected $expected)"; fi
}

echo "Smoke test against ${BASE}"

check_status "/healthz" 200 "proxy answers its own liveness"
check_status "/api/v1/health/live" 200 "api liveness through the proxy"
check_status "/api/v1/health/ready" 200 "api readiness (db + cache reachable)"
check_status "/api/v1/meta" 200 "api meta"
check_status "/" 200 "web app renders"
check_status "/api/v1/nope" 404 "unknown api route 404s"

check_json "/api/v1/health/live" "status" "alive" "liveness payload"
check_json "/api/v1/meta" "name" "Groundwork" "meta payload"

# --- curriculum ---
check_status "/api/v1/roadmap" 200 "roadmap"
check_status "/api/v1/topics/the-machine" 200 "topic detail"
check_status "/api/v1/topics/the-machine/quiz" 200 "quiz"
check_status "/api/v1/topics/does-not-exist" 404 "unknown topic 404s"
check_status "/topics/the-machine" 200 "topic overview renders"
check_status "/learn/the-machine/read-core-concepts" 200 "player renders a lesson screen"
check_status "/learn/the-machine/quiz" 200 "player renders the quiz screen"
check_status "/learn/the-machine/nonsense" 404 "unknown player step 404s"

# The answer key must never appear in any public response. This is the check
# that would catch a response model gaining a field it should not have.
leak_check() {
  local path="$1"
  local body
  body=$(curl -s --max-time 10 "${BASE}${path}")
  local found
  # `|| true` matters: grep exits 1 when it finds nothing, and with pipefail
  # that would abort the whole script exactly when the check is passing.
  found=$(printf '%s' "$body" \
    | { grep -o -E '"(is_correct|root_cause|model_answer|rubric|signal|common_failures|method|resolution)"' || true; } \
    | sort -u | tr '\n' ' ')
  if [ -z "$found" ]; then
    pass "no answer-key fields in $path"
  else
    note "answer key leaked from $path: $found"
  fi
}

for path in \
  "/api/v1/topics/the-machine/quiz" \
  "/api/v1/topics/the-machine/troubleshooting" \
  "/api/v1/topics/the-machine/interview" \
  "/api/v1/topics/the-machine/assessment" \
  "/api/v1/topics/the-machine/exercises"; do
  leak_check "$path"
done

# The rendered pages must contain real content, not just an application shell.
#
# Deliberately no pipe into grep. `grep -q` exits at the first match, which
# SIGPIPEs whatever is writing to it, and `set -o pipefail` then reports the
# check as failed — but only when the match is early in the page, which makes it
# look like a content bug rather than a script bug. Bash pattern matching has no
# such hazard.
check_page_contains() {
  local path="$1" needle="$2" label="$3"
  local page
  page=$(curl -s --max-time 20 "${BASE}${path}")
  if [[ "$page" == *"$needle"* ]]; then
    pass "$label"
  else
    note "$label (did not find '$needle' in $path)"
  fi
}

check_page_contains "/learn/the-machine/read-core-concepts" "fetch-decode-execute" "lesson prose is rendered"
check_page_contains "/learn/the-machine/read-core-concepts" "aria-label=\"Diagram\"" "diagrams are rendered"
check_page_contains "/learn/the-machine/read-internals" "Copy code" "code blocks have a copy control"
check_page_contains "/" "Computing Foundations" "roadmap lists the curriculum"

# The database must not be reachable from the host. If this connects, the
# topology has regressed.
if (exec 3<>/dev/tcp/localhost/5432) 2>/dev/null; then
  note "postgres is reachable from the host — it must not be"
  exec 3<&- 2>/dev/null || true
else
  pass "postgres is not reachable from the host"
fi

# Prove the whole chain: this string exists only in a YAML file in content/,
# so seeing it in rendered HTML means git -> ingest -> postgres -> api -> web
# all worked.
check_page_contains "/topics/the-machine" "resident set size" "content reached the browser from postgres"

# The player chrome: a persistent outline and one screen at a time is the whole
# point of the rework, so it is asserted rather than assumed.
check_page_contains "/learn/the-machine/read-core-concepts" "Topic progress" "player shows a progress bar"
check_page_contains "/learn/the-machine/read-core-concepts" "Complete and continue" "player offers the next step"
check_page_contains "/learn/the-machine/read-core-concepts" "Prove it" "player groups the outline by activity"

# --- the internal-endpoint boundary ---
#
# Verification specs are answer keys. They must be reachable by the lab broker
# over the internal network and by nothing else. This check has caught a stale
# Caddy config once already — editing the Caddyfile needs `docker compose
# restart proxy`, because a mounted config is not hot-reloaded.
check_status   "/api/v1/internal/topics/the-machine/labs/inspect-the-machine/steps/s1/checks"   404 "internal endpoints are not reachable through the proxy"

# --- accounts, grading, gating -------------------------------------------------
#
# Exercised as a real learner would: register, take the quiz, try to skip the
# troubleshooting gate, then earn the reveal.

JAR=$(mktemp)
trap 'rm -f "$JAR"' EXIT
# example.com, not example.test: `.test` is a reserved TLD and
# email-validator refuses it.
EMAIL="smoke-$$@example.com"
ORIGIN="Origin: ${BASE}"

api() { curl -s -b "$JAR" -c "$JAR" -H "$ORIGIN" "$@"; }
api_code() { curl -s -o /dev/null -w '%{http_code}' -b "$JAR" -c "$JAR" -H "$ORIGIN" "$@"; }

registered=$(api_code -X POST "${BASE}/api/v1/auth/register" \
  -H 'content-type: application/json' \
  -d "{\"email\":\"${EMAIL}\",\"password\":\"a-perfectly-fine-passphrase\",\"display_name\":\"Smoke\"}")
if [ "$registered" = "201" ]; then pass "registration"; else note "registration ($registered)"; fi

if grep -q gw_session "$JAR"; then pass "session cookie was set"; else note "no session cookie"; fi
if grep -qi "HttpOnly" "$JAR"; then pass "session cookie is httpOnly"; else note "session cookie is not httpOnly"; fi

me=$(api "${BASE}/api/v1/auth/me")
if printf '%s' "$me" | grep -q "$EMAIL"; then pass "authenticated /me"; else note "/me did not return the user"; fi

anon=$(curl -s -o /dev/null -w '%{http_code}' "${BASE}/api/v1/auth/me")
if [ "$anon" = "401" ]; then pass "anonymous /me is 401"; else note "anonymous /me returned $anon"; fi

wrong=$(curl -s -o /dev/null -w '%{http_code}' -X POST "${BASE}/api/v1/auth/login" \
  -H "$ORIGIN" -H 'content-type: application/json' \
  -d "{\"email\":\"${EMAIL}\",\"password\":\"definitely-not-it\"}")
unknown=$(curl -s -o /dev/null -w '%{http_code}' -X POST "${BASE}/api/v1/auth/login" \
  -H "$ORIGIN" -H 'content-type: application/json' \
  -d '{"email":"nobody-at-all@example.com","password":"definitely-not-it"}')
if [ "$wrong" = "401" ] && [ "$unknown" = "401" ]; then
  pass "login does not reveal whether an account exists"
else
  note "login enumeration: wrong=$wrong unknown=$unknown"
fi

csrf=$(curl -s -o /dev/null -w '%{http_code}' -b "$JAR" -X PUT \
  "${BASE}/api/v1/topics/the-machine/progress" \
  -H 'Origin: https://evil.example.com' -H 'content-type: application/json' \
  -d '{"status":"completed"}')
if [ "$csrf" = "403" ]; then pass "cross-origin write is rejected"; else note "cross-origin write returned $csrf"; fi

attempt=$(api -X POST "${BASE}/api/v1/topics/the-machine/quiz/attempts")
attempt_id=$(printf '%s' "$attempt" | python -c "import json,sys;print(json.load(sys.stdin).get('attempt_id',''))" 2>/dev/null || echo "")
if [ -n "$attempt_id" ]; then pass "quiz attempt started"; else note "could not start a quiz attempt"; fi

if [ -n "$attempt_id" ]; then
  graded=$(api -X POST "${BASE}/api/v1/quiz/attempts/${attempt_id}/submit" \
    -H 'content-type: application/json' \
    -d '{"answers":{"q1":["b"]},"score":100,"passed":true}')
  verdict=$(printf '%s' "$graded" | python -c "
import json,sys
d = json.load(sys.stdin)
print('ok' if d.get('score') == 0.0 and d.get('passed') is False else f\"score={d.get('score')} passed={d.get('passed')}\")
" 2>/dev/null || echo "unparseable")
  if [ "$verdict" = "ok" ]; then
    pass "grading ignores a client-claimed score"
  else
    note "client-claimed score was honoured ($verdict)"
  fi
fi

scenario="troubleshooting.slow-server"
locked=$(api_code "${BASE}/api/v1/topics/the-machine/troubleshooting/${scenario}/solution")
if [ "$locked" = "423" ]; then pass "solution is locked without a hypothesis"; else note "solution returned $locked, expected 423"; fi

lazy=$(api_code -X POST "${BASE}/api/v1/topics/the-machine/troubleshooting/${scenario}/hypothesis" \
  -H 'content-type: application/json' -d '{"body":"memory"}')
if [ "$lazy" = "400" ]; then pass "a token hypothesis is refused"; else note "token hypothesis returned $lazy"; fi

real=$(api_code -X POST "${BASE}/api/v1/topics/the-machine/troubleshooting/${scenario}/hypothesis" \
  -H 'content-type: application/json' \
  -d '{"body":"Memory-bound. si and so are sustained non-zero and 4GB of swap is in use."}')
if [ "$real" = "201" ]; then pass "a real hypothesis is accepted"; else note "hypothesis returned $real"; fi

unlocked=$(api "${BASE}/api/v1/topics/the-machine/troubleshooting/${scenario}/solution")
if printf '%s' "$unlocked" | grep -q "root_cause"; then
  pass "solution unlocks after a hypothesis"
else
  note "solution did not unlock"
fi

marked=$(api_code -X PUT "${BASE}/api/v1/topics/the-machine/progress" \
  -H 'content-type: application/json' -d '{"status":"completed"}')
if [ "$marked" = "200" ]; then pass "progress recorded"; else note "progress returned $marked"; fi

# Parsed rather than grepped: JSON whitespace is not part of the contract.
dash=$(api "${BASE}/api/v1/dashboard")
completed=$(printf '%s' "$dash"   | python -c "import json,sys;print(json.load(sys.stdin)['totals']['topics_completed'])" 2>/dev/null   || echo "?")
if [ "$completed" = "1" ]; then
  pass "dashboard reflects completion"
else
  note "dashboard shows topics_completed=$completed, expected 1"
fi

# --- search ------------------------------------------------------------------

hits=$(api "${BASE}/api/v1/search?q=zombie"   | python -c "import json,sys; print(json.load(sys.stdin)['total'])" 2>/dev/null || echo 0)
if [ "${hits:-0}" -gt 0 ]; then pass "search returns hits ($hits for 'zombie')"; else note "search returned $hits hits for 'zombie'"; fi

# A typo must still find the topic, or the trigram index is not doing its job.
fuzzy=$(api "${BASE}/api/v1/search?q=capabilties"   | python -c "import json,sys; print(json.load(sys.stdin)['total'])" 2>/dev/null || echo 0)
if [ "${fuzzy:-0}" -gt 0 ]; then pass "search survives a misspelling ($fuzzy hits)"; else note "misspelled query returned nothing"; fi

check_status "/api/v1/search?q=a" 422 "search rejects a one-character query"
check_status "/search?q=zombie" 200 "search page renders"

# The gate that matters. This phrase exists only in a troubleshooting root
# cause, which the API refuses to serve until a hypothesis is submitted —
# finding it through search would route around that entirely.
#
# Chosen to have no public analogue. The previous probe ("the only writable
# mount is at") began matching lessons about writable mounts once more content
# was written — a false positive in the check rather than a leak, and a reminder
# that a probe built from ordinary words decays as the corpus grows.
leak=$(api "${BASE}/api/v1/search?q=%22scratch%20files%20never%20generate%20enough%20page%20cache%22"   | python -c "import json,sys; print(json.load(sys.stdin)['total'])" 2>/dev/null || echo "?")
if [ "$leak" = "0" ]; then pass "search does not surface a gated root cause"; else note "search returned $leak hits for gated text"; fi

# ---------------------------------------------------------------- authoring
#
# The authoring endpoints read the content tree and can trigger a re-ingest, so
# they are administrator-only. This account is a learner — the first account on
# a fresh install becomes the admin and that is not this one — so every route
# must refuse it.
#
# Worth checking here rather than only in unit tests: `require_admin` existed
# for a long time and was enforced on no endpoint, so this asserts the gate is
# real through the edge, with a real session cookie.
# Anonymous first: no session at all is 401, not 403. The two statuses mean
# different things and the endpoint should distinguish them.
check_status "/api/v1/authoring/inventory" 401 "authoring inventory is 401 without a session"

# Then with this learner's real session cookie, which must be 403.
# `check_status` deliberately sends no cookie, so these use `api_code`.
for route in inventory lint; do
  code=$(api_code "${BASE}/api/v1/authoring/${route}")
  if [ "$code" = "403" ]; then
    pass "authoring ${route} refuses a non-admin"
  else
    note "authoring ${route} returned $code for a learner"
  fi
done

ingest_code=$(api_code -X POST "${BASE}/api/v1/authoring/ingest")
if [ "$ingest_code" = "403" ]; then
  pass "authoring ingest refuses a non-admin"
else
  note "authoring ingest returned $ingest_code for a learner"
fi

# The page itself must not leak the inventory to someone who cannot use it.
if curl -s -b "$JAR" "${BASE}/authoring" | grep -q "Administrator access required"; then
  pass "authoring page tells a non-admin why, without listing content"
else
  note "authoring page did not show the expected refusal"
fi


echo
if [ "$fail" -ne 0 ]; then
  echo "Smoke test FAILED" >&2
  exit 1
fi
echo "Smoke test passed."

#!/usr/bin/env bash
#
# Verifies the lab plane against a real container runtime.
#
# Separate from `task smoke` on purpose: the rest of the stack must be testable
# without a container runtime, and the broker's own tests run against a fake
# provisioner precisely so they do not need one. This script is the part that
# genuinely requires Docker, so it is opt-in.

set -euo pipefail

BASE="${BASE:-http://localhost:8080}"
fail=0
note() { printf '  \033[31mFAIL\033[0m  %s\n' "$1"; fail=1; }
pass() { printf '  \033[32m ok \033[0m  %s\n' "$1"; }

echo "Lab plane verification against ${BASE}"

if ! docker compose --profile labs ps lab-broker 2>/dev/null | grep -q lab-broker; then
  echo "  lab-broker is not running. Start it with: task labs:up"
  exit 1
fi

ready=$(curl -s --max-time 10 "${BASE}/labs/health/ready" || echo '{}')
runtime=$(printf '%s' "$ready" \
  | python -c "import json,sys;d=json.load(sys.stdin);print(d.get('runtime','?'))" 2>/dev/null || echo "?")
state=$(printf '%s' "$ready" \
  | python -c "import json,sys;d=json.load(sys.stdin);print(d.get('status','?'))" 2>/dev/null || echo "?")

if [ "$state" = "ready" ]; then pass "broker reports ready (runtime: $runtime)"; else note "broker is $state"; fi
if [ "$runtime" = "docker" ]; then
  pass "a real container runtime is in use"
else
  note "runtime is '$runtime' — set LAB_PROVISIONER=docker for a real verification"
fi

if docker image inspect groundwork/lab-foundations:1 >/dev/null 2>&1; then
  pass "lab-foundations image is built"
else
  note "lab-foundations image is missing — run: task labs:build"
fi

anon=$(curl -s -o /dev/null -w '%{http_code}' -X POST "${BASE}/labs/sessions" \
  -H 'content-type: application/json' \
  -d '{"topic_slug":"the-machine","lab_slug":"inspect-the-machine"}')
if [ "$anon" = "401" ]; then
  pass "anonymous lab creation is refused"
else
  note "anonymous lab creation returned $anon, expected 401"
fi

internal=$(curl -s -o /dev/null -w '%{http_code}' \
  "${BASE}/api/v1/internal/topics/the-machine/labs/inspect-the-machine/steps/s1/checks")
if [ "$internal" = "404" ]; then
  pass "verification specs are not reachable through the proxy"
else
  note "internal endpoint returned $internal — answer keys are exposed"
fi

echo
if [ "$fail" -ne 0 ]; then echo "Lab plane verification FAILED" >&2; exit 1; fi
echo "Lab plane verification passed."

#!/usr/bin/env bash
#
# Security invariants for the Compose topology.
#
# Cheap to run, and it prevents the single most likely way this architecture
# quietly degrades: someone adds `privileged: true` to make something work.
#
# The lab plane is exempt from the socket rule by design (see
# docs/architecture/06-lab-architecture.md) but only inside the `labs` profile.

set -euo pipefail

cd "$(dirname "$0")/.."

fail=0
note() { printf '  \033[31mFAIL\033[0m  %s\n' "$1"; fail=1; }
pass() { printf '  \033[32m ok \033[0m  %s\n' "$1"; }

echo "Compose security invariants"

# 1. No privileged containers anywhere.
if grep -rnE '^\s*privileged:\s*true' compose*.yaml >/dev/null 2>&1; then
  note "privileged: true found in a compose file"
  grep -rnE '^\s*privileged:\s*true' compose*.yaml
else
  pass "no privileged containers"
fi

# 2. No host networking.
if grep -rnE '^\s*network_mode:\s*"?host"?' compose*.yaml >/dev/null 2>&1; then
  note "network_mode: host found"
else
  pass "no host networking"
fi

# 3. The dev overrides never introduce a Docker socket. compose.yaml is allowed
#    to declare one on the labs profile, and check 7 verifies that precisely —
#    a plain grep here would flag the legitimate case.
if grep -n 'docker.sock' compose.override.yaml >/dev/null 2>&1; then
  note "docker.sock mounted by the development overrides"
else
  pass "development overrides mount no docker socket"
fi

# 4. Only the proxy publishes a port on the default profile.
published=$(docker compose config --format json 2>/dev/null \
  | python -c "
import json,sys
cfg = json.load(sys.stdin)
for name, svc in sorted(cfg.get('services', {}).items()):
    if svc.get('ports') and not svc.get('profiles'):
        print(name)
" || true)

if [ -z "$published" ]; then
  note "could not determine published ports"
elif [ "$published" = "proxy" ]; then
  pass "only 'proxy' publishes a host port"
else
  note "unexpected services publish host ports: $(echo "$published" | tr '\n' ' ')"
fi

# 5. Committed secret slots must hold recognisable placeholders, not real values.
#    Length is not the signal — a good placeholder is long and obvious. The
#    signal is whether the value announces itself as fake.
placeholder_re='change-me|dev-only|example|placeholder|not-a-real|replace-me'
bad_secrets=$(grep -E '^(SECRET_KEY|POSTGRES_PASSWORD)=' .env.example \
  | grep -vE "=(.*)($placeholder_re)" || true)

if [ -n "$bad_secrets" ]; then
  note ".env.example has a secret slot without a recognisable placeholder:"
  echo "$bad_secrets" | sed 's/=.*/=<redacted>/'
else
  pass ".env.example secret slots hold placeholders only"
fi

# 6. Service-to-service endpoints must stay blocked at the edge. Removing this
#    Caddy rule would put lab verification specs — the answer keys — one HTTP
#    request away from any browser.
if grep -q "handle /api/v1/internal/\*" infra/caddy/Caddyfile; then
  pass "internal API endpoints are blocked at the edge"
else
  note "the Caddy rule blocking /api/v1/internal/* is missing"
fi

# 7. The docker socket is confined to the labs profile, and mounted read-only.
if grep -q "docker.sock" compose.yaml; then
  if grep -q "docker.sock:/var/run/docker.sock:ro" compose.yaml; then
    pass "docker socket is mounted read-only"
  else
    note "docker socket is mounted writable"
  fi
  socket_service=$(python -c "
import json,subprocess
cfg = json.loads(subprocess.run(['docker','compose','--profile','labs','config','--format','json'],
                                capture_output=True, text=True).stdout or '{}')
for name, svc in (cfg.get('services') or {}).items():
    for volume in svc.get('volumes') or []:
        source = volume.get('source') if isinstance(volume, dict) else str(volume)
        if 'docker.sock' in str(source) and 'labs' not in (svc.get('profiles') or []):
            print(name)
" 2>/dev/null || true)
  if [ -z "$socket_service" ]; then
    pass "docker socket is confined to the labs profile"
  else
    note "docker socket is mounted outside the labs profile: $socket_service"
  fi
fi

# 8. The real .env must never be tracked by git.
if git ls-files --error-unmatch .env >/dev/null 2>&1; then
  note ".env is tracked by git"
else
  pass ".env is not tracked by git"
fi

echo
if [ "$fail" -ne 0 ]; then
  echo "Compose security invariants FAILED" >&2
  exit 1
fi
echo "All Compose security invariants hold."

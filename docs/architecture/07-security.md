# 7. Security Architecture

The platform teaches DevSecOps. Its own security posture is therefore a worked example
that appears verbatim in lessons — which sets the bar higher than "adequate for a personal
project".

## 7.1 Trust zones

```
┌────────────────────────────────────────────────────┐
│ UNTRUSTED   browser, learner input, lab containers │
├────────────────────────────────────────────────────┤
│ EDGE        Caddy — the only published port        │
├────────────────────────────────────────────────────┤
│ APP         web (no secrets) │ api │ worker │ broker│
├────────────────────────────────────────────────────┤
│ DATA        Postgres, Valkey — no host port at all  │
└────────────────────────────────────────────────────┘

Lab plane sits OUTSIDE all of these, reachable only through the broker.
```

## 7.2 Controls by layer

### Secrets
- No secret in git. `.env.example` holds names and dummy values only; `.env` is ignored.
- Compose reads from `.env`; the API reads from environment via Pydantic `Settings` — no
  config file parsing, no defaults that are valid in production.
- Generated-on-first-run secrets for local dev (`task bootstrap`) so no one is ever
  tempted to commit a working key.
- `gitleaks` in CI and as a pre-commit hook from Phase 0.
- Migration path: the `Settings` layer is the seam for Vault / SOPS / cloud secret managers.
  Introducing one becomes an IaC-track lab.

### Authentication and session
- Argon2id (memory-hard), per-user salt, tuned parameters recorded in code with a comment
  explaining the cost calibration.
- Access token: JWT, 15 min, held in memory (never `localStorage`).
- Refresh token: opaque 256-bit random, `httpOnly` + `Secure` + `SameSite=Lax`, stored
  **hashed** so database read access cannot mint a session. Rotation on use, with reuse
  detection → revoke the whole family.
- Login rate limiting per IP *and* per account, with a constant-time response so the
  endpoint cannot be used to enumerate accounts.
- Password reset tokens: single-use, 15-minute expiry, hashed at rest.

### Authorisation
- Every endpoint declares its required role/ownership explicitly. There is no "authenticated
  therefore allowed" default.
- Ownership checks happen in the service layer against the database, never from a JWT claim
  alone.
- Answer keys, `root_cause`, `model_answer` and rubric internals are excluded at the
  **response-model** level — the Pydantic schema for public responses has no field for them,
  so forgetting to strip them is impossible rather than merely discouraged.

### Input and output
- Pydantic validation on every request body, query and path parameter.
- SQLAlchemy parameterised queries only; raw SQL requires review and bound parameters.
- Learner-authored Markdown (notes) is sanitised and rendered with a restricted directive
  set — no raw HTML, no script.
- CSP with no `unsafe-inline`; nonce-based for the small amount of inline script Next.js
  needs. HSTS, `X-Content-Type-Options`, `Referrer-Policy`, frame-ancestors none.
- CORS: same-origin only through Caddy; no wildcard, ever.

### Containers and images
- Every service image: multi-stage build, non-root user, no shell in the final stage where
  practical, pinned base image **by digest**, `.dockerignore` that excludes `.git` and `.env`.
- Trivy scan in CI; build fails on HIGH/CRITICAL with a fixed version available.
- SBOM (Syft, SPDX) generated per image and attached as a build artifact.
- Image signing (cosign) from Phase 4 — again, because we teach it.

### Network
- Only the proxy publishes a port. `db` and `cache` have no `ports:` entry at all.
- Segmented Compose networks (§3.4), which become NetworkPolicies on Kubernetes.
- Lab networks are `internal: true`; egress requires an explicit per-lab allow-list.

### Lab plane
Covered in [06-lab-architecture.md](06-lab-architecture.md). The five non-negotiables,
restated because they are the ones that matter most:

1. Learner commands never run on the application host or in an application container.
2. Lab containers hold no credentials.
3. No egress and no route to the application network by default.
4. Hard TTL, enforced by a reaper.
5. Grading logic is not derivable from inside the lab.

### Data protection
- Passwords hashed, refresh tokens hashed, audit log append-only.
- Progress data is the only thing genuinely painful to lose → documented backup procedure
  and a *tested* restore in Phase 4 (an untested backup is not a backup, and that sentence
  is also a lesson in the SRE track).
- Learner notes treated as private; no cross-user reads anywhere in the API surface.

## 7.3 Security in the delivery pipeline

| Stage | Gate |
|---|---|
| pre-commit | gitleaks, ruff, biome, schema validation |
| PR | dependency audit (`uv`/`pnpm`), CodeQL or Semgrep SAST |
| build | Trivy image scan, SBOM generation |
| pre-deploy | Compose config lint, no-privileged assertion, no-published-db-port assertion |
| runtime | health checks, structured audit log, rate limits |

That "no-privileged assertion" is a small CI script that greps the Compose files and
Dockerfiles for `privileged: true`, `--privileged`, `network_mode: host`, and a mounted
`docker.sock` outside the `labs` profile, and fails the build. Cheap, and it prevents the
single most likely way this architecture would quietly degrade.

## 7.4 Known accepted risks

Stated plainly rather than buried:

| Risk | Why accepted | Condition that changes it |
|---|---|---|
| Lab broker reaches a container runtime socket | Unavoidable for local single-host labs; mitigated by rootless socket, opt-in profile, narrow API | Any multi-user or public deployment → dedicated remote lab host, mandatory |
| T2 containers share the host kernel | Adequate for a single trusted operator | Multi-tenant → T4 microVMs |
| Self-implemented auth | Small, well-understood surface; avoids a heavyweight IdP for one user | More than a handful of users, or any org requirement → swap in OIDC via the existing interface |
| Content is trusted (we author it) | We are the only authors | External contributors → sandbox the content pipeline, review directives |

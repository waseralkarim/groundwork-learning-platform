# 2. Technology Stack

Each decision below states: the choice, the alternatives, why it wins here, what it costs,
and what migrating away would involve.

Versions verified as current stable in **August 2026**. Pinned versions live in
`docs/development/VERSIONS.md` once Phase 0 lands.

---

## 2.1 Frontend — Next.js 16 (App Router) + React 19 + TypeScript

**Choice:** Next.js 16.3, App Router, React Server Components, TypeScript strict,
Tailwind CSS v4, shadcn/ui component primitives (Radix under the hood).

**Alternatives considered**

| Option | Why not |
|---|---|
| Astro | Superb for content sites, weaker for the app half (auth, progress, live terminal, quiz state). We are 50% app. |
| SvelteKit | Excellent DX, smaller ecosystem for the specific pieces we need (xterm.js integration, Radix-equivalent primitives). |
| Vite + React SPA | We would rebuild routing, data loading, and SSR. Lesson pages must be server-rendered for reading performance and deep-linking. |
| Plain server-rendered Jinja from FastAPI | Simplest, but the terminal, quizzes and progress UI become jQuery-era work. Rejected. |

**Why it fits:** the platform is a content site *and* an application. RSC lets lesson pages
render on the server with near-zero client JS, while quizzes and the lab terminal are
opt-in client islands. `output: "standalone"` produces a small container image that lifts
to Kubernetes unchanged.

**Cost:** Next.js is a large, fast-moving framework. **Mitigation:** the web service is a
*rendering layer only*. Zero business logic, zero direct database access. Every piece of
data comes from the API over HTTP. If Next.js ever becomes a liability we replace the web
service and keep everything else.

---

## 2.2 Backend — Python 3.13 + FastAPI

**Choice:** FastAPI + Pydantic v2 + SQLAlchemy 2.x (async) + Alembic migrations.

**Alternatives considered**

| Option | Why not |
|---|---|
| NestJS / TypeScript | Real advantage: one language across the stack. Loses on operator familiarity — you write Python and Bash daily, not TypeScript. Maintainability by *you* outranks language uniformity. |
| Go | Best runtime characteristics and the most "DevOps-native" language. But 3–4× the code for CRUD, and the content-ingestion tooling wants Python's YAML/Markdown ecosystem. Reconsider for the lab-broker specifically (see §2.9). |
| Django + DRF | Batteries included, excellent admin. Heavier, sync-first, and the admin advantage disappears once content lives in git rather than the database. |

**Why it fits:** async-native (matters for the lab WebSocket proxy and long-poll progress),
auto-generated OpenAPI (the frontend's TypeScript types are *generated* from it, so
frontend/backend drift is a compile error), Pydantic gives us one validation layer shared
between HTTP requests and content-schema validation, and Python is the language you can
maintain and extend without friction.

---

## 2.3 Database — PostgreSQL 18

**Choice:** PostgreSQL 18 (`postgres:18-alpine`).

**Why 18 specifically:** the new asynchronous I/O subsystem (up to 3× faster reads),
multicolumn B-tree skip scan, `uuidv7()` built in (time-ordered UUIDs — better index
locality than v4, which matters for the high-write `user_progress` and `lab_sessions`
tables), and virtual generated columns.

**What we use it for beyond rows:**
- `JSONB` for content metadata that varies by content type — avoids a table per item type.
- Built-in full-text search (`tsvector` + `pg_trgm`) — **defers Elasticsearch entirely**
  through MVP and probably through v1.
- `ltree` (optional) for the content hierarchy path.

**Alternatives:** MySQL (weaker JSON, weaker FTS, no `ltree`), SQLite (fine for tests,
no concurrency story for labs/progress), MongoDB (our data is deeply relational — progress
joins to content joins to users; rejected on fit, not fashion).

---

## 2.4 Cache and job queue — Valkey 8

**Choice:** Valkey 8 (`valkey/valkey:8-alpine`), the BSD-licensed Redis fork now the
Linux Foundation default.

**Why not Redis:** licensing ambiguity since the 7.4 relicense; Valkey is a drop-in
replacement, actively developed, and cloud providers have standardised on it.

**Used for:** response caching for compiled Markdown, rate limiting, ephemeral lab session
state, and as the broker for background jobs.

**Background jobs — ARQ.** Async-native, ~1500 lines, Redis-backed, no separate result
backend. **Alternative:** Celery (far more capable, far more moving parts — beat, flower,
result backends). We do not have Celery-shaped problems. Migration path exists if we do.

Jobs we need: content re-ingestion on git change, lab session reaping (TTL expiry),
assessment scoring, achievement evaluation, search index refresh.

---

## 2.5 Search — Postgres FTS now, Meilisearch later

MVP uses Postgres `tsvector`. When the corpus outgrows it (typo tolerance, faceting,
ranked cross-type search), add **Meilisearch** behind a `search` Compose profile.

**Not OpenSearch/Elasticsearch for the platform's own search** — operationally heavy for a
learning platform. Note the irony: OpenSearch *is* on the curriculum, so we will run it
anyway inside labs. Running it as a lab subject and not as a production dependency is the
right split.

---

## 2.6 Reverse proxy — Caddy 2

Single ingress on `localhost:8080`. Routes `/` → web, `/api/*` → api, `/labs/*` → lab-broker.

**Why:** five lines of config, automatic HTTPS the moment this leaves localhost, HTTP/3.

**Alternative — Traefik v3:** more "DevOps-native" (label-based dynamic discovery, closer
to a Kubernetes Ingress mental model, and a better teaching artifact). Rejected for MVP
because per-session lab routing goes *through* the broker rather than to per-container
hostnames, which removes the main reason to need dynamic discovery. Revisit at Phase 4.

**Consequence worth stating:** only the proxy publishes a host port. Postgres, Valkey, the
API and the worker are unreachable from the host. This is deliberate — it is the same
"one ingress, private backends" shape we teach in the Kubernetes track.

---

## 2.7 Content format — Markdown + YAML, not MDX

This is the most consequential decision in the document, so it gets the most space.

**Choice:** prose in CommonMark/GFM Markdown with YAML frontmatter and a small set of
custom `:::` directives; structured items (quizzes, labs, exercises, assessments) in
separate schema-validated YAML files.

**Why not MDX** (the obvious default):

1. MDX is *code*. Content authoring becomes JavaScript authoring, and the content pipeline
   can only ever run in Node. Our ingestion, validation and linting live in Python.
2. MDX cannot be safely validated. A JSON Schema can tell me a quiz has exactly one correct
   answer. Nothing can tell me a JSX expression is well-formed content.
3. Quiz and lab data must be gradeable **server-side**. If the answer key is in an MDX
   component, the answer key is in the browser bundle.
4. Content-as-code blocks reuse: the same lab definition should be embeddable in three
   topics without duplicating a React tree.

**Also considered and rejected:** Contentlayer (project abandoned — do not adopt), a
headless CMS such as Strapi/Payload (moves content out of git, loses review workflow and
versioning, adds a service).

**The directive set** (deliberately small and closed):

```markdown
:::objective{id=OBJ-0.1.3}
Order the memory hierarchy by latency and explain why the ordering exists.
:::

:::terminal{title="Inspect your CPU"}
$ lscpu | head -20
:::

:::warning{scope=production}
`docker run --privileged` disables essentially every container boundary.
:::

:::diagram{src=./diagrams/memory-hierarchy.mmd}

:::quiz{ref=./quiz.yaml#q4}

:::lab{ref=./labs/01-inspect-the-machine.yaml}
```

Each directive maps to one React component in a shared renderer. Adding a directive is a
deliberate two-sided change (schema + component), which keeps the vocabulary from sprawling.

**Rendering:** `remark` + `remark-gfm` + `remark-directive` → `hast` → React, compiled at
ingest time into a cached AST stored in Postgres, so the request path does no Markdown
parsing.

---

## 2.8 Authentication — built-in now, OIDC-ready

**Shipped:** email + password. Argon2id (19 MiB, 2 passes — OWASP's second recommended
configuration). **Opaque session tokens** in an `httpOnly` `SameSite=Lax` cookie, stored as
SHA-256 digests in Postgres, with a 14-day sliding window under a 90-day absolute ceiling.
CSRF defence is `SameSite=Lax` plus an Origin check on every mutation.

> **Revised during implementation.** The original plan was a 15-minute JWT access token
> held in memory plus an opaque refresh token. "Held in memory" has no meaning when React
> Server Components fetch on the server, and every workaround ends with the JWT in a
> cookie — at which point it is a session identifier with extra steps and worse
> revocation. A JWT buys stateless verification, which matters when an auth service is
> far from many resource servers. Here the API and the database are one hop apart and
> what we want is instant revocation, which Postgres gives us and a JWT fights.
> Rate limiting is per-account *and* per-IP: per-IP alone lets a botnet spread an attack,
> per-account alone lets an attacker lock people out.

**Why not an identity provider on day one:** Keycloak/Authentik/Zitadel would add a JVM or
Go service, a realm to configure, and a second database, in exchange for features
(federation, SSO, MFA policy) that a single-digit-user platform does not need yet.

**But:** the auth module sits behind an `IdentityProvider` interface from the first commit.
Swapping in OIDC later is a provider implementation, not a refactor — and that swap becomes
a genuinely good advanced lab ("add SSO to a running platform without downtime").

**Never:** roll our own crypto, store passwords reversibly, or put role claims only in the
JWT without server-side verification for sensitive operations.

---

## 2.9 Lab execution — see [06-lab-architecture.md](06-lab-architecture.md)

Summary of the technology position:

- **Tier 2 labs** (single Linux container): the broker drives the container runtime.
  Written in **Python (FastAPI)** for consistency, with **Go** as a live option if the
  WebSocket multiplexing proves hot.
- **Tier 3 labs** (Docker/systemd/k3s *inside* the lab): **Sysbox runtime** rather than
  `--privileged` Docker-in-Docker. Sysbox gives nested containers and systemd inside an
  *unprivileged* container using user namespaces — it is the difference between "we handed
  the learner root on your host" and "we did not". Linux host required.
- **Tier 4** (hostile multi-tenant / public): **Firecracker microVMs or Kata Containers**.
  The 2026 industry consensus is unambiguous — a container is not a sandbox for untrusted
  code; a kernel escape is catastrophic, so untrusted workloads get their own kernel.
  Out of scope for a single-user local deployment, in scope for the interface design.

- **Browser terminal:** xterm.js in the frontend, `ttyd` inside the lab container, WebSocket
  proxied and authorised by the broker. The browser never talks to a lab container directly.

---

## 2.10 Observability of the platform itself

OpenTelemetry SDK (Python + Node) → OTel Collector → Prometheus (metrics), Loki (logs),
Tempo (traces), Grafana (dashboards). Structured JSON logs with trace correlation.

Behind a Compose **profile** so `docker compose up` stays a ~30-second, ~1GB experience and
`docker compose --profile observability up` gives the full stack. The dashboards and
alerting rules we write for ourselves become the worked examples in the Observability track.

---

## 2.11 Supporting choices

| Concern | Choice | Note |
|---|---|---|
| Task runner | `Taskfile.yml` (go-task) | Cross-platform; `make` on Windows is a trap |
| Python packaging | `uv` | Now the de facto standard; fast, lockfile-based |
| Node packaging | `pnpm` | Strict, disk-efficient, correct peer handling |
| Linting | `ruff` (Py), `biome` (TS) | Both replace 4–5 tools each |
| Migrations | Alembic | Autogenerate reviewed by hand, never blindly |
| Diagrams | Mermaid (in-repo `.mmd`) | Text = reviewable in PRs; SVG only where Mermaid can't |
| Mail (dev) | Mailpit | `tools` profile |
| Image scanning | Trivy + Syft SBOM | In CI from Phase 0 — we teach it, so we do it |
| E2E | Playwright | Runs against real Compose stack |

---

## 2.12 Explicitly deferred

Kept out of MVP on purpose, with the door left open:

GraphQL, a service mesh, Kafka/NATS, microservice decomposition beyond the four services,
Kubernetes as the *development* environment, a headless CMS, payments, multi-tenancy,
i18n, mobile apps, AI tutoring features.

Each of these is a plausible v2 conversation. None of them unblocks a single lesson today.

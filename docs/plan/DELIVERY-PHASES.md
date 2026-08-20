# Delivery Plan

## Two parallel streams

Application work and content work run in parallel and at different rhythms. Application
phases are punctuated; content production is continuous from Phase 1 onward.

```
Phase 0  ████                    walking skeleton
Phase 1  ░░░████                 content pipeline + first topic
Phase 2  ░░░░░░░████             accounts, progress, assessment
Phase 3  ░░░░░░░░░░░████         labs
Phase 4  ░░░░░░░░░░░░░░░████     observability, search, polish
Phase 5  ░░░░░░░░░░░░░░░░░░░████ advanced labs, projects, authoring

content   ░░░████████████████████████████████████████  continuous
```

Application phases exist to *unblock content*. Anything that does not unblock content
waits.

`task verify:cold-start` guards the one requirement that underlies all of them:
the project must still work from an empty clone. It runs the whole stack in an
isolated Compose project on empty volumes, and it is the only check a working
development machine cannot fake.

---

## Phase 0 — Walking skeleton ✅ **done**

**Goal:** `docker compose up` gives a running, tested, observable-enough stack that does
almost nothing — but every future piece has somewhere to go.

- Repository scaffolding per [03-system-architecture.md §3.5](../architecture/03-system-architecture.md#35-repository-structure)
- `compose.yaml` + `compose.override.yaml`: proxy, web, api, worker, db, cache, migrate
- FastAPI skeleton: settings, structured logging, `/health/{live,ready,startup}`, OpenAPI
- Next.js skeleton: layout, dark mode, typography scale, code block component
- Alembic wired, one trivial migration
- Taskfile: `up`, `down`, `logs`, `test`, `lint`, `migrate`, `shell`, `bootstrap`
- CI: lint, test, build, Trivy, compose-check, no-privileged assertion
- `.env.example`, `.gitignore`, `.dockerignore`, `docs/development/SETUP.md`

**Done when:** clone → `cp .env.example .env` → `docker compose up` → `localhost:8080`
shows a page whose data came from the API which came from Postgres; CI is green.

---

## Phase 1 — Content pipeline and the first topic ✅ **done**

**Goal:** curriculum can be authored, validated, ingested and read. This is where the
project becomes real.

- JSON Schemas for every content type
- Markdown parser: frontmatter, GFM, the closed directive set → AST
- Content linter (all rules in [04-content-model.md §4.3](../architecture/04-content-model.md#43-validation-pipeline))
- Ingest CLI: `task content:ingest`, idempotent, deterministic UUIDv5 keys
- Content tables + read API: paths, courses, modules, topics, lessons
- Frontend: roadmap view, course view, **lesson reader** (the page that matters most —
  typography, code blocks with copy, terminal blocks, callouts, Mermaid, sticky ToC,
  prev/next, breadcrumbs)
- Content tests including the **re-ingest safety test**
- `docs/content-authoring/GUIDE.md`
- **Topic A01.M01.T01 authored in full** (see [TOPIC-0.1-IMPLEMENTATION-PLAN.md](TOPIC-0.1-IMPLEMENTATION-PLAN.md))

**Done when:** the first topic is readable end to end and genuinely pleasant to read for
90 minutes, and adding a second topic requires zero code changes.

---

## Phase 2 — Accounts, progress, assessment ✅ **done** (notes and bookmarks deferred)

- Registration, login, refresh rotation, password reset, roles
- Progress tracking: mark complete, resume where you left off, per-course percentages
- Prerequisite gating with an explicit "why is this locked" explanation
- Quiz engine: server-side grading, attempts, per-objective feedback, review mode
- Exercises and written submissions
- Troubleshooting scenarios with progressive reveal
- Assessment engine + the competence model ([05-data-model.md §5.5](../architecture/05-data-model.md#55-the-competence-model-why-we-do-not-just-count-quizzes))
- Dashboard: current position, streak, weak objectives, next recommended topic
- Notes and bookmarks

**Done when:** a learner can complete a topic properly — read, practise, be tested, be
told what they got wrong and why, and be routed to the right next thing.

---

## Phase 3 — Labs (Tier 2) ✅ **done**

- `lab-broker` service, `DockerProvisioner`
- Session lifecycle: create, attach, TTL, reap, quotas
- xterm.js terminal, WebSocket proxied and authorised through the broker
- `labcheck` binary and the full check vocabulary
- Lab UI: split instructions/terminal, per-step verification, hints, reset
- `lab-foundations` and `lab-linux` base images, built and scanned in CI
- Lab metrics and the lab-plane dashboard

**Done when:** a learner clicks "Start lab", gets a shell in under 5 seconds, breaks
something, fixes it, and the platform verifies it — with the container gone 30 minutes
later whether or not they closed the tab.

---

## Phase 4 — Observability, search, polish ← **in progress**

- OTel instrumentation across all services; `observability` profile stack ✅ **done**
  — traces, metrics and logs over OTLP, inert unless the profile is running
- Dashboards and alert rules as code, with runbooks ✅ **done** — 4 dashboards,
  6 alerts, a runbook per alert, and `task obs:verify` to prove signals arrive
- Full-text search across all content types ✅ **done** — Postgres FTS, built at
  ingest from public columns only; Meilisearch stays deferred behind the
  `search` profile until the corpus needs it
- Achievements and skill assessments ✅ **done** — the competence model from
  §5.5 implemented: evidence weighted by how hard it is to fake, scored against
  what each objective offers, topic proficiency = the weakest objective
- Certificates for completed courses ✅ **done** — gated on that model, not on
  completion; publicly verifiable at /verify/<code>
- Backup and **tested restore** procedure ✅ **done** — `task db:backup`,
  `task db:verify-restore` (restores into a scratch database and asserts progress
  still resolves), `task db:restore` with a safety dump; runbook in
  docs/runbooks/restore.md. Gaps stated: no PITR, no off-machine copies.
- Accessibility pass, performance pass, mobile pass ✅ **done** —
  `task verify:a11y` asserts the structural rules against served HTML (one main
  landmark, one h1, heading order, named controls, zoomable viewport, skip
  link, compression). Keyboard and screen-reader passes remain manual and are
  not claimed.

---

## Phase 5 — Advanced labs, projects, authoring

- Sysbox provisioner and Tier 3 labs (Docker-in-lab, k3s-in-lab)
- Dedicated Linux lab host
- Network fault injection for troubleshooting scenarios
- Project workspaces with rubric-based self-review ✅ **done** — projects live
  in `content/projects/`, gated on the topics they combine; every rubric score
  requires evidence, and self-review scores deliberately feed nothing
- Capstone flow ✅ **done for A01** — a capstone is a project requiring every
  topic in its course, not a new mechanism. Deliberately no platform change:
  self-review must not gate a certificate, so a capstone unlocks nothing and
  proves nothing to the platform. Its value is to the learner
- Admin/authoring UI (preview, lint results, ingest status) — deliberately last, because
  git plus a text editor is a perfectly good authoring tool until it isn't

---

## MVP feature list

Phases 0–2. The smallest thing that is genuinely useful for learning:

- `docker compose up` local environment
- Content pipeline with schema validation and linting
- Learning roadmap with prerequisites
- Course / module / topic navigation
- High-quality lesson reader
- Authentication and accounts
- Progress tracking with resume
- Quizzes with server-side grading and explanations
- Exercises and troubleshooting scenarios
- Assessments with the competence model
- Dashboard
- Notes and bookmarks
- Content authoring via git

## Post-MVP feature list

Interactive Tier 2/3 labs · browser terminal · platform observability stack · full-text
search · achievements · certificates · project workspaces · capstone · admin authoring UI ·
spaced repetition · personalised pacing · community/discussion · multi-user · OIDC SSO ·
Kubernetes deployment of the platform itself · public hosting

---

## Definition of Done

A **topic** is complete only when all of the following are true. This list is enforced by
the content linter and CI, not by memory.

- [ ] Overview and "why it matters" written
- [ ] Prerequisites declared and the graph is still acyclic
- [ ] Learning objectives declared, measurable, level-tagged
- [ ] Core concepts explained from first principles
- [ ] Terminology defined before use; glossary updated
- [ ] Internals/mechanism explained (L3+)
- [ ] Worked examples with real command output
- [ ] At least one guided lab with verification
- [ ] At least one challenge exercise
- [ ] At least one troubleshooting scenario (where applicable)
- [ ] Common mistakes documented
- [ ] Best practices documented
- [ ] Security considerations documented
- [ ] Production considerations documented
- [ ] Interview questions across levels with model answers
- [ ] Quiz with explanations for every option
- [ ] Assessment covering every objective
- [ ] Every objective mapped to ≥1 assessable item
- [ ] Diagrams where a diagram helps
- [ ] Integrated into a learning path and reachable
- [ ] Renders correctly; no broken links
- [ ] All tests pass; `docker compose up` works
- [ ] Documentation updated

A **phase** is complete when its features are done, tested, documented, and the Compose
stack still starts clean from an empty volume.

---

## Working rhythm

When you say **"Build the next topic"**, the sequence is always:

1. Identify the next topic from the roadmap
2. State its place, prerequisites, and objectives
3. Design it fully (subtopics, labs, exercises, troubleshooting, quiz, assessment) —
   **and get agreement on the design before writing content**
4. Author the content
5. Lint, ingest, review in the UI
6. Add/extend tests
7. Update documentation and the roadmap
8. Identify the next topic

Step 3 is not skippable. Designing a topic badly and writing 4,000 words against that
design is the most expensive mistake available to us.

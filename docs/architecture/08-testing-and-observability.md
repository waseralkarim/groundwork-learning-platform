# 8. Testing and Observability

## 8.1 Testing strategy

Five layers, each answering a different question.

| Layer | Tool | Question it answers | Runs |
|---|---|---|---|
| **Content validation** | JSON Schema + custom linter (Python) | Is the curriculum well-formed and complete? | pre-commit, CI |
| **Unit** | pytest / vitest | Does this function do what it says? | pre-commit, CI |
| **Integration** | pytest + testcontainers (real Postgres 18) | Do the service, the ORM and the schema agree? | CI |
| **API contract** | schemathesis against the OpenAPI spec | Does the API honour its own contract? | CI |
| **End-to-end** | Playwright against a real `docker compose up` | Can a human actually complete a topic? | CI, nightly |

**Content validation is the highest-value test suite in this project.** It is the only
automated thing that can tell us the curriculum is actually finished, and it is what turns
the Definition of Done from a promise into a build gate.

### What must be tested

- **Every content file**, every ingest — schema, lint rules, prerequisite DAG, glossary
  coverage, objective/assessment cross-references, dead links.
- **Grading logic** — a quiz that mis-grades destroys trust in the platform. Property-based
  tests: no attempt can score above 100, an all-correct attempt always passes, answer keys
  never appear in any serialised public response (asserted by walking the OpenAPI schema).
- **Progress state machine** — `not_started → in_progress → completed` transitions,
  idempotent re-submission, prerequisite gating.
- **Content re-ingest safety** — the critical regression test: ingest, record progress,
  rename/reorder/retitle content, re-ingest, assert progress still resolves. This is the
  bug that would silently ruin the platform six months in.
- **Lab verification checks** — each check type tested against a fixture container.
- **Auth** — token rotation, reuse detection, revocation, rate limits, ownership boundaries.
- **Migrations** — forward and backward against a seeded database.
- **Rendering** — every directive type renders; snapshot tests on the AST, not on pixels.

### Deliberately not tested
Exact prose, visual pixel-diffs, third-party library internals, or anything that would make
content edits fail unrelated tests.

### CI pipeline (GitHub Actions)

```
on PR:
  lint            ruff, biome, tsc --noEmit, gitleaks
  content         schema + lint + linkcheck + DAG                    ← blocking
  test-api        pytest unit + integration (testcontainers)
  test-web        vitest
  build           docker buildx bake all images
  scan            trivy (fail HIGH/CRIT with fix), syft SBOM
  compose-check   compose config + no-privileged assertion
  e2e             compose up → playwright → compose down
on main:
  + publish images to local registry, tag by SHA
nightly:
  + full e2e, link check against external URLs, dependency audit
```

## 8.2 Observability of the platform

The platform instruments itself, and those signals become the examples in the Observability
track. Everything below runs under `docker compose --profile observability up`.

```
api / web / worker / broker
  └── OpenTelemetry SDK (traces, metrics, logs)
        └── OTel Collector
              ├── Prometheus  (metrics)
              ├── Loki        (logs)
              └── Tempo       (traces)
                    └── Grafana (dashboards, explore, alerting)
```

### Logs
Structured JSON from the first line of code. Every log carries `trace_id`, `span_id`,
`user_id` (when authenticated), `request_id`. No `print`, no unstructured strings — because
a lesson on log aggregation that quotes our own unparseable logs would be embarrassing.

### Metrics

RED for every HTTP endpoint (rate, errors, duration) plus domain metrics that actually
answer product questions:

| Metric | Why it exists |
|---|---|
| `lesson_render_duration_seconds` | The reading path must stay fast |
| `content_ingest_duration_seconds`, `content_ingest_errors_total` | Ingestion is the riskiest job |
| `quiz_attempts_total{result}` | Learning signal |
| `lab_sessions_active`, `lab_session_duration_seconds` | Capacity and cost |
| `lab_provision_duration_seconds` | Slow lab start is the #1 UX killer on these platforms |
| `lab_check_results_total{passed}` | Reveals labs whose instructions are unclear |
| `topic_completion_total` | Are learners finishing, or bailing at a specific topic? |

That last one is the most valuable metric in the system: a topic with high starts and low
completions is a content bug, and this is how we find it.

### Traces
Distributed tracing across browser → Caddy → web → api → Postgres, and broker → lab
provisioning. Trace-to-log correlation via `trace_id` in Grafana.

### Health endpoints
- `/health/live` — process is up. Never touches dependencies.
- `/health/ready` — database reachable, migrations at head, cache reachable.
- `/health/startup` — for slow first boot.

The liveness/readiness distinction is drilled into learners in the Kubernetes track; our
own endpoints are the reference implementation, including the classic mistake we avoid
(liveness probes that check dependencies, causing cascading restarts).

### Dashboards, shipped as code
`infra/observability/grafana/dashboards/*.json`, provisioned automatically:
1. Platform overview (RED, saturation)
2. Content pipeline
3. Learning funnel (starts vs completions per topic)
4. Lab plane (active sessions, provision latency, check pass rates)

### Alerting rules
A small, real set (Prometheus rules in git): API error rate, p99 latency, lab provisioning
failures, ingest failures, database connection saturation, disk. Each rule carries a
runbook link — and the runbooks become the SRE-track examples.

## 8.3 The reflexive benefit

Because the platform is instrumented, "here is a real Prometheus query against a real
service you have running locally, showing real data about your own learning" is possible.
That is a materially better teaching experience than a synthetic demo, and it is the
strongest argument for putting effort into the platform's own observability early.

# Development Setup

## Prerequisites

| Tool | Version used | Why |
|---|---|---|
| Docker Engine | 29.x | Everything runs in containers |
| Docker Compose | v5.x | `docker compose`, not `docker-compose` |
| Task | 3.x | Task runner — [taskfile.dev](https://taskfile.dev) (optional but assumed below) |
| git | any recent | |

Node and Python are **not** required on the host. Both services build and run in
containers, which is the point — a new machine needs Docker and nothing else.

## First run

```bash
git clone <this repo> groundwork
cd groundwork
task bootstrap     # creates .env with freshly generated secrets
task up            # builds, starts, waits for every service to be healthy
```

Then open <http://localhost:8080>. The curriculum is already there: a one-shot
`seed` service ingests `content/` after migrations, so a first run gives you a
usable platform rather than an empty one.

Without Task:

```bash
cp .env.example .env
# edit .env — set SECRET_KEY and POSTGRES_PASSWORD to real random values
docker compose up --build --wait -d
```

## Verifying it works

```bash
task smoke              # end-to-end checks through the proxy
task check:compose      # compose validity + security invariants
task test               # API tests + web typecheck
task lint               # ruff + biome
task verify:a11y        # structural accessibility and compression checks
task verify:cold-start  # does a fresh clone still work?
```

Every one of these runs in CI, which is the point of writing them as scripts
rather than as instructions. The `labs` job builds the lab image, starts the lab
plane and walks all twenty labs; the `e2e` job asserts a cold start produced a
usable platform, then runs smoke, accessibility and a restore.

`task verify:cold-start` is the one worth running before you claim anything
works. It brings the whole stack up in a **separate** Compose project with empty
volumes and its own port, then checks that a learner can reach real content —
because a development machine hides every cold-start failure behind migrations
that already ran and content that was ingested weeks ago. It does not touch the
stack you are working in, and tears itself down afterwards.

`task smoke` also asserts that Postgres is **not** reachable from the host. If
that check ever starts failing, the network topology has regressed.

## Everyday commands

| Command | Does |
|---|---|
| `task up` / `task down` | Start / stop (data preserved) |
| `task nuke` | Stop and delete the data volumes |
| `task ps` | Service status |
| `task logs -- api` | Tail one service |
| `task shell:api` | Shell into the API container |
| `task shell:db` | `psql` into the database |
| `task migrate` | Apply migrations |
| `task migrate:new -- "add users"` | Autogenerate a migration |
| `task fmt` | Format everything |

## How the topology works

Only `proxy` publishes a port (8080). Everything else is on private Compose
networks:

```
localhost:8080 → proxy ─┬→ /api/*  → api:8000  → db:5432, cache:6379
                        └→ /*      → web:3000  → api:8000
```

This is deliberately the same shape as an Ingress in front of ClusterIP Services.
`infra/caddy/Caddyfile` is quoted directly in the Kubernetes track.

## Hot reload

`compose.override.yaml` is applied automatically and bind-mounts source into both
services:

- **API** — `uvicorn --reload`, source mounted read-only at `/srv/app`
- **Web** — `next dev`, source mounted at `/srv/src`

The read-only API mount means tools that rewrite files (`ruff format`,
`ruff check --fix`) cannot write through the container. Run those against the
host checkout, or use `task fmt` which handles it.

## Migrations

Migrations run in a dedicated one-shot `migrate` service that must exit
successfully before `api` and `worker` start. They are never run from the API
process — running migrations from N replicas is a lesson we would rather teach
than experience.

```bash
task migrate:new -- "add users table"   # review the generated file by hand
task migrate                            # apply
task migrate:down                       # roll back one
```

Alembic autogenerate is a starting point, not an oracle. Every generated
migration gets read before it is committed.

## Troubleshooting

**`SECRET_KEY is required`** — you have no `.env`. Run `task bootstrap`.

**`db` container restarting** — if you are upgrading from an older checkout, the
`pgdata` volume may be in the pre-PostgreSQL-18 layout. `task nuke` and start
again, or see [VERSIONS.md](VERSIONS.md#postgresql-18-data-directory).

**`dependency failed to start`** — a service failed its healthcheck. Find which:

```bash
docker compose ps
docker compose logs <service>
```

**Port 8080 is taken** — set `PUBLIC_PORT=9090` in `.env`.

**Everything is confusing** — `task nuke && task up` rebuilds from nothing. The
stack is designed to be disposable; only the database volume holds anything you
would miss, and in development you would not miss it.

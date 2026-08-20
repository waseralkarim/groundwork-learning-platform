# Versions

Recorded because the curriculum quotes this repository's real configuration, and
version-sensitive instructions must be traceable to a version that was actually
verified. Last verified **15 August 2026**.

## Runtime

| Component | Version | Pinned in |
|---|---|---|
| PostgreSQL | 18 (`postgres:18-alpine`) | `compose.yaml` |
| Valkey | 8 (`valkey/valkey:8-alpine`) | `compose.yaml` |
| Caddy | 2.10 (`caddy:2.10-alpine`) | `compose.yaml` |
| Python | 3.13 (`python:3.13-slim`) | `services/api/Dockerfile` |
| Node | 24 (`node:24-alpine`) | `services/web/Dockerfile` |

## API dependencies

Resolved versions live in the built image; ranges are declared in
`services/api/pyproject.toml`.

| Package | Range |
|---|---|
| FastAPI | `>=0.115,<1.0` |
| SQLAlchemy | `>=2.0.36,<3.0` |
| Alembic | `>=1.14,<2.0` |
| Pydantic | `>=2.10,<3.0` |
| asyncpg | `>=0.30,<1.0` |
| arq | `>=0.26,<1.0` |
| structlog | `>=24.4,<26.0` |

## Web dependencies

Exact versions are locked in `services/web/pnpm-lock.yaml`.

| Package | Resolved |
|---|---|
| Next.js | 16.3.1 |
| React / React DOM | 19.2.8 |
| Tailwind CSS | 4.3.3 |
| TypeScript | 5.9.3 |
| Biome | 2.5.8 |
| pnpm | 10.11.0 |

---

## Version-sensitive notes

### PostgreSQL 18 data directory

**Changed in 18.** Earlier images expected the data volume at
`/var/lib/postgresql/data`. From 18 the recommended mount is one level up:

```yaml
volumes:
  - pgdata:/var/lib/postgresql        # 18+
  # - pgdata:/var/lib/postgresql/data # 17 and earlier
```

The image places data in a major-version-named subdirectory beneath the mount, so
`pg_upgrade --link` can run across a major version bump without crossing a mount
boundary. Mounting the old path against an 18 image produces:

```
Counter to that, there appears to be PostgreSQL data in:
  /var/lib/postgresql/data (unused mount/volume)
```

and the container restart-loops. Teaching note: this is a good, small example of
why "just bump the tag" is not an upgrade procedure — the B13 Databases and E31
Kubernetes Operations tracks both reference it.

### PostgreSQL 18 `uuidv7()`

`uuidv7()` is a built-in function from 18. On 17 and earlier it requires an
extension or application-side generation. `app/db/base.py` uses the built-in.

### Tailwind CSS v4

v4 has no `tailwind.config.js`. Configuration is CSS-native via `@theme`, and the
PostCSS plugin moved to a separate `@tailwindcss/postcss` package. Any v3-era
tutorial will be misleading.

### Next.js 16 App Router

`output: "standalone"` is what keeps the runtime image small — it emits a
self-contained `server.js` so the runtime stage needs no `node_modules` and no
package manager.

### ruff and the local `alembic/` directory

Having a directory named `alembic/` in the project root makes ruff's isort
classify the installed `alembic` package as first-party, producing an
unsatisfiable `I001`. Fixed with `known-third-party = ["alembic"]` in
`services/api/pyproject.toml` — worth knowing because the same trap catches any
project whose directory name collides with a dependency.

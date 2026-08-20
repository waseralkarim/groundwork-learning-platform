# ApiErrorRateHigh

> More than 5% of API requests are returning 5xx over a 5-minute window.

## What it means

The API is failing requests. Not slow — failing. At 5% roughly one learner in
twenty is seeing an error page or a broken screen.

## Urgency

**Page.** Sustained 5xx means the product is not working. If it climbs past 20%,
treat it as an outage rather than a degradation.

## Confirm the cause

Find which routes are failing:

```promql
topk(10,
  sum by (http_route, http_response_status_code) (
    rate(http_server_request_duration_seconds_count{http_response_status_code=~"5.."}[5m])
  )
)
```

One route means an application bug. Every route means a dependency: the
database, the cache, or the process itself.

Then read the logs for that window, filtered to errors:

```logql
{service_name="groundwork-api"} | severity_text = "ERROR"
```

Every line carries `trace_id`. Click through to the trace — it shows exactly
which span failed, and a database span that took 30 seconds and then errored is a
different problem from an application span that raised immediately.

Check the dependencies before assuming it is code:

```bash
docker compose ps                      # is anything restarting?
docker compose exec api python -m app.healthcheck   # readiness: db + cache
docker compose logs db --tail 50
```

## What to do

- **Database unreachable** — check `db` is healthy and not out of disk. Postgres
  refuses connections when its volume fills, and the error surfaces here first.
- **Connection pool exhausted** — errors cluster on the slowest routes and the
  traces show long waits before any SQL. A slow query is holding connections;
  find it in the trace and fix the query rather than raising the pool size.
- **A single route** — read the traceback in the logs. Roll back the last deploy
  if the timing lines up; the content ingest is the other thing that changes
  behaviour without a code change.
- **Nothing obvious** — capture a trace id and the exact window before
  restarting anything. A restart destroys the evidence and usually only defers
  the incident.

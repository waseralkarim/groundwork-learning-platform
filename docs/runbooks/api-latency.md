# ApiLatencyHigh

> p99 request duration above 1.5s for 10 minutes.

## What it means

The reading path is the product. A learner moving through a topic hits the API
on every screen, and at p99 above 1.5s the page transitions feel broken even
though nothing is erroring.

## Urgency

**Ticket, not a page** — unless it is climbing, in which case it usually becomes
`ApiErrorRateHigh` within the hour as connections back up.

## Confirm the cause

Which routes:

```promql
topk(10,
  histogram_quantile(0.95,
    sum by (le, http_route) (rate(http_server_request_duration_seconds_bucket[5m]))
  )
)
```

Then open a slow trace in Tempo for that route and read the span list. There are
only three shapes and they have different fixes:

- **Many short SELECT spans** — an N+1 query. Look for a missing
  `selectinload()` on the relationship the route serialises.
- **One long SELECT span** — a query that has outgrown its index. `EXPLAIN
  ANALYZE` it against a copy of the data.
- **A long gap with no spans** — the process is not waiting on the database. It
  is either CPU-bound in Python or blocked on something not instrumented.

## What to do

- N+1: add the eager load, and add a test that asserts the query count.
- Slow query: index it, or narrow what the endpoint returns.
- Unexplained gap: check whether the container is CPU-throttled
  (`docker stats`), then look for synchronous work on the event loop.
- If the ingest ran recently, the search index rebuild is the heaviest thing in
  the system. Check `content_ingest_duration_seconds` for overlap.

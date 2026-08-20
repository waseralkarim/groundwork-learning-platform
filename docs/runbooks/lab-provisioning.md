# LabProvisioningSlow / LabProvisioningFailing

> p95 lab start above 8 seconds, or more than 10% of starts failing.

## What it means

A learner clicked "Start lab" and waited, or got an error. Slow lab start is the
single most reliable way to lose someone on a platform like this — and it
degrades gradually, so nobody notices until it is bad.

## Urgency

**Failures: page.** The labs are the reason the platform exists.
**Slow: ticket**, unless it is trending upward.

## Confirm the cause

```promql
histogram_quantile(0.95, sum by (le, lab) (rate(lab_provision_duration_seconds_bucket[10m])))
sum by (lab, outcome) (rate(lab_sessions_total[10m]))
```

If one lab is slow and the rest are fine, it is that lab's image. If everything
is slow, it is the runtime or the host.

```bash
docker compose logs lab-broker | grep -E "lab_provision_failed|lab_runtime"
bash scripts/verify-labs.sh          # can the broker reach the runtime at all?
df -h                                # disk is the usual culprit
docker system df                     # how much of it is images and volumes
```

## What to do

- **Socket permission denied** — the broker runs as UID 10002 and needs to be in
  the socket's group. Check `DOCKER_SOCKET_GID` against
  `docker compose exec lab-broker ls -ln /var/run/docker.sock`. This is the
  failure mode after a host or Docker Desktop upgrade.
- **Image not present** — the first start of a lab pulls or builds its image, and
  that is not an 8-second operation. Pre-build with `task labs:build`; a cold
  image is why the first learner of the day gets the bad experience.
- **Disk full** — the runtime cannot create a container layer. Reclaim with
  `docker image prune` *after* checking what would be deleted. Lab volumes are
  ephemeral; learner data is in Postgres and is not affected.
- **Host under load** — many concurrent sessions. Check the quota in the broker
  settings, and remember every session is a container with a CPU and memory cap.

## What not to do

Do not raise the session TTL to "give labs more time to start". The TTL governs
how long a lab lives, not how long it takes to appear, and raising it makes a
capacity problem worse.

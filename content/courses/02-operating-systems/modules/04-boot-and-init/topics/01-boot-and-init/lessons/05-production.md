---
topic: topic.boot-and-init
section: production
title: The same model, twice
order: 5
mode: explain
---

:::objective{id=OBJ-A02.5.7}
Trace a systemd unit's dependency and readiness model onto its Kubernetes
equivalent.
:::

Kubernetes did not invent its startup model. It rebuilt systemd's, with
different names, and inherited the same failure modes — which is useful, because
it means the lessons transfer in both directions.

| systemd | Kubernetes | What both are for |
|---|---|---|
| `After=` | `initContainers` | Ordering: do not start until that has finished |
| `Requires=` | (no direct equivalent) | Whether to pull a dependency in at all |
| `Type=notify` + `sd_notify` | `readinessProbe` | The service declaring it is genuinely ready |
| `Restart=on-failure` | `restartPolicy` | Whether to retry |
| `StartLimitBurst` | `CrashLoopBackOff` | Stop retrying something that keeps failing |
| Each unit is a cgroup | Each container is a cgroup | Accounting, limits, and killing the whole tree |
| `journalctl -u x` | `kubectl logs` | Per-unit log retrieval |
| `journalctl -b -1` | `kubectl logs --previous` | The log of the run that failed |
| `WatchdogSec=` | `livenessProbe` | Kill it if it stops responding |

The two most useful rows are the readiness one and the previous-log one, because
those are the two people most often reach for late.

## Started versus ready, in both worlds

The mistake has the same shape everywhere. A dependency is expressed against
*launch* rather than against *readiness*, and the result is a race that passes
on a fast machine.

```ini
# systemd: ordering against a launch
[Unit]
After=postgres.service        # postgres was exec'd. Not that it accepts connections
```

```yaml
# Kubernetes: the same mistake
initContainers:
  - name: wait-for-db
    image: busybox
    command: ["sh", "-c", "sleep 10"]   # hope ten seconds is enough
```

Both fixes are the same idea: make the dependency report its own readiness, and
wait for that report.

```ini
Type=notify                 # the service calls sd_notify when it can work
```

```yaml
readinessProbe:
  httpGet: { path: /readyz, port: 8080 }
```

A readiness endpoint that returns 200 as soon as the HTTP server is listening is
the same lie as `Type=simple`. It should check the things the service needs to
do its job — the database connection, the cache, the leader election — and stay
red until they are true.

:::warning{scope=production}
Do not put a dependency's health inside your own liveness probe. Readiness says
"do not send me traffic"; liveness says "kill me". A liveness probe that fails
when the database is slow restarts every replica of your service during a
database incident, turning a degradation into an outage. The equivalent mistake
in systemd is `BindsTo=` on a dependency that flaps.
:::

## Why the retry stops

Both systems stop retrying, and both are right to. A service that crashes
instantly and is restarted instantly is a busy loop that consumes a core and
fills a disk with logs.

```text
systemd:     Start request repeated too quickly. Failed with 'start-limit-hit'.
Kubernetes:  Back-off restarting failed container — 10s, 20s, 40s … capped at 5m
```

The operational consequence differs, and it catches people:

- **systemd stops permanently.** Fix the problem and nothing happens; the
  service stays failed until `systemctl reset-failed`.
- **Kubernetes keeps trying**, just increasingly slowly. Fix the problem and it
  recovers on the next attempt — which may be five minutes away, so "it is still
  broken" is often "it has not tried yet".

:::predict{question="A container's application is PID 1. Why does `docker stop` take ten seconds and then kill it?"}
Because PID 1 is exempt from default signal actions, and your application never
installed a handler.

`docker stop` sends `SIGTERM` and waits. For an ordinary process, a `SIGTERM`
with no handler means terminate — the kernel's default action. For PID 1, the
kernel does not apply default actions at all: a signal with no *installed*
handler is discarded. So the application carries on, the ten-second grace period
expires, and `SIGKILL` arrives, which nothing can ignore.

The costs are real: no graceful shutdown, in-flight requests dropped, buffers
unflushed, connections not drained — and ten seconds added to every deploy, on
every pod.

Two fixes, and they are not alternatives. Handle `SIGTERM` in the application,
which is correct and is what you want anyway. And run a real init —
`docker run --init`, or tini as the entrypoint — which forwards signals to your
process *and* reaps the orphans that PID 1 inherits and your application is not
collecting.

In Kubernetes the same thing appears as pods that always take their full
`terminationGracePeriodSeconds` to delete. If every pod takes exactly thirty
seconds, nothing is handling SIGTERM.
:::

## Making a boot faster, honestly

```bash
systemd-analyze                 # where the time went, by stage
systemd-analyze critical-chain  # the path that determined the total
```

Read `critical-chain`, not `blame`. Most units start in parallel and their
duration costs nothing; only the dependency chain that finished last determines
the total. Speeding up something that was not on it changes the total by zero.

Two things that genuinely help, in order:

- **Remove the dependency, not the duration.** A unit ordered
  `After=network-online.target` that does not actually need the network can
  often drop the line entirely and start immediately.
- **`systemctl disable` what is not used.** The fastest unit is one that does
  not run.

For containers the equivalent is the image: a smaller image pulls faster, and
pull time dominates start-up far more often than anything inside the container
does.

## The five things worth remembering

1. The initramfs exists because the driver for the root filesystem lives on the
   root filesystem.
2. `Requires=` and `After=` are orthogonal, and almost every real dependency
   needs both.
3. "Started" is not "ready" unless the unit type says so — `Type=notify`, or a
   readiness probe.
4. Start rate limiting can stop a service being retried, and in systemd it stops
   permanently.
5. `journalctl -b -1` and `kubectl logs --previous` answer the question the
   current log cannot.

:::checkpoint
1. What is the Kubernetes equivalent of `Type=notify`, and what is it for?
2. Why should a liveness probe not check a downstream dependency?
3. What is different about how systemd and Kubernetes give up on a failing
   service?
4. Why does a container whose app is PID 1 take the full grace period to stop?
:::

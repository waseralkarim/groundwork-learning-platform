---
topic: topic.boot-and-init
section: internals
title: What systemd actually promises
order: 3
mode: explain
---

:::objective{id=OBJ-A02.5.4}
Distinguish requirement dependencies from ordering dependencies, and predict the
start order a set of units produces.
:::

## Two questions that read as one in English

:::diagram{src=../diagrams/requires-vs-after.mmd caption="Whether, and when. Specifying one does not imply the other"}

**Requirement** — *whether* another unit is pulled in, and what happens if it
fails:

| Directive | Meaning |
|---|---|
| `Requires=` | Start it too. If it fails to start, we fail |
| `Wants=` | Start it too. If it fails, carry on anyway |
| `BindsTo=` | Like `Requires=`, and if it later *stops*, we stop |
| `Requisite=` | It must already be running. Do not start it; fail if it is not |
| `Conflicts=` | Starting us stops it |

**Ordering** — *when* we may start:

| Directive | Meaning |
|---|---|
| `After=` | Do not start until that unit has finished starting |
| `Before=` | The same edge written from the other end |

They are orthogonal, and this is the single most common misunderstanding in
unit files. `Requires=postgres.service` with no `After=` starts both at the same
instant. `After=postgres.service` with no `Requires=` orders you after postgres
*if something else happens to start it*, and does nothing at all otherwise.

Almost every real dependency wants both lines:

```ini
[Unit]
Requires=postgres.service
After=postgres.service
```

The failure mode of getting it wrong is the worst kind: it is a race, so it
works on a developer's fast laptop and fails on a loaded production node, and
the error is a connection refused that points at the wrong service.

:::warning
`Wants=` is the better default for most dependencies, and `Requires=` is
stronger than people expect: if the required unit fails, *your* unit is stopped
too. A monitoring agent that `Requires=` the application will take the
application down with it when the agent's config is wrong.
:::

## Targets replaced runlevels

A target is a unit that starts nothing itself and exists as a synchronisation
point:

```bash
systemctl get-default                       # graphical.target, multi-user.target
systemctl list-dependencies multi-user.target
systemctl isolate rescue.target             # the old "runlevel 1"
```

`network-online.target` is worth singling out because it is so widely
misunderstood. It is not automatic — something must pull it in — and "online"
means whatever the network management service reports, which for a machine with
several interfaces may not be the one your service needs. The correct incantation
is both lines, and even then it is a hint rather than a guarantee:

```ini
Wants=network-online.target
After=network-online.target
```

:::objective{id=OBJ-A02.5.5}
Distinguish the unit types, and say when a unit counts as started rather than
ready.
:::

## Started is not ready

:::diagram{src=../diagrams/unit-readiness.mmd caption="Only one of these types knows the difference between launched and ready"}

```ini
[Service]
Type=simple      # started as soon as exec() succeeds
Type=exec        # started once exec succeeded and the binary did not fail instantly
Type=forking     # started when the parent exits; PIDFile= names the real process
Type=oneshot     # started when the process exits; RemainAfterExit=yes keeps it active
Type=notify      # ready when the service says so, via sd_notify
```

With `Type=simple` — the default — systemd considers the unit started the moment
`exec()` returns. Not when the port is bound, not when the database connection
pool is warm. So `After=` on a `Type=simple` unit gives you ordering against a
*launch*, not against readiness, and the race you were trying to eliminate is
still there in miniature.

`Type=notify` is the only type that closes it. The service calls
`sd_notify(0, "READY=1")` when it is genuinely able to work, and units ordered
after it wait for that message rather than for `exec()`.

`Type=oneshot` with `RemainAfterExit=yes` is the shape for a migration: units
ordered after it wait for it to *complete*, and it stays "active" afterwards so
the dependency remains satisfied.

:::objective{id=OBJ-A02.5.6}
Explain how restart policy and start rate limiting decide whether a failing
service is retried at all.
:::

## Restart, and the limit that overrides it

```ini
[Service]
Restart=on-failure          # no, always, on-success, on-failure, on-abnormal, on-watchdog
RestartSec=5

[Unit]
StartLimitIntervalSec=10
StartLimitBurst=5
```

The trap is that these two mechanisms disagree, and the limit wins.
`Restart=always` says "restart it, whatever happens". `StartLimitBurst=5` in
`StartLimitIntervalSec=10` says "more than five starts in ten seconds means stop
trying". A service that crashes instantly hits the limit in well under a second,
and systemd gives up:

```text
Failed with result 'start-limit-hit'.
Start request repeated too quickly.
```

The important consequence for diagnosis: **at that point the service is no
longer being retried.** If you fix the underlying problem, nothing happens — the
service stays failed until someone runs `systemctl reset-failed`. Time spent
watching for it to recover is time wasted, and the journal line saying so is
easy to scroll past.

Raising `RestartSec` is usually the better fix than raising the burst: a service
that takes five seconds between attempts cannot hit a five-in-ten-seconds limit
at all.

## Every unit is a cgroup

```bash
systemd-cgls                          # the unit tree, as cgroups
systemctl status nginx                # shows the cgroup and its processes
systemctl set-property nginx.service MemoryMax=512M
```

systemd puts each unit in its own cgroup, which is how it can account for a
service's resources, apply limits declaratively, and — the operationally
important part — kill *everything* a service started rather than just the
process it launched. A daemon that forks away from its parent cannot escape,
because membership is by cgroup rather than by process tree.

:::callback
From **cgroups**: the effective limit is the tightest on the path from the root,
and `systemd-cgtop` shows live usage per cgroup. Those cgroups are these units —
`system.slice/nginx.service` is a directory, and `MemoryMax=` in a unit file is
a write to `memory.max` inside it.
:::

## The one-sentence version

`Requires=` and `After=` answer different questions and neither implies the
other; `Type=simple` reports "started" long before "ready"; and start rate
limiting can stop a service being retried at all, however permissive its
restart policy.

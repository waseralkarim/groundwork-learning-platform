# 6. Lab Architecture

This is the hardest part of the platform and the part most likely to be built badly. The
requirement is explicit: learners will be encouraged to break things, and some will try to
break *us*.

## 6.1 Threat model

**Assume the learner is a competent, motivated attacker with a root shell inside the lab.**
Not because you are one, but because a design that only holds against a cooperative user is
not a design.

| Threat | Consequence if unmitigated |
|---|---|
| Container escape → host root | Total compromise |
| Reaching the application network | Database read, other learners' data |
| Reaching the host's Docker socket | Trivially becomes host root |
| Egress to the internet | Our host becomes an attack proxy / crypto miner |
| Resource exhaustion (fork bomb, disk fill, OOM) | Denial of service for the platform |
| Persistence across sessions | Long-lived foothold |
| Exfiltrating lab answer keys / verification logic | Cheating; minor, but design for it |

**Non-negotiables that follow:**

1. Learner-supplied commands never execute on the application host or in any application
   container. Ever.
2. Lab containers hold no credentials to anything.
3. Lab networks are `internal: true` by default — no egress, no route to `app`/`data`.
4. Every session has a hard TTL and is destroyed by a reaper, not by the learner.
5. The answer key and the grading logic are not derivable from inside the lab.

## 6.2 Isolation tiers

We do not build the hardest tier first. Each tier is independently useful and ships in a
different phase.

| Tier | Environment | Isolation | Ships |
|---|---|---|---|
| **T1** | Learner's own machine | None — it's their box | Phase 1 |
| **T2** | Single ephemeral Linux container | Hardened OCI container | Phase 3 |
| **T3** | Nested Docker / systemd / k3s | **Sysbox** (user-namespaced, unprivileged) | Phase 5 |
| **T4** | Hostile multi-tenant / public | **Firecracker microVM** or **Kata Containers** | Not scoped |

### T1 — Bring your own machine

Instructions plus a downloadable `verify.sh` the learner runs locally; it emits a signed
result blob they paste back (or POSTs with their session token). Zero infrastructure,
available immediately, and honestly the *correct* mode for several topics — you should
install Docker on your own machine at least once.

### T2 — Ephemeral hardened container (the workhorse)

Covers Linux, shell, networking tools, Git, Python, databases, Prometheus/Grafana clients
— the majority of the curriculum.

Container hardening, applied to every session:

```yaml
# conceptual — the broker constructs this, it is never a user-editable compose file
read_only: true
tmpfs: [/tmp, /run, /home/learner]        # writable, noexec where possible, size-capped
cap_drop: [ALL]
cap_add: []                               # networking labs add NET_ADMIN, and only those
security_opt:
  - no-new-privileges:true
  - seccomp=infra/seccomp/lab-default.json
  - apparmor=devopspath-lab
user: "10001:10001"                       # never root unless the lab requires it
userns_mode: "host"                       # with dockerd in user-namespace remapping mode
pids_limit: 256
mem_limit: 512m
memswap_limit: 512m
cpus: 0.5
ulimits: { nofile: 1024, nproc: 256 }
storage_opt: { size: 2g }
networks: [labnet-<session>]              # internal: true
dns: [<broker-provided stub>]
```

Plus: no host bind mounts of any kind, no Docker socket, image built from a pinned digest,
and the image itself scanned in CI.

Some labs genuinely need root inside the container (package management, `iptables`). Those
run with root **inside a user namespace**, so UID 0 in the lab maps to an unprivileged UID
on the host — this is the entire point of user-namespace remapping and it is why we enable
it on the lab host rather than granting real root.

### T3 — Nested container / Kubernetes labs

The Docker and Kubernetes tracks require running Docker, systemd and k3s *inside* the lab.

**Rejected: `--privileged` Docker-in-Docker.** `--privileged` disables essentially every
container boundary; it is equivalent to handing out host root. It is also, unfortunately,
the most common way this is implemented.

**Chosen: Sysbox runtime.** Sysbox uses user namespaces, procfs/sysfs virtualisation and
ID-mapped mounts to run Docker, systemd and Kubernetes inside an *unprivileged* container.
The learner gets a full `dockerd` and a real `k3s`; the host does not get a new root user.

**Constraint you need to know about now:** Sysbox is a Linux-host technology. On Windows
with Docker Desktop the practical options are (a) run T3 labs inside a Linux VM — including
the WSL2 VM, which may work with configuration, (b) stand up a small Linux box (a VM, a
spare machine, or the k3s clusters you already run) as a dedicated lab host and point the
broker at it remotely, or (c) fall back to T1 for those specific labs. The broker's
provisioner interface makes the remote-lab-host option a configuration change, not a
rewrite. **Recommendation: plan for a dedicated Linux lab host by Phase 5.**

### T4 — microVMs

Only needed if this platform is ever exposed beyond you. The 2026 industry position is
settled: for genuinely untrusted multi-tenant code, give each workload its own kernel —
Firecracker or Kata. We design the interface for it and do not build it.

## 6.3 The lab-broker

```mermaid
sequenceDiagram
    participant B as Browser
    participant P as Caddy
    participant K as lab-broker
    participant A as api
    participant C as lab container

    B->>P: POST /labs/lab.linux.permissions/sessions
    P->>K: (forwards, with user JWT)
    K->>A: verify user + entitlement + prerequisites met
    A-->>K: ok, user_id, quota profile
    K->>K: enforce quota (max 1 active, N/day)
    K->>C: create network, create container, start
    K->>C: inject labcheck binary + step manifest
    K-->>B: { sessionId, wsUrl, expiresAt, ttlSeconds }
    B->>P: WS /labs/{sessionId}/terminal  (session token)
    P->>K: upgrade
    K->>C: attach to ttyd
    Note over B,C: learner works; broker relays bytes only

    B->>K: POST /labs/{sessionId}/steps/s2/check
    K->>C: exec labcheck --step s2
    C-->>K: { passed: true, detail }
    K->>A: record lab_check_result
    K-->>B: result + next hint

    Note over K: TTL expires or learner ends
    K->>C: kill + remove container + remove network
    K->>A: finalise lab_session
```

**Broker responsibilities:** authorisation, quota, provisioning, TTL reaping, terminal
relay, check execution, result reporting.

**Broker non-responsibilities:** it never interprets learner input, never renders content,
never executes author-supplied shell on the host.

**Provisioner interface** — the one seam that matters:

```python
class Provisioner(Protocol):
    async def create(self, spec: LabSpec, session: SessionId) -> LabHandle: ...
    async def attach(self, handle: LabHandle) -> TerminalStream: ...
    async def exec_check(self, handle: LabHandle, check: Check) -> CheckResult: ...
    async def destroy(self, handle: LabHandle) -> None: ...
```

Implementations: `DockerProvisioner` (T2), `SysboxProvisioner` (T3),
`K8sProvisioner` (T2/T3 on a cluster), `FirecrackerProvisioner` (T4). Only the first is in
scope for Phase 3.

## 6.4 The honest disclosure about local development

For T2 labs on a single-machine Compose deployment, the broker needs to talk to a container
runtime. That means either mounting the Docker socket into the broker, or running a
rootless dockerd/Podman socket dedicated to labs.

**Mounting the host Docker socket into a network-reachable service is a privilege
escalation path.** We reduce it, but we do not pretend it away:

- Prefer a **rootless Podman or rootless dockerd socket dedicated to labs**, not the host's
  primary Docker socket. This is the default we will configure.
- The broker exposes only a narrow, typed API; it never proxies arbitrary runtime calls.
- The broker runs as a non-root user with no shell in its image.
- The `labs` profile is **opt-in** (`docker compose --profile labs up`), so the risk does
  not exist in the default topology.
- Documented loudly in `docs/development/` and in the lesson that covers this exact
  pattern — because "why mounting the Docker socket is dangerous" is itself a curriculum
  item, and we get to use our own architecture as the worked example.

For any deployment beyond your own machine, the broker must target a **remote, dedicated
lab host** with no access to the application network. That is a configuration change.

## 6.5 Verification and grading

Checks are declarative and drawn from a closed vocabulary. Authors cannot supply arbitrary
host-side shell.

| Check type | Semantics |
|---|---|
| `file_exists` | Path present |
| `file_matches` | Contents match regex |
| `file_mode` | Permissions/ownership equal expected |
| `command_output` | Command stdout equals / matches / equals another command's output |
| `command_exit` | Exit code equals |
| `command_ran` | Shell history contains a matching command (for "use the right tool" steps) |
| `process_running` | Process matching pattern exists |
| `port_listening` | Port open in the lab netns |
| `http_check` | HTTP request from inside the lab returns expected status/body |
| `service_active` | systemd unit active (T3) |
| `k8s_resource` | Resource exists / field matches (T3) |

**Revised during implementation: there is no `labcheck` binary.** The broker interprets
checks itself and issues narrow `exec` calls. Building the binary made the cost clear —
another artifact to compile, ship, version and keep in step with a vocabulary that already
exists in the content schema, plus something sitting in the container for a motivated
learner to reverse. For seven checks a lab the round trips are irrelevant, and **no part of
the answer ever rests inside the container**.

Two rules hold for every check:

- **`argv` lists, never shell strings.** A `path` or `pattern` from a content file is
  passed as an argument, so it cannot become a command.
- **Re-derive rather than hard-code.** `equals_command` compares against a reference
  command run in the same container, so a lab works on any machine rather than asserting
  one operator's numbers.

## 6.6 Lab base images

Built in CI, pinned by digest, scanned by Trivy, one per track:

| Image | Contains |
|---|---|
| `lab-foundations` | coreutils, procps, gcc, strace, file, binutils |
| `lab-linux` | + systemd-less service simulation, users/groups seeded, log fixtures |
| `lab-networking` | iproute2, tcpdump, dig, nc, curl, socat, iptables (needs `NET_ADMIN`) |
| `lab-git` | git, pre-seeded repositories with deliberately messy histories |
| `lab-python` | python, uv, pytest |
| `lab-docker` | dockerd (T3 / Sysbox) |
| `lab-k8s` | k3s, kubectl, helm (T3 / Sysbox) |
| `lab-observability` | prometheus, grafana-agent, promtool, logcli |
| `lab-db` | postgres, psql, redis-cli, sample datasets |

Each image carries `/opt/lab/` scaffolding (seed scripts, fixtures) and nothing else it
does not need. Fixtures for "broken system" scenarios are baked in, so a troubleshooting
lab starts already broken, reproducibly.

## 6.7 Phasing

| Phase | Delivers |
|---|---|
| 1 | T1 labs + `verify.sh` generation from the same YAML spec |
| 3 | ✅ Broker, `DockerProvisioner`, `FakeProvisioner`, xterm.js terminal, broker-side checks, reaper, quotas, `lab-foundations` image |
| 5 | Sysbox provisioner, T3 Docker/K8s labs, dedicated lab host, network-fault injection |
| — | K8s/Firecracker provisioners: interface only, built if ever needed |

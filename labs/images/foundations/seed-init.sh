#!/bin/bash
# Seeds systemd unit files and journal excerpts for the A02 boot-and-init labs.
#
# systemd cannot be PID 1 in a tier-2 sandbox — the container's init is the
# learner's shell, which is itself one of the lessons. So the units are real
# files to read and reason about, and the journal excerpts are the output the
# corresponding commands produce on a machine where they are installed.
#
# Everything here is inert text under the session's own tmpfs.
set -euo pipefail

U=/tmp/units
mkdir -p "$U"

cat > "$U/postgres.service" <<'EOF'
[Unit]
Description=PostgreSQL database server
Wants=network-online.target
After=network-online.target

[Service]
Type=notify
User=postgres
ExecStart=/usr/lib/postgresql/17/bin/postgres -D /var/lib/postgresql/17/main
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

cat > "$U/migrate.service" <<'EOF'
[Unit]
Description=Apply database migrations
Requires=postgres.service
After=postgres.service
Before=api.service

[Service]
Type=oneshot
RemainAfterExit=yes
ExecStart=/usr/local/bin/migrate up
EOF

cat > "$U/api.service" <<'EOF'
[Unit]
Description=Orders API
Requires=postgres.service

[Service]
Type=simple
ExecStart=/usr/local/bin/orders-api
Restart=always
RestartSec=1

[Install]
WantedBy=multi-user.target
EOF

cat > "$U/cache-warmer.service" <<'EOF'
[Unit]
Description=Warm the orders cache
Wants=api.service
After=api.service

[Service]
Type=oneshot
ExecStart=/usr/local/bin/warm-cache
EOF

cat > "$U/metrics-agent.service" <<'EOF'
[Unit]
Description=Metrics agent
Requires=api.service
After=api.service
PartOf=api.service

[Service]
Type=simple
ExecStart=/usr/local/bin/metrics-agent
Restart=always

[Install]
WantedBy=multi-user.target
EOF

# ------------------------------------------------------------------ failures ---
F=/tmp/failures
mkdir -p "$F"/{alpha,bravo,charlie}

cat > "$F/alpha/unit.txt" <<'EOF'
# systemctl cat alpha.service
[Unit]
Description=Alpha ingest worker
After=network-online.target
Wants=network-online.target

[Service]
Type=notify
ExecStart=/usr/local/bin/alpha-worker
Restart=on-failure
EOF

cat > "$F/alpha/journal.txt" <<'EOF'
# journalctl -u alpha.service -b
Aug 16 04:02:11 node-7 systemd[1]: Starting Alpha ingest worker...
Aug 16 04:02:11 node-7 alpha-worker[41882]: listening on 0.0.0.0:9000
Aug 16 04:02:11 node-7 alpha-worker[41882]: ready to accept work
Aug 16 04:03:41 node-7 systemd[1]: alpha.service: start operation timed out. Terminating.
Aug 16 04:03:41 node-7 alpha-worker[41882]: received SIGTERM, shutting down
Aug 16 04:03:41 node-7 systemd[1]: alpha.service: Failed with result 'timeout'.
Aug 16 04:03:41 node-7 systemd[1]: Failed to start Alpha ingest worker.
EOF

cat > "$F/alpha/status.txt" <<'EOF'
# systemctl status alpha.service
● alpha.service - Alpha ingest worker
     Loaded: loaded (/etc/systemd/system/alpha.service; enabled)
     Active: failed (Result: timeout) since Sun 2026-08-16 04:03:41 UTC
   Main PID: 41882 (code=killed, signal=TERM)
EOF

cat > "$F/bravo/unit.txt" <<'EOF'
# systemctl cat bravo.service
[Unit]
Description=Bravo pricing service
Requires=postgres.service
After=postgres.service
StartLimitIntervalSec=10
StartLimitBurst=5

[Service]
Type=simple
ExecStart=/usr/local/bin/bravo --config /etc/bravo/config.yaml
Restart=always
RestartSec=0
EOF

cat > "$F/bravo/journal.txt" <<'EOF'
# journalctl -u bravo.service -b
Aug 16 04:11:02 node-7 bravo[52001]: FATAL: config /etc/bravo/config.yaml: no such file
Aug 16 04:11:02 node-7 systemd[1]: bravo.service: Main process exited, code=exited, status=1
Aug 16 04:11:02 node-7 systemd[1]: bravo.service: Scheduled restart job, restart counter is at 1.
Aug 16 04:11:02 node-7 bravo[52004]: FATAL: config /etc/bravo/config.yaml: no such file
Aug 16 04:11:02 node-7 systemd[1]: bravo.service: Scheduled restart job, restart counter is at 2.
Aug 16 04:11:02 node-7 bravo[52007]: FATAL: config /etc/bravo/config.yaml: no such file
Aug 16 04:11:02 node-7 systemd[1]: bravo.service: Scheduled restart job, restart counter is at 3.
Aug 16 04:11:02 node-7 bravo[52010]: FATAL: config /etc/bravo/config.yaml: no such file
Aug 16 04:11:02 node-7 systemd[1]: bravo.service: Scheduled restart job, restart counter is at 4.
Aug 16 04:11:02 node-7 bravo[52013]: FATAL: config /etc/bravo/config.yaml: no such file
Aug 16 04:11:02 node-7 systemd[1]: bravo.service: Start request repeated too quickly.
Aug 16 04:11:02 node-7 systemd[1]: bravo.service: Failed with result 'start-limit-hit'.
Aug 16 04:11:02 node-7 systemd[1]: Failed to start Bravo pricing service.
EOF

cat > "$F/bravo/status.txt" <<'EOF'
# systemctl status bravo.service   (taken at 09:40, five hours later)
● bravo.service - Bravo pricing service
     Loaded: loaded (/etc/systemd/system/bravo.service; enabled)
     Active: failed (Result: start-limit-hit) since Sun 2026-08-16 04:11:02 UTC
# note: the config file was restored by the platform team at 04:40.
EOF

cat > "$F/charlie/unit.txt" <<'EOF'
# systemctl cat charlie.service
[Unit]
Description=Charlie report generator
Requires=var-lib-reports.mount
After=var-lib-reports.mount

[Service]
Type=simple
ExecStart=/usr/local/bin/charlie
Restart=on-failure
EOF

cat > "$F/charlie/journal.txt" <<'EOF'
# journalctl -b -u charlie.service -u var-lib-reports.mount
Aug 16 04:02:03 node-7 systemd[1]: Mounting /var/lib/reports...
Aug 16 04:02:33 node-7 mount[1204]: mount.nfs: Connection timed out
Aug 16 04:02:33 node-7 systemd[1]: var-lib-reports.mount: Mount process exited, code=exited, status=32
Aug 16 04:02:33 node-7 systemd[1]: Failed to mount /var/lib/reports.
Aug 16 04:02:33 node-7 systemd[1]: Dependency failed for Charlie report generator.
Aug 16 04:02:33 node-7 systemd[1]: charlie.service: Job charlie.service/start failed with result 'dependency'.
EOF

cat > "$F/charlie/status.txt" <<'EOF'
# systemctl status charlie.service
● charlie.service - Charlie report generator
     Loaded: loaded (/etc/systemd/system/charlie.service; enabled)
     Active: inactive (dead)
# Main PID: never started. No process was executed.
EOF

echo "Seeded: five unit files in /tmp/units, three failing services in /tmp/failures."

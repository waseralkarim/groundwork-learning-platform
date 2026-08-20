#!/bin/bash
# Seeds the B06.3 filesystem hierarchy labs.
#
# The live system answers almost every question in this topic, and answers it
# better than a fixture could: /bin really is a symlink into /usr, /usr really
# is 306 MB of a 320 MB image, /usr/local and /opt really are owned by no
# package, and the lab container really does run with a read-only root, so
# "which directories must be writable" is a question a learner can settle by
# experiment rather than by being told.
#
# What is seeded is the material that needs a service we do not have:
#
#   - a real service's file layout, to classify into config, state, cache,
#     ephemeral and code
#   - the backup job that covers it, which is wrong in two ways
#   - a probe script that attempts the writes a service makes at startup, so
#     the read-only root produces a list rather than an anecdote
set -euo pipefail

export LC_ALL=C

F=/tmp/fhs
rm -rf "$F"; mkdir -p "$F"

cat > "$F/README.txt" <<'EOF'
Material for the hierarchy labs.

  service-tree.txt    every path one service touches, unsorted
  backup-manifest.txt what the backup job currently captures
  probe-writes.sh     attempts the writes a service makes at startup

Everything else in these labs reads the real system underneath you.
EOF

# ------------------------------------------------------------- service layout

cat > "$F/service-tree.txt" <<'EOF'
# Every path the "ledger" service touches, in the order somebody found them.
# Sizes are from a production host after fourteen months.
#
# Classify each one:
#
#   code        shipped by a package or an image; reinstall replaces it
#   config      decisions about THIS deployment; hand-edited or templated
#   state       cannot be regenerated; losing it loses information
#   cache       can be regenerated; losing it costs time, not data
#   ephemeral   valid only for this boot or this run
#
# Then answer: what must be in a volume, what must be backed up, and what
# must be writable for the process to start at all.

  /usr/bin/ledger                                    12M
  /usr/lib/ledger/plugins/                          104M
  /etc/ledger/ledger.conf                            4.0K
  /etc/ledger/conf.d/50-database.conf                4.0K
  /etc/ledger/tls/server.key                         4.0K
  /var/lib/ledger/ledger.db                           47G
  /var/lib/ledger/uploads/                            12G
  /var/lib/ledger/render-cache/                      210G
  /var/log/ledger/access.log                         890M
  /var/log/ledger/audit.log                          1.2G
  /var/cache/ledger/thumbnails/                       34G
  /run/ledger/ledger.pid                              4.0K
  /run/ledger/ledger.sock                                0
  /tmp/ledger-upload-*.part                          varies
  /usr/local/bin/ledger-migrate                      2.1M
  /opt/vendor-scanner/bin/scan                        68M
  /root/.ledger-admin-token                          4.0K
EOF

# ------------------------------------------------------------------- backup

cat > "$F/backup-manifest.txt" <<'EOF'
# The nightly backup, as configured. It has been green for fourteen months.

  INCLUDE  /etc
  INCLUDE  /var
  INCLUDE  /home

  EXCLUDE  /var/log
  EXCLUDE  /proc
  EXCLUDE  /sys

  # restore procedure, from the runbook:
  #   1. install the base OS
  #   2. apt-get install ledger
  #   3. restore the archive over /
  #   4. systemctl start ledger

# Two things are wrong with this and they fail in opposite directions.
# One makes the backup far larger and slower than it needs to be.
# The other means the restore procedure cannot work.
#
# Find both, using the service tree and the real system.
EOF

# ------------------------------------------------------------- write probe

cat > "$F/probe-writes.sh" <<'PROBE'
#!/bin/sh
# Attempts the writes a typical service makes while starting up, and reports
# which succeed. Nothing here is unusual — every one of these is a normal thing
# for a daemon to do on a normal machine.

printf '%-28s %-10s %s\n' PATH RESULT WHY

try() {
  target="$1"; label="$2"
  # `touch` rather than `: > "$target"`: a failed redirection on a special
  # builtin makes dash exit the whole script, and half these writes are
  # supposed to fail.
  if mkdir -p "$(dirname "$target")" 2>/dev/null && touch "$target" 2>/dev/null; then
    printf '%-28s %-10s %s\n' "$target" "ok" "$label"
    rm -f "$target" 2>/dev/null
  else
    printf '%-28s %-10s %s\n' "$target" "DENIED" "$label"
  fi
}

try /var/log/ledger/access.log   "open a log file"
try /var/lib/ledger/ledger.db    "create its database"
try /var/cache/ledger/warm       "warm a cache"
try /run/ledger/ledger.pid       "write a pid file"
try /etc/ledger/generated.conf   "write a generated config"
try /usr/local/bin/ledger-helper "drop a helper binary"
try /tmp/ledger-upload.part      "buffer an upload"
try "$HOME/.ledger/session"      "cache a session in HOME"
try /dev/shm/ledger-ipc          "shared-memory IPC segment"
PROBE
chmod 0755 "$F/probe-writes.sh"

cat > "$F/probe-notes.txt" <<'EOF'
# probe-writes.sh attempts nine writes. On an ordinary machine all nine succeed.
#
# Run it here and record which are denied.
#
# For each denial, work out WHICH GATE stopped it — there are two, and they are
# checked independently:
#
#   the mount   ro, noexec, nosuid on the filesystem itself
#   the mode    the permission bits and ownership on the directory
#
# One of the nine is denied by the mode while its mount is read-write, which is
# the case worth being able to tell apart. Another succeeds but would fail if
# the service tried to EXECUTE what it just wrote.
#
# Then answer the real question: if you had to make this service run under a
# read-only root, what is the shortest list of writable paths that works?
EOF

echo "Seeded: /tmp/fhs (a service tree, a backup manifest, a write probe)."

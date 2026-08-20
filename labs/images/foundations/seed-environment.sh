#!/bin/bash
# Seeds the B06.4 environment and shell-startup labs.
#
# Very little needs seeding here, and that is the point: a learner can create
# ~/.bashrc and ~/.profile in the tmpfs home, run bash four ways, and watch
# which files each mode reads. The experiment is better than any fixture
# because they built it.
#
# The image also supplies two findings for free. /etc/profile rewrites PATH and
# gives non-root users a PATH with no sbin in it, so `capsh` is not found in a
# login shell and is found in a script — a genuine "command not found" that
# depends only on how the shell was started. And /etc/environment exists, is
# empty, and is read by nobody, which is where a lot of misplaced configuration
# goes to be ignored.
#
# What is seeded is what one container cannot produce:
#
#   - captured environments from cron, systemd, CI and ssh, to compare
#   - a job that works when run by hand and fails when scheduled
#   - four routes a secret can take into a process, to evaluate
set -euo pipefail

export LC_ALL=C

E=/tmp/env
rm -rf "$E"; mkdir -p "$E"

cat > "$E/README.txt" <<'EOF'
Material for the environment labs.

  invocations.txt   the same command's environment, captured five ways
  nightly-report.sh a job that works by hand and fails on a schedule
  secret-routes.txt four ways a secret reaches a process

Everything about startup files you will build yourself — your home directory
is a tmpfs, so you can create dotfiles and watch which shells read them.
EOF

# --------------------------------------------------------- captured environs

cat > "$E/invocations.txt" <<'EOF'
# `env` output for the same account, captured five ways on a real host.
# Trimmed to the variables that differ.
#
# For each, work out: is it a login shell? is it interactive? and which
# startup files must therefore have run?

--- 1. ssh into the host, typed at the prompt -------------------------------
PATH=/usr/local/bin:/usr/bin:/bin:/usr/local/games:/usr/games
HOME=/home/deploy
SHELL=/bin/bash
TERM=xterm-256color
LANG=en_GB.UTF-8
PS1=\u@\h:\w\$
SSH_CONNECTION=10.2.0.14 51402 10.2.0.9 22

--- 2. ssh with a command: ssh host 'env' -----------------------------------
PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
HOME=/home/deploy
SHELL=/bin/bash
SSH_CONNECTION=10.2.0.14 51418 10.2.0.9 22

--- 3. from crontab -------------------------------------------------------
PATH=/usr/bin:/bin
HOME=/home/deploy
SHELL=/bin/sh
LOGNAME=deploy

--- 4. a systemd service ---------------------------------------------------
PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
HOME=/
LANG=C.UTF-8
INVOCATION_ID=6d9e1f4a2b7c4e8fa1d3
JOURNAL_STREAM=8:41234

--- 5. a CI runner step ----------------------------------------------------
PATH=/opt/hostedtoolcache/node/20.11.1/x64/bin:/usr/local/bin:/usr/bin:/bin
HOME=/home/runner
CI=true
RUNNER_TEMP=/home/runner/work/_temp

# Notes to check against the list above:
#
#   - two of the five have no TERM and no PS1. what does that tell you?
#   - one has HOME=/ . what breaks when a program expects a real home?
#   - the PATH in (1) is SHORTER than the PATH in (2), from the same account
#     on the same host. that is not a mistake.
#   - (3) has the shortest PATH of all, and it is the one nobody tests.
EOF

# ------------------------------------------------------------- failing job

cat > "$E/nightly-report.sh" <<'JOB'
#!/bin/bash
# Nightly reconciliation report.
# Works when the on-call engineer runs it. Fails on a schedule.

set -euo pipefail

OUT="${REPORT_DIR}/report-$(date +%F).txt"

# capability audit for the report header
capsh --print > "$OUT"

# summarise yesterday's ledger
awk '{ total += $2 } END { print "total:", total }' "${LEDGER_FILE}" >> "$OUT"

echo "wrote $OUT"
JOB
chmod 0755 "$E/nightly-report.sh"

cat > "$E/nightly-report.notes.txt" <<'EOF'
# nightly-report.sh works when its author runs it and fails on a schedule.
#
# On a bare machine it fails every way, because the author's account is not
# here. So the first job is to RECONSTRUCT the environment in which it works —
# that is where the fault actually lives.
#
# The script needs two things nobody declared: REPORT_DIR and LEDGER_FILE, and
# a PATH that can find `capsh`. On this machine try:
#
#   mkdir -p /tmp/reports
#   printf 'a 10\nb 20\nc 30\n' > /tmp/ledger.txt
#
# then put the author's settings where their dotfiles would have had them, and
# run the script five ways:
#
#   bash -lic  ...    login + interactive — a terminal
#   bash -lc   ...    login, not interactive — ssh with a command
#   bash -ic   ...    interactive, not login — a new terminal tab
#   bash -c    ...    neither — a script, a CI step
#   env -i PATH=/usr/bin:/bin bash ...        roughly what cron gives
#
# Which ones work depends entirely on WHICH FILE you put the settings in, and
# the dividing line moves when you move the file. That is the finding.
#
# There is also a second, independent fault about `capsh` that behaves
# BACKWARDS from what most people expect. Write down your predictions first.
EOF

# ----------------------------------------------------------- secret routes

cat > "$E/secret-routes.txt" <<'EOF'
# Four ways a database password reaches a process. Evaluate each against the
# five questions below, using the machine to check rather than guessing.

  A.  docker run -e DB_PASSWORD=hunter2 ...

  B.  docker run --env-file ./db.env ...

  C.  a file at /run/secrets/db_password, mode 0400, read by the app at start

  D.  the app fetches it from a secret manager at start, using a short-lived
      token mounted as a file

# For each, answer:
#
#   1. can another process running as the same user read it?
#   2. does it appear in `ps eww` output?
#   3. is it in /proc/PID/environ, and for how long?
#   4. does `docker inspect` show it to anyone who can reach the daemon?
#   5. is it inherited by every child process, including ones that
#      shell out to third-party tools?
#
# Then answer the question that decides it in practice:
#
#   6. if it leaks, what do you have to do, and can you tell that it leaked?
EOF

echo "Seeded: /tmp/env (captured invocations, a failing job, secret routes)."

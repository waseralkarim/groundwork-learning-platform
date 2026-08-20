#!/bin/bash
# Seeds the B08.4 find and xargs labs.
#
# find and xargs are both present, so most of this topic is one command to
# demonstrate. What needs seeding is a TREE with the right shapes:
#
#   - files at known ages, straddling the 24-hour boundaries, so the -mtime
#     truncation rule produces a visible off-by-one rather than a claim
#   - a large excluded subtree, so -prune versus filtering is measurable
#     rather than asserted
#   - an unreadable directory, so find's exit status has something to report
#   - filenames that are legal and hostile, reused from the B08.1 set
#
# The ages are set with `touch -d` at build time relative to now, so they are
# correct whenever the lab runs.
set -euo pipefail

export LC_ALL=C

F=/tmp/find
rm -rf "$F"; mkdir -p "$F"

cat > "$F/README.txt" <<'EOF'
Material for the find and xargs labs.

  archive/     files at known ages, straddling the 7-day boundary
  project/     a small source tree with a large node_modules to exclude
  hostile/     filenames that are legal and awkward
  cleanup.sh   a retention job with three faults

Ages in archive/ are set relative to when the seed ran, so they are always
correct. Check them with:  find archive -printf '%f %TY-%Tm-%Td\n'
EOF

# ------------------------------------------------------- files at known ages

A="$F/archive"
mkdir -p "$A"
for spec in "3 days ago:age-3d.log" \
            "6 days ago:age-6d.log" \
            "7 days ago:age-7d.log" \
            "7 days ago -2 hours:age-7d2h.log" \
            "8 days ago:age-8d.log" \
            "10 days ago:age-10d.log" \
            "30 days ago:age-30d.log"; do
  when=${spec%%:*}; name=${spec##*:}
  : > "$A/$name"
  touch -d "$when" "$A/$name"
done
: > "$A/current.log"

cat > "$F/age-task.txt" <<'EOF'
# archive/ contains files at known ages. Before running anything, predict which
# files each of these selects:
#
#     find archive -name '*.log' -mtime +7
#     find archive -name '*.log' -mtime 7
#     find archive -name '*.log' -mtime -7
#     find archive -name '*.log' -mtime +6
#
# One of them does NOT include age-7d.log, and that is the finding. Work out
# why before reading any documentation.
#
# Then answer the real question: a retention policy says "delete anything older
# than 7 days". Which predicate implements it, and what does the obvious choice
# actually do?

# ---------------------------------------------------------------------------
# Ages present:
#   current, 3d, 6d, 7d, 7d-and-2-hours, 8d, 10d, 30d
EOF

# ------------------------------------------------- a tree worth pruning

P="$F/project"
mkdir -p "$P/src" "$P/docs"
for i in 1 2 3; do : > "$P/src/module$i.log"; done
: > "$P/docs/notes.log"
for a in $(seq 1 60); do
  mkdir -p "$P/node_modules/pkg$a/lib/inner/deep"
  for b in $(seq 1 40); do : > "$P/node_modules/pkg$a/lib/inner/deep/m$b.js"; done
done
: > "$P/node_modules/stray.log"

# --------------------------------------------------------- hostile filenames

H="$F/hostile"
mkdir -p "$H"
: > "$H/plain.log"
: > "$H/a file.log"
: > "$H/it's.log"
: > "$H/-n"
: > "$H/--force"
: > "$H"/$'two\nlines.log'

# --------------------------------------------------------- the retention job

cat > "$F/cleanup.sh" <<'JOB'
#!/bin/bash
# Delete archived logs older than the retention period.
# Runs weekly from cron. Has never reported a failure.

DIR=${1:-/tmp/find/archive}
DAYS=${2:-7}

find "$DIR" -name '*.log' -mtime +$DAYS -exec rm {} \;

echo "cleanup complete"
JOB
chmod 0755 "$F/cleanup.sh"

cat > "$F/cleanup-notes.txt" <<'EOF'
# cleanup.sh has three faults and reports success for all of them.
#
#   1. It keeps a file it was asked to delete. Which one, and why?
#   2. If a subdirectory cannot be read, or an rm fails, the job still says
#      "cleanup complete" and exits 0. Two separate reasons for that.
#   3. It runs one process per file. On a directory with 50,000 logs that is
#      50,000 forks.
#
# Work out all three, then rewrite it. Copy the archive directory first —
# it deletes things.
EOF

echo "Seeded: /tmp/find (aged files, a prunable tree, hostile names, a retention job)."

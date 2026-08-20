#!/bin/bash
# Seeds the B08.1 expansion and quoting labs.
#
# Almost nothing needs seeding: the learner has bash, dash and a writable tmpfs,
# so every expansion rule in this topic is something they can make happen and
# watch. That is much better than a fixture, because the surprising results are
# ones they produced.
#
# What is seeded is what is awkward or unsafe to create by hand:
#
#   - a directory of filenames that are legal and hostile: a space, a newline,
#     a leading dash, a literal asterisk. Typing these correctly is itself a
#     quoting exercise, and getting them wrong silently produces the wrong test.
#   - `argc`, which prints exactly how many arguments it received and what each
#     one was. The single most useful teaching tool in this topic, because it
#     turns an argument about quoting into a number.
#   - a realistic log-archiving script with four separate quoting faults, to be
#     found and fixed rather than read about.
set -euo pipefail

export LC_ALL=C

S=/tmp/sh
rm -rf "$S"; mkdir -p "$S"

cat > "$S/README.txt" <<'EOF'
Material for the expansion and quoting labs.

  argc              prints the argument list a command really received
  files/            filenames that are legal, hostile, and entirely realistic
  predict.txt       lines to predict before running
  archive-logs.sh   a real script with four quoting faults

Everything else you will produce yourself. Your home and /tmp are tmpfs, so
create and destroy files freely.
EOF

# ------------------------------------------------------------------- argc

cat > "$S/argc" <<'ARGC'
#!/bin/bash
# Prints the argument list this command actually received.
printf 'argc = %d\n' "$#"
i=0
for a in "$@"; do
  i=$((i + 1))
  printf '  $%d = [%s]\n' "$i" "$a"
done
ARGC
chmod 0755 "$S/argc"

# --------------------------------------------------------- hostile filenames

D="$S/files"
mkdir -p "$D"
: > "$D/normal.log"
: > "$D/a file.log"                 # a space
: > "$D/-n"                         # looks like an option
: > "$D/--force"                    # looks like a long option
: > "$D/star*.log"                  # a literal asterisk in the name
: > "$D/tab"$'\t'"sep.log"          # a tab
: > "$D/two"$'\n'"lines.log"        # a newline. yes, this is legal.
: > "$D/space at end .log"

cat > "$S/files/README.txt" <<'EOF'
Every filename in this directory is legal on Linux. A filename may contain any
byte except NUL and /, which includes spaces, tabs, newlines and leading
hyphens.

Nothing here is contrived. Names with spaces arrive from uploads and from
Windows; names starting with a hyphen arrive from generated identifiers; names
containing a newline arrive from a bug somewhere upstream, and they are the
reason `find -print0` exists.

Work out which ones break a naive loop, and why.
EOF

# ----------------------------------------------------------------- predict

cat > "$S/predict.txt" <<'EOF'
# For each line, write down how many arguments `argc` will receive, and what
# each one is. Then run it. Do not run first.
#
# Assume:  f='a file.log'   e=''   g='*.log'   n=3
# and that you are in /tmp/sh/files

  1.  argc $f
  2.  argc "$f"
  3.  argc $e
  4.  argc "$e"
  5.  argc $g
  6.  argc "$g"
  7.  argc *.log
  8.  argc "*.log"
  9.  argc *.nomatch
 10.  argc {1..$n}
 11.  argc {1..3}
 12.  argc $(echo one two)
 13.  argc "$(echo one two)"
 14.  argc '$f'
 15.  argc "'$f'"

# Four of these surprise most people. Score yourself honestly before reading
# any explanation — the value of this exercise is entirely in the gap between
# what you predicted and what happened.
EOF

# ------------------------------------------------------- the buggy script

cat > "$S/archive-logs.sh" <<'JOB'
#!/bin/bash
# Archive application logs older than N days, then delete the originals.
# Runs nightly from cron. In production for two years.

LOGDIR=$1
DEST=$2
DAYS=$3

CUTOFF=$(date -d "-$DAYS days" +%s)

for f in $(ls $LOGDIR/*.log); do
  MTIME=$(stat -c %Y $f)
  if [ $MTIME -lt $CUTOFF ]; then
    tar czf $DEST/$(basename $f).tar.gz $f
    rm $f
  fi
done

echo done
JOB
chmod 0755 "$S/archive-logs.sh"

cat > "$S/archive-logs.notes.txt" <<'EOF'
# archive-logs.sh has four separate faults, all of them about expansion.
#
# It has worked for two years because every log file was named
# `app-2026-08-18.log` — no spaces, no surprises. Then a new service started
# writing logs whose names come from a customer-supplied identifier.
#
# Find all four. For each, say:
#
#   - which expansion stage causes it
#   - what input triggers it
#   - what the script does instead of what was intended
#
# One of the four is much worse than the other three, and it is not the one
# that produces an error message.
#
# Test against /tmp/sh/files, which contains the kind of names that arrived.
# Copy the directory first — the script deletes things.
EOF

echo "Seeded: /tmp/sh (argc, hostile filenames, prediction set, a buggy job)."

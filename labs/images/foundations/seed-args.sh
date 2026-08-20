#!/bin/bash
# Seeds the B08.7 arguments-and-options labs.
#
# What is seeded is what needs to be a real script:
#
#   - `argv`, which reports exactly what a script received. Every quoting
#     question in this topic is settled by running it.
#   - prune.sh, whose --dry-run enables deletion
#   - report.sh, whose option-parsing function works once
#   - backup.sh, a hand-rolled parser with three separate defects
set -euo pipefail

export LC_ALL=C

S=/tmp/args
rm -rf "$S"; mkdir -p "$S"

cat > "$S/README.txt" <<'EOF'
Material for the arguments-and-options labs.

  argv        report exactly what a script received, one line per argument
  prune.sh    -d deletes, -n is a dry run. --dry-run does something else.
  report.sh   parses its options in a function. Called twice, it stops working.
  backup.sh   a hand-rolled parser with three defects, two of them silent

Run them. Every claim in this topic is one command away from being checked.
EOF

# -------------------------------------------------------------------- argv

cat > "$S/argv" <<'ARGV'
#!/bin/bash
# Report exactly what this script received.
printf '  $0 = %s\n' "$0"
printf '  $# = %s\n' "$#"
if [ "$#" -eq 0 ]; then
  printf '  (no arguments)\n'
else
  i=1
  for a in "$@"; do
    printf '  $%-2s = [%s]\n' "$i" "$a"
    i=$((i + 1))
  done
fi
ARGV
chmod 0755 "$S/argv"

# --------------------------------------------------------------- prune.sh

cat > "$S/prune.sh" <<'PRUNE'
#!/bin/bash
# Remove old exports.
#
#   prune.sh [-d] [-n] DIR
#     -d   delete the files it finds
#     -n   dry run — report only
#
# The help text also advertises --dry-run, which was never implemented.
set -uo pipefail

delete=0
dry=0

while getopts ":dn" OPT; do
  case $OPT in
    d) delete=1 ;;
    n) dry=1 ;;
    \?) echo "prune: ignoring unknown option -$OPTARG" >&2 ;;
  esac
done
shift $((OPTIND - 1))

DIR=${1:-/tmp/args/exports}

echo "delete=$delete dry=$dry dir=$DIR"
for f in "$DIR"/*; do
  [ -e "$f" ] || continue
  if [ "$delete" -eq 1 ]; then
    rm -f "$f"
    echo "  removed $(basename "$f")"
  else
    echo "  would remove $(basename "$f")"
  fi
done
PRUNE
chmod 0755 "$S/prune.sh"

mkdir -p "$S/exports"
for n in 01 02 03 04; do
  echo "export $n" > "$S/exports/export-$n.csv"
done

# -------------------------------------------------------------- report.sh

cat > "$S/report.sh" <<'REPORT'
#!/bin/bash
# Produce a report for each named region.
# Works for the first region and ignores every flag after that.
set -uo pipefail

run_region() {
  local OPT verbose=0 format=text region=
  while getopts ":vf:" OPT; do
    case $OPT in
      v) verbose=1 ;;
      f) format=$OPTARG ;;
    esac
  done
  shift $((OPTIND - 1))
  region=${1:-unknown}
  echo "  region=$region verbose=$verbose format=$format"
}

run_region -v -f json us-east
run_region -v -f json eu-west
run_region -v -f json ap-south
REPORT
chmod 0755 "$S/report.sh"

# -------------------------------------------------------------- backup.sh

cat > "$S/backup.sh" <<'BAK'
#!/bin/bash
# Back up a directory. Hand-rolled option parsing.
#
#   backup.sh [--verbose] [--out FILE] DIR
set -uo pipefail

verbose=0
out=backup.tar

while [ $# -gt 0 ]; do
  case $1 in
    --verbose) verbose=1 ;;
    --out)     out=$2; shift ;;
    -*)        echo "backup: unknown option $1" >&2 ;;
    *)         break ;;
  esac
  shift
done

echo "verbose=$verbose out=$out dir=${1:-<none>} remaining=$#"
BAK
chmod 0755 "$S/backup.sh"

cat > "$S/notes.txt" <<'EOF'
# Three scripts, three questions.
#
# prune.sh
#   Run it with -n and a directory: a dry run, nothing removed. Now run it
#   with --dry-run, which the help text advertises. Count the files afterwards.
#   Then run it again with 2>/dev/null, as a cron job that keeps only stdout
#   would, and say what evidence is left.
#
# report.sh
#   Three regions, identical flags. Only the first is formatted as json.
#   Nothing fails and every region is reported. Which variable is to blame,
#   and why does the LAST line of output make it look like it worked?
#
# backup.sh
#   Three defects. One is loud. Find all three:
#     backup.sh --out                 (what does out become?)
#     backup.sh --out=file.tar /srv   (does --out=... work?)
#     backup.sh -- --verbose /srv     (what does -- do here?)
EOF

echo "Seeded: /tmp/args (argv, and three scripts with option-parsing defects)."

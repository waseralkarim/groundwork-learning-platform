#!/bin/bash
# Seeds the B08.9 testing-shell labs.
#
# What is seeded is a small script worth testing and the machinery to test it
# badly, so the learner can feel the difference:
#
#   - retention.sh, a real-ish script with four behaviours and two bugs
#   - manual-check.sh, the "test" most people actually write: run it and look
#   - a bats suite that passes while the script is broken
#   - deploy.sh, which shells out to kubectl, so it cannot be tested by running
set -euo pipefail

export LC_ALL=C

S=/tmp/bats
rm -rf "$S"; mkdir -p "$S"

cat > "$S/README.txt" <<'EOF'
Material for the testing-shell labs.

  retention.sh     decides which files to delete. Two bugs, neither obvious.
  manual-check.sh  how the script is "tested" today: run it and read the output
  first.bats       a bats suite that passes while retention.sh is broken
  deploy.sh        shells out to kubectl, so running it is not an option

Run manual-check.sh first. Then run the bats suite. Then work out what neither
of them is telling you.
EOF

# ------------------------------------------------------------- retention.sh

cat > "$S/retention.sh" <<'RET'
#!/bin/bash
# Decide which files in a directory are past their retention window.
# Prints one path per line. Prints nothing and exits 1 if the directory is
# missing, so a caller can tell "nothing to do" from "cannot do it".
set -uo pipefail

DIR=${1:?usage: retention.sh DIR [DAYS]}
DAYS=${2:-7}

if [ ! -d "$DIR" ]; then
  echo "retention: not a directory: $DIR" >&2
  exit 1
fi

# BUG 1: -mtime +N means "more than N whole days", so this keeps everything
# for DAYS+1. B08.4 measured exactly this.
find "$DIR" -maxdepth 1 -type f -mtime "+$DAYS" -print

# BUG 2: the exit status is find's, and find succeeds when it matches nothing.
# A caller cannot distinguish "nothing expired" from "the directory vanished
# between the check above and now".
RET
chmod 0755 "$S/retention.sh"

# --------------------------------------------------------- manual-check.sh

cat > "$S/manual-check.sh" <<'MAN'
#!/bin/bash
# How retention.sh is tested today: make some files, run it, read the output.
set -uo pipefail

WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT

touch -d '30 days ago' "$WORK/very-old.log"
touch -d '2 days ago'  "$WORK/recent.log"

echo "files:"
ls -1 "$WORK" | sed 's/^/  /'
echo
echo "retention.sh says these are expired:"
/tmp/bats/retention.sh "$WORK" | sed 's/^/  /'
echo
echo "looks right."
MAN
chmod 0755 "$S/manual-check.sh"

# ----------------------------------------------------------- the first suite

cat > "$S/first.bats" <<'BATS'
# The suite somebody wrote to "cover" retention.sh.
# It passes. The script has two bugs.

setup() {
  WORK="$BATS_TEST_TMPDIR/work"
  mkdir -p "$WORK"
  touch -d '30 days ago' "$WORK/very-old.log"
  touch -d '2 days ago'  "$WORK/recent.log"
}

@test "it lists an old file" {
  run /tmp/bats/retention.sh "$WORK"
  [ "$status" -eq 0 ]
  [[ "$output" == *"very-old.log"* ]]
}

@test "it does not list a recent file" {
  run /tmp/bats/retention.sh "$WORK"
  [[ "$output" != *"recent.log"* ]]
}

@test "it refuses a missing directory" {
  run /tmp/bats/retention.sh /nope
  [ "$status" -eq 1 ]
}
BATS

# ---------------------------------------------------------------- deploy.sh

cat > "$S/deploy.sh" <<'DEP'
#!/bin/bash
# Apply a manifest with kubectl, then confirm the rollout.
# Running this for real is not an option in a test.
set -euo pipefail

TARGET=${1:?usage: deploy.sh TARGET}
MANIFESTS=${MANIFESTS:-/tmp/bats/manifests}

[ -f "$MANIFESTS/$TARGET.yaml" ] || { echo "deploy: no manifest for $TARGET" >&2; exit 66; }

kubectl apply -f "$MANIFESTS/$TARGET.yaml"
kubectl rollout status "deployment/$TARGET" --timeout=60s

echo "deployed $TARGET"
DEP
chmod 0755 "$S/deploy.sh"

mkdir -p "$S/manifests"
for t in staging production; do
  printf 'apiVersion: apps/v1\nkind: Deployment\nmetadata:\n  name: %s\n' "$t" > "$S/manifests/$t.yaml"
done

cat > "$S/notes.txt" <<'EOF'
# Four questions.
#
# 1. Run manual-check.sh. It says "looks right". Is it?
#
# 2. Run `bats first.bats`. Three tests, three passes. retention.sh has two
#    bugs. Which one does each test fail to see, and why?
#
# 3. retention.sh takes a DAYS argument. How many of the three tests exercise
#    it? What does that tell you about what "3 passing tests" is worth?
#
# 4. deploy.sh calls kubectl twice. There is no cluster here. Write a test that
#    proves it calls kubectl with the right arguments, and one that proves it
#    fails when the rollout does.
EOF

echo "Seeded: /tmp/bats (a script with two bugs, and a suite that passes anyway)."

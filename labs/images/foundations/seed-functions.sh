#!/bin/bash
# Seeds the B08.6 functions-and-scope labs.
#
# Most of this topic is one-line bash invocations and the labs are better for
# having the learner run them. What is seeded is what needs to be a real script:
#
#   - `boundaries`, which runs the same assignment inside each construct and
#     reports whether it survived. Turns "does this fork?" into a table the
#     learner generates rather than reads.
#   - deploy.sh, whose helper reads a variable nobody passed it — because a
#     caller three frames up misspelled the name it meant to set
#   - healthcheck.sh, which has never failed, for two independent reasons
#   - backup.sh, whose counter is always zero
set -euo pipefail

export LC_ALL=C

S=/tmp/funcs
rm -rf "$S"; mkdir -p "$S"

cat > "$S/README.txt" <<'EOF'
Material for the functions-and-scope labs.

  boundaries      run an assignment inside each construct, report what survived
  deploy.sh       a helper reads a variable it was never passed
  healthcheck.sh  has never reported a failure, for two separate reasons
  backup.sh       counts the files it copied, and always reports zero

Everything else is a one-line bash invocation. Run them yourself — the point of
this topic is the gap between what a function looks like it does and what the
shell does with it.
EOF

# --------------------------------------------------------------- boundaries

cat > "$S/boundaries" <<'BOUND'
#!/bin/bash
# Does an assignment made inside a construct survive it?
#
# Each case sets `v` from `outer` to `inner` inside a different construct and
# reports what `v` is afterwards. Same assignment every time; only the
# surrounding construct changes.
printf '  %-46s %s\n' CONSTRUCT 'v AFTERWARDS'

run() {
  printf '  %-46s %s\n' "$1" "$2"
}

v=outer; { v=inner; };                       run '{ v=inner; }              group'        "$v"
v=outer; ( v=inner; );                       run '( v=inner; )              subshell'     "$v"
v=outer; x=$(v=inner; echo x);               run 'x=$(v=inner; ...)         cmd subst'    "$v"
v=outer; f(){ v=inner; }; f;                 run 'f(){ v=inner; }; f        function'     "$v"
v=outer; f(){ local v=inner; }; f;           run 'f(){ local v=inner; }; f  local'        "$v"
v=outer; echo x | { v=inner; };              run 'echo x | { v=inner; }     pipeline'     "$v"
v=outer; { v=inner; } < <(echo x);           run '{ v=inner; } < <(echo x)  proc subst'   "$v"
v=outer; for i in x; do v=inner; done;       run 'for ...; do v=inner; done loop'         "$v"
v=outer; while read -r _; do v=inner; done <<< x
                                             run 'while read; do v=inner    redirected'   "$v"
v=outer; echo x | while read -r _; do v=inner; done
                                             run 'echo x | while read ...   piped loop'   "$v"
BOUND
chmod 0755 "$S/boundaries"

# ------------------------------------------------------- the wrong variable

cat > "$S/deploy.sh" <<'DEP'
#!/bin/bash
# Deploy a release to a target environment.
# Reports the wrong environment, and no variable is ever undefined.
set -euo pipefail

run_step() {
  echo "  [$1] against ${target:-<unset>}"
}

deploy() {
  local targt=$1          # the whole bug is on this line
  run_step build
  run_step push
  run_step activate
}

target=staging            # a default, set once, at the top
deploy "${1:-production}"
DEP
chmod 0755 "$S/deploy.sh"

# ---------------------------------------------------- the check that passes

cat > "$S/healthcheck.sh" <<'HC'
#!/bin/bash
# Check that every service is up. Alerts if any is down.
# Has never alerted.
set -euo pipefail

SERVICES=${1:-/tmp/funcs/services.txt}

check_service() {
  local name=$1
  local port=$2
  if fake_probe "$name" "$port"; then
    echo "  $name ok"
  else
    echo "  $name DOWN"
  fi
}

failures=0
while read -r name port; do
  check_service "$name" "$port"
done < "$SERVICES"

echo "$failures services down"
exit "$failures"
HC
chmod 0755 "$S/healthcheck.sh"

cat > "$S/services.txt" <<'EOF'
api 8080
worker 9000
cache 6379
EOF

cat > "$S/fake_probe" <<'PROBE'
#!/bin/bash
# Stands in for a real probe. `worker` is down.
[ "$1" = worker ] && exit 1
exit 0
PROBE
chmod 0755 "$S/fake_probe"

# ------------------------------------------------- the counter that is zero

cat > "$S/backup.sh" <<'BAK'
#!/bin/bash
# Copy each source file to the archive and report how many were copied.
# Always reports zero.
set -euo pipefail

SRC=${1:-/tmp/funcs/src}
DEST=${2:-/tmp/funcs/archive}
mkdir -p "$DEST"

copied=0
find "$SRC" -type f -name '*.conf' | while read -r f; do
  cp "$f" "$DEST/"
  copied=$((copied + 1))
done

echo "copied $copied files"
BAK
chmod 0755 "$S/backup.sh"

mkdir -p "$S/src"
for n in app db cache proxy; do
  echo "# $n configuration" > "$S/src/$n.conf"
done

cat > "$S/notes.txt" <<'EOF'
# Three scripts, three questions.
#
# deploy.sh
#   Run it. It reports one environment; the argument says another; and a third
#   is set at the top of the file. Nothing is ever unset and set -u never
#   fires. Which one wins, and why is the bug invisible at the point it hurts?
#
# healthcheck.sh
#   `worker` is down. Run it (fake_probe must be on PATH — add /tmp/funcs) and
#   it exits 0 and reports "0 services down". There are TWO independent
#   reasons, and fixing either one alone still leaves it broken.
#
# backup.sh
#   Run it. It copies the files — check the archive — and reports zero. The
#   loop body runs. The increment runs. Where does the value go?
EOF

echo "Seeded: /tmp/funcs (boundaries, and three scripts that lie)."

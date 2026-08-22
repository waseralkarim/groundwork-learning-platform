---
topic: topic.testing-shell
section: commands
title: The forms worth knowing
order: 4
mode: do
---

## Running a suite

```bash
bats t.bats                    # one file
bats tests/                    # every .bats in a directory
bats -r tests/                 # recursively
bats --filter 'boundary' t.bats    # only tests whose name matches
bats --formatter tap t.bats        # explicit TAP
bats --print-output-on-failure t.bats
bats --version
```

The suite exits **non-zero if any test fails**, which is what makes it a CI gate.

`--print-output-on-failure` is worth having on by default in CI: without it a
failure shows the expression and not the actual output.

:::warning
`--jobs N` needs GNU `parallel` or `rush`, and **neither is installed on this
image**. Without one it does not fall back to serial — it reports
`parallel: command not found` and then `Executed 0 instead of expected 1 tests`,
which is a green-looking suite that ran nothing. Check the dependency before
putting `--jobs` in a CI command.
:::

## The shape of a test

```bash
#!/usr/bin/env bats

setup() {
  WORK="$BATS_TEST_TMPDIR/work"
  mkdir -p "$WORK"
}

@test "a name that says what should be true" {
  run ./script.sh "$WORK"
  [ "$status" -eq 0 ]
  [ "$output" = "expected" ]
}
```

```bash
setup_file() { ... }        # once, before the file
teardown_file() { ... }     # once, after
teardown() { ... }          # after each test
```

Name a test after the behaviour, not the function: *"it keeps a file that is
exactly at the boundary"* beats *"test_retention_2"*, because the name is what a
failing CI run shows you.

## What `run` gives you

```bash
run some_command arg
echo "$status"        # exit status
echo "$output"        # stdout AND stderr, combined, trailing newline stripped
echo "${lines[0]}"    # first line
echo "${#lines[@]}"   # how many lines

run bash -c 'cmd 2>/dev/null'   # when stdout must be tested alone
FAKE_RC=1 run ./script.sh       # env for this run only
```

Without `run`, a non-zero exit ends the test — so **failure paths need it**.
With `run`, forgetting `[ "$status" ... ]` means the test passes whatever
happened.

## Assertions

```bash
[ "$status" -eq 0 ]
[ "$output" = "exact" ]
[[ "$output" == *"substring"* ]]
[[ "$output" =~ ^regex$ ]]
[ "${#lines[@]}" -eq 3 ]
[ -f "$WORK/expected-file" ]
[ ! -e "$WORK/should-be-gone" ]
```

An assertion must be **the last command in its pipeline**, or errexit's
exemptions mean it can never fail (B08.5). `[ "$x" = y ] | tee log` is not an
assertion.

Because a failure reports the expression and not the values:

```bash
assert_equals() {
  [ "$1" = "$2" ] || { echo "got:  [$1]" >&2; echo "want: [$2]" >&2; return 1; }
}
```

```bash
skip "needs a database"                       # unconditional
[ -n "${SLOW:-}" ] || skip "set SLOW=1"       # conditional
echo "debug" >&3                              # print during the run
```

## A test double

```bash
setup() {
  BIN="$BATS_TEST_TMPDIR/bin"; mkdir -p "$BIN"
  cat > "$BIN/kubectl" <<'K'
#!/bin/bash
echo "kubectl $*" >> "$FAKE_LOG"
exit "${FAKE_RC:-0}"
K
  chmod 0755 "$BIN/kubectl"
  export FAKE_LOG="$BATS_TEST_TMPDIR/calls"; : > "$FAKE_LOG"
  export PATH="$BIN:$PATH"
}
```

```bash
[ "$(cat "$FAKE_LOG")" = "kubectl apply -f manifests/staging.yaml" ]
grep -q 'rollout status' "$FAKE_LOG"
[ "$(wc -l < "$FAKE_LOG")" -eq 2 ]      # called exactly twice
```

## Making a script testable in the first place

```bash
# a script that runs itself when executed, and defines only functions when sourced
main() { ... }
[ "${BASH_SOURCE[0]}" = "$0" ] && main "$@"
```

That one line is the difference between a script a suite can `source` to test
individual functions and one it can only run end to end. It is the shell
equivalent of `if __name__ == "__main__"`.

```bash
DAYS=${RETENTION_DAYS:-7}          # injectable, so a test can vary it
DIR=${1:?usage: retention.sh DIR}  # explicit input, not a global
```

Anything a test needs to vary has to be an argument or an environment variable.
A value hard-coded in the middle of a script is a value no test can reach.

## In CI

```yaml
- run: bats -r tests/
```

```bash
bats --formatter junit tests/ > results.xml    # if your CI wants JUnit
shellcheck -S warning scripts/*.sh             # the cheaper half of quality
```

`shellcheck` and `bats` answer different questions — one finds what is wrong with
the code as written, the other finds what is wrong with what it does. Run both;
`shellcheck` is the one that costs nothing.

:::try{lab=the-suite-that-proves-nothing}
:::

:::objective{id=OBJ-B08.9.2}
:::

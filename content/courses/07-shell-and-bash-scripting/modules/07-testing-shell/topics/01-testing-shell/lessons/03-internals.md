---
topic: topic.testing-shell
section: internals
title: Testing what you must not run
order: 3
mode: explain
---

## The problem

```bash
kubectl apply -f "manifests/$TARGET.yaml"
kubectl rollout status "deployment/$TARGET" --timeout=60s
```

There is no cluster in a test environment, and there had better not be. Most
people stop testing shell exactly here, and conclude that operational scripts
are simply untestable.

They are not. The script finds `kubectl` by searching `PATH` — so the test
controls what it finds.

## A test double on `PATH`

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

Three lines of behaviour, and they are the three a double needs:

- **It records how it was called** — `echo "kubectl $*" >> "$FAKE_LOG"`.
- **It returns a status the test chooses** — `${FAKE_RC:-0}`.
- **It lives in `$BATS_TEST_TMPDIR`**, so it is created fresh per test and
  cannot leak into another.

Now both directions are testable:

```bash
@test "it calls kubectl with the right manifest" {
  run deploy.sh staging
  [ "$status" -eq 0 ]
  [ "$(cat "$FAKE_LOG")" = "kubectl apply -f manifests/staging.yaml" ]
}

@test "it fails when kubectl fails" {
  FAKE_RC=1 run deploy.sh staging
  [ "$status" -ne 0 ]
}
```

The second is the one that matters and the one nobody writes. **A script's
failure path is the part that runs during an incident**, and it is the part that
has usually never executed.

This is not a trick. It is the same mechanism B08.6 measured when a shell
function shadowed `ls`: the shell resolves a name at call time, and whoever
controls the resolution controls the call.

:::warning
A double that always succeeds tests almost nothing. If `FAKE_RC` is never set to
anything but 0, the suite proves the script works when the world works — which
was never in doubt.
:::

## What a double must not become

The failure mode is a double that drifts from the real thing. Your fake
`kubectl` accepts arguments the real one rejects, returns a shape the real one
never returns, and the suite goes green against a fiction.

Three ways to keep it honest:

- **Assert the arguments, not just the call.** `kubectl apply -f
  manifests/staging.yaml` is a claim about the interface. If someone reorders the
  flags, the test should notice.
- **Keep the double trivially small.** The moment it has branching logic it is a
  second implementation with its own bugs.
- **Have one real test.** Somewhere — nightly, not per-commit — something runs
  against a real cluster. The doubles tell you the script is internally correct;
  only the real thing tells you the interface is.

That last point is the boundary between a unit test and an integration test, and
it is worth being explicit: **a double can only prove you called what you meant
to call.** It cannot prove that is the right call.

## Choosing cases

The seeded suite passed with two bugs present, because its cases came from the
happy path. Cases that find bugs come from four places:

**Boundaries.** The retention script's policy is 7 days; its fixture used 30 and
2. A file at exactly 7 days is where the behaviour changes, and where the
off-by-one lives. Test one on each side and one exactly on it.

**Failure paths.** Missing directory, absent tool, empty input, permission
denied. `run` exists so these are writable at all.

**Arguments nobody passes.** `retention.sh DIR [DAYS]` — the default is exercised
constantly and `DAYS` never. Every parameter with a default is a code path with
no coverage.

**The empty case.** Zero files, zero rows, no arguments. This is where "it
worked" and "it did nothing" produce the same output, and it is how B08.8's
health check reported zero failures while examining nothing.

A useful discipline: **write the test that would have caught the last
incident.** Those cases are already known to be real, and nobody would have
invented them.

## What not to test

Testing has a cost, and a suite nobody trusts is worse than none.

- **Not the shell itself.** A test asserting that `mkdir -p` is idempotent is
  testing coreutils.
- **Not trivial wrappers.** A function that is one `command` call with a fixed
  flag has nothing to get wrong that the double would catch.
- **Not the output format**, unless something parses it. Asserting on a
  human-readable message makes every wording change a test failure, which trains
  people to update tests without reading them.
- **Not through the double, twice.** If the only assertion is that the fake was
  called, and the fake is trivial, the test asserts that `PATH` works.

What is always worth testing: **anything that decides**, and **anything
destructive**. A boundary, a branch, an exit status, a `--dry-run` that must
really be dry.

:::objective{id=OBJ-B08.9.5}
:::

:::objective{id=OBJ-B08.9.6}
:::

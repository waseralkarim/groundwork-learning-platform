---
topic: topic.testing-shell
section: core-concepts
title: What a bats file is
order: 2
mode: explain
---

## A test is a function that must not fail

```bash
@test "retention defaults to 7 days" {
  run retention_days
  [ "$status" -eq 0 ]
  [ "$output" = "7" ]
}
```

A `.bats` file is shell. `@test "name" { ... }` is a block `bats` turns into a
function and runs with `set -e` semantics: **the test fails the moment any
command in it returns non-zero.**

That is why a bare `[ ... ]` is an assertion. There is no `assert` keyword —
`[ "$output" = "7" ]` fails the test by returning 1, exactly as it would in any
other script.

It also means an *incidental* failure fails the test. `grep` finding nothing,
`cd` into a missing directory, an arithmetic expression evaluating to zero
(B08.5) — all of them end the test, and the report will point at that line
rather than at anything you meant to assert.

:::warning
**And errexit's exemptions apply here too**, which is the trap. Measured:

```console
@test "a bare false ends the test" {
  false                     # not ok — reported at this line
  echo "never printed"
}

@test "false in a pipeline does not" {
  false | true              # the pipeline's status is true's
  echo "reached the end"    # prints; the test PASSES
}
```

So an assertion written as a non-final pipeline stage **can never fail the
test**. Every exemption B08.5 measured — `if` and `while` conditions, `&&` and
`||` operands, anything after `!` — behaves the same way. An assertion must be
the last thing in its pipeline, or it is decoration.
:::

## `run` is what lets you test a failure

```bash
run some_command --with args
```

`run` executes the command **without failing the test**, and captures:

| | |
|---|---|
| `$status` | the exit status |
| `$output` | stdout and stderr, combined, trailing newline stripped |
| `${lines[@]}` | the output split into an array of lines |
| `${lines[0]}` | the first line |

```console
$ run bash -c 'echo one; echo two; exit 3'
status=3
output=[one
two]
lines0=[one] lines1=[two]
```

Without `run`, a command that exits non-zero ends the test immediately — so
**you cannot test a failure path without it.** That is the single most common
reason a beginner's suite has no failure-path tests at all: the obvious way to
write one does not work.

Two details worth knowing. `$output` **combines stdout and stderr**, so a test
asserting on stdout can be fooled by a warning; use `run bash -c 'cmd 2>/dev/null'`
when the distinction matters. And `run` swallows the status, so a test that
forgets to assert on `$status` passes whatever the command did.

## `setup` and `teardown`

```bash
setup() {
  WORK="$BATS_TEST_TMPDIR/work"
  mkdir -p "$WORK"
  touch -d '30 days ago' "$WORK/old.log"
}

teardown() {
  : # BATS_TEST_TMPDIR is removed for you
}
```

`setup` runs before **each** test and `teardown` after each, so every test gets
a fresh fixture and cannot be affected by one that ran before it.

`setup_file` and `teardown_file` run once for the whole file — right for
something genuinely expensive, and wrong for anything a test mutates, because
that reintroduces exactly the coupling `setup` exists to prevent.

**`$BATS_TEST_TMPDIR` is created fresh per test and removed afterwards.**

```console
/tmp/bats-run-ipIrpI/test/4
```

Put fixtures and fake binaries there. A test that writes to a fixed path — even
under `/tmp` — is a test that cannot run twice at once, which matters the moment
the suite runs in CI beside another branch's.

## `skip`

```bash
@test "restores from a real backup" {
  [ -n "${RUN_SLOW_TESTS:-}" ] || skip "set RUN_SLOW_TESTS=1"
  ...
}
```

```console
ok 4 skipping is a first-class result # skip needs a database
```

A skip is reported as a pass **with its reason attached**, which is the point:
the test is still listed, still named, and still visibly not running. Commenting
a test out hides it; `skip` documents it.

## Reading the output

```console
1..4
ok 1 retention defaults to 7
not ok 3 a failing assertion shows the diff
# (in test file t.bats, line 17)
#   `[ "$output" = "orders-WRONG.tar.gz" ]' failed
```

That is **TAP** — `1..N` then one line per test. Most CI systems parse it, and
`bats --formatter tap` makes it explicit. The suite exits **non-zero if any test
fails**, which is what makes it usable as a CI gate.

The failure gives you the file, the line, and the expression. **It does not give
you the values**, so `[ "$output" = "x" ]` failing tells you the assertion failed
and not what `$output` was. Two ways round it:

```bash
# print the actual value when it matters
[ "$output" = "$want" ] || { echo "got: [$output] want: [$want]" >&2; false; }
```

```bash
# or a helper, once, at the top of the file
assert_equals() {
  [ "$1" = "$2" ] || { echo "got:  [$1]" >&2; echo "want: [$2]" >&2; return 1; }
}
```

`bats-assert` is the library that does this properly. It is not installed here,
and writing the four-line helper is a reasonable answer for a repository that
does not want another dependency.

:::note
`>&3` prints to the real stdout during a test, for debugging. Anything else your
test echoes is captured and shown only on failure — which is usually what you
want, and confusing the first time a `echo` seems to vanish.
:::

:::objective{id=OBJ-B08.9.2}
:::

:::objective{id=OBJ-B08.9.3}
:::

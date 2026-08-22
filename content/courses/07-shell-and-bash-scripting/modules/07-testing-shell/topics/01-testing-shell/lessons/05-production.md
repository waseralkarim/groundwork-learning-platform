---
topic: topic.testing-shell
section: production
title: What is worth testing
order: 5
mode: explain
---

## The standard

Most operational shell is untested, and the honest reason is that testing all of
it is not worth it. A standard that demands full coverage gets ignored; one that
names a short list gets followed.

**Always test:**

- **Anything destructive.** A `--dry-run` that must really be dry, a delete
  guarded by a flag, a retention boundary. If getting it wrong loses data, it
  gets a test.
- **Anything that decides.** A branch, a threshold, a parse. `-mtime +7` is a
  decision, and it was wrong.
- **Every failure path you rely on.** If a script is supposed to exit non-zero
  when a host is unreachable, something must have watched it do that. B08.8's
  health check could not fail, and no test had made it try.
- **Every bug you fix.** The test goes in with the fix. This is the highest-value
  rule on the list, because those cases are known to be real and nobody would
  have invented them.

**Do not bother testing:**

- The shell itself — `mkdir -p` is idempotent whether you assert it or not.
- A wrapper that is one `command` call with a fixed flag.
- Output wording, unless something parses it. Otherwise every rewording is a
  failure, and people learn to update tests without reading them.
- Anything where writing the double is more code than the thing under test.

## Where a test stops and an assertion starts

A test runs before the change ships. A **production assertion** runs every time
the script does, and they cover different things:

| | Catches |
|---|---|
| Unit test, with doubles | the logic is what you meant |
| Integration test, real tools | the interface is what you assumed |
| **Production assertion** | reality is what you expected *this time* |

The last one is what this course has been building all along — `[ -s "$BACKUP" ]`,
the checksum after a publish, the count compared against an independent count.
No test can tell you the disk filled up tonight.

The rule of thumb: **a test proves the script is right; an assertion proves the
run was.** A script that does something irreversible needs both.

## Making a script testable

Two changes buy most of it.

```bash
main() { ... }
[ "${BASH_SOURCE[0]}" = "$0" ] && main "$@"
```

Now a suite can `source` the script to test individual functions, instead of
only running it end to end. It is the shell equivalent of
`if __name__ == "__main__"`, and without it every test is an integration test.

```bash
DAYS=${RETENTION_DAYS:-7}
DIR=${1:?usage: retention.sh DIR}
```

**Anything a test needs to vary must be an argument or an environment
variable.** A threshold hard-coded mid-script is a threshold no test can reach —
which is exactly why the seeded suite never exercised `DAYS`.

The same property makes a script easier to operate. A value you can override in
a test is a value you can override at 3am.

## Running them

```bash
bats -r --print-output-on-failure tests/
```

In CI, on every change, next to `shellcheck`. The two answer different
questions — `shellcheck` finds what is wrong with the code as written, `bats`
finds what is wrong with what it does — and `shellcheck` is the one that costs
nothing, so it goes first.

A suite that is not in CI is documentation. It rots, and the first person to
find it broken deletes it.

## What a green suite is worth

Less than it looks, and that is the thing to carry out of this topic.

The seeded suite had three passing tests against a script with two bugs. Nothing
was wrong with the tests as tests — they were correct, readable, and they
asserted true things. They just asserted the things the author already believed,
which is what tests written after the fact always do.

So treat a green suite as evidence about the cases it names, and nothing more.
The useful question in review is never "are there tests" — it is **"which case
would have caught this, and is it in there?"**

## When to stop writing shell

This topic is the last of the course, and the honest summary of all of it:

A shell script is worth testing when it is short, does one thing, and glues
commands together. When you find yourself writing doubles for four different
tools, asserting on parsed JSON, or maintaining a test helper library — the tests
are telling you the script outgrew the language some time ago.

B11's `pytest` gives everything in this topic with real assertion output,
fixtures that compose, and mocking that does not depend on `PATH` ordering. The
reason to learn testing in shell first is not that shell is the right place to
test — it is that **the scripts you inherit are already in shell**, and they are
running as root on every host tonight.

## What to take from this topic

- **A passing suite is evidence about the cases it names.** Three green tests sat
  on top of two bugs.
- **Bugs live at boundaries, on failure paths, and in arguments nobody passes.**
- **`run` is what makes a failure testable** — without it, a non-zero exit ends
  the test.
- **An assertion must be the last command in its pipeline**, or errexit's
  exemptions mean it can never fail.
- **`--print-output-on-failure`** shows the actual output; anything else you want
  to see, you print yourself.
- **A double on `PATH`** makes a script testable without the thing it calls — and
  a double that always returns 0 tests almost nothing.
- **`main "$@"` behind a `BASH_SOURCE` guard** is what makes a script's functions
  reachable at all.
- **Test what decides and what destroys.** Skip the rest, deliberately.

:::objective{id=OBJ-B08.9.6}
:::

:::objective{id=OBJ-B08.9.8}
:::

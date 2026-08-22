---
topic: topic.testing-shell
section: overview
title: Three passing tests and two bugs
order: 1
mode: explain
---

A retention script. Somebody tested it the way scripts are usually tested — make
a couple of files, run it, read the output:

```console
$ ./manual-check.sh
files:
  recent.log
  very-old.log

retention.sh says these are expired:
  /tmp/tmp.93JPrR/very-old.log

looks right.
```

Then somebody wrote a real suite:

```console
$ bats first.bats
1..3
ok 1 it lists an old file
ok 2 it does not list a recent file
ok 3 it refuses a missing directory
```

**Three tests, three passes. The script has two bugs.**

## What neither of them looked at

The policy is seven days. Give the script files at 6, 7, 8 and 30 days:

```console
$ retention.sh "$W"
  age-8d.log
  age-30d.log
```

The **seven-day-old file is not listed.** `-mtime +7` means *more than seven
whole days*, so the retention window is eight — B08.4 measured this, and here it
is again, this time surviving a green test suite.

The second bug is quieter. The script's exit status is `find`'s, and `find`
succeeds when it matches nothing. A caller cannot tell "nothing expired" from
"the directory vanished between my check and now".

Neither test saw either one, for a reason worth stating plainly:

- The fixture used files at **30 days and 2 days** — nowhere near the boundary.
- The script takes a `DAYS` argument. **No test passes one.**
- No test looks at what the exit status means when the output is empty.

:::predict{question="A suite covers every line of a script and every test passes. What can you conclude about the script?"}
:::

## Tests are written from the happy path, and bugs do not live there

That is the whole lesson, and it is not specific to shell. The tests somebody
writes first are the cases they already had in mind while writing the code — so
they encode the same assumptions, including the wrong ones.

The cases that find bugs are the ones nobody was thinking about:

- **Boundaries.** Exactly 7 days. Exactly zero files. Exactly the limit.
- **Failure paths.** The directory is missing, the tool is absent, the disk is
  full. B08.8's health check could not fail, and no test had ever made it try.
- **Arguments nobody passes.** The default is exercised a thousand times; the
  option is exercised never.
- **The empty case.** Zero rows, zero files, no arguments — where "it worked" and
  "it did nothing" become the same output.

## What `bats` gives you, and what it does not

```console
$ bats t.bats
1..4
ok 1 retention defaults to 7
ok 2 backup_name composes the two parts
not ok 3 a failing assertion shows the diff
# (in test file t.bats, line 17)
#   `[ "$output" = "orders-WRONG.tar.gz" ]' failed
ok 4 skipping is a first-class result # skip needs a database
```

A failure names the **file**, the **line**, and the **expression that failed**.

It does not tell you what `$output` actually was. That is the single biggest
friction with `bats`, and it is why `bats-assert` exists — and why, without it,
you write the value into the message yourself.

## A script you cannot test by running it

```bash
kubectl apply -f "manifests/$TARGET.yaml"
kubectl rollout status "deployment/$TARGET" --timeout=60s
```

There is no cluster in a test environment, and there had better not be. This is
where most people stop testing shell entirely.

The way through is a **test double**: a script called `kubectl`, earlier on
`PATH` than the real one, which records how it was called and returns whatever
status the test wants. The script under test cannot tell the difference, because
finding a command on `PATH` is exactly what it does.

That is not a trick. It is the same mechanism B08.6 measured when a shell
function shadowed `ls`.

## What this topic covers

- What makes a script testable, and what a green suite is worth.
- `bats` — `@test`, `run`, `$status`, `$output`, `setup`, `teardown`, `skip`.
- Reading TAP, and what a failure does not tell you.
- Choosing cases from boundaries and failure paths instead of the happy path.
- Test doubles on `PATH`, for scripts that call things you must not run.
- Where a unit test stops and a production assertion starts.

Four labs:

- Make the passing suite fail, without changing the script.
- Write a suite that would have caught both bugs.
- Test a deploy script with no cluster anywhere.
- Decide what is worth testing, and defend leaving something untested.

:::objective{id=OBJ-B08.9.1}
:::

:::objective{id=OBJ-B08.9.4}
:::

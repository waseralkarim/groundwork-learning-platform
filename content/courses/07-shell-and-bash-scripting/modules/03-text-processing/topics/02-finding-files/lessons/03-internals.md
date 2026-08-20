---
topic: topic.finding-files
section: internals
title: Exit status, and what silence means
order: 3
mode: explain
---

:::diagram{src=../diagrams/exec-forms.mmd caption="Four ways to act on found files. Two of them discard the command's exit status, and one silently gives up batching."}
:::

## find's exit status reports its own problems, not the command's

```console
$ find . -name '*.log' >/dev/null; echo $?
1
$ find: './locked': Permission denied
```

find returns **1 when it could not read part of the tree**. That is the status
that matters most in a cleanup job, because the files it could not see are
exactly the ones that will not be processed — silently, and forever.

But the command's status is a separate question, and the answer depends on the
form:

```console
$ find app -name '*.log' -exec false \; ; echo $?
0
$ find app -name '*.log' -exec false {} + ; echo $?
1
```

**`-exec … \;` ignores the command's exit status completely.** A retention job
using it reports success when every `rm` failed — on a read-only filesystem, on
files owned by another user, on a full disk during a compression step.

## And a pipeline discards it entirely

```console
$ find . -name '*.log' | wc -l >/dev/null; echo $?
0
```

The pipeline reports `wc`'s status. So `find | xargs rm` returns 0 whether find
walked the whole tree or gave up on half of it. `set -o pipefail` restores it,
and `${PIPESTATUS[@]}` names which stage failed — the same mechanism B08.2
measured, arriving here with a destructive command on the end.

Which gives the honest summary of the four forms:

| Form | Batches | Command failure visible | find's own failure visible |
|---|---|---|---|
| `-exec cmd \;` | no | **no** | yes |
| `-exec cmd +` | yes | yes | yes |
| `\| xargs -0 cmd` | yes | as xargs's status | **no, without pipefail** |
| `\| xargs -0 -I{} cmd {}` | **no** | as xargs's status | **no, without pipefail** |

`-exec … +` is the only one that reports both, which is a good reason to prefer
it when it fits.

## Three ways a bulk operation acts on the wrong set

**It saw fewer files than you think.** A permission error, a `-maxdepth` you
forgot, a symlinked directory it did not follow. find defaults to **not**
following symlinks; `-L` makes it follow them, and then a symlink loop becomes
your problem.

**It saw more files than you think.** An unparenthesised `-o`, a `-name` pattern
that the *shell* expanded before find ever saw it:

```bash
find . -name *.log        # WRONG if any .log exists in the current directory
find . -name '*.log'      # the pattern reaches find
```

Unquoted, the shell globs `*.log` against the working directory first. If it
matches one file, find receives that filename as the pattern; if it matches
several, find errors. If it matches none, it happens to work — which is why this
bug appears only after somebody runs the script from a different directory.

**It ran on nothing and did something anyway.** `xargs` without `-r`.

## Making a destructive operation reviewable

The pattern worth standardising:

```bash
# 1. produce the list, once
find "$DIR" -type f -name '*.log' ! -newermt "-${DAYS} days" -print0 > /tmp/victims

# 2. show what would happen — this is the review step
tr '\0' '\n' < /tmp/victims | head -20
printf 'total: %d files\n' "$(tr -dc '\0' < /tmp/victims | wc -c)"

# 3. act on exactly that list
xargs -0 -r rm -- < /tmp/victims
```

Three properties that matter. The list is **computed once**, so nothing changes
between deciding and acting — a `find … -delete` re-walks a tree that other
processes are writing to. It is **printable**, so a human or a CI job can review
it. And step 3 acts on the *file*, not on a fresh search, so the review is of
the actual set.

`--` and `-0` handle hostile filenames; `-r` handles the empty case.

## `-delete` and when to trust it

```bash
find "$DIR" -type f -name '*.log' -mtime +7 -delete
```

`-delete` is safer than `-exec rm` in one specific way: **no shell is involved**
between selecting a file and removing it, so there is nothing to split, quote or
glob. It also implies `-depth`, so a directory is removed after its contents.

What it does not give you is a review step or a dry run. `-delete` acts as it
walks, so by the time you notice the predicate was wrong, it has finished.

The rule I would apply: **`-delete` for a predicate you have tested, in a path
you control; the list-then-act pattern for anything else** — anything with a
variable in the path, anything running as root, anything whose blast radius you
cannot state in one sentence.

And always test the predicate with `-print` first. Replacing `-print` with
`-delete` after reading the output is a two-second habit that removes most of
this topic's risk.

:::warning
Copying a directory to test a retention job **destroys the thing under test**.
`cp -r` gives every copy the current mtime, so an age-based job correctly deletes
nothing and the test passes for the wrong reason. Use `cp -a` (or `cp -rp`),
which preserves timestamps.
:::

:::objective{id=OBJ-B08.4.5}
:::

:::objective{id=OBJ-B08.4.6}
:::

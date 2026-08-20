---
topic: topic.set-euo-pipefail
section: core-concepts
title: What each option actually does
order: 2
mode: explain
---

:::diagram{src=../diagrams/errexit-exemptions.mmd caption="errexit is suppressed wherever the shell is already testing a status — and a status can be masked before errexit ever sees it."}
:::

## `set -e` — errexit

Exit if a command returns non-zero. The rule underneath the exemptions is
consistent: **errexit is suppressed wherever the shell is already examining the
status**, because otherwise `if grep -q x file` could never be written.

That covers:

- the condition of an `if`, `while` or `until`
- either operand of `&&` or `||`
- anything after `!`
- every stage of a pipeline except the last

and, crucially, **everything called from those positions**. A function invoked
as an `if` condition runs its whole body with errexit suppressed:

```console
$ bash -c 'set -e; f(){ false; echo "still here"; }; if f; then :; fi; echo done'
still here
done
```

Both `echo`s ran. The same function called plainly stops the script.

That is the trap worth internalising: **a helper's error handling depends on how
it is called**, and nothing at the call site says so.

## `set -u` — nounset

Fail on expanding a variable that was never set.

```console
$ bash -c 'set -u; echo "$UNSET"'; echo $?
bash: UNSET: unbound variable
127
```

**Exit status 127**, which conventionally means "command not found" — so in a
CI log it reads like a missing binary rather than a missing variable. Worth
knowing before you spend an hour looking for the wrong thing.

What `-u` deliberately allows:

```bash
"${VAR:-default}"    # a default if unset OR empty
"${VAR-default}"     # a default only if unset
"${VAR:?message}"    # fail deliberately, with your own message
"$@"                 # fine with zero arguments
"${array[@]}"        # fine when empty, in modern bash
```

`${VAR:?message}` is the one to reach for at the top of a script. It turns an
invisible dependency into a one-line failure naming the problem, which is
strictly better than `-u` catching it forty lines later.

:::note
`"$@"` and empty-array expansion under `-u` were errors in bash before 4.4. If
you support older systems, `"${a[@]:-}"` is the defensive form — and if you do
not, do not carry the noise.
:::

## `set -o pipefail`

A pipeline's status becomes the **last non-zero** one rather than the last
command's. Without it, `pg_dump | gzip` reports gzip's success.

B08.2 measured this in full. The interaction worth repeating here: with
`pipefail` on, a pipeline ending in `head` reports failure, because the producer
is killed by SIGPIPE and exits 141. That needs a deliberate `|| true` with a
comment — a bare one reads as sloppiness.

## The two ways a status is lost before errexit sees it

**Assignment with `local`.** This is the big one.

```console
$ bash -c 'set -e; x=$(false); echo reached'                  # rc=1, fires
$ bash -c 'set -e; f(){ local x=$(false); }; f; echo reached'  # rc=0, does not
```

A plain assignment takes the exit status of the command substitution. But
`local` — and `declare`, `export`, `readonly`, `typeset` — is **a command in its
own right**, and its status is its own success. The substitution's failure is
discarded before errexit could act on it.

So adding the word `local` to a working line removes its error checking. Silently.
The fix is to separate them:

```bash
local x
x=$(cmd)          # now the status is cmd's
```

Two lines, and `shellcheck` flags the one-line form as SC2155.

**Arithmetic evaluating to zero.**

```console
$ bash -c 'set -e; count=0; ((count++)); echo reached'    # rc=1 — script dies
$ bash -c 'set -e; count=0; ((count+=1)); echo reached'   # rc=0
$ bash -c 'set -e; count=0; count=$((count+1)); echo r'   # rc=0
```

`((...))` returns non-zero when the expression's **value** is zero, mirroring C's
notion of truth. `count++` is a post-increment: its value is the old count, which
on the first iteration is 0. So the script exits on the first increment.

`((count+=1))` evaluates to the *new* value, which is 1, so it survives — until
a counter legitimately reaches zero. The reliable forms are `count=$((count+1))`
or `: $((count++))`.

## Where the migration fails

Putting it together, the seeded script's fault is one line:

```bash
apply_migration() {
  local file=$1
  local output=$(fake_psql < "$file")     # ← the status is local's
  echo "applied $(basename "$file")"
}
```

`fake_psql` fails, `local` succeeds, the function's last command is a successful
`echo`, so the function returns 0, the loop continues, and the script reports
two migrations applied.

Every layer behaved as documented. The preamble was present and correct and
caught nothing, because the failure never reached it.

:::objective{id=OBJ-B08.5.3}
:::

:::objective{id=OBJ-B08.5.4}
:::

:::objective{id=OBJ-B08.5.5}
:::

:::objective{id=OBJ-B08.5.6}
:::

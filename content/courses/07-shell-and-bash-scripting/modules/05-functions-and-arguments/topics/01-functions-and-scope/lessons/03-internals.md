---
topic: topic.functions-and-scope
section: internals
title: Which constructs fork, and what that costs
order: 3
mode: explain
---

:::diagram{src=../diagrams/scope-and-subshells.mmd caption="A called function shares the shell's variables and can write to any of them. A forked copy returns only its output and its status — every assignment inside it is discarded."}
:::

## The boundary table, measured

The same assignment — `v=inner`, where `v` was `outer` — inside ten constructs:

| Construct | `v` afterwards |
|---|---|
| `{ v=inner; }` — group | inner |
| `f(){ v=inner; }; f` — function | inner |
| `for i in x; do v=inner; done` | inner |
| `while read; do v=inner; done <<< x` | inner |
| `{ v=inner; } < <(echo x)` — process substitution | inner |
| `f(){ local v=inner; }; f` | **outer** |
| `( v=inner; )` — subshell | **outer** |
| `x=$(v=inner; ...)` — command substitution | **outer** |
| `echo x \| { v=inner; }` — pipeline | **outer** |
| `echo x \| while read; do v=inner; done` | **outer** |

Two rules produce the whole table:

**`local` bounds a name to the call.** Nothing forked; the outer `v` was hidden
and is now visible again.

**Everything else in the second group is a fork.** `( )`, `$( )`, and *every
stage of a pipeline* run in a subshell. A subshell inherits everything and
returns only its output and its exit status; assignments die with it.

The last two rows are the ones that cost people afternoons. `{ v=inner; }` keeps
the value; `echo x | { v=inner; }` does not, and the only difference is the pipe.

## Why a piped `while read` is the classic

```console
$ n=0; printf 'a\nb\nc\n' | while read -r line; do n=$((n+1)); done; echo "n=$n"
n=0
$ n=0; while read -r line; do n=$((n+1)); done < <(printf 'a\nb\nc\n'); echo "n=$n"
n=3
```

The loop body ran three times in both. In the first, it ran in a forked shell
that then exited — so the count, and any array, flag or accumulated string, went
with it. **The loop worked and the result was thrown away**, which is why the
symptom is always "it does the work and reports nothing".

Three fixes, in order of preference:

```bash
while read -r line; do ...; done < <(command)   # process substitution
while read -r line; do ...; done < file          # a plain redirect
shopt -s lastpipe                                # bash, non-interactive only
```

`lastpipe` runs the *last* pipeline stage in the current shell, which fixes it
without restructuring — but it needs job control off, so it works in a script
and not at an interactive prompt. That inconsistency is why the redirect forms
are better: they behave the same everywhere.

## Getting a value out of a function

There are four ways, and they trade off against each other.

**1. Print it, and capture with `$( )`.**

```bash
sum=$(checksum_of "$file")
```

Reads like a function call in any other language. It costs a fork, so **no side
effect inside survives** — not a counter, not a cache, not a flag. It also
strips trailing newlines and, as B08.5 measured, `local sum=$(...)` discards the
exit status.

**2. Assign a fixed global.**

```bash
checksum_of() { REPLY=$(sha256sum "$1" | cut -d' ' -f1); }
checksum_of "$file"; echo "$REPLY"
```

No fork, side effects survive, status is the function's own. The cost is a
hard-coded name — two nested calls using `REPLY` clobber each other. (`REPLY` is
bash's own convention: `read` with no variable puts its line there.)

**3. A nameref — let the caller choose the name.**

```bash
checksum_of() {
  local -n _out=$2
  _out=$(sha256sum "$1" | cut -d' ' -f1)
}
checksum_of "$file" result; echo "$result"
```

The best of both, with one trap. A nameref whose *parameter* has the same name
as its *target* refers to itself:

```console
$ write_to() { local -n dest=$1; dest=written; }
$ caller()  { local dest=mine; write_to dest; echo "dest is now [$dest]"; }
$ caller
bash: local: warning: dest: circular name reference     (×3, on stderr)
dest is now [mine]
```

Bash **warns** rather than failing, and the assignment is lost — so under
`set -e` the script carries on and the caller reads a stale value, with the only
evidence on stderr.

The convention is an underscore prefix — `local -n _dest=$1` — which no caller
will have chosen. With it, the same code prints `written`.

:::note
The outcome depends on where the target lives. When the target is a **global**
of the same name, the warnings still appear but the write does land. It is the
realistic case — a caller function with a `local` of that name — that silently
loses it, which is the one worth designing against.
:::

**4. Return only a status, and print for humans.**

```bash
if service_is_healthy "$name"; then ...
```

The right answer whenever the value *is* a yes/no. Do not encode a count in the
status: it is one byte, and 128–165 already mean "killed by a signal".

## What `local` actually does

```console
$ g1() { local x=inner; }; g1; echo "${x:-<unset>}"
<unset>
$ g2() { declare -g y=inner; }; g2; echo "${y:-<unset>}"
inner
```

`local` hides an outer variable **for the duration of the call, including every
function called from it**. It does not isolate. `declare -g` is the deliberate
opposite — assign globally from inside a function — and is worth using when you
mean it, precisely because the accidental version looks identical.

One more asymmetry:

```console
$ f() { echo x; }; f=value; unset f; type -t f
function
```

**`unset` removes the variable and leaves the function.** A variable and a
function may share a name — they live in different namespaces — and `unset -f`
is what removes the function.

:::objective{id=OBJ-B08.6.5}
:::

:::objective{id=OBJ-B08.6.6}
:::

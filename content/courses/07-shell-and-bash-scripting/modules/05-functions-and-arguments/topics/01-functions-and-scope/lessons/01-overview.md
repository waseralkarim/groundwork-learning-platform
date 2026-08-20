---
topic: topic.functions-and-scope
section: overview
title: A function that reads a variable nobody passed it
order: 1
mode: explain
---

```bash
run_step() {
  echo "  [$1] against ${target:-<unset>}"
}

deploy() {
  local targt=$1          # ← one transposed letter
  run_step build
}

target=staging
deploy production
```

`run_step` prints `against staging`. The argument said `production`, the
variable the author meant to set is `targt`, and **`set -u` never fires** because
`target` genuinely exists — it was set at the top of the file as a default.

Nothing here is undefined, nothing fails, and the deploy goes to the wrong
environment.

## Shell scope is dynamic

Almost every language you have used is **lexically** scoped: a function can see
the variables written around it in the file. Shell is **dynamically** scoped —
a function can see the variables of whatever *called* it, however far up the
call stack.

```console
$ log()    { echo "log() sees stage=[${stage:-<unset>}]"; }
$ deploy() { local stage=production; log; }
$ deploy
log() sees stage=[production]
$ log
log() sees stage=[<unset>]
```

`log` was passed nothing and declares nothing. It read `deploy`'s `local`
variable, and the same call outside `deploy` sees nothing at all. **What a
function can see depends on who called it.**

It can also *write*:

```console
$ inner()  { x=changed-by-inner; }
$ outer()  { local x=before; inner; echo "outer now sees x=$x"; }
$ outer
outer now sees x=changed-by-inner
```

So `local` does not create an isolated variable. It creates one that is visible
to the function **and everything it calls**, and hides any outer variable of the
same name for the duration.

:::predict{question="A `for i in 1 2 3` loop calls a function that also loops with `i` and does not declare it `local`. How many times does the outer loop body run?"}
:::

## The same rule, doing real damage

```console
$ retry() { for i in 1 2 3; do :; done; }
$ for i in alpha beta gamma delta; do retry; echo -n "  [$i]"; done
  [3]  [3]  [3]  [3]
```

The outer loop still runs four times — `for` re-assigns `i` from its list each
time — but every use of `i` **after** the call sees `3`. Add one word:

```console
$ retry() { local i; for i in 1 2 3; do :; done; }
  [alpha]  [beta]  [gamma]  [delta]
```

A helper that reuses `i`, `f`, `n`, `count` or `line` will silently corrupt any
caller that uses the same name. There is no warning, because nothing is wrong.

## And a value can vanish entirely

```console
$ count=0
$ add() { count=$((count+1)); echo "value"; }
$ v=$(add); echo "v=$v count=$count"
v=value count=0
$ add >/dev/null; echo "count=$count"
count=1
```

The same function, called two ways. `$(...)` runs it **in a subshell** — a
forked copy of the shell — so the increment happened, in a process that then
exited. Only the output came back.

That is the second half of this topic: which constructs fork, and therefore
which assignments survive.

## Three things about the exit status

```console
$ bash -c 'exit 256'; echo $?
0
$ bash -c 'exit 300'; echo $?
44
$ bash -c 'exit -1';  echo $?
255
```

**An exit status is one unsigned byte.** A script that ends with
`exit "$failures"` reports **success** the moment it has 256 failures. That is
not a hypothetical if the number counts log lines or bad records.

## What this topic covers

- How a function is defined, how it is found, and how it shadows a real command.
- What a function returns when nothing says so, and why `return` is not `exit`.
- Dynamic scope, what `local` really bounds, and the bugs that follow.
- Every construct that forks, measured — so you can predict what survives.
- The four ways to hand a value back, and what each one costs.

Four labs:

- Generate the subshell-boundary table yourself and explain the two rows that
  differ by a pipe.
- Find the variable a helper read but was never given, in a script where nothing
  is undefined.
- Write a wrapper that calls itself until the shell dies, then fix it two ways.
- Return a value four different ways and argue for one.

:::objective{id=OBJ-B08.6.4}
:::

:::objective{id=OBJ-B08.6.5}
:::

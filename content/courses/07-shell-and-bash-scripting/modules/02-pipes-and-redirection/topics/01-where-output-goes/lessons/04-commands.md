---
topic: topic.where-output-goes
section: commands
title: Directing output, and finding out where it went
order: 4
mode: do
---

## Redirection

```bash
cmd > file                 # stdout, truncating
cmd >> file                # stdout, appending
cmd 2> err.log             # stderr only
cmd > out.log 2> err.log   # separated — two independent questions
cmd > file 2>&1            # both to the file. portable.
cmd &> file                # both to the file. bash shorthand.
cmd >> file 2>&1           # both, appending
cmd > /dev/null 2>&1       # discard everything
cmd 2>&1 >file             # DELIBERATE: stderr to the terminal, stdout to file
```

Only the last one is likely to be a mistake. Write `2>&1` **after** the
redirection it should follow, and reach for `&>` only when the script is already
bash-only.

## Custom descriptors

```bash
exec 3> /tmp/audit.log     # open fd 3 for the rest of the script
echo "event" >&3
exec 3>&-                  # close it

exec 3>&1                  # save the original stdout
exec 1> /tmp/all.log       # redirect everything from here on
echo "goes to the file"
exec 1>&3 3>&-             # restore, and close the saved copy
```

The second pattern — save, redirect, restore — is how a script logs a *section*
of its own output without wrapping every command. It is also how you keep a
progress message going to the terminal while bulk output goes to a file:

```bash
exec 3>&1                  # 3 is the real terminal
{
  echo "starting" >&3      # visible
  do_bulk_work             # captured
} > /tmp/work.log 2>&1
```

## Seeing where a process's output goes

```bash
ls -l /proc/self/fd/       # this shell's descriptors
ls -l /proc/1234/fd/       # another process, by PID
readlink /proc/1234/fd/1   # just stdout
```

That answers "where is this daemon actually writing" for something already
running — including the case where it is writing to a **deleted** file, which
shows as `/var/log/app.log (deleted)` and explains a disk that is full with
nothing on it.

## Pipelines and their exit status

```bash
set -o pipefail                    # pipeline status = last non-zero
cmd_a | cmd_b | cmd_c
echo "${PIPESTATUS[@]}"            # per-stage status, e.g. "1 0 0"
status=("${PIPESTATUS[@]}")        # copy it — the next command overwrites it
```

`PIPESTATUS` is valid only immediately after the pipeline. Even an `echo` in
between destroys it.

```bash
# which stage failed, reported usefully
cmd_a | cmd_b || {
  st=("${PIPESTATUS[@]}")
  echo "stage statuses: ${st[*]}" >&2
}
```

## Avoiding the subshell

```bash
# WRONG — count is lost
cmd | while read -r l; do count=$((count+1)); done

# process substitution — the loop is not in a pipeline
while read -r l; do count=$((count+1)); done < <(cmd)

# from a file
while IFS= read -r l; do count=$((count+1)); done < input.txt

# bash's lastpipe (bash only, job control off)
shopt -s lastpipe; set +m
cmd | while read -r l; do count=$((count+1)); done
```

`while IFS= read -r line` remains the canonical line reader: `IFS=` preserves
leading and trailing whitespace, `-r` stops backslash interpretation.

## Making output appear on time

```bash
grep --line-buffered PATTERN file     # grep's own option
sed -u '...'                          # GNU sed unbuffered
awk '{print; fflush()}'               # awk, explicitly
stdbuf -oL cmd                        # force line buffering
stdbuf -o0 cmd                        # force unbuffered
unbuffer cmd                          # expect(1), if installed — uses a pty
```

Diagnose it first, rather than sprinkling `stdbuf` everywhere: run the pipeline
with each stage's output timestamped and find which stage is holding lines.

```bash
cmd | while IFS= read -r l; do printf '%s %s\n' "$(date +%T)" "$l"; done
```

## Input that is not a file

```bash
cmd <<EOT           # here-doc, expands $var and $(cmd)
cmd <<'EOT'         # here-doc, expands NOTHING
cmd <<-EOT          # allows the delimiter to be indented — with TABS only
cmd <<< "$var"      # here-string, bash only
cmd < <(other)      # process substitution
diff <(a) <(b)      # two of them
```

Quote the delimiter by default. An unquoted here-doc containing a `$` in a
password, an awk program or a regex will be silently mangled.

## Discarding, duplicating, and inspecting

```bash
cmd > /dev/null            # discard stdout
cmd 2> /dev/null           # discard stderr — use sparingly, it hides real errors
cmd | tee file             # to a file and onward
cmd | tee -a file          # appending
cmd | tee /dev/stderr | next   # inspect a pipeline mid-flow
cmd | cat -A               # see tabs, CRs and line ends in the stream
```

`2> /dev/null` deserves a specific warning. It is the single most effective way
to hide a problem for months — B06.4's deploy guard failed silently for five
months because a missing command's error went there. Discard stderr only when
you know exactly which message you are discarding.

## Checking before running

```bash
bash -n script.sh          # syntax only
bash -x script.sh          # trace, showing redirections as applied
```

`bash -x` prints redirections in its trace, which makes an ordering mistake
visible without adding a single `echo`.

:::try{lab=where-output-goes}
:::

:::objective{id=OBJ-B08.2.6}
:::

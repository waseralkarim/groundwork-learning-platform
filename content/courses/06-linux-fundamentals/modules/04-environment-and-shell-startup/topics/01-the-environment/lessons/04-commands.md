---
topic: topic.environment-and-shell-startup
section: commands
title: Finding out what a process actually got
order: 4
mode: do
---

## What is in my environment

```bash
env                      # the live environment, one per line
env | sort               # worth doing — order is arbitrary
printenv PATH            # one variable, exits non-zero if unset
echo "${FOO:-unset}"     # distinguishes empty from unset
declare -p FOO           # shell variable or exported? bash tells you
```

`declare -p` is the one people do not know:

```console
$ FOO=1; export BAR=2
$ declare -p FOO BAR
declare -- FOO="1"
declare -x BAR="2"
```

The `-x` marks it as exported. That distinction is the difference between a
variable your script can see and one it cannot, and no amount of `echo $FOO` in
the parent will reveal it.

## What did *that* process get

```bash
tr '\0' '\n' < /proc/$$/environ            # this shell's snapshot
tr '\0' '\n' < /proc/1234/environ          # another process, same user
ps eww -p 1234                             # same thing, via ps
ps eww -C nginx                            # by name
```

Two cautions. Use `/proc/$$/environ`, not `/proc/self/environ`, when a redirect
is involved — `self` resolves to the wrong process and reads empty. And remember
what this shows: **the environment at `execve`**, not the live one. Variables
exported since will be missing, and variables unset since will still be there.

That property is what makes it the right tool for one specific question:
*what was this process actually started with?* — which is usually what you want
when a service is behaving as though it never received your configuration.

## Which startup files ran

```bash
bash -lic 'echo ...'     # login + interactive — a terminal
bash -lc  'echo ...'     # login only — ssh host 'cmd'
bash -ic  'echo ...'     # interactive only — a new tab
bash -c   'echo ...'     # neither — a script, cron, systemd, CI
```

Running the same probe four ways is the fastest way to locate where a setting
comes from. If it appears in `-lc` and not `-ic`, it is in a profile file; the
other way round, it is in a bashrc.

To see the order for real, bash will trace it:

```bash
PS4='+ ${BASH_SOURCE}:${LINENO}: ' bash -lixc true 2>&1 | grep '^+ /'
```

That prints every file bash sources, with line numbers, in order. It is the
definitive answer when a variable is being set by something you cannot find.

## Running with a known environment

```bash
env -i bash -c 'env'                    # start from nothing
env -i PATH=/usr/bin:/bin bash script   # approximate cron
env -u API_TOKEN cmd                    # run without one variable
env FOO=bar cmd                         # run with one added, without exporting
```

`env -i` is the tool for reproducing a scheduler's environment on your own
terminal. If a job fails under cron, run it under `env -i` with cron's PATH and
you will usually reproduce it in one attempt rather than waiting for the
schedule.

Careful with `env -i` and PATH: with no PATH at all, bash falls back to a
compiled-in default that **ends in `.`**, the current directory. Set PATH
explicitly.

## Diffing two environments

The single most useful technique in this topic:

```bash
bash -lic 'env' | sort > /tmp/interactive.env
bash -c   'env' | sort > /tmp/script.env
diff /tmp/interactive.env /tmp/script.env
```

Everything that differs is something a dotfile did, and the diff is usually
short enough to read. When somebody says "it works when I run it", this turns
that sentence into a list.

## PATH questions

```bash
command -v capsh         # where would this run from? (empty if not found)
type -a python           # every match, in order, including aliases and functions
which -a python          # similar, external command, no shell builtins
echo "$PATH" | tr : '\n' # readable
```

`type -a` beats `which` because it knows about shell builtins, functions and
aliases — which is precisely how "it works when I type it" happens when the
thing you type is an alias that no script will ever see.

## Checking a unit or a job

```bash
systemctl show -p Environment <unit>       # what the unit declares
systemctl show -p ExecStart <unit>         # and what it runs
crontab -l                                 # including any PATH= line at the top
```

A `crontab` may set `PATH=` in its own header; that is the supported way to fix
cron's PATH and it applies to every job in that crontab.

## Secrets, and what leaks them

```bash
ps eww -p <pid>                                    # environment of a process
tr '\0' '\n' < /proc/<pid>/environ                 # same, from /proc
docker inspect <id> --format '{{json .Config.Env}}' # from the host
```

Worth running once against your own services, deliberately, to see what is
visible. The result is usually more than people expect and it is a faster
argument than any policy document.

:::try{lab=which-files-run}
:::

:::objective{id=OBJ-B06.4.7}
:::

---
topic: topic.environment-and-shell-startup
section: overview
title: It works in my shell
order: 1
mode: explain
---

A script runs perfectly when you type it. The same script, unchanged, on the
same machine, as the same user, fails from cron with `command not found`.

Nothing is broken. The two shells read different files, and one of them read
none at all.

## Four modes, and only one reads everything

Bash decides what to read from two independent questions — **is this a login
shell**, and **is this interactive**. Neither implies the other, which gives four
combinations. On the machine you are about to work on:

| Invocation | Reads `/etc/profile` | Reads `/etc/bash.bashrc` |
|---|---|---|
| `bash -lic` — a terminal after login | **yes** | **yes** |
| `bash -lc` — `ssh host 'cmd'` | **yes** | no |
| `bash -ic` — a new terminal tab | no | **yes** |
| `bash -c` — a script, cron, systemd, CI | no | no |

The last row is the one that matters. **The shell that runs your automation
reads no startup files at all** — not `/etc/profile`, not `/etc/bash.bashrc`, not
`~/.bashrc`, not `~/.profile`. Everything you have accumulated in your dotfiles
over the years is simply absent.

That table is measurable rather than documentation, and you will measure it:
`/etc/bash.bashrc` on this image sets `HISTFILE`, so asking which invocations
see it settles the second column in one command.

:::predict{question="On this machine, PATH in a login shell and PATH in a script differ. Which one do you think is longer — and which one can find `capsh`?"}
:::

## PATH is not one thing

Three different mechanisms construct it, and they disagree:

```console
$ bash -c  'echo $PATH'
/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin

$ bash -lc 'echo $PATH'
/usr/local/bin:/usr/bin:/bin:/usr/local/games:/usr/games
```

Same user, same machine, same second. **The login shell's PATH is shorter and
has no `sbin` directories in it.** `/etc/profile` on Debian rewrites PATH from
scratch and gives root the `sbin` entries and everyone else `games` instead.

The consequence is immediate and backwards from what people expect:

```console
$ bash -c  'command -v capsh'      # a script finds it
/usr/sbin/capsh
$ bash -lc 'command -v capsh'      # your login shell does not
$
```

A tool that works in CI and fails when a human runs it by hand. That is not a
story anyone tells, which is exactly why it takes so long to diagnose.

## The environment is inherited, never looked up

There is no registry. A process receives a list of `KEY=VALUE` strings at
`execve` from whoever started it, and that is the entire mechanism. Which means:

- A variable you set in one terminal does not exist in another.
- A variable you set without `export` does not reach anything you run.
- Changing `~/.bashrc` changes nothing about processes already running.
- **systemd, cron and container runtimes construct the environment themselves.**
  They are not "missing" your settings; they never consulted anything that had
  them.

## And it is a snapshot, which surprises people

`/proc/PID/environ` records what a process was started with, and it never
updates. Watch what that means for a secret:

```console
$ unset API_TOKEN
$ env | grep -c API_TOKEN
0
$ tr '\0' '\n' < /proc/$$/environ | grep API_TOKEN
API_TOKEN=tok-abc123
```

**The variable is gone and the value is still there**, readable for as long as
the process lives. "We unset it after reading it" is a mitigation people believe
in and it does not do what they think.

That is one of several exposures, and they compound: `ps eww` prints another
process's environment, `docker inspect` prints every variable to anyone who can
reach the daemon, and every child process inherits the whole list — including
third-party tools you shell out to.

## What you will do

Four labs on the real system underneath you:

- Create your own dotfiles in a disposable home directory and determine, by
  experiment, exactly which shell modes read which files.
- Measure four different PATHs on one machine, find why `capsh` disappears when
  you log in, and discover what bash falls back to when PATH is unset.
- Watch a secret survive being unset, and compare the four routes a password can
  take into a process.
- Take a job that works for the engineer who wrote it and fails on a schedule,
  find both faults, and fix it so it cannot depend on anybody's shell.

:::objective{id=OBJ-B06.4.1}
:::

:::objective{id=OBJ-B06.4.2}
:::

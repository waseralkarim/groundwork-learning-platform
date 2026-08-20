---
topic: topic.environment-and-shell-startup
section: internals
title: The snapshot, and who can read it
order: 3
mode: explain
---

There are two environments for every process and most tooling does not
distinguish them. One is live; the other was frozen at `execve` and never
changes again.

:::diagram{src=../diagrams/environ-snapshot.mmd caption="The live copy is what the process sees. /proc/PID/environ is what it was handed, and it is permanent."}
:::

## Proving they are different

`/etc/bash.bashrc` is not involved; this is the process's own memory:

```console
$ export LATE_VAR=added-after-exec
$ env | grep -c LATE_VAR
1
$ tr '\0' '\n' < /proc/$$/environ | grep -c LATE_VAR
0
```

The variable exists — `env` prints it, children inherit it — and it is not in
`/proc/$$/environ`, because that region records what the kernel copied in at
`execve` and nothing updates it afterwards.

Run it the other way and the consequence gets serious:

```console
$ unset API_TOKEN
$ env | grep -c API_TOKEN
0
$ tr '\0' '\n' < /proc/$$/environ | grep API_TOKEN
API_TOKEN=tok-abc123
```

**`unset` removed it from the live copy and not from the snapshot.** The value is
readable for as long as the process exists. A process that reads a credential
from its environment and dutifully unsets it has not removed the credential from
the machine — it has removed it from its own view of itself.

What *does* clear it is a fresh `execve` without the variable:

```console
$ env -u API_TOKEN bash -c 'tr "\0" "\n" < /proc/$$/environ | grep -c API_TOKEN'
0
```

And children started *after* the unset do not inherit it, because they are
copied from the live list. So the mitigation is real and partial in a specific
way — it protects the children and not the process itself.

:::warning
This is worth stating plainly because it appears in security reviews as a
completed control: **"the application unsets the secret after startup" does not
remove it from `/proc/PID/environ`.** Anything that can read that path — the same
user, root, a debugger, a core dump, a container escape — still gets the value.
:::

## A redirect reads it differently from `cat`

A detail that will waste your time exactly once:

```console
$ cat /proc/self/environ | wc -c
200
$ wc -c < /proc/self/environ
0
```

Same path, same shell, two answers. With `cat`, `/proc/self` resolves to the
`cat` process, which was handed a copy of the environment. With the redirect the
file is opened before the program is exec'd, and the descriptor no longer refers
to anything useful by the time it is read.

The rule to carry: **use `/proc/$$/environ` or an explicit PID, not
`/proc/self/environ`, whenever a redirect is involved.** `/proc/$$/environ` is
the shell's own snapshot and always behaves.

## Who else can read it

Four exposures, and they compound rather than overlap.

**The same user, through `/proc`.** The file is `0400`, owner-only — which means
every process running as that user can read every other one's:

```console
$ stat -c '%A %U' /proc/1234/environ
-r-------- learner
```

**Anyone who can run `ps`.** No `/proc` archaeology required:

```console
$ ps eww -p 1234
  PID TTY      STAT   TIME COMMAND
 1234 ?        S      0:00 sleep 30 DB_PASSWORD=s3cr3t-from-compose HOME=/home/...
```

**Anyone who can reach the container runtime.** From the host, with no access to
the container at all:

```console
$ docker inspect <id> --format '{{range .Config.Env}}{{println .}}{{end}}'
API_TOKEN=tok-abc123
```

That is stored in the container's configuration on disk, survives the container
stopping, and is visible to anyone in the `docker` group — which is root
equivalence anyway, but it also means the secret is now in whatever backs up
`/var/lib/docker`, and in the orchestrator's API, and quite possibly in an audit
log of the API call that created it.

**Every child process**, including third-party ones. A credential exported for
your application is in the environment of every tool it shells out to, and
anything one of those tools logs on error may contain it.

## What a file gives you instead

The comparison is not "environment is insecure and files are secure" — it is
that a file has properties an environment variable cannot have:

| | Environment variable | File, mode `0400` |
|---|---|---|
| Readable by same-user processes | yes | only by the owner, and only if opened |
| In `ps eww` | **yes** | no |
| In `/proc/PID/environ` | **yes, permanently** | no |
| In `docker inspect` | **yes** | no — only the mount path |
| Inherited by every child | **yes** | no |
| Revocable while running | no | **yes — delete or rotate it** |
| Can be watched for change | no | **yes** |

The last two are what actually decides it. A variable is fixed for the life of
the process, so rotating a credential means restarting everything that holds it.
A file can be replaced underneath a running process, which is what makes short
credential lifetimes practical at all.

None of this makes environment variables wrong for configuration. A log level, a
region, a feature flag — those want to be variables. It makes them a poor
container for anything you would have to rotate after a leak.

## Why systemd and cron look hostile

They are not stripping your environment; they never had it.

`cron` runs jobs from a bare environment with a minimal PATH — typically
`/usr/bin:/bin` — plus `HOME`, `LOGNAME` and `SHELL`. It reads no dotfiles.
`systemd` services start from the manager's environment plus whatever the unit
declares, with `HOME=/` unless `User=` is set. A CI runner constructs its own,
usually prepending toolchain directories.

All three are doing the correct thing: **a scheduled job should not depend on
whose shell last edited a dotfile.** The environment you get is deliberately
minimal so that the job is reproducible, and the price is that everything it
needs has to be declared where the scheduler can see it.

:::objective{id=OBJ-B06.4.5}
:::

:::objective{id=OBJ-B06.4.6}
:::

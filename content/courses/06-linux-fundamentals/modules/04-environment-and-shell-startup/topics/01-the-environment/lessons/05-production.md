---
topic: topic.environment-and-shell-startup
section: production
title: Declaring instead of inheriting
order: 5
mode: explain
---

Everything in this topic points one way: **an environment a job inherits is an
environment nobody chose.** The production practice is to stop inheriting.

## Why "it works when I run it" is not evidence

When somebody says that, they are reporting that their shell — after reading
`/etc/profile`, a profile file, `/etc/bash.bashrc` and `~/.bashrc`, accumulated
over years by several people — happened to contain what the job needed.

That is not a property of the job. Turn the sentence into a list instead:

```bash
bash -lic 'env' | sort > /tmp/theirs.env
bash -c   'env' | sort > /tmp/scheduler.env
diff /tmp/theirs.env /tmp/scheduler.env
```

Every line of that diff is something a dotfile did, and one of them is the bug.
It is usually five to twenty lines, and it takes a minute.

## The three schedulers, and what each actually gives you

| | PATH | HOME | Reads dotfiles |
|---|---|---|---|
| **cron** | `/usr/bin:/bin` | the user's | no |
| **systemd** | a full default PATH | `/` unless `User=` is set | no |
| **CI runner** | toolchain dirs prepended | the runner's | no |

`cron` is the harshest and the most surprising, because its PATH is shorter than
anything a human ever sees. A job calling something in `/usr/local/bin` — where
your own tools live by convention — fails, and the message is `command not
found` with no hint that PATH is the reason.

`systemd`'s `HOME=/` catches a different class: anything that writes a cache or
config under `$HOME` tries to write to the root directory and fails, often with
a permissions error that sends people looking at the wrong thing entirely.

The fixes are all "declare it where the scheduler can see it":

```text
# crontab — applies to every job in this crontab
PATH=/usr/local/bin:/usr/bin:/bin
MAILTO=platform-alerts@example.com

0 2 * * * /usr/local/bin/nightly-report
```

```ini
# systemd unit
[Service]
Environment=REPORT_DIR=/var/lib/reports
EnvironmentFile=/etc/reporting/env
ExecStart=/usr/local/bin/nightly-report
User=reporting
```

## Make the script refuse rather than guess

The strongest single change is to stop scripts from depending on inheritance at
all. Three lines:

```bash
set -euo pipefail

: "${REPORT_DIR:?REPORT_DIR must be set}"
: "${LEDGER_FILE:?LEDGER_FILE must be set}"
```

`${VAR:?message}` exits immediately with that message if the variable is unset.
The job now fails at line 3 with a sentence naming the problem, instead of at
line 40 with something obscure — or, far worse, succeeding against the wrong
path because the variable defaulted to empty and the path became `/report.txt`.

For PATH, prefer being explicit over hoping:

```bash
PATH=/usr/local/bin:/usr/bin:/bin
export PATH
```

Or use absolute paths for the handful of commands that matter. Both are
defensible; what is not defensible is a script whose behaviour depends on who
launched it.

:::warning
Never write a bare `PATH=` or unset PATH. Bash's compiled-in fallback ends in
`.` — the current directory. It is searched last, so it cannot shadow a real
command; what it does is turn a **missing** command into a silent success,
running whatever is in the working directory. A wrong PATH fails loudly, and an
unset one does not.
:::

## Testing the way it will actually run

You can reproduce a scheduler on your own terminal, which beats waiting for 02:00:

```bash
# roughly cron
env -i PATH=/usr/bin:/bin HOME="$HOME" SHELL=/bin/sh bash ./nightly-report

# roughly a systemd unit
env -i PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin \
       HOME=/ bash ./nightly-report

# what CI gives you
bash -c ./nightly-report
```

Put the first of those in the repository as a test. A job that has never been run
without a human's environment has not been tested, and the first honest run
happens at 02:00 on a Sunday.

## Secrets: what each route exposes

Environment variables are the default because they are convenient, and the
convenience is real. What they cost is worth knowing precisely rather than
vaguely:

| | `-e VAR=secret` | `--env-file` | file at `/run/secrets` |
|---|---|---|---|
| In `ps eww` | **yes** | **yes** | no |
| In `/proc/PID/environ`, permanently | **yes** | **yes** | no |
| In `docker inspect` | **yes** | **yes** | no |
| Inherited by every child | **yes** | **yes** | no |
| Survives `unset` in the process | **yes** | **yes** | n/a |
| Rotatable without a restart | no | no | **yes** |

`--env-file` improves one thing only — the secret is not in your shell history
or the process list of whoever ran `docker run`. Once the container is up it is
an environment variable like any other, and `docker inspect` shows it.

The last row is the one that decides it in practice. A variable is fixed for the
life of the process, so rotating a credential means restarting everything that
holds it — which is why estates with environment-variable secrets tend to have
credentials that are years old. A file can be replaced underneath a running
process, and that is what makes short-lived credentials workable at all.

**A reasonable position:** configuration in environment variables, secrets in
files, and if a secret must be a variable, treat its lifetime as the lifetime of
the process and plan the rotation around a restart.

And do not claim a mitigation you do not have. `unset` after reading leaves the
value in `/proc/PID/environ` for the life of the process — it protects future
children, and nothing else.

## What to take from this topic

- **Two independent questions** — login and interactive — decide which files a
  shell reads, and the automation shell reads none of them.
- **A login shell does not read `~/.bashrc`.** It works because the default
  `~/.profile` sources it, which is a file people overwrite.
- **Guard anything that prints** in a startup file with an interactivity check,
  or you break `scp` and `rsync` in a way nobody will diagnose quickly.
- **PATH is constructed differently** by the image, by `/etc/profile` and by
  bash's fallback — and a login shell's is narrower than a script's.
- **`/proc/PID/environ` is a snapshot at exec**, so it answers "what was this
  started with" and never "what does it have now".
- **Declare, do not inherit.** `${VAR:?}` at the top of a script converts an
  invisible dependency into a one-line failure.

:::objective{id=OBJ-B06.4.4}
:::

:::objective{id=OBJ-B06.4.8}
:::

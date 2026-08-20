---
topic: topic.environment-and-shell-startup
section: core-concepts
title: Two questions, four answers
order: 2
mode: explain
---

Everything about startup files follows from two independent properties of a
shell. Get these separate and the rest is bookkeeping.

**Is it a login shell?** Started by `login`, by `ssh` opening a session, by `su
-`, or with `-l`. Login shells read `/etc/profile` and then **the first one that
exists** of `~/.bash_profile`, `~/.bash_login`, `~/.profile`.

**Is it interactive?** Reading commands from a terminal rather than from a file
or `-c`. A *non-login* interactive shell reads `/etc/bash.bashrc` and then
`~/.bashrc`.

Neither implies the other.

:::diagram{src=../diagrams/startup-matrix.mmd caption="Two independent questions — and one corner where the answer is not what the summary suggests."}
:::

## The corner the summary gets wrong

Almost every explanation of this says "login shells read the profile files,
interactive shells read the bashrc files". That is close, and it is wrong in one
corner that matters:

**A login shell does not read `~/.bashrc`.** Not even an interactive one. Measure
it — `~/.bashrc` sets `FROM_BASHRC`, `~/.profile` sets `FROM_PROFILE`:

```console
$ bash -lic 'echo ${FROM_PROFILE:-no}/${FROM_BASHRC:-no}'
1/no
$ bash -ic  'echo ${FROM_PROFILE:-no}/${FROM_BASHRC:-no}'
no/1
```

The reason it appears to work on a normal machine is that **the default
`~/.profile` sources it**, explicitly:

```sh
if [ -n "$BASH_VERSION" ] && [ -f "$HOME/.bashrc" ]; then
  . "$HOME/.bashrc"
fi
```

So `~/.bashrc` reaching a login shell is a convention implemented in a file you
can overwrite — and people overwrite it constantly, then spend an afternoon
wondering why their aliases work in a terminal tab and not after `ssh`.

`/etc/bash.bashrc` arrives by the same trick, from `/etc/profile`:

```sh
if [ "${PS1-}" ]; then
  if [ "${BASH-}" ] && [ "$BASH" != "/bin/sh" ]; then
    if [ -f /etc/bash.bashrc ]; then
      . /etc/bash.bashrc
    fi
  fi
```

Note the `$PS1` test: that is `/etc/profile` checking whether the shell is
interactive. Which is why a **login, non-interactive** shell — `ssh host 'cmd'` —
gets `/etc/profile` and not `/etc/bash.bashrc`.

## And that explains the guard nobody explains

Every distribution's `~/.bashrc` opens with this, and almost nobody knows why:

```sh
# If not running interactively, don't do anything
case $- in
    *i*) ;;
      *) return;;
esac
```

`~/.profile` sources `~/.bashrc` **unconditionally**, and `~/.profile` runs for
*non-interactive* login shells too. Without the guard, `ssh host 'cat file'`
would execute your aliases, your prompt setup and anything that prints — and
output from a startup file lands in the middle of the data stream, corrupting
`scp`, `rsync` and `git push` over ssh.

Debian says so in the first line of the file it ships:

```text
# ~/.bashrc: executed by bash(1) for non-login shells.
```

**Never print anything from a startup file without checking that the shell is
interactive.** It is the single most common way to break file transfer over ssh,
and the error it produces names neither the shell nor the file.

## The first-match rule, which silently disables things

Login shells read the **first** of `~/.bash_profile`, `~/.bash_login`,
`~/.profile` — not all of them. Adding a `~/.bash_profile` therefore stops
`~/.profile` from being read at all, with no warning:

```console
$ cat ~/.profile        ; # export FROM_PROFILE=yes
$ bash -lc 'echo ${FROM_PROFILE:-none}'
yes

$ echo 'export WHICH=bash_profile' > ~/.bash_profile
$ bash -lc 'echo ${WHICH:-none}/${FROM_PROFILE:-none}'
bash_profile/none
```

`FROM_PROFILE` did not change and is no longer set. This is the standard way
people lose their PATH after installing a tool whose installer helpfully creates
a `~/.bash_profile` — which is why most `~/.bash_profile` files you will see
contain nothing but a line sourcing `~/.profile` or `~/.bashrc`.

## Where each thing actually belongs

| Put it in | If it must be present for |
|---|---|
| `~/.bashrc` | interactive shells — aliases, prompt, completion |
| `~/.profile` | every login session, including `ssh host 'cmd'` |
| the unit / crontab / CI config | **anything a machine runs** |

The third row is the important one and it is not a dotfile. A scheduled job's
environment has to come from the scheduler, because no dotfile is consulted.

:::note
`/etc/environment` exists on this image, is **empty**, and no shell reads it. It
is consumed by PAM during login. In a container there is usually no PAM at all,
so variables put there have no effect whatsoever — a genuinely popular way to
configure nothing.
:::

## What non-interactive bash reads

Almost nothing, with one hook:

```console
$ echo 'export FROM_BASH_ENV=yes' > /tmp/benv.sh
$ BASH_ENV=/tmp/benv.sh bash -c 'echo $FROM_BASH_ENV'
yes
```

`BASH_ENV` is the only startup file a non-interactive bash will read. It is
almost never set, and it is worth knowing for two opposite reasons: it is
occasionally the right tool for making a wrapper apply to every script, and it
is a persistence mechanism worth checking when a machine is behaving strangely.

## The environment itself

A process's environment is a list of `KEY=VALUE` strings handed to it at
`execve`. There is no lookup, no registry and no inheritance in the object-
oriented sense — a copy is made, once, and after that the two are unrelated.

```console
$ FOO=bar                     # a shell variable
$ bash -c 'echo ${FOO:-unset}'
unset

$ export FOO=bar              # now it is in the environment
$ bash -c 'echo ${FOO:-unset}'
bar
```

`export` is the whole difference. Without it the variable exists in that shell
and nowhere else, which is why a script that "sets" a variable cannot change its
parent — the copy went the other way.

Three consequences worth having ready:

- **Editing `~/.bashrc` does nothing to running processes.** They took their copy
  at start. A long-running daemon has the environment it was launched with,
  possibly years ago.
- **A child cannot change its parent's environment.** Anything that appears to —
  `source`, `eval "$(...)"` — is running commands *inside* the parent rather than
  in a child.
- **Every child gets the whole list**, including tools you did not write. A
  credential exported for one program is visible to everything that program
  shells out to.

## PATH, and where it comes from

PATH is an ordinary environment variable with one special role: it is the
ordered list of directories the shell searches for a command. On this machine
three different things set it, and they disagree.

**The image** sets one via Docker's `ENV`, and it is what any process inherits
by default:

```console
$ tr '\0' '\n' < /proc/1/environ | grep ^PATH
PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
```

**`/etc/profile`** replaces it in login shells, and branches on who you are:

```sh
if [ "$(id -u)" -eq 0 ]; then
  PATH="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
else
  PATH="/usr/local/bin:/usr/bin:/bin:/usr/local/games:/usr/games"
fi
```

Root keeps the `sbin` directories; everyone else gets `games` instead. So
logging in as a normal user makes your PATH **narrower** than a script's.

**Bash's compiled-in fallback** applies when PATH is not set at all:

```console
$ env -u PATH bash -c 'echo $PATH'
/usr/local/bin:/usr/local/sbin:/usr/bin:/usr/sbin:/bin:/sbin:.
```

Note the final entry. **`.` — the current directory.** It is searched *last*, so
it cannot shadow a real command — `ls` still resolves to `/usr/bin/ls`. The
hazard is the opposite one: a command that **should** have failed with
`command not found` silently succeeds instead, running whatever happens to be in
the working directory.

That is why a bare `PATH=` in a script is worse than a wrong PATH. A wrong PATH
fails loudly; an unset one turns a missing tool, a typo, or a helper that was
never installed into silent execution of a file somebody else may have chosen.

:::objective{id=OBJ-B06.4.3}
:::

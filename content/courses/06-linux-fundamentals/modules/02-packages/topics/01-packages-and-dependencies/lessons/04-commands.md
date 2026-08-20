---
topic: topic.packages-and-dependencies
section: commands
title: The commands, and which tool answers which question
order: 4
mode: do
---

There are two tools and they answer different questions. Reaching for the wrong
one is the most common way to conclude a machine is broken when it is not.

- **`dpkg` / `dpkg-query`** — what is installed *here*. Reads the local
  database. Works offline, works with no network, works in a container whose
  archive lists were deleted.
- **`apt` / `apt-cache` / `apt-get`** — what is *available*, and how to get from
  here to there. Needs archive metadata, which container images routinely delete.

If a command needs to know about a package you do not have, it is an `apt`
question and it may not work in a stripped image.

## What is installed

```bash
dpkg-query -W -f='${Package} ${Version}\n'          # every package, exact version
dpkg-query -W -f='${Version}' openssl               # one package, exact version
dpkg -l | grep openssl                              # human listing — TRUNCATES
```

Use `dpkg-query -W` when the answer matters. `dpkg -l` pads to terminal width
and cuts long version strings, which is precisely where the interesting suffix
lives.

The status field is worth reading rather than assuming:

```bash
dpkg-query -W -f='${Status}\n' xauth
# unknown ok not-installed     <- never installed
# install ok installed         <- normal
# deinstall ok config-files     <- removed, config left behind
```

That third state matters: `remove` leaves configuration behind, `purge` does
not. A machine can be full of packages that are gone but not gone.

## Which package owns this file

```bash
dpkg -S /usr/bin/openssl                    # path -> package
dpkg -S "$(readlink -f /usr/bin/awk)"       # resolve first; alternatives hide the owner
dpkg -L openssl                             # package -> every path it owns
dpkg -L openssl | grep bin/                 # ...just the binaries
```

Two facts about `dpkg -S` that cost people time:

- It matches **substrings**, not just exact paths, so `dpkg -S bin/ls` works and
  `dpkg -S ls` returns a great deal of noise. Give it a full path.
- It knows nothing about symlinks. Resolve the path yourself.

## Reading the metadata

```bash
dpkg-query -W -f='${Depends}\n' coreutils
dpkg-query -W -f='${Pre-Depends}\n' coreutils
dpkg-query -W -f='${Essential}\n' bash
dpkg-query -W -f='${Priority}\n' bash
dpkg-query -W -f='${Conffiles}\n' bash
dpkg-query -W -f='${Installed-Size}\n' gcc     # in kilobytes
```

Any field in the control file works inside `-f`. That makes `dpkg-query` a
general reporting tool — the closure summary, an inventory, a size ranking, all
of it is one format string.

```bash
# the ten largest packages on this machine
dpkg-query -W -f='${Installed-Size}\t${Package}\n' | sort -rn | head -10
```

## Dependencies, both directions

```bash
apt-cache depends openssl                    # what it needs
apt-cache rdepends --installed libssl3t64    # what needs it
apt-cache show openssl                       # the full stanza
```

`rdepends` is the one to reach for before removing anything. It answers "who
would this break" without needing to simulate.

## Asked for, versus pulled in

```bash
apt-mark showmanual        # what somebody asked for
apt-mark showauto          # what came as a consequence
apt-mark manual <pkg>      # "I rely on this directly" — protects it from autoremove
```

Marking a package manual is how you record a dependency you have started using
directly. It is a one-word fix for a whole category of "autoremove broke
production".

## Simulating before doing

```bash
apt-get -s remove openssh-client       # -s: simulate. no root needed, no changes
apt-get -s remove openssl
apt-get -s autoremove
```

`-s` is the habit worth building. It runs the solver and prints the plan without
touching anything, and it works as an unprivileged user — so there is no excuse
for finding out what a removal cascades into by performing it.

The three outcomes you will see:

```text
Remv openssh-client                    # a leaf. nothing depends on it.
Remv ca-certificates
Remv openssl                           # a cascade. it took something with it.
E: Unable to satisfy dependencies      # refused. something Pre-Depends on it.
```

## Verifying what is on disk

```bash
dpkg -V                                # verify everything
dpkg -V bash                           # verify one package
dpkg -V | grep -v '^missing'           # the signal, minus the slim-image noise
find /etc -name '*.dpkg-*'             # upgrades that did not fully apply
```

`dpkg -V` output is `<flags> [c] <path>`. Nine flag positions, `?` for "not
checked"; in practice you are reading the third, where `5` means the md5 does
not match. A `c` before the path marks a conffile — which usually means *you*
changed it, and is the one case where a finding is not alarming.

## The command that answers nothing

```console
$ dpkg -S /usr/local/bin/acme-agent
dpkg-query: no path found matching pattern /usr/local/bin/acme-agent
```

Worth practising as a deliberate move rather than meeting by accident. When
auditing a machine, run `dpkg -S` over the binaries in `PATH` and see what comes
back empty — that list is the software nobody is patching.

```bash
# every binary in the usual places that no package owns
for f in /usr/local/bin/* /usr/local/sbin/* /opt/*/bin/*; do
  [ -e "$f" ] || continue
  dpkg -S "$(readlink -f "$f")" >/dev/null 2>&1 || echo "unowned: $f"
done
```

:::try{lab=what-put-this-file-here}
:::

:::objective{id=OBJ-B06.2.1}
:::

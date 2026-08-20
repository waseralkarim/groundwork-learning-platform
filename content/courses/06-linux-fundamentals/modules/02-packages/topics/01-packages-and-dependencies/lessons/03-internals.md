---
topic: topic.packages-and-dependencies
section: internals
title: Relationships, conffiles, and what cannot be removed
order: 3
mode: explain
---

The dependency declaration is the part of a package that does real work, and it
has more than one strength. Treating them as interchangeable is the source of an
entire class of production surprise.

## Four strengths, two guarantees

```console
$ apt-cache depends openssh-client
openssh-client
  Depends: libc6
  Depends: libssl3t64
  Depends: passwd
  Recommends: <xauth>
  Suggests: <keychain>
  Suggests: <libpam-ssh>
```

| Field | Installed automatically? | What it promises |
|---|---|---|
| **Pre-Depends** | yes | present and configured *before unpacking starts* |
| **Depends** | yes | present and configured before this is configured |
| **Recommends** | yes, by default | nothing — it is a strong opinion |
| **Suggests** | no | nothing at all |

Only the first two are guarantees. **`Recommends` is the dangerous one**,
because it is installed by default, so software that depends on it works
everywhere the author looked — right up until somebody builds an image with
`--no-install-recommends`, which every container guide on earth tells them to do.

On this system, that is not hypothetical:

```console
$ dpkg-query -W -f='${Status}\n' xauth
unknown ok not-installed
```

`openssh-client` recommends `xauth`; the image build skipped it. Anything here
relying on X11 forwarding through SSH would fail with a message about `xauth`
not being found, on a machine where `ssh` is definitely installed.

:::warning
`--no-install-recommends` is good advice and it changes the contract. You are
declaring that you will find and install the missing pieces yourself. Most
people take the flag and skip the second half.
:::

Three more fields you will meet, all about incompatibility rather than need:

- **`Provides`** — a virtual name several packages can satisfy. On this machine
  `mawk` provides `awk`, and so would `gawk`: that is precisely what the
  `/usr/bin/awk` symlink is choosing between.
- **`Conflicts`** — cannot be installed together. `grep` both **provides** and
  **conflicts with** `rgrep`, which is the idiom for "exactly one package may
  supply this name". It is what lets something depend on a name without caring
  who supplies it. The canonical case is `mail-transport-agent`, where `exim`,
  `postfix` and `sendmail` all use the pattern.
- **`Breaks`** — weaker than Conflicts. The other package may remain installed
  but must be upgraded first. Real example, from here:

  ```console
  $ dpkg-query -W -f='${Breaks}\n' libssl3t64
  … openssh-client (<< 1:9.4p1), openssh-server (<< 1:9.4p1) …
  ```

  The current TLS library records that it breaks SSH older than `1:9.4p1`. A
  compatibility boundary somebody discovered once, written down so nobody has
  to discover it again.

## Pre-Depends is why some removals are impossible

Ask the system to remove the TLS library:

```console
$ apt-get -s remove libssl3t64
E: Unable to satisfy dependencies. Reached two conflicting decisions:
   1. libssl3t64:amd64 is selected for removal
   2. libssl3t64:amd64 is selected for install because:
      1. coreutils:amd64 is selected for install
      2. coreutils:amd64 Pre-Depends libssl3t64 (>= 3.0.0)
```

**`coreutils` pre-depends on the TLS library.** `ls`, `cp` and `mkdir` are in
the same package as `sha256sum` and `cksum`, and those link against OpenSSL. So
the crypto library and the file utilities are welded together, and neither can
leave.

That is worth sitting with, because it demolishes a common mental model. The
dependency graph is not organised the way you would organise it. You cannot
reason about what depends on what from the names; you have to ask.

:::predict{question="Before running it: how many packages would be removed if you removed openssl? And openssh-client?"}
:::

## Essential means the answer is no

Twenty-two packages on this system carry a flag that changes the rules:

```console
$ dpkg-query -W -f='${Package} ${Essential}\n' | grep ' yes$' | wc -l
22
```

```text
base-files base-passwd bash bsdutils coreutils dash debianutils diffutils
dpkg findutils grep gzip hostname init-system-helpers libc-bin ncurses-base
ncurses-bin perl-base sed sysvinit-utils tar util-linux
```

`Essential: yes` means the package system will refuse to remove it rather than
warn — the removal has to be forced past an explicit override. It is the set of
things assumed to be present by everything else, including the package manager
itself. `dpkg` is on the list, which is the system declaring that it cannot
uninstall itself.

Priority is a separate and softer axis:

```text
  119 optional
   33 required
    7 important
    3 standard
```

`Priority: required` marks the base system; `important` marks what a competent
administrator expects on any machine. Neither is enforced the way `Essential` is.

## Conffiles: the checksum that decides an upgrade

A package declares which of its files are *configuration* — files you are
expected to edit — and records a checksum for each at install time:

```console
$ dpkg-query -W -f='${Conffiles}\n' | grep -c '^ */'
75
```

Seventy-five tracked files. That checksum is what lets an upgrade answer a
question it otherwise could not: *did the administrator change this?*

:::diagram{src=../diagrams/conffile-decision.mmd caption="Four outcomes, and only one prompts. The dangerous branch is the unattended one, because it reports success."}
:::

The branch that causes incidents is the bottom right. During an unattended
upgrade nobody answers the prompt, the default applies, **your version is kept**,
and the maintainer's new version is written alongside as `.dpkg-dist`. The
upgrade exits zero. Six months later something needs an option that only exists
in the new default file, and the file on disk has never contained it.

```console
$ find /etc -name '*.dpkg-dist' -o -name '*.dpkg-old' -o -name '*.dpkg-new'
```

That command finds upgrades that silently did not fully apply. On a fleet that
has been running for years it is rarely empty, and nobody runs it.

:::note
This is also why configuration management exists. Conffile handling is a
reasonable answer for one machine with an administrator at the keyboard, and it
does not scale to four hundred machines being upgraded at 3am — so the fleet
answer is to own the file completely and stop letting the package ship it.
:::

## Integrity checking, and what it is worth here

Every non-configuration file also has a recorded checksum, which makes
verification possible:

```console
$ dpkg -V | wc -l
4634
```

Four thousand six hundred and thirty-four discrepancies on a freshly built
image. That number is not a compromise — it is the slim base image, which
deliberately strips documentation, man pages and locales:

```text
  4633  missing      /usr/share/{doc,man,lintian,locale}/...
     1  ??5??????    c /etc/bash.bashrc
```

**One real finding in 4,634 lines**, and it is a checksum mismatch on a conffile
of `bash` — caused by this platform's own Dockerfile appending a lab prompt to
it. The flags decode positionally: `5` in the third column means the md5 does
not match, and the `c` marks it as a conffile.

The lesson generalises well past `dpkg`. **An integrity check whose output is
99.98% expected noise is not an integrity check** — it is a wall that people
learn to walk past. Any control producing thousands of findings on a healthy
system will be ignored on an unhealthy one, and the failure will look exactly
like this.

:::objective{id=OBJ-B06.2.3}
:::

:::objective{id=OBJ-B06.2.5}
:::

---
topic: topic.distributions-and-versions
section: commands
title: Identifying a system and settling a version argument
order: 4
mode: explain
---

## What am I on

```bash
cat /etc/os-release

# the scriptable form — it is valid shell, so source it
. /etc/os-release
echo "$ID $VERSION_ID ($VERSION_CODENAME)"
```

Sourcing it is the idiom worth knowing: the file is deliberately written as
`KEY=value` shell assignments, so `.` gives you the fields as variables with no
parsing.

For a script that must handle several families:

```bash
. /etc/os-release
case "$ID $ID_LIKE" in
  *debian*) pkg=apt ;;
  *rhel*|*fedora*) pkg=dnf ;;
  *alpine*) pkg=apk ;;
  *) echo "unknown distribution: $ID" >&2; exit 1 ;;
esac
```

Matching on `$ID $ID_LIKE` together is what makes Ubuntu, Mint and every other
Debian derivative work without naming them.

:::try{lab=what-am-i-running run="cat /etc/os-release; echo '---'; command -v lsb_release || echo 'lsb_release: NOT INSTALLED'"}
The file is there and the tool people reach for is not. `lsb_release` is a
package rather than a guarantee, and a script depending on it fails on a
perfectly ordinary system.
:::

## What not to use

```bash
uname -a                    # the KERNEL — the host's, in a container
cat /etc/debian_version     # says "trixie/sid" on Ubuntu
lsb_release -a              # a package; frequently absent
cat /etc/*-release          # may match several files, order undefined
```

Each of these appears in real scripts and each fails somewhere specific. `uname`
is the worst in a container, because it reports the host's kernel and looks like
a correct answer.

## Reading a version

```bash
dpkg-query -W -f='${Version}\n' openssl      # exact, epoch included
dpkg-query -W -f='${Package} ${Version}\n' | head

# every package carrying an epoch
dpkg-query -W -f='${Package} ${Version}\n' | awk '$2 ~ /:/'
```

`dpkg-query -W` is the precise form. `dpkg -l` truncates long versions to fit
its columns, which is a real trap when the thing you are checking is a suffix.

:::try{lab=read-a-version-string run="dpkg-query -W -f='${Package} ${Version}\n' | awk '$2 ~ /:/' | head -5"}
Packages here carrying an epoch. Each one is a decision somebody made years ago
that every future version of that package must keep carrying.
:::

## Comparing versions

```bash
dpkg --compare-versions "3.5.6-1" lt "3.5.10-1" && echo older

# in a condition
if dpkg --compare-versions "$installed" lt "$required"; then
  echo "needs upgrading"
fi
```

It prints nothing and exits 0 or 1, which is what makes it usable. The operators
are `lt le eq ne ge gt`.

**Do not compare versions with anything else.** Not `[ "$a" \> "$b" ]`, which is
string comparison and gets `1.10` versus `1.9` wrong. Not `sort -V`, which is
close and does not implement epochs or `~`. Not a numeric conversion, which
cannot represent revisions.

If you are on a system without dpkg, `rpm --eval '%{lua:...}'` and `apk version
-t` are the equivalents; each distribution ships the comparison its own package
manager uses, and that is the one to borrow.

## Proving a backport

```bash
zcat /usr/share/doc/<pkg>/changelog.Debian.gz | head -30
```

On a full system this names the CVE and the date. On a slim container image it
does not exist — check before writing it into a runbook:

```bash
find /usr/share/doc -name 'changelog*' | wc -l     # 0 on debian:*-slim
```

Where it is absent, the distribution's online security tracker carries the same
data and is the thing to link in a ticket.

## What is in the archive

```bash
cat /etc/apt/sources.list /etc/apt/sources.list.d/*.sources 2>/dev/null
```

Modern Debian and Ubuntu use the deb822 format in `.sources` files rather than
the single-line `sources.list`. A script that greps only `sources.list` will
find nothing on a current system and conclude there are no repositories
configured, which is a wrong answer that looks like a finding.

## The five worth keeping

```bash
. /etc/os-release && echo "$ID $VERSION_ID"        # what am I on
dpkg-query -W -f='${Version}\n' <pkg>               # what version, exactly
dpkg --compare-versions "$a" gt "$b"                # settle it properly
dpkg-query -W -f='${Package} ${Version}\n' | awk '$2 ~ /:/'   # find the epochs
find /usr/share/doc -name 'changelog*' | wc -l      # can I prove a backport here
```

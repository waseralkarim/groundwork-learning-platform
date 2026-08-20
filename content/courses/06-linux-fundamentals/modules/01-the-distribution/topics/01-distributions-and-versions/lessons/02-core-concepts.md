---
topic: topic.distributions-and-versions
section: core-concepts
title: Identity, and what a version records
order: 2
mode: explain
---

## Identifying a system, portably

```bash
cat /etc/os-release
```

```text
PRETTY_NAME="Debian GNU/Linux 13 (trixie)"
NAME="Debian GNU/Linux"
VERSION_ID="13"
VERSION_CODENAME=trixie
ID=debian
```

The fields that matter for a script are **`ID`** and **`VERSION_ID`**, because
they are stable and machine-readable. `PRETTY_NAME` is for humans and its format
is not guaranteed. `VERSION_CODENAME` matters because package archives are
addressed by codename rather than by number.

Two more fields appear on derivatives and are worth knowing:

```text
ID=ubuntu          ID_LIKE=debian        # Ubuntu
ID=rocky           ID_LIKE="rhel centos fedora"
```

**`ID_LIKE`** is how a script says "I do not know this distribution
specifically, but it behaves like one I do". It is the correct hook for
"use apt here, dnf there" logic, and it is far better than guessing from the
presence of a binary.

The file exists at `/etc/os-release` and `/usr/lib/os-release`, the second being
the vendor's copy for systems where `/etc` may be empty. Reading either is fine;
`/etc` wins where both exist.

## Why the alternatives are worse

You will find all of these in real scripts, and all of them have failed
somewhere:

| Approach | Why it fails |
|---|---|
| `lsb_release -a` | A **package**, not a guarantee. Not installed on this container, on Alpine, or by default on RHEL derivatives. |
| `/etc/debian_version` | Says `trixie/sid` on **Ubuntu**. Identifies a lineage, not a distribution. |
| `uname -a` | Reports the **kernel**. In a container that is the host's kernel and says nothing about the userland you are in. |
| `cat /etc/*-release` | Often works, may match several files, and the output order is undefined. |
| Checking for `/etc/redhat-release` | Works until a derivative moves it. |

The container in the lab makes the first one concrete: `lsb_release` is simply
not there, and a script depending on it fails on a system that is otherwise
perfectly ordinary.

:::warning
`uname` is the one that catches people in containers specifically. A Debian
container on a Ubuntu host reports Ubuntu's kernel version, so a script that
branches on `uname` will branch on the **host**, not on the filesystem it is
actually running against. That is a wrong answer that looks like a right one.
:::

## What a version string records

```text
4 : 14.2.0 - 1
│    │       └── distribution revision
│    └── upstream version
└── epoch
```

:::diagram{src=../diagrams/version-anatomy.mmd caption="Three components compared in order, and two suffixes that sort in opposite directions"}
:::

**Upstream version** is what the software's own authors released. It is the only
part they know about, and the only part a CVE will usually mention.

**Distribution revision** counts what the distribution did to that same upstream
release. `-1` is the first packaging of it; `-2` means the distribution changed
something — a patch, a build fix, a **backported security fix**. This is where
"our version is old but not vulnerable" lives.

**Epoch** is a manual override, and it exists for one reason: upstream
versioning sometimes goes backwards. A project releases `2007.11`, then renames
its scheme and releases `1.0`. Normal comparison says the new release is older,
so the upgrade never happens. Bumping the epoch forces the ordering, permanently
— **an epoch can never be removed**, because doing so would make the next
version compare as older.

`gcc` here is `4:14.2.0-1`. That `4` is a decision somebody made years ago and
every future gcc package will carry it.

## Suffixes, and the two that sort in opposite directions

```text
3.5.6-1~deb13u2     a Debian 13 update — security or point release
5.2.37-2+b9         a binary NMU: rebuilt, no source change
1.0~rc1             a pre-release
```

The rule that makes pre-releases work: **`~` sorts before nothing at all.** So
`1.0~rc1 < 1.0`, and a release candidate is correctly older than the release it
precedes. Without that character there would be no way to express it — `1.0rc1`
sorts *after* `1.0`.

And `+` sorts after nothing, which is why `2.0-1+b1 > 2.0-1` — a rebuild is
newer than what it rebuilt.

:::predict{question="A vendor ships version `2024.05` of a tool, then re-numbers to semantic versioning and ships `1.0.0`. You package both. What happens on upgrade, and what is the fix?"}

Nothing happens: `1.0.0` compares as *older* than `2024.05`, because the first
component is compared numerically and 1 is less than 2024. Every machine stays
on the old release and the package manager reports it as up to date.

The fix is an **epoch**: package the new one as `1:1.0.0`, which beats anything
without an epoch regardless of the rest of the string. And it is permanent —
every subsequent release must carry `1:` forever, because dropping it would make
the next version compare as older and strand everyone again.

This is exactly why `gcc` carries a `4:`, and why epochs are rare, deliberate,
and never reversed.

## Comparison is not string comparison

Three rules, and each has caused real failures:

**Numeric, in parts.** `1.10 > 1.9`, because 10 > 9. String comparison says the
opposite, and shell `[ "$a" \> "$b" ]` does string comparison.

**Epoch first, and decisively.** `1:1.0 > 99.0`. An epoch is compared before
anything else, so a package with one always beats a package without one.

**Revision last.** `3.5.6-2 > 3.5.6-1`, so a security backport is correctly
newer than the release it patches.

The tool that settles it:

```bash
dpkg --compare-versions "$a" gt "$b" && echo newer
```

It exits 0 or 1 and prints nothing, which makes it usable in a condition. If you
are comparing versions in a script by any other means, you are probably wrong in
at least one of the nine cases the lab tests.

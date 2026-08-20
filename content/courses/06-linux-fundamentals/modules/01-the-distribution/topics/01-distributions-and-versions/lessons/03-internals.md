---
topic: topic.distributions-and-versions
section: internals
title: Release models, and what a backport does to a scanner
order: 3
mode: explain
---

## Three release models

**Fixed.** Versions freeze at release and change only for security fixes and
grave bugs. Debian stable, RHEL, Ubuntu LTS. You get a system that behaves the
same in November as it did in January, and software that is progressively
further behind upstream. Upgrading is an event you schedule.

**Rolling.** Continuously updated, always close to upstream. Arch, openSUSE
Tumbleweed, Alpine edge. You get current software and no upgrade event — and no
moment at which the system is known to be unchanging, which is exactly what a
change-managed environment needs.

**Long-term support.** A fixed release with a support commitment measured in
years. What is supported is almost always *security fixes only* — the versions
do not move, and the commitment is that somebody will keep backporting.

The trade is the same one every time: **predictability against currency**, and
the honest way to choose is to ask which one your failure mode is. A fleet that
cannot tolerate surprise changes wants fixed. A workstation whose owner wants
this week's tooling wants rolling. Neither is more serious than the other.

## What "supported until 2030" actually promises

Less than it sounds, and it is worth reading precisely:

- **Security fixes for packages in the archive**, usually backported rather than
  upgraded.
- **Not** new features, not new upstream versions, and frequently not every
  package — many distributions have a smaller "supported" subset than their
  archive.
- Often tiered: full support for some years, then a longer period of critical
  fixes only.

So an LTS commitment is a promise that somebody will keep patching what you
already have. If you need a newer version of something, the support lifetime
does not help you and you are stepping outside the archive.

## Backporting, and the argument it lets you win

A backport takes a fix from a newer upstream release and applies it to the older
one. The bug goes away; the version number does not change.

```text
upstream:  3.5.6 (vulnerable) → 3.5.9 (fixed)
Debian:    3.5.6-1~deb13u2    ← the fix from 3.5.9, applied to 3.5.6
```

This has one large practical consequence: **version-based vulnerability scanning
against a stable distribution is wrong by default.** A scanner comparing `3.5.6`
against "fixed in 3.5.9" reports you vulnerable when the fix has been in place
for weeks.

What to do about it:

- Use a scanner that understands distribution security data — the distribution
  publishes exactly which package versions carry which fix.
- When triaging a finding, check the distribution's own security tracker before
  anything else. The question is not "is my version below the fixed version" but
  "has my distribution shipped the fix".
- Read the changelog, which records backports explicitly with the CVE named:
  `zcat /usr/share/doc/<pkg>/changelog.Debian.gz`

That last one has a catch worth finding out about now rather than during a
triage. On this lab image it does not work — **there are no changelogs at all**:

```bash
$ find /usr/share/doc -name 'changelog*' | wc -l
0
```

`debian:13-slim` excludes documentation deliberately, via a dpkg configuration
fragment that ships with the image:

```text
/etc/dpkg/dpkg.cfg.d/docker   →  "Many files which are normally unnecessary in
                                  containers are excluded, and this
                                  configuration file keeps them that way."
```

So the slim base image, chosen for size, has removed the evidence you would use
to prove a backport shipped. That is a real cost of a base-image decision that
nobody makes deliberately, and the answer in a container is to use the
distribution's **online** security tracker rather than the local changelog —
the data is the same and it is not in your image.

This is also the single most common source of noise in a container scanning
pipeline, and the reason a "critical" finding count is often close to
meaningless without that context.

:::warning
The inverse mistake is worse and does happen: assuming a backport exists because
the distribution is stable. It might not have shipped yet, or the package might
not be in the supported subset. "Stable therefore patched" is as wrong as
"version is old therefore vulnerable" — both replace checking with a rule of
thumb.
:::

## Derivatives

Ubuntu is built from Debian's archive; Rocky and Alma from RHEL's. A derivative
inherits most decisions and diverges on policy — release cadence, which packages
are supported, how long, and what is added.

Two things follow that matter operationally:

**`ID_LIKE` is the correct hook.** A script that handles `debian` should handle
`ubuntu` via `ID_LIKE=debian` rather than by listing every derivative it has
heard of.

**Inherited identity files lie.** `/etc/debian_version` on Ubuntu reports a
Debian codename, because Ubuntu *is* built from Debian. It is telling the truth
about lineage and answering a different question from the one asked.

## Where this shows up in containers

A container image *is* a distribution userland — the same archive, the same
policy, the same version strings. Everything here applies unchanged, and two
consequences are specific to images:

**The base image is a release choice** and usually an unexamined one. `FROM
debian:13-slim` commits you to that archive's policy for the life of the image,
and `FROM alpine` commits you to musl instead of glibc, which is a much larger
decision than the size saving that motivated it.

**A tag is not a version.** `debian:13-slim` moves as point releases ship, so two
builds a month apart contain different packages. That is usually what you want
for security and is not reproducible — which is the A04.1 digest-versus-tag
argument, arriving from a different direction.

## The commands that settle arguments

```bash
. /etc/os-release && echo "$ID $VERSION_ID ($VERSION_CODENAME)"

dpkg-query -W -f='${Version}\n' openssl        # the real version, epoch and all
dpkg --compare-versions "$a" gt "$b"           # the only comparison worth trusting

# what was backported — on a full system. Absent on slim images, so check
# whether it exists before relying on it in a runbook.
zcat /usr/share/doc/openssl/changelog.Debian.gz 2>/dev/null | head -20 \
  || echo "no changelog in this image — use the distribution's security tracker"
```

The first is what belongs in a script. The third is what settles a version
argument. And the fourth is what belongs in a ticket reply where it exists,
because it turns "we think it is patched" into a dated entry naming the CVE —
which is why noticing that your base image has removed it is worth doing before
you need it.

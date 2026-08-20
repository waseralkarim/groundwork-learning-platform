---
topic: topic.distributions-and-versions
section: production
title: Choosing a release, and living with the choice
order: 5
mode: explain
---

## The choice is a policy, not a logo

Nearly every distribution argument is really an argument about release policy,
and phrasing it that way makes it decidable:

**How often are you willing to be surprised?** Fixed releases surprise you on a
schedule you choose. Rolling releases surprise you continuously and in small
increments. Neither is safer; they fail differently.

**How long must this run without a major upgrade?** An appliance in the field
for seven years and a container rebuilt twenty times a day are opposite answers
to the same question.

**Who is patching it?** An LTS commitment is somebody else agreeing to keep
backporting. Stepping outside the archive — a third-party repository, a vendor
tarball, a compiled-from-source binary — moves that work to you, permanently and
usually silently.

**What do your dependencies require?** A kernel module, a specific glibc, a
database version. These are constraints rather than preferences and they
usually decide it.

## What stepping outside the archive costs

This is the decision that quietly creates the most work, and it is rarely made
deliberately. Every one of these takes a package out of the distribution's
support:

- A third-party apt repository for a newer version
- A vendor `.deb` downloaded and installed
- Something compiled from source into `/usr/local`
- A language package manager installing system-wide — `pip install`, `npm -g`

Each is reasonable in isolation. What they share is that **the distribution is
no longer patching that software and nobody has written down that it is now
yours.** The failure arrives years later as a CVE against something nobody
remembers installing.

If you must, the mitigations are dull and effective: record it somewhere the
team reads, pin the version, and put the thing that patches it on a schedule
with a name against it. This is A05.2's shared-responsibility lesson in a
different vocabulary — a layer with no owner and no error state.

## Containers change the calculation

A container image is a distribution userland with the same policy, and two
things shift:

**Lifetime collapses.** An image rebuilt on every deploy does not need a
five-year support commitment; it needs the base to be current at build time.
That argues for a fixed release with frequent point updates rather than for the
longest LTS available.

**Size becomes visible** in a way it is not on a VM, which is why `-slim` and
Alpine get chosen. Both have costs worth naming: slim variants strip
documentation — including the changelogs you would use to prove a backport — and
Alpine replaces glibc with musl, which is a genuine compatibility decision
rather than a size optimisation.

**And the tag moves.** `debian:13-slim` is a moving target: two builds a month
apart contain different packages. That is what you want for security patching
and it is not reproducible, which is the digest-versus-tag argument from A04.1
arriving from the packaging side. Pin by digest when you need to reproduce a
build; track the tag when you need the patches.

## Reading a version-based finding

A scanner reports `openssl 3.5.6` against a CVE fixed in `3.5.9`. Three
questions, in order:

1. **What is the full version?** `dpkg-query -W`, not the scanner's summary. If
   it ends `~deb13u2`, the distribution has revised it at least twice.
2. **Has the distribution shipped a fix?** Their security tracker is
   authoritative and the local changelog says so where it exists.
3. **Is this package in the supported set?** LTS commitments often cover a
   subset, and the answer for something from a third-party repository is no.

Most findings of this shape resolve at step 2, and a pipeline that cannot do
step 2 automatically produces a "critical" count that nobody can act on. That is
a tooling problem rather than a security one, and it is worth fixing precisely
because unactionable findings train people to ignore the actionable ones.

## What to write down when you choose

The decision is usually made once and questioned for years, so the reasoning
should outlive the person:

```text
Distribution and release:  Debian 13 (trixie), fixed
Why:                       predictable, 20+ deploys/day rebuild the image,
                           no kernel module or glibc constraint
Support until:             <date>, security fixes only
What we run outside it:    <list, with an owner each>
What would change this:    a dependency needing a newer glibc; a compliance
                           requirement for a vendor-supported OS; moving to
                           an appliance model with field lifetimes
Base image pinning:        tag in CI for patches, digest in release manifests
```

The last two lines are the ones that make it a decision rather than an accident.
Somebody arriving in two years can tell what would justify revisiting it, and
whether it still holds — which is the same discipline the A05 topics asked for
about layers and placement.

## The audit worth running

On an inherited fleet, four commands and one question:

```bash
. /etc/os-release && echo "$ID $VERSION_ID"          # what are we actually on
dpkg-query -W -f='${Package} ${Version}\n' | wc -l    # how much is installed
ls /etc/apt/sources.list.d/                           # what is outside the archive
find /usr/local -maxdepth 2 -type f -perm -111 | head # what was compiled in
```

Then: **for everything the last two commands found, who patches it?** On most
inherited systems the honest answer for at least one entry is "nobody, and we
had forgotten it was there" — which is the finding, and it is the one this topic
exists to make askable.

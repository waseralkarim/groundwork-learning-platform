#!/bin/bash
# Seeds the B06.1 distribution and version labs.
#
# Most of this topic needs no seeding at all, which is unusual and worth saying:
# a container knows exactly which distribution it is, and its package database
# is a real one with 160-odd real entries and real version strings. The labs
# read the actual system rather than a fixture.
#
# What is seeded is the material a single Debian container cannot provide:
# captured identity files from other distributions, so a learner can see that
# /etc/os-release is the portable answer and everything else is not; and a set
# of version-comparison cases to predict before testing.
#
# The comparison cases are chosen so that four of the nine are counter-intuitive
# in different ways. Getting them all right by instinct is not possible, which
# is the point of writing predictions down first.
set -euo pipefail

export LC_ALL=C

# ------------------------------------------------------------ other distros

D=/tmp/distros
rm -rf "$D"; mkdir -p "$D"

cat > "$D/README.txt" <<'EOF'
Captured identity files from four systems. This container is only one of them.

For each, work out the distribution, the release, and the codename — and note
which file was needed to do it.
EOF

cat > "$D/alpha-os-release.txt" <<'EOF'
# /etc/os-release
PRETTY_NAME="Ubuntu 24.04.1 LTS"
NAME="Ubuntu"
VERSION_ID="24.04"
VERSION="24.04.1 LTS (Noble Numbat)"
VERSION_CODENAME=noble
ID=ubuntu
ID_LIKE=debian
UBUNTU_CODENAME=noble
EOF

cat > "$D/bravo-os-release.txt" <<'EOF'
# /etc/os-release
NAME="Rocky Linux"
VERSION="9.4 (Blue Onyx)"
ID="rocky"
ID_LIKE="rhel centos fedora"
VERSION_ID="9.4"
PLATFORM_ID="platform:el9"
PRETTY_NAME="Rocky Linux 9.4 (Blue Onyx)"
EOF

cat > "$D/charlie-os-release.txt" <<'EOF'
# /etc/os-release
NAME="Alpine Linux"
ID=alpine
VERSION_ID=3.20.3
PRETTY_NAME="Alpine Linux v3.20"
HOME_URL="https://alpinelinux.org/"
EOF

cat > "$D/delta-os-release.txt" <<'EOF'
# /etc/os-release
NAME="Arch Linux"
PRETTY_NAME="Arch Linux"
ID=arch
BUILD_ID=rolling
ANSI_COLOR="38;2;23;147;209"
HOME_URL="https://archlinux.org/"
EOF

cat > "$D/what-else-was-tried.txt" <<'EOF'
# What a script tried before reading /etc/os-release, and what happened.
# Captured across the same four systems.

$ lsb_release -a
  ubuntu   : works (lsb-release installed by default)
  rocky    : bash: lsb_release: command not found
  alpine   : sh: lsb_release: not found
  arch     : bash: lsb_release: command not found
  this container: not installed either

$ cat /etc/debian_version
  ubuntu   : trixie/sid          <- says Debian, on Ubuntu
  rocky    : no such file
  alpine   : no such file
  arch     : no such file

$ uname -a
  all four : reports the KERNEL. Says nothing about the distribution.
             In a container it reports the HOST's kernel.

$ cat /etc/*-release
  works, sometimes matches several files, output order not defined
EOF

# ---------------------------------------------------------------- versions

V=/tmp/versions
rm -rf "$V"; mkdir -p "$V"

cat > "$V/cases.txt" <<'EOF'
# Nine comparisons. Predict each before testing.
#
# Write "gt", "lt" or "eq" for the relationship of A to B.

  A                      B
1 1.10                   1.9
2 1.0                    1.0-1
3 1.0~rc1                1.0
4 1:1.0                  99.0
5 4:14.2.0-1             15.0.0
6 3.5.6-1~deb13u2        3.5.6-1~deb13u1
7 2.0-1                  2.0-1+b1
8 1.0.0                  1.0
9 1.0~~                  1.0~
EOF

cat > "$V/anatomy.txt" <<'EOF'
# A Debian version string, fully decomposed.

        4  :  14.2.0  -  1
        │     │          │
        │     │          └── distribution revision
        │     │              changes the distribution made to this upstream
        │     │              release: a patch, a rebuild, a security backport
        │     │
        │     └── upstream version
        │         what the software's own authors released
        │
        └── epoch (optional, rare)
            a manual override, used when upstream versioning went backwards
            and normal comparison would order the releases wrongly.
            It beats every other component.

# Suffixes you will meet:
#
#   ~deb13u2   a Debian 13 update — security or point release.
#              `~` sorts BEFORE nothing, so 1.0~rc1 < 1.0
#
#   +b9        a binary NMU: rebuilt without a source change,
#              usually against a new library
#
#   +deb12u1   the same idea as ~debNuN on some releases; `+` sorts AFTER
#              nothing, so 2.0-1+b1 > 2.0-1
EOF

# ------------------------------------------------------------------ choices

C=/tmp/choices
rm -rf "$C"; mkdir -p "$C"

cat > "$C/README.txt" <<'EOF'
Four situations. Choose a distribution and release model for each, and say what
the choice commits you to — including what you will have to do that the other
options would not have required.

One of them has a constraint that makes the usual answer wrong.
EOF

cat > "$C/alpha.txt" <<'EOF'
situation: alpha — a fleet of 400 application servers
lifetime: 5+ years, replaced on a rolling schedule
team: 3 platform engineers
change appetite: low; every upgrade is a change-managed event
dependencies: a JVM application, nothing exotic
compliance: annual audit requires a supported OS with security updates
EOF

cat > "$C/bravo.txt" <<'EOF'
situation: bravo — a developer workstation image
lifetime: reimaged whenever it breaks
team: 40 engineers who install their own tools
change appetite: high; they want current versions of everything
dependencies: whatever each engineer needs this week
compliance: none
EOF

cat > "$C/charlie.txt" <<'EOF'
situation: charlie — a container base image for 60 microservices
lifetime: rebuilt on every deploy, 20+ per day
team: 8 engineers across 4 squads
change appetite: moderate; they want small images and fast pulls
dependencies: mostly static Go binaries, two Python services
compliance: images are scanned; findings must be actionable
EOF

cat > "$C/delta.txt" <<'EOF'
situation: delta — an appliance shipped to customer sites
lifetime: 7 years in the field, updated over a slow link, sometimes never
team: 5 engineers
change appetite: near zero; a failed update means a site visit
dependencies: a kernel module for custom hardware
compliance: customers require a named support lifetime in the contract
EOF

echo "Seeded: /tmp/distros, /tmp/versions, /tmp/choices."

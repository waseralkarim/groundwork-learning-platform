#!/bin/bash
# Seeds the B06.2 package labs.
#
# Like B06.1, most of this topic needs no fixture. The container has a real
# package database with 162 real entries, a real dependency graph, real
# conffile checksums, and — usefully — a real integrity failure, because the
# image's own Dockerfile appends a prompt to /etc/bash.bashrc, which is a
# conffile of bash. The labs read the actual system.
#
# What is seeded is the material one container cannot provide:
#
#   - the seven relationship fields collected into one readable page. Every
#     stanza is real and checkable with dpkg-query on this machine; they are
#     gathered here only because they are spread across seven packages
#   - the four outcomes of an upgrade meeting a modified conffile, which needs
#     a package upgrade and therefore a network and root
#   - a script whose dependencies must be audited, so "which of these commands
#     is guaranteed to be here" becomes a question with a checkable answer
#   - a vendor agent installed the way vendor agents actually arrive, so the
#     unowned-file case is something other than /opt/lab
set -euo pipefail

export LC_ALL=C

P=/tmp/pkg
rm -rf "$P"; mkdir -p "$P"

cat > "$P/README.txt" <<'EOF'
Material for the package labs.

  relationships.txt      seven ways one package can refer to another
  conffile-outcomes.txt  what an upgrade does with a config file you edited
  collect-metrics.sh     a script to audit: what does it actually require?
  deployed/              a vendor agent, installed the way they usually are

Everything else in these labs reads the real system.
EOF

# ------------------------------------------------------- relationship fields

cat > "$P/relationships.txt" <<'EOF'
# The seven relationship fields.
#
# Every stanza below is real and comes from THIS machine. Check any of them:
#
#   dpkg-query -W -f='${Package}: ${Breaks}\n' libssl3t64
#
# Only two of the seven are guarantees. Work out which two before reading on.

Package: openssh-client
Depends: libc6, libedit2, libfido2-1, libgssapi-krb5-2, libselinux1,
         libssl3t64 (>= 3.5.0), zlib1g, passwd, adduser
Recommends: xauth
Suggests: keychain, libpam-ssh, monkeysphere, ssh-askpass

Package: coreutils
Pre-Depends: libacl1 (>= 2.2.23), libattr1 (>= 1:2.4.48), libc6 (>= 2.38),
             libcap2 (>= 1:2.10), libgmp10 (>= 2:6.3.0+dfsg),
             libselinux1 (>= 3.1~), libssl3t64 (>= 3.0.0), libsystemd0 (>= 254)
Essential: yes
Priority: required

Package: mawk
Provides: awk

Package: grep
Provides: rgrep
Conflicts: rgrep

Package: gcc
Provides: c-compiler

Package: libssl3t64
Breaks: freeradius (<< 3.2.7+dfsg-1+deb13u1), libssl3 (<< 3.5.6-1~deb13u2),
        openssh-client (<< 1:9.4p1), openssh-server (<< 1:9.4p1),
        python3-m2crypto (<< 0.38.0-4)

# --------------------------------------------------------------------------
# What each one means:
#
# Depends       must be installed and configured, or this package will not be
#               configured. A hard requirement.
#
# Pre-Depends   must be fully installed BEFORE this package is even unpacked.
#               Used when the unpacking itself needs the dependency to work.
#               Rare, strong, and it is why some removals are impossible.
#
# Recommends    installed by default; not required. "Works without it, in a way
#               somebody would call broken." Skipped by
#               --no-install-recommends, which is why minimal images have
#               surprises in them.
#
# Suggests      never installed automatically. Documentation, effectively.
#
# Provides      declares a virtual name this package satisfies. mawk provides
#               awk, and so would gawk — which is exactly what the
#               /usr/bin/awk symlink is choosing between.
#
# Conflicts     cannot be installed at the same time. Note that grep both
#               PROVIDES and CONFLICTS with rgrep: that is the idiom for
#               "exactly one package may supply this name", and it is what
#               lets something depend on the name without caring who supplies
#               it. The canonical case is mail-transport-agent, where exim,
#               postfix and sendmail all use this pattern.
#
# Breaks        this package breaks those versions of that package. Weaker than
#               Conflicts: the other package may stay installed, but must be
#               upgraded before this one is configured. Read libssl3t64's
#               list — the current TLS library records that it breaks
#               openssh-client older than 1:9.4p1. A real compatibility
#               boundary, written down.
EOF

# ----------------------------------------------------------- conffile outcomes

cat > "$P/conffile-outcomes.txt" <<'EOF'
# What an upgrade does with a configuration file you edited.
#
# dpkg records an md5 for every conffile at install time. On upgrade it compares
# three things: the checksum it recorded, the file on disk now, and the file in
# the new package. Four cases follow, and only one of them prompts.

  you edited it?   package changed it?   what happens
  ---------------------------------------------------------------------------
  no               no                    nothing. file left alone.
  no               yes                   silently replaced with the new version.
  yes              no                    your version kept. no message.
  yes              yes                   CONFLICT -> prompt

# The prompt, when it appears:
#
#   Configuration file '/etc/example/example.conf'
#    ==> Modified (by you or by a script) since installation.
#    ==> Package distributor has shipped an updated version.
#      What would you like to do about it ?
#       Y or I  : install the package maintainer's version
#       N or O  : keep your currently-installed version
#         D     : show the differences between the versions
#         Z     : start a shell to examine the situation
#    The default action is to keep your current version.
#
# On an unattended upgrade there is nobody to answer it, so the default applies
# and your version is kept — which means a new option the package added is not
# in your file, and the upgrade reports success.
#
# The residue this leaves on disk:
#
#   example.conf.dpkg-dist   the maintainer's version, when you kept yours
#   example.conf.dpkg-old    your version, when you took the maintainer's
#   example.conf.dpkg-new    the new version, when the prompt was deferred
#
# Finding *.dpkg-dist files on a machine is finding upgrades that silently did
# not fully apply.
EOF

# ------------------------------------------------------------- audit target

cat > "$P/collect-metrics.sh" <<'EOF'
#!/bin/sh
# Collects host metrics for the monitoring pipeline.
# Runs from cron every 60s on every machine in the fleet.

OUT=/tmp/metrics.prom

# clear a stale lock left by a previous run that was killed mid-write
fuser -k "$OUT" 2>/dev/null

cpu=$(awk '/^cpu /{print $2+$4}' /proc/stat)
mem=$(grep MemAvailable /proc/meminfo | tr -s ' ' | cut -d' ' -f2)
con=$(ss -tan 2>/dev/null | wc -l)
cid=$(openssl rand -hex 8)

printf 'node_cpu_total %s\n'        "$cpu" >  "$OUT"
printf 'node_mem_available %s\n'    "$mem" >> "$OUT"
printf 'node_connections %s\n'      "$con" >> "$OUT"
printf 'node_collector_id{id="%s"} 1\n' "$cid" >> "$OUT"

curl -sf --max-time 5 --data-binary @"$OUT" http://metrics.internal:9091/push
EOF
chmod 0755 "$P/collect-metrics.sh"

cat > "$P/collect-metrics.notes.txt" <<'EOF'
# collect-metrics.sh runs on every machine in the fleet.
#
# It was written on a workstation, where everything it needs happened to be
# installed. The question is which of the commands it calls are actually
# guaranteed to exist on a minimal machine, and which are there by luck.
#
# For each command it invokes, find:
#
#   1. which package provides it
#   2. whether that package is Essential  (dpkg-query -W -f='${Essential}')
#   3. whether it was asked for or pulled in  (apt-mark showmanual)
#
# Then sort the commands into three groups:
#
#   always there    Essential, or Priority: required
#   somebody asked  installed on purpose here; a minimal machine would not
#                   have it unless somebody asks again
#   not here at all arrived nowhere, because it was only a Recommends
#
# One of the commands it calls is in the third group. The script has been in
# production for a year, so work out how that is possible before deciding what
# it means.
EOF

# --------------------------------------------------------- the vendor agent

mkdir -p "$P/deployed/usr/local/bin" "$P/deployed/etc/acme" "$P/deployed/var/log/acme"

cat > "$P/deployed/usr/local/bin/acme-agent" <<'EOF'
#!/bin/sh
# ACME Observability Agent 4.2.1
# Installed via: curl -sSL https://get.acme.example/install.sh | sh
exec /usr/local/lib/acme/agent-bin "$@"
EOF
chmod 0755 "$P/deployed/usr/local/bin/acme-agent"

cat > "$P/deployed/etc/acme/agent.conf" <<'EOF'
endpoint = https://ingest.acme.example/v1
interval = 30s
api_key_file = /etc/acme/key
EOF

cat > "$P/deployed/install-record.txt" <<'EOF'
# How this arrived, from the runbook that set the fleet up in 2023.

  curl -sSL https://get.acme.example/install.sh | sh

# That is the entire record. It ran as root, wrote the paths below, and
# registered a systemd unit.
#
#   /usr/local/bin/acme-agent
#   /usr/local/lib/acme/agent-bin
#   /etc/acme/agent.conf
#   /etc/acme/key                  (mode 0600)
#   /etc/systemd/system/acme-agent.service
#   /var/log/acme/
#
# Questions to answer from the package database:
#
#   - which package owns any of these?
#   - what version is installed?
#   - when did it last change?
#   - is it affected by the CVE announced last week?
#   - what happens to it on a distribution upgrade?
EOF

echo "Seeded: /tmp/pkg (relationships, conffile outcomes, an audit target, a vendor agent)."

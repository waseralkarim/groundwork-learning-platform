#!/bin/bash
# Seeds the A04.4 identity and least-privilege labs.
#
# Three things are set up here.
#
# A permissions tree with deliberate traps — the ones that come up in real
# incidents rather than the ones in tutorials. The most useful is a directory
# that is readable and not executable: `ls` works, opening a file inside it does
# not, and the error says "Permission denied" on the file rather than on the
# directory, which sends people to the wrong place.
#
# An SSH key set, so a learner can match public keys to private ones and read
# what is actually inside an encrypted private key. The encrypted one exposes
# `aes256-ctr` and `bcrypt` in its own header — the previous two topics visible
# in one artefact.
#
# And an audit target: four service accounts, described the way an inventory
# would describe them, exactly one of which is correctly scoped.
#
# One thing this image cannot demonstrate live, recorded here so the lab does
# not pretend otherwise: there is no sshd, so `ssh` cannot be made to refuse a
# world-readable private key — it fails at connection before it ever loads the
# key. The lab uses captured output for that one point and says so.
set -euo pipefail

export LC_ALL=C

# ------------------------------------------------------------------- perms

P=/tmp/perms
rm -rf "$P"; mkdir -p "$P"

# 1. readable directory, no execute bit. `ls` succeeds, opening fails.
mkdir -p "$P/listable"
echo "the contents of this file are not secret, and you cannot read them" > "$P/listable/data.txt"
chmod 0644 "$P/listable"

# 2. executable directory, no read bit. Opening a known name succeeds, `ls` fails.
#
# 0111 rather than 0711: the learner owns these directories, so the *owner* bits
# are the ones that apply, and 0711 would leave the owner with full rwx and
# demonstrate nothing. Getting this wrong is itself the lesson — permission bits
# are evaluated by the first matching class, not by the union of them.
mkdir -p "$P/traversable"
echo "you can read this only if you already know the filename" > "$P/traversable/known.txt"
chmod 0111 "$P/traversable"

# 3. a file whose mode looks fine and whose directory does not
mkdir -p "$P/locked"
echo "unreachable" > "$P/locked/open.txt"
chmod 0644 "$P/locked/open.txt"
chmod 0000 "$P/locked"

# 4. a normal control
mkdir -p "$P/normal"
echo "readable" > "$P/normal/file.txt"
chmod 0755 "$P/normal"

cat > "$P/README.txt" <<'EOF'
Four directories. For each, predict before testing:

  - can you list it?
  - can you read a file inside it, given the name?

Then test both, and explain any result that surprised you. Two of these produce
an error that names the wrong object.
EOF

# --------------------------------------------------------------------- keys

K=/tmp/keys
rm -rf "$K"; mkdir -p "$K"

ssh-keygen -t ed25519 -f "$K/alice" -N '' -q -C 'alice@ops'
ssh-keygen -t ed25519 -f "$K/bob"   -N '' -q -C 'bob@ops'
ssh-keygen -t ed25519 -f "$K/carol" -N 'correct-horse' -q -C 'carol@ops'
ssh-keygen -t rsa -b 4096 -f "$K/legacy" -N '' -q -C 'deploy@ci-2019'

# An authorized_keys as a real server accumulates one: current staff, a key
# nobody can account for, and a CI key from a decommissioned system.
{
  cat "$K/alice.pub"
  cat "$K/bob.pub"
  printf '%s\n' "$(cat "$K/legacy.pub")"
  ssh-keygen -t ed25519 -f "$K/.orphan" -N '' -q -C 'root@build-01'
  cat "$K/.orphan.pub"
} > "$K/authorized_keys"
rm -f "$K/.orphan"          # the private half is gone; nobody knows who holds it
chmod 0644 "$K/authorized_keys"

cat > "$K/inventory.txt" <<'EOF'
# who we believe holds access, from the team wiki (last edited 14 months ago)
alice@ops     - platform team, current
bob@ops       - platform team, current
carol@ops     - platform team, current

# not listed anywhere:
#   (there are more keys in authorized_keys than there are people here)
EOF

# Captured from a machine with a real sshd, because this image has none.
cat > "$K/captured-ssh-refusal.txt" <<'EOF'
# Captured on a host running sshd. This image has no sshd, so it cannot be
# reproduced here — the connection fails before the key is ever loaded.

$ chmod 644 ~/.ssh/id_ed25519
$ ssh deploy@app-01
@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@
@         WARNING: UNPROTECTED PRIVATE KEY FILE!          @
@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@
Permissions 0644 for '/home/deploy/.ssh/id_ed25519' are too open.
It is required that your private key files are NOT accessible by others.
This private key will be ignored.
Load key "/home/deploy/.ssh/id_ed25519": bad permissions
deploy@app-01: Permission denied (publickey).
EOF

# ------------------------------------------------------------------ accounts

A=/tmp/accounts
rm -rf "$A"; mkdir -p "$A"

cat > "$A/alpha.txt" <<'EOF'
service: alpha — image build runner
runs as: root
capabilities: all (privileged container)
justification: "needs to run docker build"
secrets mounted: registry push credentials, cloud admin key
network: unrestricted egress
EOF

cat > "$A/bravo.txt" <<'EOF'
service: bravo — reporting API
runs as: uid 10001, non-root
capabilities: none added, default set dropped
justification: "reads from a replica, serves JSON"
secrets mounted: database read-only credential, scoped to one schema
network: egress to the database only
EOF

cat > "$A/charlie.txt" <<'EOF'
service: charlie — log shipper
runs as: uid 0
capabilities: CAP_DAC_READ_SEARCH added
justification: "must read log files owned by many different users"
secrets mounted: log backend write token
network: egress to the log backend only
EOF

cat > "$A/delta.txt" <<'EOF'
service: delta — nightly cleanup cron
runs as: uid 10001
capabilities: none
justification: "deletes files older than 30 days"
secrets mounted: the platform's shared deploy key (same key used by CI)
network: unrestricted egress
EOF

cat > "$A/README.txt" <<'EOF'
Four workloads. Exactly one is correctly scoped.

For each of the others, name what it holds that it does not need, and what an
attacker gets by compromising it that they should not.
EOF

echo "Seeded: /tmp/perms, /tmp/keys, /tmp/accounts."

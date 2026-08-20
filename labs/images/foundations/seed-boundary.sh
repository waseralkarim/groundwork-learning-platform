#!/bin/bash
# Seeds the "permission denied, but why" challenge.
#
# Three refusals that print almost the same thing and have three different
# causes. Only one is seeded here — the other two are properties the sandbox
# already has, which is the point: a read-only rootfs and an empty capability
# set are the real configuration, not a simulation of one.
set -euo pipefail

mkdir -p /tmp/challenge

cat > /tmp/challenge/secret.txt <<'EOF'
Well done. This file was unreadable because of its mode bits, and nothing else.
The check that refused you was the file permission check: EACCES.
EOF

# Unreadable even by its owner. DAC applies to you too.
chmod 000 /tmp/challenge/secret.txt

# Something to attempt a privileged operation against.
touch /tmp/challenge/marker

echo "Challenge ready. Three operations in /tmp/challenge and elsewhere will be refused."

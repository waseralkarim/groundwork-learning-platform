#!/bin/bash
# Seeds the A04.2 encryption labs.
#
# Two things are set up here that the labs would otherwise spend their time on
# rather than on the lesson.
#
# First, a byte-level XOR helper. Several steps need to XOR two files to show
# that a reused keystream cancels the key out of the arithmetic — and the
# obvious tool does not work: the image has mawk, which has no bitwise
# functions at all. `awk 'BEGIN{print xor(5,3)}'` fails with "function xor never
# defined". Shell arithmetic does have `^`, so the helper is a shell loop, and
# that is worth knowing before a learner spends twenty minutes on it.
#
# Second, an intercepted-traffic set: messages encrypted under a deliberately
# reused nonce, which is the challenge lab's whole subject.
#
# Nothing here is secret and nothing leaves the session's tmpfs.
set -euo pipefail

export LC_ALL=C

# ------------------------------------------------------------------ xor helper

cat > /tmp/xorfiles <<'HELPER'
#!/bin/bash
# XOR two files byte by byte and print the result as hex.
#
# mawk has no xor(), so this uses shell arithmetic. Slow, and irrelevant at
# these sizes.
export LC_ALL=C
od -An -tu1 -v "$1" | tr -s ' ' '\n' | grep . > /tmp/.xa
od -An -tu1 -v "$2" | tr -s ' ' '\n' | grep . > /tmp/.xb
paste -d' ' /tmp/.xa /tmp/.xb | while read -r x y; do
  [ -n "$y" ] || continue
  printf '%02x' $(( x ^ y ))
done
echo
HELPER
chmod 0755 /tmp/xorfiles

# Print the printable characters of a hex string, so a recovered XOR can be
# eyeballed. Non-printing bytes become dots.
cat > /tmp/unhex <<'HELPER'
#!/bin/bash
export LC_ALL=C
sed 's/../& /g' | tr ' ' '\n' | grep . | while read -r h; do
  d=$(( 16#$h ))
  if [ "$d" -ge 32 ] && [ "$d" -le 126 ]; then
    printf "$(printf '\\%03o' "$d")"
  else
    printf '.'
  fi
done
echo
HELPER
chmod 0755 /tmp/unhex

# Hex on stdin, raw bytes on stdout. `xxd -r -p` would do this and `xxd` is not
# in the image — it lives in a package the labs do not otherwise need, and one
# tool in a lab image is one more thing to patch.
cat > /tmp/unhexbin <<'HELPER'
#!/bin/bash
export LC_ALL=C
tr -d ' \n' | sed 's/../& /g' | tr ' ' '\n' | grep . | while read -r h; do
  printf "$(printf '\\%03o' "$(( 16#$h ))")"
done
HELPER
chmod 0755 /tmp/unhexbin

# ------------------------------------------------------------------ structured
#
# A file with repeating structure, which is what makes ECB's failure visible.
# Real data looks like this far more often than people expect: database pages,
# disk images, bitmaps, and any record format with fixed-width fields.

S=/tmp/structured
mkdir -p "$S"

{
  i=0
  while [ $i -lt 6 ]; do
    printf 'RECORD__________'
    i=$((i+1))
  done
  printf 'SALARY:00090000!'
  i=0
  while [ $i -lt 6 ]; do
    printf 'RECORD__________'
    i=$((i+1))
  done
} > "$S/payroll.bin"

# ------------------------------------------------------------------- intercept
#
# Four messages captured off a wire. They were encrypted with AES-256-CTR under
# one key, and the nonce was reused for all four because the implementer treated
# it as a configuration constant.
#
# The learner never gets the key. They do not need it.

I=/tmp/intercept
mkdir -p "$I"

KEY=4f8d2a9c1e7b03f56a8c4d2e9f1b7a3c5d8e2f4a6b9c1d3e5f7a8b2c4d6e8f0a
NONCE=00000000000000000000000000000001

printf 'ORDER 1001 SHIP 24 UNITS TO DEPOT NORTH  ' > "$I/.p1"
printf 'ORDER 1002 SHIP 18 UNITS TO DEPOT SOUTH  ' > "$I/.p2"
printf 'ORDER 1003 SHIP 96 UNITS TO DEPOT NORTH  ' > "$I/.p3"
printf 'ORDER 1004 SHIP 12 UNITS TO DEPOT CENTRAL' > "$I/.p4"

n=1
while [ $n -le 4 ]; do
  openssl enc -aes-256-ctr -K "$KEY" -iv "$NONCE" \
    -in "$I/.p${n}" -out "$I/capture-${n}.enc" 2>/dev/null
  n=$((n+1))
done

# Message 1 is known plaintext: it was also published on a public order board.
# That is the crib, and it is how a real recovery starts.
cp "$I/.p1" "$I/known-plaintext-1.txt"
rm -f "$I/.p1" "$I/.p2" "$I/.p3" "$I/.p4"

cat > "$I/README.txt" <<'EOF'
Four messages captured from an internal ordering service.

All four were encrypted with AES-256-CTR under the same key. The key was not
captured and is not available to you.

known-plaintext-1.txt is the cleartext of capture-1.enc. It was published on a
public order board, so it is not a secret.

Recover the contents of the other three.
EOF

# ------------------------------------------------------------------- payment
#
# One encrypted instruction, for the malleability step. The key is present
# because the point of that lab is what an attacker does *without* it, and the
# learner needs to decrypt afterwards to see what their tampering achieved.

P=/tmp/payment
mkdir -p "$P"

printf 'TRANSFER 0100 GBP TO ACCT 55512' > "$P/instruction.txt"
printf '%s' 'a3f7c9128e4b6d05a1c8f2e94b7d3a6058e1c4f792b6d8a03c5e7f194a2b6d8c' > "$P/key.hex"
printf '%s' '0f1e2d3c4b5a69788796a5b4c3d2e1f0' > "$P/iv.hex"

openssl enc -aes-256-ctr \
  -K "$(cat "$P/key.hex")" -iv "$(cat "$P/iv.hex")" \
  -in "$P/instruction.txt" -out "$P/instruction.enc" 2>/dev/null

echo "Seeded: /tmp/structured, /tmp/intercept, /tmp/payment, /tmp/xorfiles, /tmp/unhex."

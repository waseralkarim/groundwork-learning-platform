#!/bin/bash
# Seeds the A04.3 certificate and TLS labs.
#
# Builds a small PKI at container start — root, intermediate, and a set of leaf
# certificates that are each broken in exactly one way. Generating them here
# rather than baking them into the image matters for one of them: an expired
# certificate baked in months ago would also be expired for the wrong reason,
# and a learner cannot tell "expired because the lab meant it" from "expired
# because the image is old".
#
# Two mechanics worth knowing, both found by probing rather than by reading:
#
#   * `openssl x509 -req -days -1` does not produce an expired certificate — it
#     is rejected. Explicit `-not_before` / `-not_after` do.
#
#   * `openssl s_server -cert` reads only the FIRST certificate in the file, so
#     concatenating a chain into one file — which is exactly what nginx wants —
#     silently sends the leaf alone. Intermediates need `-cert_chain`.
#
# Every key here is generated fresh in a throwaway container and dies with the
# session. None of them protects anything.
set -euo pipefail

export LC_ALL=C

P=/tmp/pki
mkdir -p "$P"
cd "$P"

req() { openssl req "$@" 2>/dev/null; }
sign() { openssl x509 -req "$@" 2>/dev/null; }

# ------------------------------------------------------------------- the CA

req -x509 -newkey rsa:2048 -keyout root.key -out root.crt -days 3650 -nodes \
  -subj "/CN=Groundwork Root CA/O=Groundwork" \
  -addext "basicConstraints=critical,CA:TRUE"

req -newkey rsa:2048 -keyout int.key -out int.csr -nodes \
  -subj "/CN=Groundwork Issuing CA/O=Groundwork"
cat > int.ext <<'EOF'
basicConstraints=critical,CA:TRUE,pathlen:0
keyUsage=critical,keyCertSign,cRLSign
EOF
sign -in int.csr -CA root.crt -CAkey root.key -out int.crt -days 1825 -extfile int.ext

cat > leaf.ext <<'EOF'
subjectAltName=DNS:lab.internal
basicConstraints=CA:FALSE
keyUsage=critical,digitalSignature,keyEncipherment
EOF

# ------------------------------------------------------- one good, five broken

B=/tmp/broken
mkdir -p "$B"

# good — signed by the intermediate, correct SAN, in date
req -newkey rsa:2048 -keyout "$B/good.key" -out good.csr -nodes -subj "/CN=lab.internal"
sign -in good.csr -CA int.crt -CAkey int.key -out "$B/good.crt" -days 365 -extfile leaf.ext

# expired — same in every other respect
req -newkey rsa:2048 -keyout "$B/expired.key" -out expired.csr -nodes -subj "/CN=lab.internal"
sign -in expired.csr -CA int.crt -CAkey int.key -out "$B/expired.crt" \
  -not_before 20240101000000Z -not_after 20240201000000Z -extfile leaf.ext

# self-signed — no CA involved at all
req -x509 -newkey rsa:2048 -keyout "$B/selfsigned.key" -out "$B/selfsigned.crt" \
  -days 365 -nodes -subj "/CN=lab.internal" \
  -addext "subjectAltName=DNS:lab.internal"

# wrong name — valid chain, valid dates, SAN for a different host
cat > wrongname.ext <<'EOF'
subjectAltName=DNS:other.internal
basicConstraints=CA:FALSE
EOF
req -newkey rsa:2048 -keyout "$B/wrongname.key" -out wrongname.csr -nodes -subj "/CN=other.internal"
sign -in wrongname.csr -CA int.crt -CAkey int.key -out "$B/wrongname.crt" -days 365 -extfile wrongname.ext

# CN only, no SAN — the one that passes openssl and fails every browser
cat > cnonly.ext <<'EOF'
basicConstraints=CA:FALSE
EOF
req -newkey rsa:2048 -keyout "$B/cnonly.key" -out cnonly.csr -nodes -subj "/CN=lab.internal"
sign -in cnonly.csr -CA int.crt -CAkey int.key -out "$B/cnonly.crt" -days 365 -extfile cnonly.ext

# issued by an unrelated CA the trust store has never heard of
req -x509 -newkey rsa:2048 -keyout rogue.key -out rogue.crt -days 3650 -nodes \
  -subj "/CN=Some Other CA" -addext "basicConstraints=critical,CA:TRUE"
req -newkey rsa:2048 -keyout "$B/unknownca.key" -out unknownca.csr -nodes -subj "/CN=lab.internal"
sign -in unknownca.csr -CA rogue.crt -CAkey rogue.key -out "$B/unknownca.crt" -days 365 -extfile leaf.ext

# The trust anchor a learner verifies against, and the intermediate a correct
# server would send. Copied so the broken set is self-contained.
cp root.crt int.crt "$B/"

cat > "$B/README.txt" <<'EOF'
Six certificates, all claiming to be lab.internal (one of them does not).

Exactly one is entirely correct. Each of the others is broken in one way, and
each produces a different verification error code.

Verify against root.crt. The intermediate is int.crt, and a correctly
configured server would send it.

    openssl verify -CAfile root.crt -untrusted int.crt <cert>
    openssl verify -CAfile root.crt -untrusted int.crt -verify_hostname lab.internal <cert>

Note the second form. Some faults only appear when the hostname is checked,
which is itself worth knowing.
EOF

# ------------------------------------------------------------------- servers
#
# A script the labs use to start a TLS server on demand. Kept here rather than
# in each lab because the -cert_chain detail is easy to get wrong and is not
# what the labs are teaching.

cat > /tmp/serve-tls <<'HELPER'
#!/bin/bash
# serve-tls <port> <cert> <key> [chain]
#
# Starts an HTTPS server in the background. If a chain file is given it is sent
# alongside the leaf — `-cert` alone sends only the first certificate in the
# file, which is the single most common way a server ends up serving an
# incomplete chain.
port=$1; cert=$2; key=$3; chain=${4:-}
if [ -n "$chain" ]; then
  openssl s_server -accept "$port" -cert "$cert" -key "$key" -cert_chain "$chain" -www -quiet >/dev/null 2>&1 &
else
  openssl s_server -accept "$port" -cert "$cert" -key "$key" -www -quiet >/dev/null 2>&1 &
fi
sleep 1
echo "listening on $port"
HELPER
chmod 0755 /tmp/serve-tls

rm -f "$P"/*.csr
echo "Seeded: /tmp/pki (root, intermediate), /tmp/broken (six leaves), /tmp/serve-tls."

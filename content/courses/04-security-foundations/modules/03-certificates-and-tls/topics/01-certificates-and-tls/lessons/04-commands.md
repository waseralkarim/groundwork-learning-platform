---
topic: topic.certificates-and-tls
section: commands
title: Reading certificates, and testing a server you cannot reach by name
order: 4
mode: explain
---

## Reading one

```bash
openssl x509 -in cert.crt -noout -text            # everything
openssl x509 -in cert.crt -noout -subject -issuer -dates
openssl x509 -in cert.crt -noout -ext subjectAltName
openssl x509 -in cert.crt -noout -ext basicConstraints
```

Those four short forms answer most questions faster than reading the full dump.
`-ext subjectAltName` in particular is the first command to run on any "the
browser says it is invalid" report — if it prints `No extensions in
certificate`, you have found it.

:::try{lab=six-ways-to-fail run="/opt/lab/seed-tls.sh >/dev/null; openssl x509 -in /tmp/broken/cnonly.crt -noout -subject -ext subjectAltName" title="A certificate with a name and no SAN"}
A subject that says `CN=lab.internal` and no SAN extension at all. OpenSSL will
verify this against that hostname quite happily. No browser will.
:::

## Verifying one

```bash
openssl verify -CAfile root.crt cert.crt                       # chain only
openssl verify -CAfile root.crt -untrusted int.crt cert.crt     # supply intermediates
openssl verify -CAfile root.crt -untrusted int.crt \
    -verify_hostname api.example.com cert.crt                   # and check the name
```

Run **both** of the last two. The chain check and the name check are separate,
and a certificate that passes the first can fail the second — which is exactly
how a hostname mismatch hides from a careless test.

## Testing a live server

```bash
openssl s_client -connect host:443 -servername host </dev/null
openssl s_client -connect host:443 -servername host -showcerts </dev/null
openssl s_client -connect host:443 -servername host -verify_hostname host </dev/null
```

`-servername` sets SNI. Omit it and a server hosting many sites gives you its
default certificate, which is a different certificate from the one your users
get — and is a very easy way to debug the wrong thing for an hour.

The lines worth reading from the output:

```text
depth=2 CN=Groundwork Root CA          ← how far the chain reached
depth=1 CN=Groundwork Issuing CA
depth=0 CN=lab.internal
Protocol: TLSv1.3
Cipher: TLS_AES_256_GCM_SHA384
Verify return code: 0 (ok)             ← the verdict
```

The `depth=` lines are the chain the server actually sent, walked outward. If
you only see `depth=0`, the server sent one certificate — and if the verdict is
20 or 21, that is your diagnosis in two lines.

`-showcerts` prints each certificate with its subject and issuer, which is how
you confirm that what was sent actually chains together rather than merely
looking plausible.

:::try{lab=the-handshake-in-the-open run="/opt/lab/seed-tls.sh >/dev/null; /tmp/serve-tls 4443 /tmp/broken/good.crt /tmp/broken/good.key >/dev/null; openssl s_client -connect 127.0.0.1:4443 -CAfile /tmp/broken/root.crt </dev/null 2>&1 | grep -E 'depth=|Verify return code'"}
One `depth=0` line and code 21. The server was started without its intermediate,
so the client has a leaf it cannot connect to anything it trusts.
:::

## Testing a name that does not resolve where you need it

This is the one worth memorising, because it comes up constantly when a service
is behind an ingress and you want to test a specific backend:

```bash
curl --resolve api.example.com:443:10.0.1.5 https://api.example.com/health
```

It sends the correct SNI and the correct `Host` header while connecting to an
address you choose. Compare with the wrong approach:

```bash
curl -H 'Host: api.example.com' https://10.0.1.5/health    # fails
```

That sets the HTTP header but not SNI, and the certificate is chosen during the
TLS handshake — before any HTTP header is sent. So the server presents its
default certificate for the IP address, and verification fails with a hostname
mismatch before your header is ever read. The `Host:` trick works for plain
HTTP and cannot work for HTTPS.

## Curl's exit codes

```bash
curl -sS https://host/ ; echo "rc=$?"
```

| Code | Meaning |
|---|---|
| 60 | **Every** certificate fault — expiry, self-signed, unknown issuer, incomplete chain *and* hostname mismatch |
| 35 | TLS handshake failure — usually a protocol or cipher mismatch, not a certificate |
| 7 | Connection refused — not TLS at all |

The important thing about 60 is how little it narrows down. Four of OpenSSL's
six distinct codes collapse into it, and so does the hostname check. **The
message is the diagnosis, not the exit code:**

```text
curl: (60) SSL certificate problem: certificate has expired
curl: (60) SSL certificate problem: self-signed certificate
curl: (60) SSL certificate problem: unable to get local issuer certificate
curl: (60) SSL: no alternative certificate subject name matches target hostname
```

Same code, four different faults, four different fixes. A monitoring check that
records only the exit status has thrown away everything useful, which is a
common and quiet failure of TLS alerting.

## Building a certificate

```bash
# A key and a signing request
openssl req -newkey rsa:2048 -keyout server.key -out server.csr -nodes \
    -subj "/CN=api.example.com"

# Extensions the CSR does not carry reliably — put them on the signature
cat > ext.cnf <<'EOF'
subjectAltName=DNS:api.example.com,DNS:www.api.example.com
basicConstraints=CA:FALSE
keyUsage=critical,digitalSignature,keyEncipherment
EOF

openssl x509 -req -in server.csr -CA ca.crt -CAkey ca.key \
    -out server.crt -days 365 -extfile ext.cnf
```

The `-extfile` is not optional in practice. Extensions requested in a CSR are
requests; the issuer decides what actually goes in, and `openssl x509 -req`
copies **none** of them by default. A certificate signed without `-extfile` comes
out with no SAN — which is precisely how the CN-only certificate in the lab is
made, and a common way to produce one accidentally.

To make an expired certificate deliberately — for testing an alerting path,
which is a legitimate thing to want:

```bash
openssl x509 -req -in server.csr -CA ca.crt -CAkey ca.key -out expired.crt \
    -not_before 20240101000000Z -not_after 20240201000000Z -extfile ext.cnf
```

`-days -1` does not work; it is rejected rather than producing a past date.

## The trust store

```bash
ls /etc/ssl/certs/ | head
grep -c 'BEGIN CERTIFICATE' /etc/ssl/certs/ca-certificates.crt
```

On this image that count is around **150**. Each one can issue a valid
certificate for any name, including yours, and your domain's TLS is only as
strong as the least careful of them. Knowing the number changes how the system
feels.

## The commands worth keeping

```bash
openssl x509 -in c.crt -noout -subject -issuer -dates -ext subjectAltName
openssl s_client -connect h:443 -servername h </dev/null 2>&1 | grep -E 'depth=|Verify return'
openssl verify -CAfile root.crt -untrusted int.crt -verify_hostname h c.crt
curl --resolve name:443:10.0.1.5 https://name/health
```

Four commands, and between them they identify every fault in this topic.

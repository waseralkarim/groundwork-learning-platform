---
topic: topic.certificates-and-tls
section: production
title: Expiry, workarounds, and the trust store as an attack surface
order: 5
mode: explain
---

## The most predictable outage there is

Certificate expiry has a date printed on it, months in advance, and still takes
down major services every year. That is worth thinking about, because it says the
problem is not knowledge.

What actually fails:

- **Nobody owns it.** The person who issued it has changed team, and the
  certificate is not in any inventory.
- **Renewal is manual** and depends on someone acting on an email that goes to a
  distribution list nobody reads.
- **Automation renews the file and nothing reloads it.** The new certificate is
  on disk and the process is still serving the old one from memory. This one is
  vicious, because every check of the *file* passes.
- **Monitoring watches the wrong thing.** It checks the certificate on the load
  balancer and not the one on the origin, or the public endpoint and not the
  internal mesh.
- **An intermediate expires**, not the leaf. Everything you monitor looks fine.

The controls that work are dull:

**Automate issuance and renewal** — ACME, cert-manager, or your cloud's managed
certificates. A certificate a human renews is a certificate that will eventually
not be renewed.

**Alert on the certificate the client sees**, from outside, by connecting. Not on
a file's modification time, not on an inventory spreadsheet. `openssl s_client`
against the real endpoint is the check that cannot be fooled by a stale process.

**Alert at 30 and 14 days**, not at 2. Renewal often needs a change window, and a
two-day warning during a code freeze is an incident with extra steps.

**Check the whole chain's dates**, not just the leaf:

```bash
openssl s_client -connect host:443 -servername host -showcerts </dev/null 2>/dev/null \
  | openssl crl2pkcs7 -nocrl -certfile /dev/stdin 2>/dev/null \
  | openssl pkcs7 -print_certs -noout -text 2>/dev/null | grep -A2 Validity
```

**Reload after renewal, and prove it.** The check is not "did the file change" —
it is "does a new connection get the new certificate".

## The workaround that becomes permanent

Every TLS failure has a fast fix that makes it go away:

```bash
curl -k https://internal.service/          # --insecure
```
```python
requests.get(url, verify=False)
```
```yaml
insecureSkipTLSVerify: true
```

Each of these does the same thing, and it is worth being precise about what:
they do not trust *that* certificate. They **stop verifying anything**, on that
connection, permanently. Any certificate is accepted, from anyone, including
someone between you and the server. The encryption still happens; the assurance
about who you are talking to is gone entirely, which is the part that was
protecting you.

They are all reasonable for sixty seconds while you confirm a hypothesis. They
are all disasters when they survive into a manifest, because they are invisible:
everything works, forever, and nothing ever alerts.

The proper fixes, matched to the fault:

| Fault | Workaround | Actual fix |
|---|---|---|
| Self-signed internal cert | `-k` | Add that CA to the client's trust store |
| Incomplete chain | `-k` | Serve the intermediate — leaf first, then intermediate |
| Hostname mismatch | `-k` | Connect by a name in the SAN, or reissue with the right name |
| Expired | `-k` | Renew, and automate it |
| No SAN | `-k` | Reissue with `subjectAltName` |

Note that four of the five are server-side and take about as long as the
workaround does.

## Internal PKI

Running your own CA is normal and correct for internal traffic — service meshes
do it automatically, and it is what makes mutual TLS between services practical.
It is not a compromise, provided:

- **The root's private key is offline.** It cannot be rotated without touching
  every trust store you own, so it should be used a handful of times and then
  locked away. Intermediates do the issuing.
- **Certificate lifetimes are short.** Days or hours, not years. Short lifetimes
  make revocation mostly unnecessary, which matters because revocation barely
  works — CRLs are large and stale, OCSP adds a round trip and most clients
  soft-fail it, meaning an attacker who can block the OCSP request gets the
  certificate accepted anyway. **Expiry is the revocation mechanism that
  functions.**
- **Issuance is automated and audited.** A human minting certificates by hand
  will eventually mint one with no SAN, and you have met that certificate.
- **Your root is distributed deliberately**, to the workloads that need it, and
  not by adding it to every image because it was easier.

## Mutual TLS, in one paragraph

Everything so far has the client verifying the server. **mTLS** adds the reverse:
the client presents a certificate too and the server verifies it the same way —
same chain walk, same codes.

That turns the certificate into an identity rather than a transport detail, which
is what service meshes use it for. The operational cost is that now you have
certificates on both ends and twice as many things to renew, which is why mTLS
without automated issuance is a bad idea rather than a strong one.

## The trust store is an attack surface

Around 150 CAs on this image, and any one of them can issue a valid certificate
for any name you own. Your TLS is as strong as the least careful of them, and
there have been real incidents — CAs compromised, and CAs that simply issued
certificates they should not have.

Two things help, and neither is pinning:

**Certificate Transparency.** Every publicly-trusted certificate is logged to
append-only public logs. You cannot prevent a misissuance, but you can *find out*
— monitoring CT logs for your own domains is cheap and is the control most
organisations skip.

**CAA records.** A DNS record naming which CAs may issue for your domain. CAs
are required to check it, so it narrows 150 down to the ones you chose. It is
one DNS record and it is rarely present.

**Pinning** — accepting only one specific certificate or key — is the control
people reach for and it is usually wrong. It removes the trust store's breadth
and replaces it with an outage on the day you renew, or on the day a mobile app
with a pinned certificate cannot be updated fast enough. Pin the *CA* rather than
the leaf if you must, and only where you control both ends.

## The five-minute audit

On a service you have just inherited:

```bash
# What is actually served, and does the chain reach a trust anchor?
openssl s_client -connect host:443 -servername host </dev/null 2>&1 \
  | grep -E 'depth=|Verify return code'

# When does it expire, and what names does it cover?
openssl s_client -connect host:443 -servername host </dev/null 2>/dev/null \
  | openssl x509 -noout -dates -ext subjectAltName

# Is renewal automated, and does anything reload after it?
# Is there a CAA record?
dig +short CAA example.com
```

Four questions: is the chain complete, when does it expire, who renews it, and
who is allowed to issue for you. Most services answer the first two well and the
second two not at all.

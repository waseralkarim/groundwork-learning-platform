---
topic: topic.certificates-and-tls
section: internals
title: Six codes, and what each one is actually telling you
order: 3
mode: explain
---

`openssl verify` returns a number. So does `s_client`, in its
`Verify return code:` line. Reading that number is the difference between a
diagnosis and an afternoon.

Here is the whole set you will meet, each produced deliberately in the lab.

## 0 — ok

The chain reached a trust anchor, every signature checked, every certificate was
in date, and the constraints allowed it.

Note what this does **not** include: the hostname. `openssl verify` skips the
name check unless you pass `-verify_hostname`, so a certificate can return `OK`
and still be wrong for the host you are talking to. In the lab, one of the six
certificates does exactly that.

## 10 — certificate has expired

```text
error 10 at 0 depth lookup: certificate has expired
```

The clock is past Not After. `at 0 depth` says it is the leaf; a non-zero depth
means an *intermediate* expired, which is rarer and much more confusing because
the leaf looks fine.

The fix is renewal, and the interesting question is why it was not automatic.
Certificate expiry is the most predictable outage in computing — the date is
printed on the certificate — and it still causes major incidents every year.

One trap: if the certificate looks in date to you, check the **machine's clock**.
A container with a badly skewed clock produces this error against a perfectly
good certificate, and so does a certificate whose Not Before is in the future,
which is error 9 and looks nearly identical at a glance.

## 18 — self-signed certificate

```text
error 18 at 0 depth lookup: self-signed certificate
```

The certificate signed itself. There is no chain to walk and no third party
vouching for anything.

This is not automatically wrong. Internal services, test environments and
bootstrap CAs use self-signed certificates legitimately. It is an error only
because the client was not told to trust this one specifically.

Two fixes, and the difference matters: **add that certificate to the client's
trust store** (correct for an internal service), or **get one from a CA the
client already trusts** (correct for anything public). The wrong fix is
`-k` / `--insecure` / `verify=False`, which does not trust that certificate — it
stops verifying *anything*, on that connection, forever.

## 19 — self-signed certificate in certificate chain

The chain ended at a root the client does not have. Same situation as 18, one
level up: you built a proper hierarchy and the client has never heard of your
root.

## 20 — unable to get local issuer certificate

```text
error 20 at 0 depth lookup: unable to get local issuer certificate
```

**This is the one you will meet most.** The verifier has a certificate, read its
Issuer field, and cannot find that issuer anywhere — not in what the server sent,
not in the trust store.

Almost always: **the server is not sending its intermediate.**

## 21 — unable to verify the first certificate

The same fault reported from the client end of a live handshake. `s_client`
typically prints both:

```text
verify error:num=20:unable to get local issuer certificate
verify error:num=21:unable to verify the first certificate
Verify return code: 21 (unable to verify the first certificate)
```

Treat 20 and 21 as one diagnosis: **the chain is incomplete**.

:::warning
This is the fault with the misleading symptom. It works in browsers — which
cache intermediates from other sites and sometimes fetch missing ones — and
fails in `curl` (exit **60**), in health checks, in Java clients and in language
runtimes, all of which verify exactly what was sent.

So "it works in my browser" is not evidence that a chain is correct. It is
evidence that your browser has been to another site with the same CA.
:::

The fix is server-side: send the intermediate. In nginx that means concatenating
leaf and intermediate into the file named by `ssl_certificate` — leaf first,
order matters. Most ACME clients write a `fullchain.pem` for exactly this, and
pointing at `cert.pem` instead is how the mistake usually happens.

A client *can* compensate by putting the intermediate in its own trust bundle,
and you will see that work in the lab — code 21 becomes code 0. But that is a
workaround applied per client, forever, on every client. The server sending its
chain fixes it once.

## 62 — hostname mismatch

```text
error 62 at 0 depth lookup: hostname mismatch
```

The chain is perfect and the certificate is for a different name.

In the lab this is the fault that **passes** the plain chain check and appears
only when you add `-verify_hostname`. That is worth internalising: `openssl
verify` returning `OK` does not mean a client will accept the certificate.

Common real causes: requesting by IP address rather than name (so the "hostname"
is `10.244.7.19`, which is in nobody's SAN); a wildcard that does not match —
`*.example.com` covers `api.example.com` but **not** `example.com` itself, and
not `a.b.example.com`; or a certificate that simply was not reissued when a name
was added.

## The seventh fault, which produces no error at all

One certificate in the lab is broken and OpenSSL will not tell you. It has a
Common Name and **no Subject Alternative Name**.

```bash
openssl verify -CAfile root.crt -untrusted int.crt -verify_hostname lab.internal cnonly.crt
# cnonly.crt: OK
```

OpenSSL falls back to the Common Name when a certificate carries no SAN.
Browsers do not — Chrome has required SAN since 2017 — so the same certificate is
valid to `curl` and invalid to every browser.

The lesson generalises past this one case: **verification is policy, not
arithmetic.** The signature check is mathematics and identical everywhere;
whether a CN fallback is allowed, whether SHA-1 is acceptable, how long a
certificate may be valid, whether Certificate Transparency is required — those
are decisions each verifier makes, and they differ. When two clients disagree
about one certificate, neither is broken, and the question is which policy
differs.

:::predict{question="A monitoring check reports your API's certificate as valid. Users report browser warnings. Both are looking at the same server. Where do you look first?"}

At the Subject Alternative Name, and then at the chain.

Two policy differences produce exactly this split, and both are common:

**No SAN.** The monitoring check probably uses OpenSSL or `curl`, which falls
back to the Common Name. The browser does not. `openssl x509 -noout -ext
subjectAltName` settles it in one command, and "No extensions in certificate" is
your answer.

**An incomplete chain**, the other way round. Browsers hide it, so if the
*monitor* is the thing complaining and browsers are fine, suspect this.

Both are configuration, neither is a cryptographic failure, and in both cases
the two clients are behaving correctly.

## TLS, assembled from what you already built

The handshake is short when you know the parts:

1. Client sends the protocol versions and cipher suites it supports, plus **SNI**
   — the hostname it wants, in the clear, so a server with many certificates
   knows which to present.
2. Server picks a suite and sends its **certificate chain**.
3. Both sides do an **ephemeral key exchange** — A04.2 — to derive a shared
   secret neither transmitted.
4. Server **signs** the handshake transcript with the private key matching its
   certificate. This is the step that proves it holds the key the certificate
   names, and it is a signature over a digest — A04.1.
5. Client **verifies the chain**, the signature, and the hostname.
6. Everything after is **symmetric encryption** with the derived key — A04.2.

Nothing in TLS is a new primitive. On this lab image you will see it negotiate
`TLSv1.3`, `TLS_AES_256_GCM_SHA384` — an AEAD mode, as the previous topic
demanded — and a key exchange group of `X25519MLKEM768`, which is X25519
combined with a post-quantum algorithm, now the default in OpenSSL 3.5.

Step 4 is worth one more sentence, because it is what stops the obvious attack.
Certificates are public; anyone can copy one. Presenting a stolen certificate
fails at step 4, because signing the transcript needs the **private** key, which
never leaves the server. The certificate says "this name uses this public key";
the signature proves "I hold the matching private key". Both are needed and
neither is sufficient.

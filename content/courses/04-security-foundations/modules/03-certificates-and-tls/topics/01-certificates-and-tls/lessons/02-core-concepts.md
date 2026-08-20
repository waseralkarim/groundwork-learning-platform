---
topic: topic.certificates-and-tls
section: core-concepts
title: A signed statement, and a chain to something you already trusted
order: 2
mode: explain
---

## The object

A certificate contains, roughly:

```text
Subject:      CN=shop.example.com
Issuer:       CN=Example Issuing CA
Validity:     Not Before ... Not After ...
Public Key:   (the subject's public key)
Extensions:
  Subject Alternative Name: DNS:shop.example.com, DNS:www.shop.example.com
  Basic Constraints:        CA:FALSE
  Key Usage:                digitalSignature, keyEncipherment
Signature:    (the issuer's signature over everything above)
```

The signature is the whole value of the document. Everything above it is a
claim; the signature is somebody staking their reputation on that claim.

And note what a signature *is*, because you built it two topics ago: a hash of
the contents, transformed with the issuer's **private** key. Verifying it uses
the issuer's **public** key — which is in the issuer's certificate. That is
already the chain.

## Why the chain exists

The leaf is signed by an intermediate. The intermediate is signed by a root. The
root is signed by itself and is trusted because it is **in the client's trust
store** — not because of any signature, but because someone decided to put it
there.

That last step is worth sitting with. Trust in this system does not come from
mathematics. It comes from a list, shipped with your operating system or your
container image, of organisations whose signatures you have agreed to accept in
advance.

:::diagram{src=../diagrams/chain.mmd caption="Three checks at three depths, and the intermediate that servers routinely forget to send"}
:::

The intermediate exists for an operational reason: the root's private key is
enormously valuable and cannot be replaced without updating every trust store on
earth, so it is kept offline — in a safe, on hardware, used a handful of times a
decade. Intermediates do the day-to-day issuing and can be revoked and replaced
if compromised.

**The consequence you will meet in production:** the client has the root and does
*not* have the intermediate. So **the server must send it**. A server configured
with only its leaf certificate produces error 20, and this is the single most
common TLS misconfiguration there is.

:::predict{question="A server sends only its leaf certificate, omitting the intermediate. It works perfectly in your browser and fails in curl, in the Kubernetes health check, and in the partner's Java client. Why does the browser succeed where everything else fails?"}

Because the browser has seen that intermediate before, on some other site, and
cached it.

Browsers cache intermediates across sites, and some will additionally fetch a
missing one using the *Authority Information Access* extension in the leaf. So a
broken chain works in the browser of anyone who has recently visited another
site using the same CA — which is most people, most of the time.

`curl`, health checks, and most language runtimes do neither. They verify
exactly what was sent.

This is why "it works in my browser" is worth nothing as evidence about a TLS
chain, and why the fix — send the intermediate — is not optional even when it
appears to be working.

## What the verifier actually checks

At each depth, walking from the leaf:

1. **Signature.** Did the issuer named here actually sign this, provably?
2. **Validity window.** Is now between Not Before and Not After?
3. **Basic constraints.** Is a certificate that signed another allowed to?
   `CA:FALSE` on a leaf is what stops anyone with any certificate minting
   certificates for anyone else.
4. **Path length.** An intermediate with `pathlen:0` may sign leaves but not
   further CAs.

And once, at depth 0 only:

5. **The name.** Is the hostname you asked for among the certificate's Subject
   Alternative Names?

That last check is separate from the chain, and separately skippable — which is
why a certificate can have a perfect chain and still be wrong for the host you
are talking to. `openssl verify` does not check it unless you ask with
`-verify_hostname`, and that is a trap worth knowing: a certificate that
`openssl verify` calls `OK` may still be rejected by every real client.

## SAN, and the field that is nearly dead

The **Subject Alternative Name** extension lists the names a certificate is
valid for. It is a list, so one certificate can cover
`shop.example.com`, `www.shop.example.com` and `*.api.example.com` together.

The **Common Name** in the subject is the legacy field. It was never designed
for this — it is a human-readable label — and it holds exactly one value, which
is why SAN replaced it.

Here is the part that causes real confusion, and you will verify both halves in
a lab:

- **Browsers ignore CN entirely.** Chrome has required SAN since 2017. A
  certificate with a CN and no SAN is simply invalid to them.
- **OpenSSL still falls back to CN** when no SAN is present. `openssl verify
  -verify_hostname lab.internal` on a CN-only certificate returns `OK`.

So the same certificate is valid and invalid depending on who asks. Not a bug in
either — a policy difference, with browsers ahead. When someone reports "it works
with curl but the browser says the certificate is invalid", **check for a SAN
first**; it is the answer more often than anything else.

## What a certificate does not prove

It binds a **name** to a **key**, vouched for by an issuer. That is all.

It does not establish that the operator is honest, that the site is safe, that
the company is the one you meant, or that the data is handled well. A phishing
site can get a valid certificate in minutes, free, and routinely does — the
padlock means the connection is private, not that the destination is
trustworthy.

There is one more property worth being clear-eyed about. Your trust store holds
around **150 certificate authorities**, and any one of them can issue a valid
certificate for **any name**, including yours. The security of your domain's TLS
rests on the least competent of those 150. This is a real, structural weakness of
the system — mitigated by Certificate Transparency, which makes issuance public
and auditable, so a certificate issued for your domain without your knowledge can
at least be *noticed*.

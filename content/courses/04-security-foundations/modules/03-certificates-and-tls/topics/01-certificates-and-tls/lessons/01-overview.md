---
topic: topic.certificates-and-tls
section: overview
title: "\"Certificate error\" is six different problems"
order: 1
mode: explain
---

You have built almost all of TLS already.

A04.1 gave you hashing and signatures over digests. A04.2 gave you key exchange
and hybrid encryption. TLS is those three, arranged: agree a session key,
encrypt the traffic with it, and prove — with a signature — that the other end
is who it claims.

The genuinely new part is that last step, and it is where all the operational
pain lives. Not because the cryptography is hard, but because **"certificate
error" is a category, not a diagnosis.** It covers at least six unrelated
faults:

| Code | What it means | Fix |
|---|---|---|
| 10 | Certificate has expired | Renew it |
| 18 | Self-signed | Get one from a CA the client trusts |
| 19 | Self-signed root in the chain | Trust the root, or use a public CA |
| 20 | Cannot find the issuer | **The server is not sending the intermediate** |
| 21 | Cannot verify the first certificate | Usually 20, seen from the client end |
| 62 | Hostname mismatch | The name you asked for is not in the certificate |

Six codes, six fixes, and almost nothing in common. Renewing a certificate that
has a hostname mismatch achieves nothing; adding the intermediate does not help
an expired one. In this topic you will produce every one of them deliberately
and read the code rather than guessing.

:::note
The single most common of these in production is **20** — an incomplete chain —
and it has a signature symptom: it works in your browser and fails in `curl`,
in a health check, and in every other client. That is not a mystery, and by the
end of this topic you will know exactly why in one sentence.
:::

## What a certificate actually is

A public key, a list of names, a validity window, some constraints — and a
signature over all of it from somebody else.

That is the whole object. The interesting content is not in the certificate; it
is in **who signed it and whether you already trust them**. Strip the signature
and it is a text file anybody could write.

Which leads to the property people find uncomfortable when they first meet it:
a certificate proves that a CA vouched for a name/key binding. It does not prove
the site is honest, safe, competent, or the company you meant to visit. A
phishing site with a valid certificate is extremely normal.

## What you will do

You will be a certificate authority. Root, intermediate, leaf, all built by
hand, and you will see that issuing a certificate is one command and the
authority is entirely a matter of who has decided to trust you.

Then you will run a TLS server, connect to it, and read the handshake — the
chain it sent, the depth it verified to, the cipher it negotiated. Everything
locally, in one container, with no network.

Then you will break it six ways and read the codes.

## The finding that costs the most afternoons

One of the labs ends on a certificate that **`curl` accepts and every browser
rejects**. Same certificate, same server, two verdicts.

The reason is not cryptographic and it is not a bug. OpenSSL's verifier still
falls back to the legacy Common Name field when a certificate carries no Subject
Alternative Name; browsers stopped doing that years ago and require SAN. So the
certificate is simultaneously valid and invalid, depending on who is asking.

You will confirm both halves yourself, which is the only way that particular
lesson ever sticks.

## Where this sits

This is the last topic in the course that builds a primitive. What follows —
identity, least privilege, the trust store as an attack surface — is about who
is allowed to do what, and it assumes you can already establish who somebody is.

It is also the topic you will use most often. Every ingress, every service mesh,
every webhook, every registry pull and every health check against an HTTPS
endpoint either succeeds or fails on the rules in here.

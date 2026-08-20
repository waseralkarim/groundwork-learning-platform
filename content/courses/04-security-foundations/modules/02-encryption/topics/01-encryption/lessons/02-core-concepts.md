---
topic: topic.encryption
section: core-concepts
title: The key is the secret, and the two kinds of key
order: 2
mode: explain
---

## The algorithm is public

Every cipher worth using is fully published. AES has a public specification,
public reference code, and twenty-five years of people trying to break it. Its
security does not depend on any of that being hidden.

This is **Kerckhoffs's principle**, and it is a design rule rather than an
observation: a system should stay secure even if everything about it except the
key is public. The reasoning is practical. Algorithms leak — they are in
binaries you ship, in libraries you link, in the memory of machines you do not
control. Keys can be rotated; a secret algorithm cannot, and the moment it is
reverse-engineered you have nothing left.

Two consequences you will act on:

- **A cipher nobody can inspect is a warning, not a feature.** "Proprietary
  military-grade encryption" describes something that has not been reviewed.
- **The key is the whole security boundary.** Every question about an encrypted
  system reduces to: where is the key, who can read it, and what happens when it
  leaks. Which is why later courses spend far more time on key management than
  on ciphers.

:::warning
The corollary catches people in review: **encrypting with a key stored beside
the ciphertext protects nothing.** A database encrypted with a key in the
application's config, on the same host, backed up to the same bucket, survives
exactly one threat — someone stealing the bare disk. It is still worth doing;
it is just a much narrower claim than "the data is encrypted" suggests.
:::

## Symmetric: fast, and one problem

One key, used for both directions.

```bash
openssl enc -aes-256-cbc -pbkdf2 -pass pass:hunter2 -in report.pdf -out report.enc
openssl enc -d -aes-256-cbc -pbkdf2 -pass pass:hunter2 -in report.enc -out report.pdf
```

AES-256 runs at over a gigabyte a second per core on ordinary hardware — you
will measure it — and modern CPUs have dedicated instructions for it. There is
no performance reason not to encrypt bulk data.

The problem is entirely elsewhere: **both parties need the same key.** For two
people that is an awkward phone call. For a service with ten thousand clients it
is ten thousand keys, or one shared key that ten thousand parties can leak. And
you cannot send the key over the channel you are trying to protect, because
anyone who could read the data can read the key.

That single problem is why the other kind exists.

## Asymmetric: slow, and it solves that problem

A key **pair** with a mathematical relationship: what one half encrypts, only
the other half decrypts. Publish one, keep the other, and the distribution
problem disappears — anyone can encrypt to you without ever having shared a
secret with you.

```bash
openssl genpkey -algorithm RSA -pkeyopt rsa_keygen_bits:2048 -out private.key
openssl pkey -in private.key -pubout -out public.key
```

The pair does two different jobs depending on which half you use first, and
mixing them up is a common confusion:

| Encrypt with | Decrypt with | Achieves |
|---|---|---|
| Recipient's **public** key | Recipient's **private** key | Confidentiality — only they can read it |
| Your **private** key | Your **public** key | A signature — only you could have produced it |

The second row is not really encryption and is better thought of as its own
operation, but the key pair is the same and the intuition carries: the public
half is for the world, the private half is what proves you are you.

:::predict{question="Anyone can encrypt a message with your public key. What does receiving a message that decrypts correctly with your private key prove about who sent it?"}

Nothing at all.

The public key is public — that is the point of it. Anyone can use it, so a
message that decrypts correctly proves only that *somebody* encrypted to you.

This surprises people because encryption feels private and private feels
trusted. Proving origin is a separate operation — a signature, or a MAC —
and it needs the sender to hold a key too. Confidentiality and authenticity are
different properties, and asymmetric encryption gives you exactly one of them.

## The price

Asymmetric encryption is not a better version of symmetric. It is a different
tool with a much worse cost profile, and both limits are hard:

**It is thousands of times slower.** You will measure RSA-2048 private-key
operations at a couple of thousand a second against AES at over a gigabyte a
second.

**It cannot encrypt more than a few hundred bytes.** RSA can only encrypt a
message smaller than its modulus, minus padding — for a 2048-bit key that is
exactly 245 bytes. Not "inadvisable above": *refused*. You will watch it accept
245 bytes and reject 246.

So encrypting a file with RSA is not slow, it is impossible. And that constraint
is what forces the design every real system uses.

## Hybrid: what everything actually does

Generate a fresh random symmetric key. Encrypt the data with it. Encrypt *the
key* — 32 bytes, comfortably under the limit — with the recipient's public key.
Send both.

The slow algorithm handles 32 bytes. The fast one handles everything else. You
get asymmetric key distribution and symmetric performance, and this is what TLS,
PGP, `age`, and every encrypted-storage product are doing underneath.

You will build it by hand in the second lab, which is the fastest way to stop
finding TLS mysterious.

## Key exchange, and a better answer

There is a second way two parties reach a shared key, and it is what modern TLS
actually uses.

**Diffie–Hellman** lets both sides derive the same secret from their own private
key and the other's public key — without that secret ever being transmitted.
An eavesdropper who captures the entire exchange cannot compute it.

```bash
openssl pkeyutl -derive -inkey mine.key -peerkey theirs.pub
```

You will run that on both sides and see identical output, having sent nothing
secret. It feels like a trick the first time.

It is preferred over encrypting a key with RSA for one specific reason:
**forward secrecy**. If the keys are ephemeral — generated per connection and
discarded — then someone who steals the server's long-term private key next year
cannot decrypt traffic they recorded this year. With RSA key transport they can,
because the recorded handshake contains the session key encrypted to a key that
is now theirs.

That difference is why "we should rotate that key eventually" is a different
severity depending on which scheme is in use.

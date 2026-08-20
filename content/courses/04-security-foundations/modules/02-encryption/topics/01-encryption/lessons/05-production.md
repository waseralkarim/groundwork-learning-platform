---
topic: topic.encryption
section: production
title: Where the key lives is the whole question
order: 5
mode: explain
---

You will almost never choose a cipher. AES-256-GCM or ChaCha20-Poly1305, and the
decision takes ten seconds. Everything difficult about encryption in production
is about keys: where they live, who can read them, how they rotate, and what
happens when one leaks.

## "Encrypted at rest" is a narrow claim

It is worth knowing exactly what it buys, because it is frequently reported as
though it settles the question.

Disk-level encryption — LUKS, EBS encryption, a cloud provider's default —
protects against **the disk leaving the building**: a decommissioned drive, a
stolen laptop, a datacentre theft. Those are real, and it is worth having.

It protects against essentially nothing else. On a running machine the volume is
mounted and the key is in memory, so:

- A compromised application reads plaintext, because it reads through the
  filesystem like everything else.
- `SELECT * FROM users` returns plaintext.
- A backup taken through the database returns plaintext.
- Anyone with shell access reads plaintext.

So "the database is encrypted at rest" and "an attacker who gets in cannot read
the data" are different claims, and only the first one is usually true. When
someone offers the first as an answer to the second, the useful question is
**which threat does that stop**.

Application-level encryption — the application encrypts specific fields before
storing them — is a genuinely different control, because the database and its
backups never hold plaintext. It costs you queryability on those fields, which
is why it is reserved for things worth that price.

## Where the key lives

Roughly in order of how much they are worth:

| Where | Worth |
|---|---|
| In the repository | Nothing. It is in the history forever, and rotating is the only fix. |
| In an environment variable | Slightly more. Visible in `/proc`, in crash dumps, in `docker inspect`, and in any log that dumps the environment. |
| In a file with restrictive modes | More. Survives a casual look; does not survive reading the disk or the backup. |
| In a secrets manager, fetched at start | Better. Access is logged and revocable, and rotation does not need a redeploy. |
| In a KMS or HSM, where the key never leaves | Best. The application sends data to be decrypted rather than holding the key. |

The last row is the one people skip and it changes the threat model rather than
merely hardening it: a compromised application can *ask* for decryptions, which
is loggable and rate-limitable, but it cannot walk away with the key.

Two rules with no interesting exceptions. **A key in a repository is compromised
from the moment it is committed** — removing it in a later commit changes
nothing, because the history has it and so does every clone. And **a key and the
data it protects should not share a blast radius**: same host, same bucket, same
backup, same access control all mean one compromise gets both.

## Rotation, and what it actually requires

"We rotate keys annually" is common and frequently means "we have never rotated
a key", because rotation is a design property rather than a task.

To rotate you need to know **which key encrypted which data**, so ciphertext
needs a key identifier stored alongside it. Without one, rotation means
decrypting everything with the old key and re-encrypting with the new one in a
single operation you cannot pause, and that is why it never happens.

With a key id, rotation is ordinary: new writes use the new key, reads select
the key by id, and old data migrates in the background. Envelope encryption —
each record encrypted with its own key, which is itself encrypted with a master
key — makes it cheaper still, because rotating the master means re-encrypting a
set of small keys rather than all the data.

Design for it up front. Adding a key id afterwards means a migration over the
data you were trying to avoid touching.

## What to look for in review

- **`openssl enc` anywhere.** The output is malleable, and the tool cannot do
  otherwise. Ask what stops someone modifying the file.
- **A hardcoded IV or nonce.** Not secret, but it must vary. A constant one in
  CTR mode means every message shares a keystream, which is the whole of the
  final lab.
- **The deprecated-KDF warning.** It is printed, ignored, and means the password
  became a key at almost no cost.
- **Encryption with no integrity mechanism.** If nothing verifies the ciphertext,
  an attacker steers what it decrypts to. Reach for AEAD, not encrypt-then-hash
  invented locally.
- **A key in the repository, the image or the environment.** Check the image
  layers too — a key deleted in a later `RUN` is still in the layer that added
  it.
- **A long-lived key doing key exchange.** Without ephemeral keys there is no
  forward secrecy, so traffic captured today is readable when that key is
  eventually lost.
- **`Math.random()`, `rand()` or a seeded PRNG generating a key.** Use the
  system CSPRNG. This has shipped in production more than once.

## Reading a breach notice, again

The previous topic's exercise applies here with a twist. "The data was
encrypted" invites exactly one question: **where was the key?**

If the answer is "on the same host", "in the same backup" or "in the application
config", then the encryption stopped the disk being useful and stopped nothing
else. If the answer is "in a KMS the attacker did not have access to", the claim
is meaningful and the notice should say so, because the difference is the
difference between an inconvenience and a disclosure.

That question also works in the other direction, on your own systems, before
anything has gone wrong. Take any dataset you would have to notify about, and
ask where its key is and who can read it. The answer is usually shorter and
worse than expected, and it is a better use of an afternoon than choosing a
cipher.

## What carries forward

The next topic is certificates and TLS, and it is this topic plus the previous
one, composed:

- A **key exchange** establishes a shared secret — Diffie–Hellman, built here.
- **Hybrid encryption** protects the traffic with it — built here.
- A **signature over a digest** proves who you are talking to — the hash from
  A04.1, with a private key attached.
- A **certificate** is that signature, plus a name, plus a chain to someone the
  client already trusts.

There is nothing in TLS that is not one of those four. Having built three of
them by hand, the handshake stops being a diagram and becomes a sequence you can
predict — which is what makes its failure modes readable rather than mysterious.

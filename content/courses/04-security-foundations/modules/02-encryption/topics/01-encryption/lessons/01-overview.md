---
topic: topic.encryption
section: overview
title: The one thing it does, and four it does not
order: 1
mode: explain
---

Encryption is the only primitive that keeps data secret. Hashing cannot — it
destroys the data rather than protecting it. Access control cannot once someone
is past it. If the requirement is *nobody without the key can read this*,
encryption is the answer and nothing else is.

It is also the primitive people expect the most from, and four of those
expectations are wrong. Each one is a real production failure, and you will
produce each of them here.

**It does not keep data unaltered.** In the labs you will change the amount in
an encrypted payment instruction from `TRANSFER 0100` to `TRANSFER 0000` without
ever learning the key, and the recipient will decrypt it successfully. Encryption
without a separate integrity mechanism is not merely incomplete — it hands an
attacker a channel that looks trustworthy.

**It does not say who sent it.** Anyone with the public key can encrypt. A
message that decrypts correctly proves only that somebody had the key, and that
is a weaker statement than it sounds.

**It does not survive a repeated nonce.** You will recover three secret messages
from intercepted ciphertext, using one known plaintext and no key at all, because
an implementer treated a nonce as a configuration constant.

**It does not hide structure by default.** In the wrong mode, an encrypted file
still shows you where its repeated records are — and you will see that directly,
in hex, in the first lab.

:::note
The pattern in all four: encryption's guarantee is narrow and precise, and every
failure comes from expecting a wider one. Knowing exactly where the guarantee
stops is more useful than knowing how AES works, and it is what this topic is
for.
:::

## Two kinds, and why both exist

**Symmetric** — one key encrypts and decrypts. It is fast: you will measure it
at over a gigabyte a second on one core. Its entire problem is that both parties
need the same key, and getting it to them is the hard part.

**Asymmetric** — a key pair, where what the public key encrypts only the private
key decrypts. It solves the distribution problem: publish one half, keep the
other. In exchange it is thousands of times slower and cannot encrypt more than
a few hundred bytes at a time.

So neither is usable alone, and every real system uses both. You will build that
combination by hand and measure why it has to exist.

## The specific things this explains

- Why `openssl enc` cannot produce authenticated ciphertext at all, and what
  that says about using it to encrypt a file
- Why RSA refuses to encrypt 246 bytes but accepts 245
- Why "encrypted at rest" is a much smaller claim than it sounds, and exactly
  which attacks it stops
- Why TLS negotiates a fresh key for every connection rather than using the
  server's certificate key directly
- Why a hardcoded IV is a finding even though an IV is not secret
- Why two parties can agree a shared secret over a wire an eavesdropper is
  reading, without ever sending it

## How this topic works

Everything is demonstrated locally, in one container, with `openssl`. No
network, no remote server, no trust in a diagram.

That includes the attacks. You will tamper with a ciphertext and watch it
decrypt to something you chose; you will XOR two intercepted messages and watch
the key cancel out of the arithmetic entirely. Both take one command, and both
are the reason the modern answer is an authenticated mode rather than a
cipher plus good intentions.

Four labs. The last one gives you four intercepted messages and one crib, and
asks for the other three.

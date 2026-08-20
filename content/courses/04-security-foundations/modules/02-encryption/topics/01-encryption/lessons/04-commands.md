---
topic: topic.encryption
section: commands
title: The commands, and the warnings worth reading
order: 4
mode: explain
---

## Symmetric

```bash
# Encrypt and decrypt with a password. -pbkdf2 and -iter are not optional.
openssl enc -aes-256-cbc -pbkdf2 -iter 600000 -pass pass:hunter2 -in in -out out
openssl enc -d -aes-256-cbc -pbkdf2 -iter 600000 -pass pass:hunter2 -in out -out in

# With a raw key and IV instead of a password — for demonstrating mechanics.
openssl enc -aes-256-ctr -K "$(openssl rand -hex 32)" -iv "$(openssl rand -hex 16)" -in in -out out

# What key did that password actually produce?
openssl enc -aes-256-cbc -pbkdf2 -pass pass:hunter2 -in in -out out -p
```

`-p` prints the salt, key and IV that were derived, which is the fastest way to
see that a password is not a key and something stands between them.

:::try{lab=what-the-key-protects run="printf hello > /tmp/f; openssl enc -aes-256-cbc -pass pass:x -in /tmp/f -out /tmp/f.enc; echo rc=$?" title="The warning that is not an error"}
`*** WARNING : deprecated key derivation used` — and then exit code 0 and a
file written. It is a warning about a real weakness that does not stop
anything, which is why it survives in scripts for years.
:::

## The cipher list is the finding

```bash
openssl enc -ciphers
```

Read what comes back. CBC, CFB, CTR, ECB, OFB — and **no GCM**, no
ChaCha20-Poly1305, nothing authenticated. Confirm it directly:

```bash
openssl enc -aes-256-gcm -pbkdf2 -pass pass:x -in in -out out
# enc: AEAD ciphers not supported
```

So the subcommand everyone reaches for to encrypt a file cannot produce
ciphertext that detects tampering. For real work use `age`, `gpg --symmetric`,
or your language's AEAD API — `openssl enc` is for understanding mechanics,
which is what it is doing in these labs.

## Asymmetric

```bash
# A key pair, and the public half extracted from it.
openssl genpkey -algorithm RSA -pkeyopt rsa_keygen_bits:2048 -out private.key
openssl pkey -in private.key -pubout -out public.key

# Modern alternatives — smaller and faster.
openssl genpkey -algorithm ED25519 -out sign.key      # signatures
openssl genpkey -algorithm X25519 -out exchange.key   # key exchange

# Inspect what you have.
openssl pkey -in private.key -text -noout | head -5
```

The size difference is worth seeing once: an Ed25519 private key is 119 bytes on
disk against 1704 for RSA-2048, and its signatures are 64 bytes against 256.

## Encrypting with a public key, and its limit

```bash
openssl pkeyutl -encrypt -pubin -inkey public.key -in secret -out secret.enc
openssl pkeyutl -decrypt -inkey private.key -in secret.enc -out secret
```

Try it with something large and read the error:

```text
Public Key operation error
...:data too large for key size:...
```

For RSA-2048 with PKCS#1 padding the ceiling is exactly **245 bytes** — the
256-byte modulus minus 11 bytes of padding. 245 works, 246 is refused. That
number is why hybrid encryption exists, and it is a hard limit rather than a
performance guideline.

## Hybrid, by hand

Four commands, and they are the shape of every encrypted-transport system:

```bash
# 1. a fresh symmetric key — 32 raw bytes
openssl rand -out session.key 32
KHEX=$(od -An -tx1 -v session.key | tr -d ' \n')

# 2. the bulk data, with the fast algorithm
openssl enc -aes-256-ctr -K "$KHEX" -iv "$(openssl rand -hex 16)" -in big.dat -out big.enc

# 3. the key itself, with the slow one — 32 bytes is far under the 245 limit
openssl pkeyutl -encrypt -pubin -inkey their.pub -in session.key -out session.key.enc

# 4. send big.enc and session.key.enc together
```

The slow algorithm encrypted 32 bytes and produced 256. The fast one did
everything else.

Note `-K` with hex rather than `-kfile`. `-kfile` reads the file as a
*passphrase* and runs the key derivation over it — which works, but means the
thing you carefully generated as a key is being treated as a password. `-K` is
the raw key, and it is also why this invocation produces no KDF warning.

:::try{lab=why-nobody-encrypts-with-rsa run="head -c 246 /dev/urandom > /tmp/big; openssl genpkey -algorithm RSA -pkeyopt rsa_keygen_bits:2048 -out /tmp/k 2>/dev/null; openssl pkey -in /tmp/k -pubout -out /tmp/p 2>/dev/null; openssl pkeyutl -encrypt -pubin -inkey /tmp/p -in /tmp/big -out /dev/null" title="246 bytes is one too many"}
`data too large for key size`. Drop to 245 and it succeeds. The lab has you find
that boundary yourself and then work out what it implies for encrypting a file.
:::

## Key exchange

```bash
openssl genpkey -algorithm X25519 -out mine.key
openssl pkey -in mine.key -pubout -out mine.pub
# ...exchange public keys...
openssl pkeyutl -derive -inkey mine.key -peerkey theirs.pub | openssl dgst -sha256
```

Run it on both sides and the digests match. Nothing secret crossed the wire —
each side combined its own private key with the other's public one and arrived
at the same value. An eavesdropper with both public keys cannot compute it.

## Measuring

```bash
openssl speed -seconds 3 aes-256-cbc     # bytes per second, by input size
openssl speed -seconds 3 rsa2048         # operations per second, by operation
openssl speed -seconds 3 ecdhx25519      # key agreements per second
```

Read the RSA output carefully: `sign` and `decaps` are the **private-key**
operations and are the slow ones, at a couple of thousand a second. `verify` and
`encaps` use the public key and are thirty times faster. People who have only
benchmarked verification come away with a badly wrong idea of RSA's cost.

## Randomness

```bash
openssl rand -hex 32      # a 256-bit key
openssl rand -base64 24   # a password-shaped secret
openssl rand -out key.bin 32
```

This reads the kernel's CSPRNG. Use it, or `/dev/urandom`, and nothing else — a
key from a language's ordinary random number generator is a key an attacker can
predict, and that failure has shipped in production more than once.

## The commands worth keeping

```bash
openssl enc -ciphers | grep -ci gcm         # 0 — this tool cannot authenticate
openssl rand -hex 32                        # a real key
openssl pkeyutl -derive -inkey a -peerkey b # a shared secret, never transmitted
openssl speed rsa2048                       # why nothing encrypts bulk data with it
```

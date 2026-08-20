---
topic: topic.encryption
section: internals
title: The mode decides more than the cipher does
order: 3
mode: explain
---

AES encrypts exactly 16 bytes. That is the whole primitive — one block, one key,
16 bytes in and 16 out.

Everything you actually encrypt is longer than 16 bytes, so something has to
decide how the cipher is applied repeatedly. That decision is the **mode of
operation**, and it matters more than the cipher choice: AES in one mode and AES
in another have entirely different security properties, with the same key and
the same algorithm.

"We use AES-256" therefore says almost nothing, in the same way "we use SHA-512"
said almost nothing about password storage. The question is always which mode.

## ECB, and why it is the example in every textbook

Electronic Codebook is the obvious approach: chop into blocks, encrypt each one
independently.

The consequence is immediate and fatal. **Identical plaintext blocks produce
identical ciphertext blocks.** Structure survives encryption.

In the lab you will encrypt a file of repeating fixed-width records and dump the
ciphertext, and you will see this:

```text
5301d1251af08a9ea49cf85982d8df6e
*
a1515645f0803ee0c9531256c72127a7
5301d1251af08a9ea49cf85982d8df6e
*
00657ea140655a44782747705d422fad
```

The `*` is `od` telling you the previous line repeated. Six identical records
became six identical ciphertext blocks, and the one block that differs is
plainly visible between them — that is the salary field, and an attacker who
knows the file format knows exactly where it is without decrypting anything.

This is the famous encrypted-penguin image, which survives ECB as a recognisable
penguin. You do not need the picture; the hex says it.

:::diagram{src=../diagrams/modes.mmd caption="Same cipher, same key, two modes — and only one of them hides that the records repeat"}
:::

Real data has this structure far more often than people assume: database pages,
disk images, fixed-width record formats, bitmaps, and anything with a repeated
header.

## CBC, CTR, and the IV

Every usable mode fixes ECB the same way — by making each block's encryption
depend on something that varies.

**CBC** XORs each plaintext block with the previous ciphertext block before
encrypting, so identical blocks encrypt differently because their predecessors
differ. The first block has no predecessor, so it uses an **initialisation
vector**.

**CTR** turns the block cipher into a stream: encrypt a counter to produce a
**keystream**, and XOR that with the plaintext. No padding, parallelisable, and
the counter starts from a **nonce**.

The IV and the nonce are the same idea under two names, and the naming is worth
taking seriously. Both are:

- **Not secret.** They are sent in the clear alongside the ciphertext, and they
  have to be — the recipient needs them.
- **Required to vary.** Same key and same IV means the same plaintext produces
  the same ciphertext, and ECB's problem is back at the level of whole messages.

"Nonce" — number used once — names the requirement rather than the value, which
is the more honest term. A hardcoded IV is a finding in review even though an IV
is not a secret, and that is the sentence that confuses people until they see
what reuse costs.

## What reuse costs, arithmetically

For counter mode the answer is exact rather than merely bad.

CTR produces a keystream from key and nonce, then `ciphertext = plaintext XOR
keystream`. Encrypt two messages under the same key and nonce and you get the
same keystream twice:

```text
c1 = p1 XOR ks
c2 = p2 XOR ks

c1 XOR c2 = (p1 XOR ks) XOR (p2 XOR ks)
          = p1 XOR p2                      ← the keystream cancels
```

**The key has left the equation entirely.** An attacker who captures two
ciphertexts learns the XOR of the two plaintexts, without the key and without
attacking AES in any way. AES-256 is not weakened; it is bypassed.

And if any one plaintext is known — a fixed header, a published record, a
message the attacker sent themselves — then `p1 XOR p2 XOR p1 = p2`, and the
other message falls out directly.

In the final lab you will do exactly that: four intercepted messages, one known
plaintext, and the other three recovered. You never see the key.

:::predict{question="A service encrypts every record with AES-256-CTR using a nonce read from its config file, which has never been changed. What has an attacker who captures the encrypted database got?"}

The XOR of every pair of records, which for structured data is usually enough.

Records share format: the same field names, the same padding, the same lengths.
XOR two of them and the shared structure cancels to zero bytes, leaving exactly
the positions where they differ — which is the data. One known record, or one
record the attacker created by using the service normally, unravels the rest.

The database is encrypted with a 256-bit key and is readable anyway. Nothing
about AES failed; the nonce did.

## Encryption is not integrity

Here is the property that surprises people most, and it is worth being precise
about because "encrypted" is routinely treated as "protected".

**A ciphertext altered in transit decrypts without error.** Not to the original
message — to something else — and the recipient has no way to tell.

In counter mode it is worse than random corruption, because the relationship is
predictable. Flipping bit *n* of the ciphertext flips bit *n* of the plaintext,
and nothing else changes. An attacker who knows the message format can make a
*chosen* change.

You will do this in the lab. An encrypted payment instruction reads
`TRANSFER 0100 GBP TO ACCT 55512`; you flip one bit in the ciphertext, without
the key; it decrypts as:

```text
TRANSFER 0000 GBP TO ACCT 55512
```

One bit, one character, no key, and a valid-looking instruction the recipient
will act on. This is **malleability**, and every unauthenticated mode has it.
CBC has a messier version — a tampered block corrupts itself but flips chosen
bits in the *next* block — and the messiness makes it less controllable, not
safe.

:::warning
This is why encrypting a config file with `openssl enc` and shipping it is worse
than it looks. Anyone who can write to that file can change what it decrypts to.
They cannot read it — but they can steer it, and the application will treat the
result as trusted because it decrypted.
:::

## AEAD: the actual answer

The fix is not to add a hash. It is to use a mode that authenticates as it
encrypts: **AEAD**, authenticated encryption with associated data.
`AES-256-GCM` and `ChaCha20-Poly1305` are the two you will meet.

An AEAD mode produces ciphertext *and* an authentication tag. Decryption
verifies the tag first and **fails** if a single bit was altered — no plaintext
is returned at all. Tampering becomes an error rather than a different message.

The "associated data" part covers fields that must be authentic but not secret —
a message header, a record id, a sequence number. They are not encrypted, but
altering them breaks the tag, which is how a protocol stops an attacker
reordering or replaying messages whose contents they cannot read.

Here is the finding that makes this concrete, and you will hit it yourself:

```bash
$ openssl enc -aes-256-gcm -pbkdf2 -pass pass:x -in file -out file.enc
enc: AEAD ciphers not supported
```

**`openssl enc` cannot do authenticated encryption at all.** The subcommand
predates AEAD and was never extended. So the tool most people reach for to
"encrypt a file" is structurally incapable of producing something that detects
tampering — and it gives no warning, because from its point of view nothing is
wrong.

That is the single most useful thing to take from this topic. If you are
encrypting a file, use `age`, or `gpg`, or your language's AEAD API. If you see
`openssl enc` in a script, the ciphertext it produces is malleable, and now you
know exactly what that permits.

## Choosing, in one table

| Job | Use | Not |
|---|---|---|
| Bulk data, in transit or at rest | AES-256-GCM or ChaCha20-Poly1305 | Any unauthenticated mode |
| A file on disk | `age`, or `gpg --symmetric` | `openssl enc` |
| Sharing with someone you have no shared secret with | Hybrid: ephemeral key + their public key | RSA over the data itself |
| Two parties agreeing a session key | ECDH, ephemeral | A long-lived shared key |
| A password becoming a key | Argon2id or PBKDF2 with a real iteration count | The password as the key |

That last row connects back to the previous topic. `openssl enc -pass pass:...`
has to turn your password into a key, and the default way it does so is the old
one:

```text
$ openssl enc -aes-256-cbc -pass pass:x -in file -out file.enc
*** WARNING : deprecated key derivation used.
Using -iter or -pbkdf2 would be better.
```

It warns, and then does it anyway — exit code 0, ciphertext written. The
deprecated derivation is a single hash pass, which is the previous topic's
mistake in a different tool: a password turned into a key at a cost of
essentially nothing, so guessing the password costs essentially nothing.

Two habits follow. Always pass `-pbkdf2 -iter`, and treat that warning as an
error rather than as noise — a script that has been printing it for three years
has been producing weakly-derived keys for three years.

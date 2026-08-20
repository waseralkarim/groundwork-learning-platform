---
topic: topic.identity-and-least-privilege
section: internals
title: SSH keys, and what least privilege is measured in
order: 3
mode: explain
---

## Public key authentication, step by step

This is A04.2's asymmetric cryptography doing the job most engineers actually
meet it doing.

1. You generate a key **pair**. The private half stays on your machine; the
   public half is a single line of text that is not a secret.
2. The public half is appended to `~/.ssh/authorized_keys` on the server.
3. On connection, the server sends a **challenge** — data including a session
   nonce, so it is different every time.
4. You **sign** it with your private key.
5. The server **verifies** the signature against the public key it has on file.

**No secret crosses the wire, in either direction.** That is the whole reason
this is better than a password: there is nothing to intercept, nothing to replay
— the challenge differs each session — and nothing for a compromised server to
steal, because it only ever had the public half.

You can run steps 3–5 directly, without a server:

```bash
echo "server-challenge-nonce-8f2a1c" > chal.txt
ssh-keygen -Y sign -f alice -n sshtest chal.txt
ssh-keygen -Y verify -f allowed -I alice@ops -n sshtest -s chal.txt.sig < chal.txt
# Good "sshtest" signature for alice@ops with ED25519 key SHA256:F5LX29...
```

Change one byte of the challenge and it becomes `incorrect signature`. Put
somebody else's public key in the allowed list and it fails to verify. That is
authentication, complete, and you will do it in the lab.

## What the key files contain

```bash
$ cat alice.pub
ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIM7+qVy+bm36viryxBFOmL9AGuOgUf06iHG8xjMA1Dsw alice@ops
```

Three fields: algorithm, the key itself in base64, and a **comment**. The comment
is free text — it is not verified, not unique, and not an identity. It is the
only clue you will have about who a key belongs to, which is worth knowing
before you rely on it.

The fingerprint is A04.1 applied to identity:

```bash
$ ssh-keygen -lf alice.pub
256 SHA256:X+yAqncwtc/XTaovdrn19lPpR6V56XevRHRRRvS1mfI alice@ops (ED25519)
```

A SHA-256 digest of the public key, so two keys can be compared at a glance
rather than by eye across 68 base64 characters.

And you can always derive the public half from the private one, which is how you
answer "which of these private keys matches this authorized entry":

```bash
ssh-keygen -y -f alice            # prints the public key
ssh-keygen -y -f carol -P 'correct-horse'   # if it is passphrase-protected
```

The reverse is not possible, which is the point.

## Inside an encrypted private key

Open one and both previous topics are visible:

```text
$ sed -e 1d -e '$d' carol | base64 -d | head -c 60
openssh-key-v1.....aes256-ctr....bcrypt.....

$ sed -e 1d -e '$d' alice | base64 -d | head -c 60
openssh-key-v1.....none....none.....
```

A passphrase-protected key is **AES-256-CTR encrypted**, with the key derived
from your passphrase by **bcrypt** — a deliberately slow KDF, exactly as A04.1
demanded, because the file is a stealable offline target and the passphrase is
all that stands in front of it.

An unprotected key says `none` twice. It is plaintext on disk, and anyone who
reads the file has your identity.

:::warning
`ssh-keygen` sets `0600` on private keys and SSH refuses to use one that is more
permissive:

```text
Permissions 0644 for '/home/deploy/.ssh/id_ed25519' are too open.
This private key will be ignored.
```

That refusal is one of the very few places a tool declines to do what you asked
for your own protection, and it is worth respecting rather than working around.
This lab image has no `sshd`, so that message is captured from a real host
rather than reproduced here.
:::

## Why `authorized_keys` grows and never shrinks

It is the identity equivalent of a firewall rule set. Adding an entry is
routine, urgent and safe-feeling. Removing one risks locking somebody out, and
nobody is sure who a key belongs to, because the only clue is an unverified
comment.

So they accumulate:

```text
alice@ops
bob@ops
deploy@ci-2019        ← a CI system decommissioned three years ago
root@build-01         ← nobody knows; the private half is somewhere
```

Each line is a **permanent, unexpiring credential**. There is no validity
window in the format, no revocation, and no log of use. If the private half of
`root@build-01` was on a laptop that was sold, that access still works.

The audit is one command and almost nobody runs it: count the entries, and
compare against the list of people who should have access. In the lab there are
four entries and three people.

The fixes are structural rather than diligent. **Certificate-based SSH** — the
CA signs short-lived user certificates, so `authorized_keys` is replaced by "any
certificate this CA signed, and they expire in eight hours". Or a bastion that
issues credentials per session. Both replace an append-only list with something
that expires by default, which is the only mechanism that reliably removes
access.

## Least privilege, as a measurement

The principle is easy to state and useless to apply directly. What makes it
actionable is a question with a concrete answer:

> **If this component is fully compromised, what does the attacker reach?**

Answer it for real, listing things:

- Which secrets are mounted, and what does each one open?
- What can the network reach from here?
- What is the uid, and what does that uid own elsewhere?
- What capabilities are in the **bounding** set, not just the effective one?
- What would a shell here be able to do to the rest of the system?

The audit lab does exactly this for four workloads, and the pattern that emerges
is that the excess privilege is almost never the *primary* function. It is a
mounted secret for a feature that was removed, a shared key that also opens
production, a capability inherited from a base image, unrestricted egress on a
service that talks to one database.

Two rules earn their keep:

**Privilege granted for a reason outlives the reason.** Nothing removes it when
the reason goes away, because nothing records why it was granted.

**Shared credentials multiply blast radius.** The nightly cleanup job in the
audit holds the platform's shared deploy key. Compromising a cron job that
deletes old files should not yield the ability to deploy, and it does — not
because anyone decided that, but because there was one key and it was easier.

## Capabilities: measure the ceiling, not the floor

```bash
grep -E '^Cap(Eff|Bnd)' /proc/self/status
/sbin/capsh --decode=<value>
```

- **CapEff** — held now.
- **CapBnd** — the ceiling on what could ever be regained, including through a
  setuid binary.

A process with `CapEff: 0000000000000000` looks unprivileged and, with a
bounding set of fourteen capabilities and nine setuid binaries on the
filesystem, is not as constrained as that zero suggests. `cap_setuid` and
`cap_dac_override` are both in that bounding set here.

This is why `securityContext.capabilities.drop: ["ALL"]` and
`allowPrivilegeEscalation: false` are separate settings that both matter: one
lowers the floor, the other lowers the ceiling. Auditing only the effective set
measures the floor and calls it done.

---
topic: topic.identity-and-least-privilege
section: commands
title: The commands that answer "what do I actually hold"
order: 4
mode: explain
---

## Who am I

```bash
id                          # uid, gid, supplementary groups
id -u; id -g; id -Gn        # the parts, scriptably
whoami                      # uid only, and fails if the uid has no name
grep -E '^(Uid|Gid|Groups):' /proc/self/status
```

Read `/proc/self/status` when the answer matters. `id` consults the name
database; `/proc` reports what the kernel actually has, and they disagree exactly
when it is most interesting — a container running as a uid with no passwd entry.

:::try{lab=who-am-i-really run="id; echo '---'; grep -E '^(Uid|Gid|Groups):' /proc/self/status" title="Two answers to the same question"}
`id` gives you names; `/proc/self/status` gives you the numbers the kernel is
actually enforcing on. The `Uid:` line has four values — real, effective, saved
and filesystem — and the difference between them is what setuid manipulates.
:::

## What am I allowed to do

```bash
grep -E '^Cap(Inh|Prm|Eff|Bnd)' /proc/self/status
/sbin/capsh --decode=00000000a80425fb
```

Full path on `capsh` — `/sbin` is not on an unprivileged PATH, and `command not
found` here does not mean the tool is missing.

Read **CapBnd**, not just CapEff. Effective is what you hold now; bounding is the
ceiling on what could ever be regained. An audit that stops at CapEff will call
a container unprivileged while it retains `cap_setuid` in its bounding set.

## Why was I denied

This is the highest-value command in the topic:

```bash
namei -l /tmp/perms/listable/data.txt
```

```text
f: /tmp/perms/listable/data.txt
drwxr-xr-x root    root    /
drwxrwxrwt root    root    tmp
drwxr-xr-x learner learner perms
drw-r--r-- learner learner listable     ← no x: the path stops here
                            data.txt - Permission denied
```

It walks every component of the path and prints the mode and owner of each. The
culprit is visible — `drw-r--r--`, no execute bit — even though the error you
started with named `data.txt`, which is mode 644 and perfectly readable.

Without `namei` this is a guessing game up the tree. With it, it is one command.

```bash
stat -c '%A %U:%G %n' file        # mode, owner, group in one line
ls -ld dir                        # the directory itself, not its contents
```

`ls -ld` rather than `ls -l` when asking about a directory — without `-d` you get
its contents and not the thing you were asking about.

## Permission bits

```bash
umask                            # what is being removed from new files
umask 0077                       # everything private to the owner
chmod 640 secret.conf
chmod g+rX -R dir/               # capital X: x on directories, not on files
```

`X` is worth knowing. `chmod -R a+x` on a tree makes every data file executable;
`a+rX` sets the execute bit only where it already exists or on directories,
which is almost always what was meant.

:::try{lab=the-bit-that-is-not-read run="/opt/lab/seed-identity.sh >/dev/null; cd /tmp/perms; ls listable; cat listable/data.txt" title="Listing works, reading does not"}
`ls` succeeds because the directory has `r`. `cat` fails because it has no `x`,
so the name inside cannot be resolved. Two independent bits, and the error names
the file rather than the directory that refused.
:::

## Finding privilege on a system

```bash
# Every setuid binary — each one is a potential escalation
find / -xdev -perm -4000 -type f 2>/dev/null

# setgid too
find / -xdev -perm -2000 -type f 2>/dev/null

# World-writable files, which are rarely intended
find / -xdev -perm -0002 -type f 2>/dev/null

# Files with capabilities attached — invisible to a permissions audit
getcap -r / 2>/dev/null
```

`-xdev` keeps it on one filesystem, which matters on a host with network mounts.
`getcap -r` is the one people forget: a binary can hold capabilities without
being setuid, and it will not appear in any of the mode-based searches.

## SSH keys

```bash
ssh-keygen -t ed25519 -C 'alice@ops'      # generate; ed25519 unless told otherwise
ssh-keygen -lf key.pub                     # fingerprint — a SHA-256 of the key
ssh-keygen -y -f privatekey                # derive the public half
ssh-keygen -y -f key -P 'passphrase'       # ...from a protected key
ssh-keygen -p -f key                       # add or change a passphrase
```

`-y` answers "which of these private keys corresponds to this authorized entry",
which is the question that actually comes up.

Sign and verify a challenge directly — this is what authentication does:

```bash
ssh-keygen -Y sign -f alice -n sshtest challenge.txt
ssh-keygen -Y verify -f allowed_signers -I alice@ops -n sshtest \
    -s challenge.txt.sig < challenge.txt
```

The `allowed_signers` format needs quotes around the namespace, which is not
obvious from the error:

```text
alice@ops namespaces="sshtest" ssh-ed25519 AAAAC3Nza...
```

## Auditing authorized_keys

```bash
wc -l < ~/.ssh/authorized_keys                    # how many keys
ssh-keygen -lf ~/.ssh/authorized_keys             # fingerprint each one
awk '{print $NF}' ~/.ssh/authorized_keys          # the comments, such as they are
```

Then compare the count against the number of people who should have access. The
comment is free text, unverified and not an identity — but it is the only clue
there is, and a comment naming a system decommissioned three years ago is a
finding on its own.

## Reading a private key's own header

```bash
sed -e 1d -e '$d' privatekey | base64 -d | head -c 60 | tr -c '[:print:]' '.'
```

`aes256-ctr` and `bcrypt` means it is passphrase-protected. `none` twice means
it is plaintext on disk, and anyone who reads the file has that identity.

## The five worth keeping

```bash
id; grep -E '^Cap(Eff|Bnd)' /proc/self/status    # who am I, what do I hold
namei -l /path/that/failed                        # why was I denied
find / -xdev -perm -4000 -type f 2>/dev/null      # what can escalate
getcap -r / 2>/dev/null                           # ...including invisibly
ssh-keygen -lf ~/.ssh/authorized_keys             # who can log in as me
```

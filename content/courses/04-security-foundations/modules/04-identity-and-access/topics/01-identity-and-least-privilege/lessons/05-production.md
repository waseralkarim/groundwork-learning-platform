---
topic: topic.identity-and-least-privilege
section: production
title: Blast radius, and the privilege nobody granted on purpose
order: 5
mode: explain
---

## Ask the question that has an answer

"Is this least privilege?" is unanswerable and produces meetings. Replace it:

> **If this is fully compromised, what does the attacker reach?**

Then list things. Secrets mounted, network reachable, files owned, capabilities
in the bounding set, what a shell here could do next. The list is finite, it can
be written down, and two engineers will produce nearly the same one — which is
what makes it a review rather than an opinion.

It also reframes the argument productively. "You should not run as root" invites
a debate about necessity. "Compromising the log shipper currently yields the
cloud admin key" invites a fix.

## Where excess privilege actually comes from

Almost never from a bad decision. From reasonable ones nobody revisited:

**The reason outlived.** A capability added to debug a problem in 2023. A secret
mounted for a feature since removed. Nothing records *why* a permission exists,
so nothing triggers its removal when the why goes away.

**Convenience under pressure.** It was 2am, the narrow credential did not work,
the broad one did, and the ticket to narrow it was never written.

**Inherited from a base image.** A `USER` line missing, capabilities the parent
image set, a setuid binary in a package installed for one tool. You did not grant
it and you own it.

**Sharing.** One deploy key for everything, because per-service keys meant
managing more keys. Now the cleanup cron can deploy.

**Copied from something that worked.** The most common of all. A manifest copied
from a service that genuinely needed privilege, into one that does not.

None of these appear in a manifest review as *wrong*. They appear as normal, and
the only thing that finds them is measuring what a component holds against what
it does.

## SSH access decays in one direction

`authorized_keys` and its equivalents accumulate. Adding is urgent and safe;
removing risks an outage and nobody is sure who a key belongs to.

Three properties make this worse than it sounds:

- **No expiry.** The format has no validity window. A key added in 2019 works
  today.
- **No revocation.** Removing the line is the only mechanism, and it requires
  knowing which line.
- **No identity.** The comment is unverified free text. `root@build-01` tells you
  nothing checkable.

Diligence does not fix an append-only list; structure does:

**SSH certificates.** A CA signs short-lived user certificates and the server
trusts the CA rather than a list of keys. Access expires by default — typically
hours — so removing someone means not reissuing. This is the single biggest
improvement available and it is well-supported and rarely deployed.

**A bastion issuing per-session credentials**, with a log of who connected to
what and when. Solves the audit problem as well as the expiry one.

**Failing both, an audit with teeth**: count the entries, name a human owner for
each, and remove anything unowned. Any key nobody will claim should be removed
today — if it turns out to be needed, someone will say so within an hour, and
that is how you learn who owns it.

## Containers: the settings that matter

The measurement translates directly:

```yaml
securityContext:
  runAsNonRoot: true
  runAsUser: 10001
  allowPrivilegeEscalation: false     # lowers the ceiling
  readOnlyRootFilesystem: true
  capabilities:
    drop: ["ALL"]                     # lowers the floor
```

`drop: ["ALL"]` and `allowPrivilegeEscalation: false` are different controls and
both are needed. The first empties the effective set; the second stops a setuid
binary refilling it. Auditing only the effective set — which is what most
tooling reports — measures the floor and misses the ceiling.

`readOnlyRootFilesystem` is the one people skip because something breaks. What
breaks is usually a temp directory, fixed with an `emptyDir`, and the payoff is
that an attacker cannot write a binary anywhere it will persist.

And verify on the running workload rather than the manifest — the whole point of
this topic:

```bash
kubectl exec deploy/api -- id
kubectl exec deploy/api -- grep -E '^Cap(Eff|Bnd)' /proc/self/status
kubectl exec deploy/api -- find / -xdev -perm -4000 -type f 2>/dev/null
```

## What to check on a system you inherit

Half an hour, and it is worth more than a week of policy documents:

```bash
# Who can log in, and does that match the humans?
sudo wc -l /home/*/.ssh/authorized_keys /root/.ssh/authorized_keys 2>/dev/null

# Who can become root without a password?
sudo grep -rE 'NOPASSWD|ALL=\(ALL\)' /etc/sudoers /etc/sudoers.d/ 2>/dev/null

# What can escalate?
sudo find / -xdev -perm -4000 -type f 2>/dev/null
sudo getcap -r / 2>/dev/null

# What runs as root that need not?
ps -eo user,comm --sort=user | uniq -c | sort -rn | head -20

# Which accounts have a shell and a password hash, and are they people?
sudo awk -F: '$7 !~ /nologin|false/ {print $1, $7}' /etc/passwd
```

The last one finds service accounts with interactive shells, which is a
finding roughly every time.

## The two sentences worth keeping

**Authentication is a door and authorization is what is behind it.** Most of the
effort goes into the door, and the damage is decided by the room.

**Privilege is measured by what a compromise reaches, not by what a manifest
says.** The manifest is intent; the running process is fact; and they differ
often enough that measuring is the only honest way to answer.

That is also where this course ends up, across all four topics. Hashing,
encryption and certificates each had a version of the same lesson — the
primitive is rarely the weakness, and naming it is how a design avoids
discussing the parts that are. Here the primitive is a permission bit, and the
weakness is nobody having asked what the process actually holds.

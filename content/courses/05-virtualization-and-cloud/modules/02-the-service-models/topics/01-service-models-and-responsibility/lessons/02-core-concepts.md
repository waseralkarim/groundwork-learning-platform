---
topic: topic.service-models-and-responsibility
section: core-concepts
title: One stack, four places to draw the line
order: 2
mode: explain
---

## The stack, once

Every deployment of every application has roughly the same layers. Listing them
in order is the whole trick, because once they are written down the service
models stop being categories and become a position:

```text
data                              ← always yours
access control                    ← always yours
configuration                     ← always yours
application code
application runtime
database software
container runtime
guest OS  ·  OS patching
hypervisor  ·  firmware  ·  hardware
power  ·  cooling  ·  physical security
```

A service model is a horizontal line through that list. Everything above it is
yours; everything below is somebody else's.

:::diagram{src=../diagrams/the-boundary.mmd caption="Four lines through one stack — and the three layers above every line"}
:::

## The four positions

**Colocation** — you rent space, power and a network drop. The hardware is
yours, which means firmware, disks and the replacement of both. Fourteen of the
seventeen layers are yours.

**IaaS** — the line sits under the guest OS. The provider handles hardware,
firmware and the hypervisor; you get an image and everything from there up,
including every OS patch, forever. Eleven layers.

**PaaS** — the line moves up past the OS, the container runtime and the database
software. You supply an image and a schema. Eight layers, plus three **shared**.

**SaaS** — you have stopped running the application. Three layers.

The progression is not "worse to better". Each step removes work and adds
dependency, and both halves are real.

## What each step actually costs

Moving up removes work you were doing badly — most organisations patch operating
systems worse than a cloud provider does — and takes away control you may need:

**Control over timing.** On IaaS you decide when to patch. On PaaS the provider
decides *that* you will and you decide *when* within a window. On SaaS you find
out afterwards.

**Control over version.** You can pin a PostgreSQL minor version on IaaS
indefinitely. On managed PostgreSQL you can defer and not decline.

**Visibility.** You can read a kernel log on IaaS. On PaaS you get what is
exported. On SaaS you get a status page, and the status page is the vendor's
opinion of whether you are having an outage.

**Exit cost.** It rises at every step and is rarely priced at the point the
decision is made. Moving off IaaS is mostly moving VMs. Moving off a managed
database is a migration. Moving off SaaS is a project, sometimes an
impossible one.

**Concentration risk.** Everything you run comes to depend on one provider's
control plane. That is a real trade and not a reason to avoid it — it is a
reason to know your failure domains, which the next module is about.

## The three that never transfer

Compute the intersection of "yours" across all four deployments and exactly
three survive:

**Data.** Its contents, who may see it, how long it is kept, and whether it
should exist. No provider can know your retention obligations.

**Access control.** Who has an account, what it can do, and what happens when
they leave. Every provider gives you excellent tools and none of them decides
your policy.

**Configuration.** The settings you chose. A bucket is private by default and
public because something set it that way.

The reason these three matter more than their number suggests: they are exactly
where breaches happen. Not kernel escapes and hypervisor bugs — those exist and
are rare — but a public bucket, an over-permissive role, and a default
credential.

:::warning
"We moved to SaaS so security is handled" is the most expensive sentence in this
topic. SaaS removes fourteen of your seventeen layers and leaves the three that
appear in breach reports. The work that remains is smaller, more important, and
nobody else can do it.
:::

## The shared band

PaaS is the only model with layers that are genuinely both parties'. Three of
them, and each has the same shape — **the provider acts and you must respond**:

| Layer | Provider does | You must |
|---|---|---|
| OS patching | publishes new node images | roll nodes onto them |
| Database patching | applies the patch | choose the window |
| Backups | takes them | verify a restore works |

Every one of these fails when read as "theirs". A node image published and never
rolled leaves you on the vulnerable version with a green dashboard. A backup
taken faithfully and never restored is a file of unknown quality.

:::predict{question="A managed database provider takes automated backups daily, retains them 35 days, and reports every backup as successful. What have you actually got?"}

An untested claim, and possibly a serious gap.

Three things are unverified until you check them yourself. **Whether a restore
works** — the only test of a backup is a restore, and "backup succeeded" means a
file was written. **What the RPO is** — daily backups mean up to 24 hours of
data loss, which may be far outside what anyone has agreed. And **how long a
restore takes** — restoring a large database can take hours, and that is your
RTO whether or not anybody has written it down.

The provider's responsibility is to take the backup. Yours is to know what it is
worth, and that is a shared layer read as theirs.

## Fault is not preventability

The distinction that decides most incident reviews, and the one people conflate.

**Fault** is whose mistake it was. **Preventability** is who could have stopped
it. In the provider's layers they are the same party. In the shared band they
are different, and that is what makes those incidents contentious.

A provider changes a default seccomp profile in a node image, announces it 30
days ahead, and your application breaks because it used a blocked syscall. The
*change* was theirs; the *outage* was preventable by you, and the mechanism —
reading release notes and testing node images before rolling them — is the
shared layer working as designed.

Answering "whose fault" ends the conversation. Answering "who could have
prevented it, and what would that have taken" produces an action. Both questions
are legitimate; only one of them improves anything.

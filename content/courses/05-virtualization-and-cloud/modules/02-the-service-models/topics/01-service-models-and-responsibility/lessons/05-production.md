---
topic: topic.service-models-and-responsibility
section: production
title: The band where things fall between two parties
order: 5
mode: explain
---

## Shared layers need a named owner on your side

The provider's half of a shared layer is automatic. Yours is not, and nothing
fails when you skip it — which is precisely why it gets skipped.

Four shared layers, and the mechanism each one needs:

| Layer | They do | You need |
|---|---|---|
| Node OS images | publish | a rolling upgrade cadence, and an alert on image age |
| Managed DB patches | apply | a maintenance window that is not "any" |
| Backups | take | a scheduled restore test into a scratch environment |
| Deprecations | announce | somebody owning the provider's change feed |

The common shape: **they do the doing, you do the noticing.** Noticing has no
error state, so it needs a schedule and a name against it or it does not happen.

If you write one thing down after this topic, make it a list of your shared
layers with an owner for each. Most teams have never written that list, and the
act of writing it usually finds one that nobody had.

## The default that is a decision

Managed services ship with defaults that are choices you did not make:

- Maintenance window: **any time**. Which is how a three-hour database patch
  lands at 14:00 on a Tuesday.
- Backup retention: whatever the provider picked, which may be shorter than what
  you have agreed with someone.
- Auto-upgrade: on or off, and both are wrong for somebody.
- Deletion protection: usually off.

None of these are hidden. All of them are left alone, because the service works
without touching them and there is no moment that forces the question. Setting a
maintenance window is a two-minute change that prevents an entire class of
incident, and it is the single highest-value thing to check on a managed
database you have inherited.

## Reading a status page

The status page is the vendor's opinion of whether you are having an outage, and
the two frequently disagree.

Status pages are usually per-service and per-region, updated by humans, and lag
the actual event — often by longer than your own detection. A green page during
your incident means "not yet acknowledged", not "not happening".

So: **do not use a vendor status page as a detection mechanism.** Use your own
monitoring to detect, and the status page to confirm and to communicate. And
subscribe to the machine-readable feed rather than checking a web page, because
during an incident nobody remembers to check.

The related habit: when you suspect a provider issue, capture the evidence
*now* — request ids, timestamps, error bodies, region. Support conversations go
very differently with them, and they are unavailable afterwards.

## What moving up actually buys, and costs

The honest framing for a decision document:

**Buys:** people back. A team of four cannot patch operating systems, run a
database and build a product. It also buys a level of operational quality most
organisations cannot reach — cloud providers patch and run infrastructure better
than almost anyone does in-house, because it is the only thing they do.

**Costs:** control over timing and version, visibility into what is happening,
exit cost that rises with every step, and concentration risk as more of your
estate comes to share one provider's control plane and its bad days.

Both halves are real. The failure is not choosing a model — it is choosing one
without writing down what was given up, so that two years later nobody knows why
the database is somewhere with a two-week migration path.

## The three that stay, in production terms

Data, access control and configuration are yours at every model. What that means
concretely:

**Data.** Classification, retention, residency, and encryption above the
provider's layer where it matters. A provider encrypts at rest by default and
that protects against a stolen disk — the A04 lesson applies unchanged.

**Access control.** Who has an account and what it may do, across your own
systems *and* the provider's console. The provider gives you excellent tools;
the policy is yours, and so is removing people who have left.

**Configuration.** Everything you set, and everything you left at its default. A
public bucket is a configuration; so is a maintenance window of "any".

These three do not shrink as you move up the models. They become a larger
fraction of what you own, which is the opposite of how the move usually gets
described.

## Fault, preventability, and what a postmortem should ask

Provider incidents produce a predictable and useless conversation about blame.
The version that improves something asks three questions in order:

1. **What happened, technically?** Facts before attribution.
2. **Who could have prevented it, and what would that have taken?** Not whose
   fault — who had the ability. In shared layers this is frequently you, even
   when the change was theirs.
3. **What do we change so the next one costs less?** Usually not "switch
   provider". Usually a mechanism on your side of a shared layer, or a
   dependency that should not have been in series.

The third is where the value is, and blame conversations reliably prevent
reaching it.

## The inherited-system checklist

Half an hour, on any cloud estate you have just taken over:

```text
1. Which managed services are we on, and what is each one's maintenance window?
2. Which layers are shared, and who owns our half of each?
3. When did a restore last run — not a backup, a restore?
4. What is our real availability, with every dependency multiplied?
5. Who reads the provider's deprecation feed?
6. What would it take to leave each managed service, roughly?
```

Question 3 finds the most serious thing most often. Question 5 usually has no
answer at all, and the deprecation that eventually causes an outage was
announced twelve months earlier to an address nobody reads.

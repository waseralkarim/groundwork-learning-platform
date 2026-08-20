---
topic: topic.service-models-and-responsibility
section: internals
title: Reading a responsibility claim for what it leaves out
order: 3
mode: explain
---

## The vendor diagram is accurate and incomplete

Every major provider publishes a version of this:

```text
We are responsible for SECURITY OF THE CLOUD:
  physical infrastructure, hardware, virtualisation, the managed services

You are responsible for SECURITY IN THE CLOUD:
  your data, your access control, your configuration
```

Nothing in it is false. It is a good summary and it should be read for three
things it does not say.

**It does not name the shared band.** The diagram has two columns. The layers
where both parties must act — patch published, patch adopted — appear in
neither, and they are where incidents cluster.

**It does not describe availability.** It is a *security* model. It says nothing
about who is responsible when the service is simply down, which is a different
question with a different answer and its own document.

**It does not quantify.** "Your data" and "physical infrastructure" occupy equal
space on the page and are wildly different amounts of work. The count — 14, 11,
8, 3 — is not in any vendor diagram, and it is the number that would change how
people plan.

The phrase to notice is **"undifferentiated heavy lifting"**. It is usually
accurate: patching an OS does not distinguish your product. It is also the
sentence that moves the conversation away from what you are handing over with
it, and that is worth doing deliberately rather than by agreement.

## Reading an SLA as a number

A vendor's availability promise is arithmetic, and the arithmetic is worth doing
once because the numbers are smaller than they sound:

| SLA | Downtime per month | Per year |
|---|---|---|
| 99% | 7h 12m | 3d 15h 36m |
| 99.9% | 43m 11s | 8h 45m 35s |
| 99.95% | 21m 35s | 4h 22m 47s |
| 99.99% | 4m 19s | 52m 33s |
| 99.999% | 25s | 5m 15s |

*(30-day month, 365-day year. Vendors measure per calendar month, so a 31-day
month is slightly more forgiving — which is itself worth knowing when a figure
is disputed.)*

Three things follow that people routinely miss.

**Your availability is the product of your dependencies.** A service on three
components at 99.9% each, all required, is 0.999³ = **99.7003%** — **2h 9m** a
month, not 43 minutes. Dependencies in series multiply, and almost nobody counts
them all. Add a fourth and it is 99.6%; add ten and the promise on the page has
become 99%.

**The SLA is a refund, not a guarantee.** Missing 99.9% typically means a
service credit worth a fraction of your bill, which will not cover what the
outage cost you. It is a statement of intent with a penalty attached, not a
promise about physics.

**The measurement window is the vendor's.** Monthly and per-service, so a
six-hour outage in one region on one service may fall inside the promise once
averaged. Read what is being measured before treating the number as your
availability.

## What "shared" costs operationally

Each shared layer needs a named owner and a mechanism on your side, or it is not
being done:

**OS patching on managed nodes.** The provider publishes; you roll. Without a
schedule, nodes drift and the dashboard stays green because nothing is failing —
you are simply running the old image. The mechanism is a rolling node upgrade on
a cadence, plus an alert on node image age.

**Managed database patching.** The provider will apply it. Your only control is
*when*, and the default is "any time". Setting a window is a two-minute change
that prevents a class of incident, and it is left at the default constantly.

**Backups.** They are taken. The mechanism you need is a **restore test** on a
schedule, into a scratch environment, asserting that the data is usable. Until
that has run, you have a file.

**Deprecations.** Providers remove things with notice. The notice arrives by
email to an address nobody reads. The mechanism is somebody owning the
provider's change feed and the deprecation calendar for services you use.

The pattern in all four: **the provider does the doing and you must do the
noticing.** Shared layers fail silently, because nothing on your side errors when
you have not noticed.

## Choosing a model

The honest version of the decision has three inputs, and headcount dominates:

**How many people do you have?** A team of four cannot patch operating systems,
run a database, and build a product. Moving up buys people back, and it is the
single largest factor.

**What is genuinely differentiating?** Your product is. Your PostgreSQL
configuration is almost certainly not. Spending scarce attention on the
undifferentiated part is a real cost even when you do it well.

**What can you not give up?** A specific version, a compliance requirement about
data location, a latency floor, a plausible exit. These are constraints rather
than preferences, and they pull the line back down.

Two considerations that belong in the decision and rarely appear:

**Exit cost**, which rises at every step and is never priced when it is cheapest
to think about. And **concentration risk** — the more you move up, the more of
your estate shares one provider's control plane and its bad days.

Neither is a reason not to move up. Both are reasons to write down what you are
accepting, so the next person can see it was a decision.

## The audit worth running

On any system you have inherited, four questions with checkable answers:

```text
1. For every layer, who patches it — named team or named provider service?
2. Which layers are shared, and what is our mechanism for each?
3. When did we last verify a restore, rather than a backup?
4. What is our actual availability, given every dependency multiplied?
```

Question 2 finds the most, because "shared" is where things fall between two
parties who each believe the other has it. Question 3 finds the most serious,
because a backup nobody has restored is the single most common untested
assumption in operations.

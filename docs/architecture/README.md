# Architecture Documentation

Read in order on a first pass.

| # | Document | Answers |
|---|---|---|
| 1 | [Vision and Principles](01-vision-and-principles.md) | What are we building and what will we refuse to compromise on? |
| 2 | [Technology Stack](02-technology-stack.md) | What are we building it with, and what did we reject? |
| 3 | [System Architecture](03-system-architecture.md) | What are the services, how do they talk, how is the repo laid out? |
| 4 | [Content Model](04-content-model.md) | How is curriculum authored, validated and versioned? |
| 5 | [Data Model](05-data-model.md) | What does the database look like? |
| 6 | [Lab Architecture](06-lab-architecture.md) | How do learners run real systems safely? |
| 7 | [Security](07-security.md) | What is the threat model and what defends against it? |
| 8 | [Testing and Observability](08-testing-and-observability.md) | How do we know it works, and how do we see it working? |

Related:
- [Curriculum Roadmap](../curriculum/ROADMAP.md) — the actual product
- [Delivery Phases](../plan/DELIVERY-PHASES.md) — build order and Definition of Done
- [First Topic Plan](../plan/TOPIC-0.1-IMPLEMENTATION-PLAN.md) — where we start

## The five decisions that matter most

Everything else is reversible. These are the ones to argue about now.

1. **Content is Markdown + YAML in git, not MDX and not a CMS.** It keeps content
   validatable, gradeable server-side, and independent of the frontend framework.
   ([§2.7](02-technology-stack.md#27-content-format--markdown--yaml-not-mdx))
2. **Content database rows are keyed by a deterministic UUIDv5 of a stable content ID.**
   Renaming, reordering or retitling content can never orphan a learner's progress.
   ([§5](05-data-model.md))
3. **The lab plane is architecturally separate from the application plane**, and lab
   isolation is tiered so we ship useful labs long before we build the hard sandbox.
   ([§6](06-lab-architecture.md))
4. **The content linter is a build gate.** The Definition of Done is machine-checked, which
   is the only reason to believe a 700-topic curriculum will stay consistent.
   ([§4.3](04-content-model.md#43-validation-pipeline))
5. **The platform is a teaching artifact.** Its own Compose file, pipeline, dashboards and
   Terraform get quoted into lessons, which means "good enough for a side project" is not
   good enough here. ([§1.6](01-vision-and-principles.md#16-engineering-principles))

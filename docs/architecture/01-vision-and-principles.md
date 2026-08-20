# 1. Vision and Principles

## 1.1 What this is

A self-hosted learning environment for DevOps engineering. It must be able to take someone
who does not know what a process is, and — following a single ordered path — leave them
able to design, build, deploy, secure, observe, troubleshoot and scale production systems.

## 1.2 What this is not

- Not a documentation site with a sidebar.
- Not a video course index.
- Not a "copy this command" tutorial collection.

The distinguishing feature is that **every concept is accompanied by something the learner
has to do**, and most of those things involve a real machine that can really break.

## 1.3 The five learning modes

Every substantial topic delivers content in five modes. This is the core product idea and
it drives the entire data model.

| Mode | Purpose | Learner activity |
|---|---|---|
| **Explain** | Build the mental model from first principles | Read, study diagrams |
| **Show** | Ground the model in reality | Read annotated commands, output, config |
| **Do** | Guided practice with known-good steps | Follow a lab, verified step by step |
| **Break** | Diagnostic skill — the actual job | Given symptoms only, find root cause |
| **Design** | Judgement — the senior/architect skill | Choose between trade-offs, defend it |

Most learning platforms stop at *Show*. A few reach *Do*. **Break** and **Design** are
where DevOps competence actually lives, and they are the parts we must not compromise on.

## 1.4 Difficulty ladder

Every topic is authored across five levels. A learner may traverse only the levels they
need, but content must exist for all five before a topic is considered complete.

| Level | Named | The learner can... |
|---|---|---|
| L1 | Beginner | ...explain what it is and why it exists |
| L2 | Intermediate | ...use it correctly for normal tasks |
| L3 | Advanced | ...troubleshoot it and automate it |
| L4 | Expert | ...run it in production, with failure modes understood |
| L5 | Architect | ...design systems with it, and justify the trade-offs |

## 1.5 Content quality rules (enforced, not aspirational)

These are checked by an automated content linter in CI, not left to good intentions.

1. **No undefined terminology.** Every term used must be defined in the topic that
   introduces it or in a prerequisite topic. The linter maintains a glossary index and
   fails on first-use of an undefined term.
2. **Objectives are measurable.** Every topic declares learning objectives using action
   verbs that map to an assessable item. "Understand networking" fails lint; "Given a
   CIDR block, compute the usable host range" passes.
3. **Every objective has an assessment item.** Linter cross-references objective IDs
   against quiz questions, exercises and labs. Orphan objectives fail.
4. **Prerequisites form a DAG.** Cycle detection at ingest time.
5. **Explain *why* and *how it works inside*, not only *how to use*.** Topics declare
   required sections; missing `internals` or `why-it-matters` sections fail lint for
   L3+ content.
6. **Production reality is separated from development convenience.** Any topic that shows
   a command that is unsafe in production must carry a `production-note` block.
7. **Version-sensitive content is tagged.** Any command or API that changed behaviour
   across versions carries a `since:` / `deprecated:` marker with the version pinned in
   `content/versions.yaml`.

## 1.6 Engineering principles

- **Content is data, not code.** Curriculum lives in git as Markdown + YAML with schemas.
  It is never embedded in React components. Reordering the curriculum must be a YAML edit.
- **The platform is itself a teaching artifact.** Its Compose file, its Dockerfiles, its
  CI pipeline, its Prometheus rules and its Terraform are all quoted *from the real repo*
  into lessons. Nothing taught is fake. This is a hard constraint on how we build it: if
  we would be embarrassed to show it in a lesson, it is not good enough to merge.
- **Local-first, cloud-ready.** `docker compose up` is the primary target. The
  architecture must survive translation to Kubernetes without a rewrite: no shared
  filesystem assumptions, config from environment, stateless services, health and
  readiness endpoints from day one.
- **Assume the learner is hostile.** Not because you are, but because the lab design is
  only correct if it holds against someone trying to escape it. See
  [06-lab-architecture.md](06-lab-architecture.md).
- **Boring technology.** Every dependency must justify itself against "could we do this
  with Postgres and standard library". Mature > popular.
- **Incremental and vertical.** We ship thin end-to-end slices, one topic at a time.
  No horizontal "build all the models first" phases.

## 1.7 The single most important constraint

The curriculum is the product. The application is the delivery mechanism.

If we ever find ourselves spending three weeks on an application feature and zero weeks on
curriculum, we have drifted. Application work is justified only when it unblocks
curriculum that cannot be delivered without it.

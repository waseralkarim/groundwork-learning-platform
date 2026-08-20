# 4. Content Model

## 4.1 Hierarchy

```
LearningPath          "DevOps Engineer"
 └── Level            L0 Foundations … L5 Architect  (a tag, not a container)
      └── Course      "Containers & Docker"
           └── Module "Images and Layers"
                └── Topic  "How the layered filesystem works"   ← the unit of work
                     ├── Lesson         (prose, the Explain + Show modes)
                     ├── Lab[]          (Do)
                     ├── Exercise[]     (Do, ungraded practice)
                     ├── Troubleshooting[]  (Break)
                     ├── DesignChallenge[]  (Design)
                     ├── Quiz           (knowledge check)
                     ├── InterviewSet   (beginner→architect questions + model answers)
                     └── Assessment     (the gate)
Project               spans many courses; referenced, not nested
```

**Topic is the unit of work.** "Build the next topic" means producing every child of one
Topic node. A Topic is sized to 45–120 minutes of learner time. If it exceeds that, it
splits.

## 4.2 Authoring format

Prose in Markdown, structure in YAML, both in git, both schema-validated.

### `topic.yaml`

```yaml
id: topic.foundations.machine            # stable, never changes
slug: the-machine
title: "The Machine: CPU, Memory, Storage"
summary: "What a computer physically does when it runs your program."
order: 1
levels: [L1, L2]
estimated_minutes: 90

prerequisites: []                        # topic ids
unlocks: [topic.foundations.os-kernel]

objectives:
  - id: OBJ-0.1.1
    level: L1
    verb: explain
    statement: "Explain the roles of CPU, RAM and persistent storage."
    assessed_by: [quiz.q1, quiz.q2, exercise.e1]
  - id: OBJ-0.1.3
    level: L2
    verb: analyse
    statement: "Given vmstat output, classify a workload as CPU-, memory- or I/O-bound."
    assessed_by: [troubleshooting.slow-server, assessment.part-b]

sections:                                # enforced by linter per level
  - overview
  - why-it-matters
  - core-concepts
  - internals
  - commands
  - common-mistakes
  - production-considerations

terminology:                             # feeds the global glossary
  - term: instruction cycle
    definition: "Fetch, decode, execute — the loop a CPU repeats."
  - term: syscall
    definition: "A request from user space asking the kernel to do privileged work."

tags: [hardware, cpu, memory, fundamentals]
versions_used: []                        # references content/versions.yaml keys
```

### `lesson.md`

```markdown
---
topic: topic.foundations.machine
section: core-concepts
---

## What actually happens when you run a program

...prose...

:::objective{id=OBJ-0.1.1}

:::terminal{title="Look at your own CPU" verify=false}
$ lscpu | head -12
:::

:::diagram{src=./diagrams/instruction-cycle.mmd caption="The fetch-decode-execute loop"}

:::warning{scope=production}
`free -h` "free" column is not "available". Read the `available` column.
:::
```

### `quiz.yaml`

```yaml
id: quiz.foundations.machine
pass_score: 70
questions:
  - id: q1
    type: single_choice          # single_choice | multi_choice | ordering | fill_command | short_answer
    level: L1
    objectives: [OBJ-0.1.1]
    stem: "Which statement about RAM is true?"
    options:
      - { id: a, text: "Contents survive a power loss" }
      - { id: b, text: "Contents are lost on power loss", correct: true }
      - { id: c, text: "It is slower than an SSD" }
    explanation: >
      RAM is volatile...
    distractor_notes:
      c: "Common confusion — SSDs are ~1000× slower than RAM."
```

`correct` and `explanation` are **stripped server-side** before the quiz is sent to the
browser. They are returned only with a graded attempt.

### `labs/01-inspect-the-machine.yaml`

```yaml
id: lab.foundations.inspect-machine
title: "Inspect the machine you are running on"
type: guided                     # guided | challenge | troubleshooting
tier: 2                          # isolation tier required — see 06-lab-architecture
image: devopspath/lab-foundations:1
duration_minutes: 20
objectives: [OBJ-0.1.1, OBJ-0.1.2]

setup:
  - run: /opt/lab/seed.sh        # runs inside the container before the learner attaches

steps:
  - id: s1
    instruction: "Find out how many CPU cores this machine has."
    hint: "`lscpu` summarises what the kernel knows about the CPU."
    verify:
      - type: command_ran
        pattern: "^lscpu|nproc"
  - id: s2
    instruction: "Report total memory in MiB into /tmp/answer-memory"
    verify:
      - type: file_exists
        path: /tmp/answer-memory
      - type: file_matches
        path: /tmp/answer-memory
        pattern: '^\d+$'
      - type: command_output
        command: "cat /tmp/answer-memory"
        equals_command: "awk '/MemTotal/ {print int($2/1024)}' /proc/meminfo"

solution:
  explanation: >
    ...why this works, and what the numbers mean...
```

**Verification is declarative.** Authors never supply shell to be run on our host — they
supply checks from a fixed, audited vocabulary that `labcheck` executes *inside* the lab.

### `troubleshooting/slow-server.yaml`

```yaml
id: trouble.foundations.slow-server
title: "The application server got slow at 14:00"
level: L3
reveal_policy: progressive       # symptoms → hints → method → solution, learner-gated
symptoms:
  - "Response times went from 40ms to 2.5s"
  - "No deploy happened today"
artifacts:                       # what the learner is given to reason from
  - type: command_output
    label: "vmstat 1 5"
    content: |
      procs -----------memory---------- ---swap-- ...
  - type: log
    label: "/var/log/app/app.log tail"
    content: |
      ...
diagnostic_questions:
  - "Is the bottleneck CPU, memory or I/O? What in the output tells you?"
root_cause: >
  ...
method: >
  The generalisable procedure, not just this answer...
```

The `reveal_policy: progressive` field is doing real pedagogical work: the API refuses to
serve `root_cause` until the learner has submitted a hypothesis. Handing over the answer
immediately is the failure mode of every troubleshooting tutorial on the internet.

## 4.3 Validation pipeline

Run in CI and before every ingest. **This is how the Definition of Done is enforced.**

```
content/ ──► parse ──► schema validate ──► semantic lint ──► link check ──► ingest
                            │                    │               │
                     JSON Schema per       ┌─────┴──────┐   internal refs,
                     content type          │            │   external URLs,
                                   objectives have  prereq DAG   image paths
                                   assessments     has no cycles
                                           │            │
                                   undefined terms  orphan content
                                   (glossary)      (unreachable topic)
```

Lint rules, all failing the build:

| Rule | Rationale |
|---|---|
| Every objective referenced by ≥1 assessable item | §1.5.3 |
| Every assessable item references ≥1 objective | Prevents busywork content |
| Prerequisite graph is acyclic | Ordering must be computable |
| No topic unreachable from a learning path | No orphan content |
| Every term used is in the glossary or a prerequisite topic's terminology | §1.5.1 |
| Required sections present for the declared levels | §1.5.5 |
| Objective statements use an approved measurable verb | §1.5.2 |
| Every code block declares a language | Rendering + testability |
| Every quiz question has an explanation | Wrong answers must teach |
| Version-sensitive commands reference `versions.yaml` | §1.5.7 |
| Every lab has at least one `verify` check | No unverifiable "labs" |

## 4.4 Versioning and reuse

- **Versioning is git.** Content has no in-database version history; the database is a
  projection. `content_version` records the ingested commit SHA so a learner's progress can
  be attributed to the content revision they saw.
- **Ingestion is idempotent.** Keyed on the stable `id` field, never on file path or title.
  Renaming a directory or retitling a topic must not orphan anyone's progress. This is the
  classic failure of content platforms and we design it out on day one by deriving the
  database primary key as a deterministic **UUIDv5 of the content `id`**.
- **Reuse by reference.** A lab or quiz question can be referenced from multiple topics
  (`ref:` in YAML). Content is never copy-pasted between topics; the linter flags
  near-duplicate blocks.
- **Deprecation, not deletion.** Removing content marks it `status: retired` so existing
  progress records stay resolvable.

## 4.5 Authoring workflow

```
1. Design the topic in docs/plan/  (the design step happens before any content is written)
2. Scaffold:      task content:new -- --course 01 --module 01 --topic the-machine
3. Write lesson.md, then labs, then quiz, then assessment
4. task content:lint            # fast local feedback
5. task content:ingest          # into local Postgres
6. Read it in the UI — if it is boring to read, it is not finished
7. PR → CI runs full validation + link check + rendering smoke test
```

Content and code live in the same repository through v1. Splitting `content/` into its own
repo is a future option that the architecture already permits — nothing in `content/`
imports from `services/`.

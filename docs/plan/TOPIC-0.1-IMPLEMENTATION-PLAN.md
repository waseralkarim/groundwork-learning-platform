# First Topic — Detailed Implementation Plan

## Recommendation

**Track A → Course A01 "Computing Foundations" → Module M01 "How a Computer Runs Your Code"
→ Topic T01: "The Machine — CPU, Memory, Storage, and What 'Running a Program' Actually
Means."**

### Why this topic first

- It is genuinely first. Nothing in the roadmap precedes it; its prerequisite list is empty.
- It is the topic most platforms skip, and skipping it is why engineers later cannot reason
  about OOM kills, `exec format error`, page cache, or why a container is "just a process".
- Its labs are naturally **Tier 1/2** — inspecting a machine — so it exercises the full
  content pipeline without needing the lab broker to exist yet.
- It **foreshadows deliberately**: virtual memory → cgroup limits; user/kernel space →
  namespaces; CPU architecture → multi-arch images; storage persistence → volumes and PVs.
  Every forward reference is registered so later topics can call back to it.

### Its place in the curriculum

```
[ START ] → A01.M01.T01  The Machine
                 ↓
           A01.M01.T02  From Source Code to a Running Process
                 ↓
           A01.M02.T01  User Space and the Kernel
                 ↓
           A02  Operating Systems → B06 Linux Fundamentals → ...
```

**Prerequisites:** none. Assumed knowledge: can open a terminal and type a command. That
is the entire assumption, and even that is bootstrapped in the topic's preface.

---

## Subtopic breakdown

| # | Subtopic | Level | Est. |
|---|---|---|---|
| 1 | What a computer is made of: CPU, RAM, storage, buses, I/O | L1 | 10m |
| 2 | The instruction cycle: fetch, decode, execute — and why binaries are architecture-specific | L1–L2 | 15m |
| 3 | The memory hierarchy: registers → cache → RAM → SSD → network, and the latency numbers | L1–L2 | 15m |
| 4 | Storage: volatile vs persistent, block devices, what a filesystem adds | L1–L2 | 10m |
| 5 | What "running a program" means: program vs process, loading, execution | L2 | 15m |
| 6 | Where the resources go: virtual memory, the page cache, and what "free memory" really means | L2–L3 | 15m |
| 7 | Observing a real machine: reading `lscpu`, `/proc/meminfo`, `vmstat`, `lsblk` | L2–L3 | 15m |
| 8 | Why this matters for DevOps — the forward map | L2 | 5m |

Total: ~100 minutes. At the upper end of the target range; if it grows further, subtopics
6–7 split into a second topic.

---

## Learning objectives

| ID | L | Objective | Assessed by |
|---|---|---|---|
| OBJ-A01.1.1 | L1 | Explain the distinct roles of CPU, RAM and persistent storage, and predict what is lost on power failure | quiz q1,q2 · ex1 |
| OBJ-A01.1.2 | L1 | Describe the fetch-decode-execute cycle in your own words | quiz q3 · assessment A |
| OBJ-A01.1.3 | L2 | Explain why a binary built for one CPU architecture will not run on another, and identify the architecture of a machine and a binary | lab2 · lab3 · quiz q5 |
| OBJ-A01.1.4 | L2 | Order the memory hierarchy by latency and justify the ordering with approximate magnitudes | ex2 · quiz q7 |
| OBJ-A01.1.5 | L2 | Distinguish a program from a process and describe what happens between typing a command and code executing | lab2 · quiz q9 · assessment A |
| OBJ-A01.1.6 | L2 | Interpret `free -h` correctly, explaining the difference between *free* and *available* memory and the role of the page cache | lab1 · quiz q11 · trouble1 |
| OBJ-A01.1.7 | L3 | Given `vmstat`/`top` output, classify a workload as CPU-bound, memory-bound or I/O-bound and state the evidence | trouble1 · trouble2 · assessment B |
| OBJ-A01.1.8 | L3 | Estimate whether a given workload will fit on a given machine, and predict the failure mode if it does not | assessment C |

Every objective maps to at least one assessable item — required by the linter.

---

## Labs

### Lab 1 — *Inspect the machine you are running on* (guided, T2)

Image: `lab-foundations`. ~20 min.

Steps, each individually verified: identify architecture (`uname -m`), core count
(`lscpu`, `nproc`), total and available memory (`free -h`, `/proc/meminfo`), block devices
and filesystems (`lsblk`, `df -h`), then write specific derived answers to files that
`labcheck` validates by **re-deriving the value** rather than comparing against a stored
constant.

Deliberate teaching move: step 4 asks for "free memory" and step 5 reveals that the number
they reported is the wrong one, then explains `available` and the page cache. Being briefly
wrong is the point — it is a far stronger correction than being told up front.

### Lab 2 — *Watch a program become a process* (guided, T2)

Write `hello.c` → `gcc` → inspect with `file`, `readelf -h` (note the architecture field),
`ldd` (dynamic linking) → run it → `strace ./hello` and read the syscalls → observe
`execve`, `write`, `exit_group`.

This single lab makes concrete: compilation, binary format, architecture tagging, dynamic
linking, process creation, and syscalls. It is the highest-value 20 minutes in the topic
and it seeds the entire Linux and container tracks.

### Lab 3 — *The wrong architecture* (challenge, T2)

The learner is given a pre-built `arm64` binary on an `amd64` machine and this only:

```
$ ./tool
bash: ./tool: cannot execute binary file: Exec format error
```

No hint that it is architectural. They must investigate (`file`, `uname -m`, `readelf -h`)
and write a diagnosis. Solution revealed only after a hypothesis is submitted.

Callback registered: this exact error returns in C14 Docker as "you pulled an arm64 image
onto an amd64 node", and the lesson there explicitly references this lab.

### Lab 4 — *Where did the memory go?* (guided, T2)

A seeded process allocates 400MB in a 512MB-limited container. Learner watches `free`,
`/proc/meminfo`, and `/proc/<pid>/status` change, then pushes past the limit and observes
the OOM kill in `dmesg`.

Callback: C14 (container memory limits) and E26 (`OOMKilled` pods) both reference it.

---

## Exercises

1. **Volatility sort** — classify ten storage locations by persistence across process exit,
   reboot, and power loss.
2. **Latency ladder** — order nine operations by latency and assign order-of-magnitude
   figures; scored on ordering, not memorised numbers.
3. **Read the output** — five snippets of real `lscpu`/`free`/`lsblk` output; answer a
   specific question about each.
4. **Sizing** — "40 processes, ~300MB RSS each, 16GB RAM, no swap. What happens?" Show the
   arithmetic, then the failure mode.

---

## Troubleshooting scenarios

### T1 — *"The server got slow at 14:00"* (L3, progressive reveal)

Given: response times up 60×, no deploy today, plus `vmstat 1 5`, `free -h`, `top`, and a
`dmesg` tail. The learner must classify the bottleneck **before** any hint is offered, and
must state which line of output supports the conclusion.

Root cause: swapping — memory pressure, high `si`/`so`, elevated `wa`, healthy idle CPU.

Teaches the generalisable method, not the answer: *symptom → which resource → which
evidence → confirm → root cause*. That method is repeated and refined in every
troubleshooting scenario in the curriculum, and this is where it is introduced.

### T2 — *"Two servers, same app, one is fast"* (L3)

Identical specs on paper. One is `arm64` running an `amd64` binary under emulation.
Teaches: "same specs" is not "same machine".

---

## Quiz

15 questions: 5 recall (L1), 6 application (L2), 4 analysis (L3, output-interpretation).
Every option — correct and incorrect — carries an explanation, and distractors are chosen
to match the misconceptions the topic is specifically trying to kill:

- "free memory is available memory"
- "more cores always means faster"
- "SSDs are about as fast as RAM"
- "a program and a process are the same thing"
- "a binary is a binary"

Pass: 70%. Failing routes the learner back to the specific subtopics behind their missed
objectives, not to the top of the page.

---

## Assessment

Three parts, all required:

- **A — Explain (written).** "A colleague asks why their program runs on their laptop but
  not on the server. Explain what could be happening in terms of architecture, memory and
  the loader." Graded against a rubric with model answer and common-failure notes.
- **B — Diagnose (practical).** A fresh, unseen `vmstat`/`free` output set. Classify,
  justify, propose the next diagnostic command.
- **C — Reason (design-flavoured).** "You must run 200 copies of a 300MB-RSS process on a
  32GB machine. What happens, in what order, and what would you measure first?" This is a
  deliberate L5-shaped question asked at L3 depth — the architect muscle starts on day one.

---

## Interview questions

Beginner ("What is the difference between RAM and disk?") through architect ("How would you
decide the instance memory size for a service you have never run?"), each with a model
answer *and* an explanation of what a strong answer demonstrates versus a memorised one.

---

## Content files produced

```
content/courses/01-computing-foundations/
├── course.yaml
└── modules/01-how-a-computer-runs-your-code/
    ├── module.yaml
    └── topics/01-the-machine/
        ├── topic.yaml
        ├── lesson.md
        ├── diagrams/{instruction-cycle,memory-hierarchy,program-to-process}.mmd
        ├── labs/{01-inspect-the-machine,02-program-to-process,
        │          03-wrong-architecture,04-where-did-memory-go}.yaml
        ├── exercises.yaml
        ├── troubleshooting/{slow-server,mystery-slow-twin}.yaml
        ├── quiz.yaml
        ├── interview.yaml
        └── assessment.yaml
```

Plus: glossary entries, `content/paths/devops-engineer.yaml` registration, and the
`lab-foundations` image definition.

---

## Application work this topic requires

It requires all of Phase 0 and Phase 1, and nothing beyond them. That is intentional — the
first topic is the forcing function that proves the pipeline, and it must not need the lab
broker (Phase 3) or the assessment engine (Phase 2) to be *readable*.

Sequencing: labs 1–4 ship first as **Tier 1** (run on your own machine or in a plain
`docker run` the learner starts, with a downloadable `verify.sh`), and are upgraded to
in-browser **Tier 2** in Phase 3 with **no content changes** — the same YAML spec drives
both. That upgrade path is the main thing the lab spec format is designed to make possible.

---

## Estimated effort

| Work | Effort |
|---|---|
| Phase 0 walking skeleton | 2–3 sessions |
| Phase 1 content pipeline + reader | 3–4 sessions |
| Topic content (~6,000 words + 4 labs + 15 questions + 2 scenarios + assessment) | 2–3 sessions |

Subsequent topics cost only the last row, which is the entire point of building the
pipeline before the content.

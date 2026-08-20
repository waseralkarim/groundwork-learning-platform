# Content Authoring Guide

Curriculum lives in `content/` as Markdown and YAML. It is validated by a schema
and a linter that run in CI, so a topic that is not finished cannot merge.

## The rhythm

```bash
task content:new -- --course 01-computing-foundations \
                    --module 01-how-a-computer-runs-your-code \
                    --topic 02-the-kernel
# write topic.yaml first, then lessons, then labs, then quiz
task content:lint      # fast, no database — run this constantly
task content:ingest    # load into the local database
# read it in the UI at localhost:8080 — if it is boring to read, it is not done
```

`content:lint` needs no database and takes under a second. Run it after every
few paragraphs rather than at the end.

## Directory layout

```
content/
├── paths/<path>.yaml
└── courses/NN-<course-slug>/
    ├── course.yaml
    └── modules/NN-<module-slug>/
        ├── module.yaml
        └── topics/NN-<topic-slug>/
            ├── topic.yaml            # objectives, prerequisites, terminology
            ├── lessons/NN-<section>.md
            ├── diagrams/*.mmd        # Mermaid, inlined at load time
            ├── labs/NN-<lab>.yaml
            ├── troubleshooting/<scenario>.yaml
            ├── exercises.yaml
            ├── quiz.yaml
            ├── interview.yaml
            └── assessment.yaml
```

Directory names are for humans. **Nothing in the database is keyed on them** —
keys come from the `id:` field, so directories can be renamed and reordered
freely. That is guaranteed by a test, not by convention.

## The `id` field is permanent

Every content file declares an `id`. It is hashed into a UUIDv5 that becomes the
database primary key, and learner progress points at that key.

**Changing an `id` orphans every learner's progress for that content.** Titles,
slugs, summaries, order and file paths are all safe to change. `id` is not.

If content is genuinely retired, set `status: retired` rather than deleting it,
so historical progress stays resolvable.

## Writing lessons

Frontmatter, then Markdown:

```markdown
---
topic: topic.the-machine
section: core-concepts
title: The three resources
order: 2
mode: explain          # explain | show | do | break | design
---

Prose here.
```

### Directives

The vocabulary is closed. Adding one is deliberately a two-sided change: the
linter's `ALLOWED_DIRECTIVES` and a renderer component in
`services/web/src/content/Markdown.tsx`.

| Directive | Use for |
|---|---|
| `:::objective{id=OBJ-X.Y.Z}` | Marking where an objective is taught |
| `:::terminal{title="..."}` | Command sessions with output |
| `:::warning{scope=production}` | Things that are fine locally and dangerous in production |
| `:::note` / `:::aside` | Supporting detail that is not on the main line |
| `:::callback` | Registering a forward reference to a later course |
| `:::checkpoint` | Self-check before moving on |
| `:::diagram{src=../diagrams/x.mmd caption="..."}` | A Mermaid diagram |
| `:::predict{question="..."}` | Make the learner commit before the answer appears |
| `:::try{lab=<slug> run="<cmd>"}` | A real shell, inline in the lesson |

Diagram paths are relative **to the lesson file**, which lives in `lessons/`, so
diagrams at the topic root are `../diagrams/…`.

### The two interactive directives

`:::predict` hides its body behind an input the learner has to fill in. Use it
where the obvious answer is wrong — that is the whole value. The body is the
correction, so write it as one: say what actually happens and why the intuitive
answer misleads. It teaches rather than grades, so the gate is client-side and
the answer is in the page source. Do not use it for anything that counts; the
graded reveal is the troubleshooting hypothesis gate, which is server-side.

`:::try` opens a real container shell in the middle of the prose. The session is
an ordinary lab session against a lab **in the same topic**, so it inherits that
lab's image, seed script, isolation tier, TTL and per-user quota — a lesson can
never ask for a shell the learner could not open from the lab screen. The linter
rejects a `lab=` slug that is not in the topic.

Use it immediately after describing what a command reports, with `run=` set to
that command. Keep the body to one or two sentences saying what will differ from
the example output — the container is smaller than the server in the transcript,
and a learner who does not expect that reads the difference as a mistake.

### Code blocks

Every fenced block needs a language. The linter enforces it — unlabelled blocks
cannot be highlighted and cannot be tested.

Use `text` for terminal output, `bash` for commands, `yaml`, `python`, and so on.

## Objectives

An objective is a promise that something will be assessable.

```yaml
objectives:
  - id: OBJ-A01.1.7
    level: L3
    verb: classify
    statement: >-
      Given vmstat output, classify a workload as CPU-, memory- or I/O-bound
      and cite the specific evidence.
    assessed_by: [quiz.q12, troubleshooting.slow-server, assessment.B]
```

Two rules, both enforced:

- **The verb must be measurable.** `understand`, `know` and `learn` are rejected
  because nothing can test them. See `MEASURABLE_VERBS` in
  `services/api/app/content/schema.py`.
- **`assessed_by` must reference things that exist.** The available identifiers
  are `quiz.<qN>`, `exercise.<eN>`, `assessment.<A>`, `lab.<lab-slug>` and
  `troubleshooting.<scenario-slug>`.

## Quizzes

- Every option — right and wrong — should carry a `note` explaining the
  misconception it targets. The instant a learner discovers they were wrong is
  the most valuable moment on the platform; wasting it is the real cost of a
  lazy distractor.
- Question levels should span the levels the topic claims to teach. A quiz that
  only tests recall certifies nothing.
- `correct`, `note` and `explanation` are stripped server-side. They are never
  present in any response the browser receives before an attempt is graded.

## Troubleshooting scenarios

The most valuable content type, and the easiest to get wrong.

- Give **symptoms and artifacts**, never the diagnosis.
- `reveal_policy: progressive` means the API refuses to serve `root_cause` until
  the learner has submitted a hypothesis.
- `method` matters more than `root_cause`. The learner should leave with a
  procedure they can apply to a problem they have never seen, not the answer to
  this one.
- Include at least one artifact that is a red herring or that rules something
  out. Diagnosis is elimination.

## Labs

- `verify` checks come from a closed vocabulary and run **inside** the lab
  container. Authors never supply shell that runs on our infrastructure.
- Prefer checks that re-derive the expected value (`equals_command`) over ones
  that hard-code it, so the lab works on any machine.
- A lab with no verification is not a lab, and the schema rejects it.
- `type: challenge` means the learner gets a problem, not a procedure. If every
  step has a hint, it is a guided lab wearing a costume, and the linter says so.

## The sandbox, as it actually is

Everything below cost someone an hour to discover. The lab walker found most of
them; the rest came from probing before writing, which is the habit worth
copying — **probe the sandbox before scoping a topic, and let the findings change
the design.**

**Two different shells.** A step's `walkthrough` runs under **bash**. A
`command_output` or `command_exit` check runs under **dash** (`/bin/sh -lc`). So
a walkthrough may use arrays, `<(process substitution)` and `[[ ]]`, and a check
may not. A range loop that works in a walkthrough will fail a check with
`[: Illegal number:`.

**There is no `time` builtin** in dash, and no `/usr/bin/time`. Measure with
`date +%s%N` before and after, subtract, and divide. When timing anything that
spawns a process, measure the spawn cost separately and subtract it — `openssl`
takes ~3ms to start, which is the same order as the thing you are timing, and an
unadjusted figure is wrong by a factor of two.

**No network egress.** `allow_egress` defaults false and content labs cannot set
it. Anything involving a remote server has to be built locally — which has
usually turned out better anyway. A learner building their own CA and watching
`s_client` produce three distinct verification failures beats any remote example.

**Tools that are not there, or not where you expect.** `mawk` has no bitwise
functions at all — `awk 'BEGIN{print xor(5,3)}'` fails — so byte arithmetic goes
in a shell loop. `xxd` is absent; use `od -An -tx1`. `capsh` exists at
`/sbin/capsh`, which is **not** on an unprivileged PATH, so `command not found`
there does not mean the tool is missing. There is no `sshd`, so SSH sessions
cannot be demonstrated — but `ssh-keygen -Y sign` / `-Y verify` runs the whole
challenge-response exchange without one.

**Set `LC_ALL=C`** before any byte-level `printf`, or a multi-byte locale will
silently write more bytes than you asked for.

**Ownership beats intent in permission demos.** A seed script runs as the
learner, so the *owner* bits are the ones that apply to everything it creates.
A directory at `0711` intended to show "traversable, not readable" gives the
owner full `rwx` and demonstrates nothing; `0111` is what you want.

**Things that do not do what their name suggests:** `openssl x509 -req -days -1`
does not produce an expired certificate — it is rejected; use explicit
`-not_before` / `-not_after`. `openssl s_server -cert` reads only the *first*
certificate in a file, so a concatenated chain — exactly what nginx wants —
silently serves the leaf alone; intermediates need `-cert_chain`. `openssl
x509 -req` copies **no** extensions from a CSR, so signing without `-extfile`
produces a certificate with no SAN.

**Check what you assert, not what you assume.** Two examples worth internalising:
`curl` returns exit 60 for expiry, self-signed, unknown issuer *and* hostname
mismatch, so an exit code is not a diagnosis. And a file inside a
non-traversable directory cannot be `stat`ed at all — `ls -l` returns
`-????????? ? ? ? ?`, so a lab step that displays the file's mode to prove it was
readable cannot work.

**The package database is a rich, free fixture — and the image is its own worst
example.** `dpkg` works entirely offline, so ownership, dependency, conffile and
integrity questions all answer instantly even though `/var/lib/apt/lists/` was
deleted at build time; `apt-cache depends`, `rdepends` and `policy` also work,
because they read `/var/lib/dpkg/status`. **`apt-get -s` runs the full solver
without root**, so removals can be simulated by a learner. Three properties of
this image were not arranged and are used directly by B06.2: `dpkg -S` on
`/opt/lab/*` returns nothing, because the platform's own seed scripts are
unowned; `dpkg -V` returns **4,634** lines, of which 4,633 are documentation the
slim base strips and exactly one is a real checksum mismatch on
`/etc/bash.bashrc`, caused by the Dockerfile appending the lab prompt to a `bash`
conffile; and because the build uses `--no-install-recommends`, **`pstree`,
`killall`, `fuser` and `xauth` are all absent** on a machine where `procps` and
`openssh-client` are installed.

**Two counts that look wrong and are not.** The Dockerfile names 17 packages but
`apt-mark showmanual` reports 16 — `util-linux` was already installed and is
recorded as *automatic* despite being requested. And `apt-get -s remove` output
needs careful slicing: the package list sits on the line *after* `will be
REMOVED` (`grep -A1 … | tail -1`), and the Essential warning needs `tail -6`, not
`tail -4`. Both cost a lab-walk cycle.

**The lab container's isolation is itself teachable material.** Labs run with
`ReadonlyRootfs` and tmpfs at `/tmp`, `/home/learner` and `/run`, so a learner can
measure a read-only root rather than be told about one. What that surfaces:
`/tmp` and `$HOME` are the only paths that are both writable and executable;
`/run` is mounted `rw` but is `755 root:root`, so an unprivileged write fails on
the **mode** while the mount permits it — the one case that separates `EROFS`
from `EACCES` in the same container. `/dev/shm` is writable `1777` and `noexec`,
and is a Docker default the broker never configures. Docker also masks seven
`/proc` paths with `/dev/null` (major 1, minor 3), `/proc/kcore` among them.
`mountpoint /home/learner` reports `is a mountpoint`, which makes mount-masking
demonstrable rather than hypothetical.

**Two shell traps that cost a lab-walk cycle each.** In `dash`, a failed
redirection on a *special builtin* (`: > "$f"`) exits the whole script — so a
probe meant to record failures must use `touch "$f" 2>/dev/null` instead, since
an external command's failure is survivable. And `apt-get -s remove` prints its
package list on the line *after* `will be REMOVED`, so slice with `grep -A1 … |
tail -1`; the Essential warning needs `tail -6`.

**YAML block scalars take their indentation from the first non-empty line.** A
diff-style artifact whose `+` lines are shallower than that first line silently
ends the scalar and produces a parse error pointing at the wrong place. Open such
a block with a comment line at the intended indent.

**Shell startup in the lab image, measured.** `/etc/bash.bashrc` sets `HISTFILE`
and `/etc/profile` rewrites PATH, which makes "which mode reads what" a
one-command question. `bash -c` reads nothing; `bash -lc` reads `/etc/profile`
but not `/etc/bash.bashrc` (the latter is sourced *by* `/etc/profile`, guarded on
`$PS1`); and a login shell does **not** read `~/.bashrc` — only the default
`~/.profile` sourcing it makes that appear to work. `/etc/skel` ships both files,
so the mechanism is readable on the machine. The learner's `$HOME` is a tmpfs, so
labs can create and destroy dotfiles freely — which makes the whole matrix an
experiment rather than a fixture.

For a non-root user `/etc/profile` **assigns** a PATH with no `sbin`, so `capsh`
and `ldconfig` are reachable from `bash -c` and not from `bash -lc`. `ip` is
unaffected because `/usr/sbin/ip` symlinks to `../bin/ip`. And `/proc/PID/environ`
is an `execve` snapshot: `unset` does not remove a value from it, and a redirect
(`< /proc/self/environ`) reads empty where `cat` does not — use `/proc/$$/environ`.

**Two shell-quoting traps in walkthroughs.** `${VAR:+yes}` on an unset variable
prints an empty string and still exits 0, so a `|| echo no` fallback never fires
— use an explicit `if [ -n "${VAR:-}" ]`. And a `file_matches` pattern cannot
span a line break, so any phrase a check greps for must be emitted on one line.

**Shell-topic fixtures: build the hostile filenames, do not describe them.** A
filename may hold any byte except NUL and `/`. A seeded directory containing
`a file.log`, `-n`, `--force`, `star*.log`, a tab and a **newline** makes every
rule in B08.1 measurable — and produced an unplanned lesson: `ls *.log | wc -l`
reports 7 for the same six files `argc *.log` reports, because of the newline.
Fixtures that are realistically hostile teach more than prose about them.

Two tools carry these labs and are worth reusing: `set -x`, which prints a
command after expansion and quotes any word that needed it, and a nine-line
`argc` helper that prints `$#` and each argument bracketed. They turn every
quoting argument into a number. `printf '[%s]
' "$@"` does the same with no
helper, because printf repeats its format.

**Tool availability, checked rather than assumed:** `od` is present; **`xxd`,
`hexdump` and `shellcheck` are not**, so a lesson may reference shellcheck as
advice but no lab step may depend on it. `local` works in dash and is *not* a
bashism; `[[`, arrays and `<<<` are.

**PATH does not persist between lab steps.** Each step runs in a fresh shell, so
an `export PATH=` in step 1 is gone by step 2. Helper scripts invoked from
generated files must use absolute paths, and any step that builds fixtures should
rebuild what it needs rather than relying on an earlier step's shell state.

**Editing files with a Python heredoc writes CRLF on Windows.** `Path.write_text`
uses the platform default, so a seed script edited that way gains `` on every
line and then fails with `cannot execute: required file not found` — the CR ends
up in the shebang. Write bytes, or strip CRs afterwards, and re-check any `.sh`
you touched. Content `.md`/`.yaml` tolerate it; shell scripts do not.

**Timing-based labs need a seeded producer.** Buffering cannot be shown with
instantaneous output, so B08.2 seeds `drip` (one line per second, stamped with
the time it was *emitted*) and `stamp` (prints when each line *arrived*). The two
columns side by side make the delay undeniable: through a plain pipe every line
arrives at +3s; with `--line-buffered` arrival matches emission. `stdbuf` is
present; `sponge`, `xxd`, `hexdump` and `shellcheck` are not.

**A walkthrough can reproduce the bug it is teaching.** A step demonstrating
grep's truncation warning wrote `grep ... > app.conf 2>&1`, which sent the
warning into the file under test. When a step's own shell uses the construct
being taught, write the check first and confirm the step observes what it claims.

**The duplication check can tell you what a topic is FOR.** Before B08.3 the
count was: `grep` in 58 built lessons, `awk` in 22, "regular expression" in zero.
That is not just "no overlap" — it is the topic's framing, and it went straight
into the overview. Run the check with word boundaries (`sed`), because bare
`sed` matches "used" and "based" and reports 81 false positives.

**Text-tool findings from the image**, all measured: `grep` exits 0/1/**2** and
`grep -c` prints `0` while still exiting **1**; BRE and ERE invert the escaping
(`grep 'a+'` matches nothing, `grep 'a\+'` matches, `grep -E` reverses both);
`cut -d' ' -f2` returns the empty string on every line of column-aligned output
while `awk '{print $2}'` works; and `awk -F' '` is special-cased back to the
default, so only `-F'[ ]'` behaves like cut. `grep -P` is **not** compiled in
here, and only `C`, `C.utf8` and `POSIX` locales exist — so locale-dependent
collation cannot be demonstrated and must not be taught as measured.

**Seed ragged data, not aligned data.** Sample input with single-space columns is
why people write `cut -d' '` and believe it works. B08.3's `access.log` has
deliberately uneven column widths so the naive tool fails the way it fails in
production.

**Age-based fixtures must be built, not copied.** `cp -r` sets every copy's
mtime to now, so a seeded retention test deletes nothing and passes for the wrong
reason; `cp -a` preserves them. B08.4's seed uses `touch -d '7 days ago'` at
seed time so the ages are correct whenever the lab runs, and places files at 3,
6, 7, 8, 10 and 30 days — deliberately straddling the `-mtime` boundary, which is
the only place the truncation is visible.

**find/xargs facts measured on this image** (findutils 4.10): `-mtime +7` selects
eight days and older, so a seven-day-old file is excluded; `-exec false \;`
returns 0 while `-exec false {} +` returns 1; find returns 1 on an unreadable
directory and a pipeline discards that; `xargs` runs the command on empty input
unless given `-r`; `xargs -I{}` gives up batching (8 invocations against 1); and
`-prune` beats `! -path` by roughly 4x on a 2,649-path tree. findutils 4.10
issues **no** warning about `-maxdepth` placement, so do not claim one.

**Prefer a printed boolean to a compound `command_exit`.** A check like
`grep X f | grep -q Y && ! grep X f | grep -q Z` is hard to get right under dash
and gives no diagnostic when it fails. Have the walkthrough print
`does +7 include age-7d.log? 0` and assert on that line instead — it is readable
in the answer file and the failure message points at the value.

**The lab image has no Python.** `python3`, `python`, `ed` and `patch` are all
absent; `perl`, `sed` and `awk` are present. Two B08.5 labs used a `python3`
heredoc to patch a script and failed the walk with `python3: command not found` —
the walkthrough carried on, so the failure surfaced as a *content* mismatch three
checks later rather than as a missing tool. Patch a file with `sed -i` for a
one-line change and an `awk` splice for a multi-line one, which reads better in a
shell course anyway. Check `command -v` for anything a walkthrough shells out to.

**errexit facts measured on this image**, all of which shaped B08.5: `local
x=$(false)` returns **0** where `x=$(false)` returns 1, because `local` is a
command whose status is its own; `((count++))` returns **1** when `count` is 0
while `((count+=1))` and `count=$((count+1))` return 0; `set -u` exits **127**;
errexit's suppression extends through a called function's whole *body*, not just
the call; and a `trap ... EXIT INT TERM` handler **returns**, so a signalled
script resumes and runs to its end with status 0. That last one is worth writing
a lab around — it is much worse than the double-run it looks like.

**A seed fixture must be measured before the lesson is written around it.** Two
drafts of B08.5's `migrate.sh` were wrong in ways only running it revealed: an
`((count++))` killed the script on iteration 1, *before* the intended fault; and
a `local checksum=$(...)` masked nothing, because the masked command was the
function's last one and its status was returned anyway. Run the seed and read its
real output before writing a word about what it demonstrates.

**The schema can be validated without Docker.** `pydantic` and `pyyaml` are
importable from the host, so `ContentLoader(Path('content')).load()` plus
`lint(tree)` from `services/api` runs the *entire* content gate — parse, schema
and every lint rule — in about a second and with no container. That is worth
reaching for first even when Docker is healthy; it turns the schema-conformance
round trip from a two-minute `compose run` into an instant one. Docker is still
needed for ingest and the lab walk.

**The local Git Bash is close enough to the lab image to pre-verify a
walkthrough.** Both are bash 5.2, so seeded scripts and walkthrough bodies can be
run on the host before the image is even rebuilt — B08.6's entire seed and every
step's expected output were confirmed that way during a Docker outage, and the
container run afterwards was byte-identical. Do not trust it for anything
touching the tool inventory, tmpfs layout or `/proc`.

**Never measure a scope question through a pipe.** A probe that called a nameref
function as `f dest | sed …` reported the assignment lost — but the *fork*
discarded it and the nameref was innocent, which sent a wrong claim into a
lesson. Any probe about what survives an assignment must run the case in the
current shell, and the probe itself must be checked for constructs that fork.

**Bound recursion before triggering it.** `ls() { ls -l "$@"; }` with `FUNCNEST`
unset — the default — recursed until the container was unresponsive and took
Docker Desktop's engine with it for the rest of the session. Set `FUNCNEST=10`
first, in the probe and in the lab.

**Watch for `$?` being reset by something between the failure and the read.** A
function *definition* is a command and a successful one, so `false; f(){
return; }; f` returns **0** while `f(){ return; }; false; f` returns 1. The first
draft of a lab asserted the wrong one; the walk caught it. The general form: any
claim of the shape "and then `$?` is still N" needs the intervening commands
counted.

**Check the tool inventory before scoping — it can expand the topic, not just
limit it.** B08.7 was planned around `getopts` alone; `getopt --version` showed
**util-linux 2.41.5**, so long options, `--opt=value`, abbreviations and
permutation could all be demonstrated rather than described, and the topic became
a comparison of three parsers instead of a tour of one.

**A probe process must actually accept the arguments you are showing off.**
`sleep 5 --password=hunter2 &` exits immediately with `unrecognized option`, so
reading `/proc/$!/cmdline` gets `No such file or directory`. Use a script that
ignores its arguments and sleeps.

**Anything that can loop forever needs an iteration guard before it goes near a
lab.** A demonstration of a rewound `OPTIND` — a helper doing a bare `OPTIND=1`
while its caller is mid-parse — re-reads the same option indefinitely. The guard
also *makes the point*, because the output ends in `...LOOPING` rather than
hanging the walk.

**Two probes in this session measured the wrong thing and nearly shipped it.**
One ran a nameref call inside a pipeline, so the **fork** discarded the
assignment and the nameref took the blame. The other asserted the arguments
vanish when `getopt` rejects an option — it actually prints a usable list with
the bad option removed, which is a sharper lesson. Both were caught by re-running
the case in isolation. **When a probe confirms what you expected, re-run it with
the suspected cause removed.**

**Test the invariant, not the race.** B08.8's central defect — a cleanup trap
removing its own lock file — has a window two instructions wide, and could only
be reproduced by driving three file descriptors by hand. A lab step that tried
to hit it by staggering three real runs **does not reproduce it at all**: the
third run contends on the same inode and is correctly refused. Any test built
from `sleep`s would pass almost every time and fail in CI occasionally, which is
worse than no test. Find the property the race violates — here, "the lock file
still exists after a run that held it has finished" — and assert that.

**Killing a backgrounded shell function kills the subshell, not the work.**
`run A 3 & holder=$!; kill -9 "$holder"` kills the subshell running the
function; the `bash script` it invoked survives, keeps holding its lock, and the
next assertion fails — on the fixed script as well as the broken one. Background
the program directly, or drop the check. This produced a test that failed
against both scripts and looked like a content bug in the fix.

**`/proc/self/fd/N` is not a reliable way to read an inode number.** Two
descriptors on the same file reported different inodes. Use `stat -c%i` on the
path, and `readlink /proc/PID/fd/N` to show the `(deleted)` suffix when a file
has been unlinked while open — that one is trustworthy and is the clearest
evidence a lock has lost its name.

**When the lab walker times out on a session, read the broker log before
suspecting your content.** `docker compose logs lab-broker` showed
`container ... is not running` and `409`, which localised the problem to one
lab's step in seconds. The walker's own traceback says only that an HTTP call
timed out.

**Check who owns a container before cleaning up.** A tidy-up impulse during this
session nearly removed ~25 "leftover" containers that turned out to be the
user's MCP servers, a kind cluster and an unrelated lab. `docker ps --format
'{{.Names}}\t{{.Image}}'` first, every time.

**Write content files with the Write/Edit tools, not with shell heredocs.**
Escaped strings inside heredocs mangle `\n`, `\\` and line continuations in YAML
walkthroughs, repeatedly and silently. Normalise every new file to LF before
linting; a CR in a shebang gives `cannot execute: required file not found`.

## What the linter enforces

| Rule | Why |
|---|---|
| `unique-id` | Two things sharing an id overwrite each other |
| `prereq-resolves`, `prereq-acyclic` | Curriculum order must be computable |
| `objective-assessed` | An unassessed objective is a promise we cannot keep |
| `assessable-mapped` | Assessment with no objective is busywork |
| `done-lesson/quiz/lab/assessment` | The Definition of Done, as code |
| `done-troubleshooting` | Required once a topic claims L3+ |
| `directive-known` | Keeps the vocabulary closed |
| `code-language` | Highlighting and testability |
| `link-resolves` | No broken relative links |
| `quiz-distractors`, `quiz-level-spread` | Quiz quality (warnings) |
| `lab-verification`, `lab-challenge` | Lab quality (warnings) |

Errors block the build. Warnings do not, but they are visible and should be
argued with rather than ignored.

## Definition of Done

A topic ships when the linter passes **and** the checklist in
[../plan/DELIVERY-PHASES.md](../plan/DELIVERY-PHASES.md#definition-of-done) is
satisfied. The linter covers most of it; the parts it cannot check — whether the
prose is any good, whether the troubleshooting scenario is genuinely hard — are
what review is for.

## Style

- Explain *why* before *how*. A command with no model behind it is a magic spell.
- Define a term before leaning on it. Add it to `terminology` in `topic.yaml`.
- Show real output, not invented output.
- Separate development convenience from production reality explicitly.
- Register forward references with `:::callback` so later topics can call back.
- Write for someone reading for ninety minutes, not skimming for thirty seconds.

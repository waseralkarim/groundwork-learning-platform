---
topic: topic.processes
section: production-considerations
title: What this becomes
order: 5
mode: design
---

:::objective{id=OBJ-A01.2.8}

## The shutdown contract

Every production system has one, whether or not anyone wrote it down:

```text
orchestrator                     your process
─────────────                    ────────────
stop routing traffic
SIGTERM              ──────────▶ handler runs
                                   stop accepting work
                                   finish in-flight requests
                                   flush, close, exit
   wait grace period
SIGKILL (if still alive) ──────▶ gone, mid-anything
```

Three things break it, and all three are this topic:

**The process has no handler.** Nothing happens on SIGTERM; it dies at the grace
period with work in flight. If it is PID 1, the signal is discarded outright.

**The handler is slower than the grace period.** A worker with a 60-second job
and a 30-second grace period will be killed mid-job every single time. Grace
period must exceed the longest unit of work, or the work must be interruptible.

**Traffic is still arriving when SIGTERM lands.** Removal from the load balancer
is not instantaneous, so a correct handler keeps serving for a moment before it
stops. Exiting immediately on SIGTERM causes the connection errors that
"graceful shutdown" was meant to prevent.

:::warning{scope=production}
The most common bug is the one that looks like success: shutdown works locally
where there is no load balancer and no in-flight work, and drops requests in
production where there is both. Test shutdown *under traffic* or you have not
tested it.
:::

## Sizing by processes, not just memory

The Machine taught you to size by RSS. Processes are the second budget, and it
is a smaller number than people expect.

Every process costs a PID, a process-table entry and a kernel stack. `pid_max`
is 4,194,304 on modern kernels but often 32,768 by default, and containers get a
`pids` cgroup limit that is far lower still — the labs in this topic run with 256.

Reaching that limit fails in a way that is genuinely confusing: `fork: retry:
Resource temporarily unavailable`, while `free` shows plenty of memory and the
CPU is idle. Nothing can start — not a new worker, not your shell, not the
diagnostic command you were about to run.

Three things reach it:

- A fork bomb, deliberate or accidental (a retry loop that spawns)
- Thread-per-connection under load — threads consume the same budget
- **Zombie accumulation**, which is the quiet one: each zombie uses no memory and
  no CPU, so every dashboard looks fine right up until nothing can start

## Common mistakes

**`kill -9` first.** It removes the process's chance to clean up. Try `SIGTERM`,
wait, then escalate.

**Trying to kill a zombie.** It is already dead. Signal the parent.

**Trying to kill a process in D.** The kernel is not delivering signals to it.
Fix the I/O.

**Assuming your shutdown handler runs.** If your process is PID 1 with no
handler, it does not. Verify it rather than assuming.

**Reading load average as CPU.** It counts runnable *plus* uninterruptible. High
load with idle CPU means I/O, not compute.

**`pkill -f` without checking.** Run `pgrep -a -f` first. A loose pattern matches
more than you meant, and you find out afterwards.

## Security note

The process boundary is a security boundary, and three of its properties are
load-bearing:

**A process runs as a user, and that is checked on every access.** Running a
service as root means a compromise of that service is a compromise of the host.
This is why the containers in this platform run as UID 10001 and why the lab
containers do too.

**You can only signal processes you own** (unless you are root). This is not a
formality — it is what stops one user's shell from killing another's database.

**File descriptors survive `exec`.** A process can open a privileged file, drop
privileges, and keep the descriptor. That is a useful pattern and a real leak
risk: a child inherits every descriptor not marked close-on-exec, so a carelessly
opened secret can end up in a subprocess that should never have seen it.

## What this becomes

| From this topic | Becomes |
|---|---|
| PID 1 is special | The PID 1 problem in containers, and `--init` (**C14**) |
| SIGTERM then SIGKILL | `docker stop`, `terminationGracePeriodSeconds` (**C14**, **E26**) |
| Orphan reparenting | Why containers need something that reaps (**C14**) |
| Process states | Reading node pressure and stuck pods (**E31**) |
| Signal handlers | Graceful shutdown, `preStop` hooks, zero-downtime deploys (**C18**) |
| The process tree | What a PID namespace actually renumbers (**C16**) |
| Process budgets | `pids` cgroup limits and fork-bomb containment (**C16**) |

:::note
When the container track says "a container is a process in its own namespaces",
you now have the first half of that sentence in full. Namespaces are what
**C14** adds. The process was always the interesting part.
:::

:::checkpoint
This topic is done when you can:

1. Explain, in order, what happens between `docker stop` and a dead container
2. Diagnose a process that will not die, and say which of three causes it is
3. Explain why a machine with free memory and idle CPUs cannot start a process
:::

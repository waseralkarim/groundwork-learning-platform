---
topic: topic.the-scheduler
section: overview
title: Slow, or waiting for a turn?
order: 1
mode: explain
---

A process that is not making progress is in one of two situations, and they need
opposite responses.

It is **running and slow** — doing work, badly or in quantity. A profiler helps.
More CPU helps.

Or it is **runnable and waiting** — it has work, it is not blocked on anything,
and it does not have a CPU. A profiler shows almost nothing. More CPU for *this*
process may not help either, depending on why it is waiting.

Telling those apart is not a matter of judgement. The kernel counts the second
one, per task, in nanoseconds, in a file, and almost nobody reads it.

## The specific things this explains

- Why a service is slow while `top` shows the CPU 60% idle
- Why `nice` appears to do nothing, right up until it does everything
- Why nice 19 does not mean "5% of the CPU" — it means about 1.5%
- What changed when Linux 6.6 replaced CFS with EEVDF, and why it was about
  latency rather than fairness
- Why a real-time thread that never blocks can freeze a machine, and why
  creating one needs a capability
- What "context switches per second" on a dashboard is actually telling you

:::callback
From **cgroups**: `cpu.weight` is a share of *contended* CPU, and does nothing
when nothing is contended. This topic is the mechanism underneath that sentence
— what "share" means, how the kernel computes it, and why the same statement is
true of `nice` for exactly the same reason.
:::

## The file that answers the question

```bash
cat /proc/self/schedstat
# 2500747400 2500202000 3016
```

Three numbers: nanoseconds spent on a CPU, nanoseconds spent **waiting on a run
queue**, and timeslices run.

That reading is from a container limited to half a CPU, running one busy loop
for five seconds. It ran for 2.50 seconds and waited 2.50 seconds — which is the
quota, exactly, expressed as time the work spent queued rather than as a
percentage of anything.

:::diagram{src=../diagrams/run-queue.mmd caption="Runnable-but-waiting is a distinct state, and the time spent in it is counted"}

Add a second busy loop on the same CPU and the split changes:

:::terminal{title="One busy loop, then two, on the same CPU"}
$ alone:     ran 2.50s   waited 2.50s   (the quota)
$ contended: ran 1.77s   waited 5.21s   (the quota, and a competitor)
:::

Nothing about the work changed. The second process spent three times longer
queued than running, and every millisecond of that is latency somebody
experiences.

## Fair does not mean equal

The scheduler's job is to decide who runs next, thousands of times a second,
using a rule that is cheap to evaluate and does not starve anyone. Linux's rule
is proportional share: each task has a **weight**, and it receives CPU in
proportion to its weight against the sum of all runnable weights.

:::diagram{src=../diagrams/weight-to-share.mmd caption="nice → weight → share, and why the denominator is what matters"}

`nice` sets that weight, through a lookup table where each step is about 1.25×.
Which produces the fact most people have wrong:

| nice | weight | Share against one nice-0 competitor |
|---|---|---|
| −20 | 88761 | 98.9% |
| −5 | 3121 | 75.3% |
| 0 | 1024 | 50% |
| 5 | 335 | 24.7% |
| 10 | 110 | 9.7% |
| 19 | 15 | **1.4%** |

Nice 19 is not "a bit lower priority". It is about one seventieth of a nice-0
task, and you can measure it in a lab in under a minute.

:::predict{question="A process is niced to 19 on an otherwise idle machine. How much CPU does it get?"}
All of it.

The share is your weight divided by the sum of all *runnable* weights. Alone,
that sum is your own weight, so the fraction is 1 whatever the numerator is.
Nice 19 on an idle machine runs exactly as fast as nice 0.

This is the same property as `cpu.weight` from the previous topic, and it
produces the same false negative: someone renices a batch job, tests on a quiet
machine, sees no change, and concludes it did nothing. The setting is working
perfectly; the test contained no competition for it to arbitrate.

It is also why the failure mode is sudden. The batch job is invisible for weeks
and then, on the one busy afternoon when it matters, it is getting 1.4% of a
CPU and its queue is backing up. Nothing changed except that somebody else
turned up.

The corollary is worth stating: **a weight is not a limit.** If you need a
ceiling that applies on an idle machine, `nice` is the wrong tool and `cpu.max`
is the right one.
:::

## What you already have

From **Threads and Concurrency** you counted threads and measured what a CPU
limit does to them. From **cgroups** you read `cpu.weight` and `cpu.stat` and
watched pressure climb. This topic goes one level down: the weights arbitrated
between, the queue tasks wait in, and the per-task counters that say which of
your processes actually waited.

## How to work through it

Concepts, mechanism, tools, production. Four labs: read your own scheduling
state and try to change your policy; measure the nice ratio against the weight
table and check whether the arithmetic holds; separate waiting from running and
voluntary from involuntary switches; and finally diagnose three workloads where
the CPU is not the bottleneck people assumed.

The central measurement — a nice-19 process getting one seventieth of the CPU —
takes about ninety seconds and is hard to forget afterwards.

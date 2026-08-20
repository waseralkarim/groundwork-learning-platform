# LabStepFailingForEveryone

> A single lab step fails for more than 80% of learners over 6 hours.

## What it means

This is not an infrastructure alert. It is a **content bug** routed through the
monitoring system, and it is the most valuable alert in the set.

A step almost everyone fails is nearly always an instruction that does not say
what it means, or a check that verifies something different from what the
instruction asked for. Learners do not report this — they assume they are the
problem and move on, which is exactly why it needs to be measured.

## Urgency

**No page.** Read it during the working day, with the lab open.

## Confirm the cause

The alert labels name the lab and the step. Start by walking it yourself:

```bash
python scripts/walk-labs.py --lab <lab-slug>
```

If the walker passes, the instruction and its check disagree for humans but not
for the scripted path — which points at the *wording*, not the mechanics.

Then read the step as though you had not written it:

- Does the instruction name the exact file path the check looks for?
- Does it say the format? "Write the number" and "write the number in MiB as a
  bare number" produce different answers and only one passes.
- Does the check depend on state a previous step created, which a learner might
  reasonably have done differently?
- Does the hint actually help, or does it restate the instruction?

## What to do

Fix the content, not the check — unless the check is genuinely wrong.

Then add a `walkthrough:` to the step if it lacks one, so the walker covers it
from now on, and re-run `task labs:walk`.

Three of the first eight labs had exactly this class of bug: a path that did not
exist, a demonstration that demonstrated nothing, and an instruction needing a
capability the sandbox drops. All three passed their automated checks. This
alert exists because those were found by hand, and that does not scale.

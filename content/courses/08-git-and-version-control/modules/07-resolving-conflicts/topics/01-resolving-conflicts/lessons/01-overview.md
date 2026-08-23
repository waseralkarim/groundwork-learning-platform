---
topic: topic.resolving-conflicts
section: overview
title: The default markers leave out the answer
order: 1
mode: explain
---

B10.3 established what a conflict is, precisely:

> Both sides changed the same region **relative to the base**.

Every part of that sentence does work, and the last three words do the most. The
base is not context — it is the term the rule is stated in. Without it there is
no such thing as "changed"; there are only two values.

Now look at what Git shows you by default:

```text
<<<<<<< HEAD
retries = 1
=======
retries = 5
>>>>>>> other
```

Two values. The base is absent.

:::predict{question="Ours says 1 and theirs says 5. Which one is correct?"}
:::

**It is not determinable from what is shown**, and that is the point of this
topic. Two possibilities:

- If the base was `3`, both sides changed it. A real disagreement, and someone
  has to decide.
- If the base was `1`, only they changed it. The rule says take theirs — `5` —
  with nothing to decide at all.

Same markers. One case needs a conversation with whoever understands the system;
the other needs nobody. The default interface cannot distinguish them, so it
presents a mechanical answer as a judgement call — and a judgement call made
without information is a coin-flip.

## The base was there the whole time

```console
$ git cat-file -p :1:cfg.txt
retries = 3
```

Stage 1, exactly as B10.3 described. The information was never missing. It is
simply not in the file you were asked to edit, and retrieving it takes a command
most people resolving a conflict have never seen.

One setting moves it to where the decision happens:

```console
$ git config --global merge.conflictStyle zdiff3
```

```text
<<<<<<< HEAD
retries = 1
||||||| merged common ancestors
retries = 3
=======
retries = 5
>>>>>>> other
```

**This removes work rather than adding reading.** Every region where ours still
matches the base stops being a decision — only they changed it, so theirs is the
answer. That class of conflict is invisible under the default and mechanical
with the base shown.

`zdiff3` additionally hoists lines common to both sides out of the conflicted
region, so on a large conflict the output is *shorter* than the default's.

:::note
Being fair to the default: for a small conflict in code you wrote an hour ago,
you remember what the line said, and two-way markers are fine. It is defensible
for the easy case and wrong for the hard one — which is a poor way round for a
default.
:::

:::objective{id=OBJ-B10.7.2}
:::

## Not every conflict writes markers

The other half of this topic is that the search-for-`<<<<<<<` habit misses two
of the four conflict kinds entirely.

| Kind | Stages | Markers | The question |
|---|---|---|---|
| content | 1, 2, 3 | yes | which lines |
| modify/delete | 1, 2 | **no** | should this file exist |
| add/add | 2, 3 — **no base** | yes | what should this file be |
| rename/rename | **three paths** | **no** | what is this called |

**`modify/delete` writes nothing** because there is no third version to merge
against. Your copy sits in the tree looking entirely normal, and the merge simply
will not complete.

**`add/add` has no stage 1** — neither side inherited the file, so there is no
base and the attribution rule genuinely does not apply. `diff3` shows no base
section here, honestly, because there is none.

**`rename/rename` leaves three unmerged paths** for one disagreement, with both
files present and their content intact. Nothing looks wrong.

Which gives the habit that replaces grepping:

```console
$ git diff --name-only --diff-filter=U
```

That is the complete set of decisions you owe, including the invisible ones.

:::warning
A commit is refused while any path has non-zero stages — so a merge with an
unresolved modify/delete cannot complete. What lets it through is `git add -A`,
which sweeps unresolved paths in alongside the edited ones and accepts whatever
the working tree happens to hold. **Stage paths individually during a conflicted
merge.**
:::

:::objective{id=OBJ-B10.7.3}
:::

## What this topic covers

- Configuring a conflict style that shows the base, and why that is not a
  preference
- The conflicts that write no markers, and how to find them
- Reading conflict shapes out of the index when the file explains nothing
- A method for a merge with thirty conflicts rather than one
- When to stop resolving and change approach instead

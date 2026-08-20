---
topic: topic.packages-and-dependencies
section: production
title: How software actually reaches a machine
order: 5
mode: explain
---

Everything so far assumed software arrives as a package. On a real machine that
is true of most of it and false of the part that causes trouble.

## Six routes, and what each one commits you to

| Route | Owned? | Who patches it |
|---|---|---|
| The distribution archive | yes | the distribution, via backports |
| A third-party apt repository | yes | the vendor, on their schedule |
| A `.deb` downloaded and installed | yes | **you**, by noticing a release |
| A vendor script (`curl \| sh`) | **no** | you, if you remember it exists |
| A language package manager (pip, npm, gem) | **no** to dpkg | you, via a separate toolchain |
| `COPY` in a Dockerfile | **no** | you, on rebuild |

The first three keep the machine answerable: a version to report, an upgrade
path, integrity checking, and a line in any inventory. The last three do not.

That is not an argument for never using them — a vendor agent may only ship as a
script, and `COPY` is how your own application gets in. It is an argument for
**knowing which of your software is in the bottom three**, because that list is
your actual patching obligation and it exists whether or not anyone has written
it down.

:::callback{to=topic.distributions-and-versions}
B06.1's decision record had a line called *outside the archive*, and the claim
was that it would be the line that mattered in two years. This is why: it is the
only part of the estate the machine cannot tell you about.
:::

## The inventory question, answered honestly

When somebody asks "what are we running", the package database answers
completely and in milliseconds:

```bash
dpkg-query -W -f='${Package}\t${Version}\t${Architecture}\n'
```

That is an SBOM in one command, and it is exactly what a scanner reads. It is
also **only true of what dpkg knows about**, which is why a scan of a machine
running a `curl | sh` agent comes back clean about that agent forever — not
because it is safe, but because nothing looked.

The complementary question — what is here that dpkg has never heard of — takes
more work and is worth automating once:

```bash
for f in /usr/local/bin/* /opt/*/bin/*; do
  [ -e "$f" ] || continue
  dpkg -S "$(readlink -f "$f")" >/dev/null 2>&1 || echo "unowned: $f"
done
```

Run that across a fleet and the output is a list of things somebody installed
once, that receive no security updates, and that appear in no report. In my
experience it is never empty and frequently surprising.

## `--no-install-recommends` is a contract with two halves

Every container guide tells you to use it, and they are right — it is often the
difference between a 180 MB image and a 400 MB one. What they leave out is that
you have just changed what "installed" means.

`Recommends` is where a package puts things it works without *in a way somebody
would consider broken*. Skipping them is fine when you know which ones you
skipped. The failure mode is specific and it always looks the same:

> It works on my machine and fails in the container, with an error about a
> command that has nothing to do with what I changed.

The fix is not to drop the flag. It is to install the pieces you actually need,
explicitly, so they are declared rather than inherited — which also means the
next person can see them in the Dockerfile.

## `autoremove` is safe exactly as far as the record is accurate

A package marked automatic with nothing depending on it can be removed, because
nobody asked for it. That reasoning is sound and its premise decays.

The common way it decays: a dependency of something you installed turns out to
be useful directly. A script starts calling it. Nothing updates the record —
it is still marked automatic, and nothing declares that your script needs it.
Later the thing that pulled it in gets removed, `autoremove` runs, and a script
nobody was thinking about stops working.

```bash
apt-mark manual jq        # "we rely on this directly now"
```

One command, and it makes the record true again. Running `apt-get -s autoremove`
on a machine you did not build is a fast way to find out what somebody's
assumptions were.

## Conffiles do not scale, which is why configuration management exists

The conffile mechanism is a reasonable answer to a real problem for **one
machine with an administrator present**. Every part of it assumes that: the
prompt assumes somebody answers, the `.dpkg-dist` file assumes somebody looks,
the "keep your version" default assumes your version was deliberate.

At fleet scale none of those hold, and the result is drift that reports success.
So the fleet answer inverts the model: **own the file completely**. Configuration
management writes it, the package's version is irrelevant, and divergence is
detected rather than negotiated.

That is not a criticism of the mechanism. It is what happens when a design's
assumptions stop being true, and recognising the pattern is more useful than the
specific case — plenty of tools in this path are excellent at one scale and
actively misleading at another.

Meanwhile, on machines that still work the original way, this finds the damage:

```bash
find /etc -name '*.dpkg-dist' -o -name '*.dpkg-old' -o -name '*.dpkg-new'
```

## Findings that nobody can action are worse than no findings

`dpkg -V` on this image reports 4,634 discrepancies, of which 4,633 are the slim
base image doing exactly what it was chosen to do. One is real.

Put that in a compliance pipeline unfiltered and you get a control that produces
thousands of criticals on a healthy machine. What happens next is predictable:
somebody writes a suppression that hides the whole check, or people learn to
scroll past it. Either way the control is gone, and the paperwork says it is
running.

This is the same shape as B06.1's vulnerability scanner reporting 47 criticals
against backported packages. **The cost of an unactionable finding is not the
time to triage it — it is the credibility it spends**, and that credibility is
what you need when a real finding arrives.

The fix is the same in both cases: make the tool understand the system it is
inspecting. Filter the deliberate exclusions, alert on the residue, and check
that the residue is small enough for a human to read.

## What to take from this topic

- **Ask the machine, not your memory.** `dpkg -S` on a path is faster than any
  reasoning about where files come from, and it is correct.
- **The gap between requested and installed is the real size of a decision.**
  Sixteen became 162 here. That ratio is normal.
- **`Recommends` is not a dependency**, and every minimal image has quietly
  dropped some.
- **Simulate removals.** `apt-get -s` costs nothing and works unprivileged.
- **The files nothing owns are the ones you are responsible for.** Nowhere on
  the machine records that they exist, so the list has to live somewhere else.
- **A check that cries wolf is not a check.**

:::objective{id=OBJ-B06.2.7}
:::

:::objective{id=OBJ-B06.2.8}
:::

---
topic: topic.identity-and-least-privilege
section: core-concepts
title: Who the kernel thinks you are
order: 2
mode: explain
---

## Identity is numbers

```bash
id
# uid=10001(learner) gid=10001(learner) groups=10001(learner)
```

The kernel knows `10001`. The name `learner` is a lookup in `/etc/passwd`
performed for your benefit, and nothing enforces that it exists — a container
running as uid 10001 with no matching entry works perfectly and shows
`uid=10001` with no name. This is why `runAsUser: 10001` in a manifest and a
`learner` account in an image are two independent facts, and why file ownership
survives across containers that disagree about names.

Three parts of an identity matter:

- **uid** — the user. `0` is root, and root is special to the kernel rather than
  to the permission bits.
- **gid** — the primary group, which new files you create belong to.
- **supplementary groups** — additional groups you carry. These are the quiet
  ones: a group added years ago for one purpose grants access to everything that
  group can reach, forever, and it appears in no manifest.

:::note
An identity is established once, at process start, and then inherited. A process
cannot gain a uid it was not given — except through the one mechanism this topic
spends time on, which is setuid.
:::

## Authentication and authorization are different failures

| | Authentication | Authorization |
|---|---|---|
| Question | Who are you? | May you do this? |
| When | Once, at session start | Every operation |
| Typical failure | 401, `Permission denied (publickey)`, `Authentication failure` | 403, `EACCES`, `Operation not permitted` |
| Fix | Credentials, keys, tokens | Permissions, roles, capabilities |

Telling them apart is the first move in any access incident, and the error text
usually says which. `Permission denied (publickey)` is authentication — SSH
never established who you are. `EACCES` on a file is authorization — the kernel
knows exactly who you are and is refusing.

Getting this backwards wastes hours: people rotate credentials to fix an
authorization problem, or grant broader permissions to fix a failed login.

## Permission bits, and the rule people get wrong

```text
-rw-r--r--  1 alice  staff  data.txt
 │└┬┘└┬┘└┬┘
 │ │  │  └── other:  r--
 │ │  └───── group:  r--
 │ └──────── owner:  rw-
 └────────── type
```

The rule that surprises people: **the first matching class wins.** The kernel
checks owner, then group, then other, and stops at the first that applies. It is
not a union.

So a file you own with mode `077` is **unreadable to you** and readable by
everyone else. You are the owner, the owner bits are `---`, and the check stops
there. This is not a curiosity — it is how a "fix" of `chmod 077` locks out the
one account that needed access while opening it to everything else.

## On directories, `r` and `x` are different things

This is the single most useful thing in the lesson.

- **`r` on a directory** — you may *list* its contents.
- **`x` on a directory** — you may *traverse* it: resolve a name inside it.

They are independent, and you need `x` on **every** directory along a path to
reach anything inside it.

:::diagram{src=../diagrams/access-decision.mmd caption="Every directory on the path is part of the decision, and the error names only the last object"}
:::

Which produces the error that sends people to the wrong file:

```text
$ cat listable/data.txt
cat: listable/data.txt: Permission denied

$ ls listable
data.txt                                    ← the name is right there

$ ls -l listable
-????????? ? ? ? ?  ? data.txt              ← and nothing else is
```

The file is fine — mode 644, owned by you — and you cannot see that, because
`stat` on an entry needs traversal too. The read bit lets you enumerate names
and nothing more, which is what those question marks are: *something is here and
I am not permitted to learn anything about it.*

The **directory** is mode 644 — readable, not traversable — so the path cannot be
resolved, and the error names the object you asked for rather than the one that
refused. Hours are lost to this, because every instinct says to look at the file
the error named, and the file cannot even be inspected.

The inverse exists too: a directory with `x` and no `r` lets you open
`known.txt` if you already know the name and refuses to tell you what is in
there. That is a legitimate pattern — it is how `/home` is often configured.

:::predict{question="A deployment adds a file to a config directory with mode 0644 and the application, running as a different user, reports Permission denied on that file. The file's mode is correct. Where do you look?"}

At `x` on every directory in the path, and at the ownership of each.

The error names the file because that is what was asked for; the refusal can
come from any directory between the root and it. `namei -l /path/to/file` walks
the whole path and prints the mode and owner of each component, which turns a
guess into a two-second answer.

The second thing to check is the **umask** of whatever created the file, and
whether the file's *group* is what you expect — a file created by a process with
a different primary group is a common cause of a mode that looks right and an
owner that is not.

## umask

New files do not get the mode you asked for; they get it minus the umask.

```bash
umask          # 0022
touch f        # -rw-r--r--   (666 minus 022)
mkdir d        # drwxr-xr-x   (777 minus 022)
```

Files are never created executable, which is why the base is 666 rather than
777. A umask of `0077` makes everything private to the owner, which is the right
default for anything handling secrets — and is not the default anywhere.

## setuid: the sanctioned escalation

An ordinary user changes their own password, which means writing to
`/etc/shadow`, which is `root:shadow` mode `0640` and unreadable to them. Both
things are true, and the mechanism that reconciles them is setuid:

```bash
$ ls -l /usr/bin/passwd
-rwsr-xr-x 1 root root 118168 /usr/bin/passwd
   ↑
   s, not x — run as the owner, not as the caller
```

Executing it gives you a process running as **root**, doing a narrowly defined
job on your behalf.

That is a real escalation, granted deliberately, and it is why every setuid
binary is part of your attack surface. A bug in any of them is a path to root
for anyone who can run it. There are nine on this lab image, and you will list
them.

One of those nine is worth noticing: `/usr/lib/openssh/ssh-keysign`, which
arrived when this course added `openssh-client` for a single topic. Adding a
package added an escalation path. That is exactly the trade the image's own
header comment describes, and it is the ordinary way attack surface grows —
not by a bad decision, but by a reasonable one nobody counted.

## Capabilities: root, split up

Root's powers are divided into units that can be granted separately — bind a low
port, change file ownership, read any file, load a kernel module. A02 covered
the mechanism; here it is the *measurement* that matters.

```bash
grep -E '^Cap(Eff|Bnd)' /proc/self/status
# CapEff: 0000000000000000
# CapBnd: 00000000a80425fb

/sbin/capsh --decode=00000000a80425fb
```

Two different questions, and both need answering:

- **CapEff** — what this process holds **now**. Here: nothing at all.
- **CapBnd** — the **ceiling**. What it could ever regain, including across an
  `execve` of a setuid binary. Here: fourteen capabilities.

An audit that reads only the effective set concludes the process is
unprivileged. The bounding set is what an attacker actually works within, and
dropping it — `capabilities: drop: ["ALL"]` — is what makes the answer stick.

Note `/sbin/capsh` with the full path: `/sbin` is not on an unprivileged user's
PATH, and `capsh: command not found` is not the same as the tool being absent.

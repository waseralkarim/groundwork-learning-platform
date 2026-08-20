---
topic: topic.the-filesystem-hierarchy
section: commands
title: Reading a machine's layout
order: 4
mode: do
---

Four questions, and the commands that answer each. None of them need root.

## Where did the bytes go

```bash
du -sh /usr /var /etc /opt /home /usr/local     # the top-level shape
du -sh /usr/* | sort -rh | head                 # inside the big one
du -sh /var/lib/* | sort -rh | head             # what state exists
df -h                                           # what filesystems, and how full
```

`du` measures what is *there*; `df` measures what the filesystem thinks is
*used*. When they disagree the difference is usually a deleted file some process
still holds open — which is A01.5's territory and worth remembering exists.

## Who owns this directory

```bash
dpkg -S /var/log                 # base-files, apt: /var/log
dpkg -S /usr/local               # no path found — reserved for you
ls -l / | grep '^l'              # what is a symlink (the usr-merge)
readlink -f /bin/sh              # where a path actually lands
```

Two things to know about the ownership question here. `/usr/local`, `/opt` and
`/srv` answering "no path found" is **correct** — those are the directories no
package may claim. The same answer under `/usr/bin` is a real finding.

## What is mounted, and how

```bash
findmnt                          # the mount tree, readable
findmnt /var/lib                 # which mount governs this path
mountpoint /opt/lab              # is something mounted exactly here?
cat /proc/mounts                 # the raw list, always available
awk '$2=="/run"{print $4}' /proc/mounts     # options for one mount
```

`findmnt` is the friendly one and `/proc/mounts` is the one that is always
present — worth knowing both, because minimal images sometimes lack the first.

The distinction that matters: **`findmnt <path>` tells you which mount governs a
path**, which may be an ancestor. `mountpoint <path>` asks whether something is
mounted at *exactly* that path, which is the question to ask when files have
apparently vanished.

```bash
findmnt -o TARGET,SOURCE,FSTYPE,OPTIONS      # the four columns worth reading
cat /proc/1/mountinfo                        # what the runtime attached, in full
```

`/proc/1/mountinfo` is the honest answer to "what volumes does this container
have", regardless of what any manifest claims.

## Can I write here, and if not, which gate stopped me

```bash
touch /var/log/probe             # the answer is in the error text
stat -c '%A %U:%G' /run /tmp     # the mode gate
findmnt -no OPTIONS /run         # the mount gate
```

Read the error rather than assuming:

| Message | `errno` | Gate | Fix |
|---|---|---|---|
| `Read-only file system` | `EROFS` | the mount | remount, or declare a writable path |
| `Permission denied` on write | `EACCES` | mode / ownership | `chown`, `chmod`, or run as the right user |
| `Permission denied` on **execute** | `EACCES` | `noexec` on the mount | put the binary somewhere executable |

The third row is the one that reads as a permissions problem and is not — the
file may be mode `0755` and owned by you, and still refuse to run.

A quick sweep of everything writable:

```bash
# every writable mount, with the options that constrain it
findmnt -no TARGET,OPTIONS | grep -v ' ro,'

# what can I actually write to, empirically
for d in /etc /var/log /var/lib /run /tmp "$HOME" /dev/shm /usr/local/bin; do
  if touch "$d/.probe" 2>/dev/null; then rm -f "$d/.probe"; r=writable; else r=no; fi
  printf '%-16s %s\n' "$d" "$r"
done
```

The empirical loop beats reading the mount table, because it accounts for both
gates at once.

## Where is the unpackaged software

```bash
ls -la /opt /usr/local/bin /usr/local/lib /srv
```

By construction, anything here came from outside the package system. It is the
same list B06.2 built with `dpkg -S`, arrived at from the layout instead — and
it is faster, because you are looking in the three places such software is
*supposed* to go rather than searching for absences.

```bash
# unpackaged software, both ways, and compare
ls /opt /usr/local/bin 2>/dev/null
for f in /usr/local/bin/* /opt/*/bin/*; do
  [ -e "$f" ] || continue
  dpkg -S "$(readlink -f "$f")" >/dev/null 2>&1 || echo "unowned: $f"
done
```

If the second list is longer than the first, somebody installed unpackaged
software somewhere it does not belong, and that is worth knowing.

:::try{lab=who-owns-which-directory}
:::

:::objective{id=OBJ-B06.3.1}
:::

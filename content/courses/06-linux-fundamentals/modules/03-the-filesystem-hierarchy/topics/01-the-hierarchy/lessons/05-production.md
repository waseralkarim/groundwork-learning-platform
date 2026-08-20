---
topic: topic.the-filesystem-hierarchy
section: production
title: Deciding what persists
order: 5
mode: explain
---

Every containerised service forces the same three decisions, and the hierarchy
already answers them. What goes in a volume, what gets backed up, and what must
be writable — these are the same question asked about different time horizons.

## The four lifetimes

Sort every path a service touches into one of these, and the rest follows
mechanically:

| Lifetime | Belongs in | Volume? | Backup? |
|---|---|---|---|
| **Rebuilt from the image** — code | `/usr` | no | no |
| **Rebuilt from config management** — decisions | `/etc` | no | the *source*, not the file |
| **Cannot be regenerated** — state | `/var/lib` | **yes** | **yes** |
| **Can be regenerated** — cache | `/var/cache` | maybe, for warmth | **no** |
| **This boot only** — pids, sockets | `/run` | no (tmpfs) | no |
| **This request only** — scratch | `/tmp` | no (tmpfs) | no |

The row people get wrong is `/etc`. Backing up configuration files feels
prudent and it captures the wrong artefact: what you want is the template and
the values that produced them, which live in a repository. Restoring hand-edited
`/etc` files onto a fresh machine reintroduces exactly the drift B06.2's conffile
scenario was about.

The row that costs money is `/var/cache`. It is adjacent to `/var/lib`, it looks
identical, and it is frequently ten or a hundred times larger. A backup job that
captures `/var` wholesale is backing up a thumbnail cache every night forever.

:::callback{to=topic.packages-and-dependencies}
B06.2's register of software "outside the archive" and this topic's `/opt` and
`/usr/local` are the same list. The hierarchy tells you where to look; the
package database tells you what it found.
:::

## Read-only roots, in practice

Running a container with `read_only: true` is the cheapest large security
improvement available, and it fails on the first try for nearly every real
service. The failures are almost never the application's own files:

- **The language runtime.** The JVM writes performance data to
  `/tmp/hsperfdata_<user>`. Python writes `__pycache__` next to source. Node
  writes to `~/.npm` if anything shells out to npm.
- **The TLS library.** OpenSSL will try to write a random seed file at `$HOME/.rnd`
  in some configurations.
- **The resolver and the user database.** Anything that calls `getpwnam` may want
  to open files that a hardened image has moved.
- **The application's own logging library**, which creates its directory at
  startup rather than assuming it exists.

The method that works is to stop predicting and measure:

```yaml
services:
  ledger:
    read_only: true
    tmpfs:
      - /tmp
      - /run
    volumes:
      - ledger-data:/var/lib/ledger
```

Start it, read the error, add the narrowest path that fixes it, repeat. Three or
four rounds usually finish it, and what you are left with is documentation
nobody had before: **an explicit, tested list of everything this service writes.**

Two rules for that list. Keep the paths **narrow** — `/var/lib/ledger`, not
`/var`. And prefer `tmpfs` over a volume for anything that does not need to
survive, because a tmpfs both satisfies the write and guarantees the data cannot
outlive the container.

:::warning
A writable path that is also executable is where a compromised process puts its
payload. If a path only needs to hold data, mount it `noexec`. This platform's
own lab containers make the opposite choice for `/tmp` deliberately and record
why next to the flag — the point is that it was a decision, not a default.
:::

## The mount that hides things

A volume mounted over a directory covers whatever was underneath. The classic
production version:

```yaml
volumes:
  - ./config:/etc/ledger        # the image's default configs are now invisible
```

The image shipped `/etc/ledger/ledger.conf` and `/etc/ledger/conf.d/`. The bind
mount contains only `ledger.conf`. The service starts with no `conf.d` at all,
and nothing logs a warning, because from the process's point of view the
directory simply does not exist.

The diagnostics are cheap and worth reaching for early:

```bash
mountpoint /etc/ledger          # is something mounted exactly here?
cat /proc/1/mountinfo           # everything the runtime attached
```

The habit: **when files that should exist do not, ask whether something is
mounted on top before you ask whether something deleted them.** Deletion is
loud and leaves traces; masking is silent and reversible.

## What a backup should contain

The manifest that survives review names paths rather than trees, and says why
each is there:

```text
BACKUP   /var/lib/ledger/ledger.db      state — cannot be regenerated
BACKUP   /var/lib/ledger/uploads/       state — user-supplied, irreplaceable
SKIP     /var/lib/ledger/render-cache/  cache in a state directory (see note)
SKIP     /var/cache/ledger/             regenerable
SKIP     /var/log/ledger/               shipped to the log system already
SKIP     /etc/ledger/                   generated from the config repo
CAPTURE  /opt/vendor-scanner/           outside the archive; no package restores it
```

Three things that manifest gets right and most do not.

**It skips a cache that is living in `/var/lib`.** Real services put caches in
state directories, so the rule cannot be "back up `/var/lib`" — it has to be
"back up things that cannot be regenerated", applied per path.

**It captures `/opt`.** A restore procedure that says "install the OS, install
the package, restore the archive" silently assumes every binary came from a
package. Anything installed by a vendor script has to be captured or scripted,
or the restore produces a machine that is missing something nobody remembers.

**It records the reason.** In two years the paths will have changed and the
reasoning is what lets somebody update the manifest instead of guessing.

## What to take from this topic

- **The hierarchy is an ownership contract**, and the package database will
  confirm it: `/usr/local`, `/opt` and `/srv` are owned by nothing, deliberately.
- **`/usr` is the installed system** — 306 MB of a 320 MB image here — and it is
  read-only in spirit, which is what makes images and read-only roots possible.
- **`/var/lib` and `/var/cache` are not the same kind of thing**, and no backup
  policy that treats `/var` as one directory is correct.
- **A write can be refused by the mount or by the mode**, and the error message
  tells you which. `Read-only file system` and `Permission denied` are different
  problems.
- **Mounting over a directory hides it.** Silent, reversible, and the first
  thing to check when files are missing.
- **A read-only root turns "what does this write?" into a list**, and the list is
  the documentation you never had.

:::objective{id=OBJ-B06.3.7}
:::

:::objective{id=OBJ-B06.3.8}
:::

---
topic: topic.boot-and-init
section: commands
title: Reading a boot, and interrogating a unit
order: 4
mode: do
---

:::objective{id=OBJ-A02.5.8}
Diagnose a service that will not start, from its unit file and its journal
output.
:::

## What did this machine boot with?

```bash
cat /proc/cmdline                    # every parameter the bootloader chose
uname -r                             # the kernel that was chosen
cat /proc/version                    # and who built it, with what
grep btime /proc/stat                # boot time, as a unix timestamp
date -d "@$(awk '/btime/{print $2}' /proc/stat)"
cut -d' ' -f1 /proc/uptime           # seconds since then
ls /sys/firmware/efi                 # UEFI, or not
zcat /proc/config.gz | grep -E '^CONFIG_(BLK_DEV_INITRD|CGROUPS)='
```

:::try{lab=read-your-boot run="cat /proc/cmdline" title="This machine's kernel command line"}
Note `initrd=`, and note `panic=`. Both are decisions somebody made about how
this machine should behave when things go wrong, and both are readable long
after the boot they applied to.
:::

## How long did it take, and where did the time go?

```bash
systemd-analyze                      # firmware, loader, kernel, userspace
systemd-analyze blame                # slowest units, descending
systemd-analyze critical-chain       # the path that determined total time
systemd-analyze critical-chain nginx.service
systemd-analyze plot > boot.svg      # the whole thing as a timeline
```

`blame` and `critical-chain` answer different questions and people reach for the
wrong one. `blame` lists the slowest units, most of which started in parallel
and cost nothing. `critical-chain` shows the dependency path that actually
determined when boot finished — which is the only list where making something
faster makes the boot faster.

## Interrogating a unit

```bash
systemctl status nginx               # state, PID, cgroup, recent log lines
systemctl cat nginx                  # the unit file, plus every drop-in override
systemctl show nginx                 # every property, resolved
systemctl list-dependencies nginx    # what it pulls in
systemctl list-dependencies --before nginx   # what waits on it
systemctl show -p After -p Requires -p Wants nginx
```

`systemctl cat` is the one to reach for first. It shows the vendor unit *and*
the drop-ins from `/etc/systemd/system/nginx.service.d/`, which is where the
setting that is confusing you usually lives. Reading only the file in
`/lib/systemd/system` is how people spend an hour on a value that is being
overridden.

```bash
systemctl edit nginx                 # create a drop-in, correctly
systemctl daemon-reload              # after editing unit files by hand
systemctl reset-failed nginx         # clear the start-limit counter
```

`reset-failed` is the command people do not know they need. Once a service has
hit its start limit it is no longer being retried — fixing the underlying
problem changes nothing until the counter is cleared.

## The journal

```bash
journalctl -u nginx                     # this unit only
journalctl -u nginx -b                  # since the current boot
journalctl -u nginx --since '10 min ago'
journalctl -b -1 -p err                 # errors from the *previous* boot
journalctl -f -u nginx                  # follow
journalctl -k                           # kernel messages — dmesg, with history
journalctl -o json-pretty -u nginx -n 1 # every field, not just the message
```

`journalctl -b -1` is the one that matters after an unexplained reboot: the
current boot's log cannot contain the reason the previous one ended. If it
returns nothing, the journal is not persistent — `Storage=persistent` in
`/etc/systemd/journald.conf`, and a `/var/log/journal` directory — and that is
worth fixing before the next incident rather than after.

:::try{lab=what-init-is-missing run="ls /run/systemd/system" title="Is systemd PID 1 here?"}
It is not, and the absence of that directory is the standard test. The lab has
you work out which of init's jobs is therefore nobody's.
:::

## Boot failed. What now?

Interrupt the bootloader and edit the command line for one boot:

```text
systemd.unit=rescue.target       # minimal, root shell, no network
systemd.unit=emergency.target    # more minimal: root filesystem only
init=/bin/sh                     # bypass systemd entirely. The last resort
systemd.log_level=debug          # verbose init, when the failure is after the kernel
```

From an emergency shell the root is usually mounted read-only:

```bash
mount -o remount,rw /
journalctl -b -1 -p err
dracut --force            # or update-initramfs -u — rebuild the initramfs
```

If the failure is `/dev/root does not exist` after a kernel upgrade, the
initramfs is missing a storage driver. Boot the previous kernel from the menu and
regenerate.

## The container versions of all of this

```bash
cat /proc/1/comm                        # your entrypoint, not systemd
ls /run/systemd/system                  # absent
docker run --init …                     # give the container a real init
kubectl logs pod -c app --previous      # the journal of the run that failed
kubectl describe pod                    # events: the closest thing to a boot log
```

`--previous` is the direct analogue of `journalctl -b -1`. The current
container's logs cannot contain the reason the last one exited, and reaching for
it late is the same mistake in a different vocabulary.

:::checkpoint
1. Which parameter would you add to bypass systemd entirely, and when?
2. Why does `systemd-analyze blame` mislead, and what should you read instead?
3. What does `systemctl cat` show that reading the unit file does not?
4. Which command tells you why the machine rebooted last night?
:::

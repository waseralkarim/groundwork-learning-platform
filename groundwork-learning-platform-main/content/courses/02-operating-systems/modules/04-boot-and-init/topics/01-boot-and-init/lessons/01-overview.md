---
topic: topic.boot-and-init
section: overview
title: Everything that had to happen before your service existed
order: 1
mode: explain
---

Between power-on and your process running there are five handovers, each between
components that know almost nothing about each other. Firmware cannot read your
filesystem. The bootloader cannot talk to your disk controller. The kernel
cannot mount the root it is about to boot from — not yet.

Every one of those gaps has a specific bridge, and knowing which bridge failed
is the difference between a five-minute recovery and a rebuild.

## The specific things this explains

- Why a machine boots to `dracut: /dev/root does not exist` after a kernel
  upgrade, and what to type at that prompt
- Why `Requires=` without `After=` is the commonest unit-file bug there is
- Why a service that "started successfully" was not yet able to serve traffic
- Why a crashlooping service stops being restarted, and why that is deliberate
- Why your container has no init, and what that costs
- Why `initContainers` and readiness probes exist, and what they are copies of

## The chain

:::diagram{src=../diagrams/boot-chain.mmd caption="Five handovers, each between components that barely know each other"}

The stage people find surprising is the initramfs. The kernel needs a driver to
see the root filesystem — NVMe, RAID, LUKS, LVM, iSCSI — and that driver lives
*on* the root filesystem it cannot yet read. The way out is to load a small root
into RAM first, containing exactly the drivers this machine needs, use it to
mount the real one, then throw it away.

Which is why a kernel upgrade that regenerates the initramfs without the right
driver produces a machine that cannot find its own disk, with the disk in
perfect health.

## What your machine actually booted with

Every parameter the bootloader chose is still readable:

:::terminal{title="/proc/cmdline on the machine running this platform"}
initrd=\initrd.img WSL_ROOT_INIT=1 panic=-1 nr_cpus=16
hv_utils.timesync_implicit=1 console=hvc0 debug pty.legacy_count=0
:::

`initrd=` names the RAM filesystem. `panic=-1` says reboot immediately on a
kernel panic rather than hanging — a deliberate choice, and one worth
recognising when you meet a machine that reboots instead of leaving you a trace.
`console=` decides where kernel messages go, which is the difference between
having output to read during a failed boot and having none.

:::callback
From **Processes**: PID 1 is treated specially by the kernel — it adopts orphans,
and a signal with no installed handler is not delivered to it. You met that as a
property of your container's shell. This topic is about what a *real* PID 1 does
with those responsibilities, and what it means that yours does not.
:::

## Then the part that never finishes

Booting the kernel is the easy half. The second half is starting a few hundred
units in an order that satisfies their dependencies, and this is where the model
matters:

:::predict{question="A unit has `Requires=postgres.service` and nothing else. When does it start relative to postgres?"}
At the same instant, which is almost certainly not what was meant.

systemd separates two questions that read as one in English. `Requires=` answers
*whether* — pull postgres in, and fail if it fails. `After=` answers *when* —
do not start until postgres has. They are orthogonal, and specifying one does
not imply the other.

So `Requires=postgres.service` alone starts both simultaneously. The service
comes up, tries to connect to a database that is still initialising, and fails
— intermittently, depending on which one wins the race, which is what makes it
so annoying to diagnose. It works on a fast machine and fails on a loaded one.

The fix is both lines:

```ini
Requires=postgres.service
After=postgres.service
```

And even that is weaker than it looks, because `After=` on a `Type=simple` unit
means "after postgres was *launched*", not "after postgres can accept
connections". Getting that last step right needs `Type=notify` — which is
exactly the gap Kubernetes readiness probes exist to fill.
:::

## What you already have

From **Processes**, PID 1's contract and what happens when an ordinary program
inherits it. From **cgroups**, the hierarchy — and systemd puts every unit in
one, which is why `systemd-cgls` shows you a tree of services. From **Files and
Filesystems**, mounts, which is what `switch_root` is doing.

## How to work through it

Concepts, mechanism, tools, production. Four labs: read what this machine
booted with, from its own kernel command line and configuration; find out what
your container's PID 1 is and which of init's jobs nobody is doing; work out the
start order a set of real unit files produces, and find the bug in them; and
diagnose three services that will not start, where one of them is not broken at
all any more.

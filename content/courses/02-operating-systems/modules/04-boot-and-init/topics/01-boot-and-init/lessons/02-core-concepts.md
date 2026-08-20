---
topic: topic.boot-and-init
section: core-concepts
title: The five handovers
order: 2
mode: explain
---

:::objective{id=OBJ-A02.5.1}
Trace the boot sequence from firmware to the first user-space process, naming
what each stage hands to the next.
:::

## Firmware knows about disks, not filesystems

UEFI initialises hardware and then looks for a bootloader. It can read exactly
one filesystem — FAT, on the EFI system partition — and it finds the bootloader
by path, recorded in NVRAM variables you can read with `efibootmgr`.

Legacy BIOS could not even do that. It read the first 512 bytes of a disk and
jumped to them, which is why the MBR bootloader had to be a two-stage
arrangement squeezed into 446 bytes.

```bash
ls /sys/firmware/efi        # exists on a UEFI boot; absent on BIOS or in a VM
efibootmgr -v               # the boot entries, in order
```

The absence of `/sys/firmware/efi` is a fact rather than a fault. Many
hypervisors, containers and WSL kernels boot by a path that involves no firmware
at all.

## The bootloader chooses a kernel and writes its command line

GRUB or systemd-boot presents a menu, loads the chosen kernel and its initramfs
into memory, assembles a command line, and jumps to the kernel's entry point.

The command line is the most useful artefact of the whole stage, because it
survives:

```bash
cat /proc/cmdline
```

:::objective{id=OBJ-A02.5.2}
Interpret a kernel command line, and identify the parameters that matter for
boot and for recovery.
:::

| Parameter | What it does |
|---|---|
| `root=UUID=…` | Which filesystem to mount as `/`. By UUID, because device names are not stable |
| `initrd=` | Where the initramfs was loaded from |
| `ro` | Mount the root read-only initially; init remounts it writable after checking |
| `init=/bin/sh` | Run this instead of `/sbin/init`. **The recovery lever** |
| `single` / `systemd.unit=rescue.target` | Boot to a minimal state |
| `panic=N` | Reboot N seconds after a kernel panic. `-1` means immediately, `0` means hang |
| `console=` | Where kernel messages go. Getting this wrong means a silent failed boot |
| `nomodeset` | Skip kernel mode setting — the standard fix for a blank screen on boot |
| `systemd.log_level=debug` | Verbose init, when the failure is after the kernel |

`init=/bin/sh` is the one to remember. It bypasses systemd entirely and gives
you a shell as PID 1 on the real root — the recovery of last resort when init
itself is what is broken.

:::objective{id=OBJ-A02.5.3}
Explain why an initramfs exists, and what fails without one.
:::

## The initramfs, and the problem it solves

The kernel must mount the root filesystem. To do that it needs a driver for the
controller the root is on, and the module for that driver lives in `/lib/modules`
— on the root filesystem it cannot mount yet.

The way out is a small compressed root loaded into RAM alongside the kernel,
containing exactly the modules this machine needs. The kernel unpacks it, runs
`/init` inside it, that assembles whatever is required to see the real root —
loading NVMe drivers, assembling RAID, unlocking LUKS, activating LVM — and then
`switch_root` pivots to the real root and frees the RAM disk.

```bash
lsinitrd /boot/initramfs-$(uname -r).img | head      # Fedora/RHEL
lsinitramfs /boot/initrd.img-$(uname -r) | head      # Debian/Ubuntu
dracut --force                                       # rebuild it
update-initramfs -u                                  # the Debian spelling
```

This matters operationally because the initramfs is **generated per machine and
per kernel**. A kernel upgrade regenerates it; if the generator does not include
the driver for this machine's storage, the new kernel boots and cannot find its
own disk. The disk is healthy, the filesystem is intact, and the machine drops
to an emergency shell.

The fix is almost always to boot the previous kernel from the bootloader menu
and regenerate — which is why keeping more than one kernel installed is not
hoarding.

## Then PID 1

`switch_root` executes `/sbin/init`, which becomes PID 1 and inherits two
responsibilities from the kernel:

- **Orphans are reparented to it**, so it must reap them or the process table
  fills with zombies.
- **Signals with no installed handler are not delivered to it**, so it cannot be
  killed by accident — and cannot be stopped by a `SIGTERM` it does not handle.

On a machine that is systemd. In a container it is your application, which
almost certainly implements neither.

```bash
cat /proc/1/comm        # systemd on a host; your entrypoint in a container
ls /run/systemd/system  # exists only if systemd is actually PID 1
```

That second command is the standard test, and it is what tools use to decide
whether they are on a systemd machine at all.

:::callback
From **Processes**: you sent a signal to a process that would not die and
established the difference between an ignored signal and one that cannot be
received. The kernel's PID 1 rule is the second case, and it is the reason
`docker stop` on a shell-as-PID-1 container waits the full ten seconds and then
kills it.
:::

## The one-sentence version

Firmware finds a bootloader, the bootloader loads a kernel and a RAM disk, the
RAM disk exists solely to make the real root mountable, and whatever runs as
PID 1 afterwards inherits orphans and a signal exemption whether or not it was
written to.

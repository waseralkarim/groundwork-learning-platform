#!/bin/bash
# Seeds the "wrong architecture" challenge.
#
# Writes an ELF header claiming AArch64. The kernel reads that header, refuses,
# and produces exactly the error the lab is about — which is the whole point:
# the failure happens in the loader, before any code runs.
#
# printf rather than a scripting language, so the lab image needs no runtime.
set -euo pipefail

mkdir -p /tmp/challenge

# ELF magic, 64-bit, little endian, version 1, then padding to offset 16.
printf '\177ELF\002\001\001\000\000\000\000\000\000\000\000\000' > /tmp/challenge/tool
# e_type = ET_EXEC (2), e_machine = EM_AARCH64 (183 = 0xB7).
printf '\002\000\267\000' >> /tmp/challenge/tool
# Enough trailing bytes for the kernel to read a plausible header.
head -c 176 /dev/zero >> /tmp/challenge/tool

chmod +x /tmp/challenge/tool
echo "There is a program at /tmp/challenge/tool. It does not run. Find out why."

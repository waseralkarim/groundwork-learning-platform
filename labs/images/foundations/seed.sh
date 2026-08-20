#!/bin/bash
# Baseline lab seeding. Runs once, before the learner attaches.
set -euo pipefail

# Only the history file. Shell configuration cannot live here at all: setup
# commands run *after* the container has started, by which time bash has already
# read its startup files, so anything written to ~/.profile or ~/.bashrc now is
# read by nobody. The prompt and history flushing are baked into
# /etc/bash.bashrc in the image, which is read at shell start.
touch "$HOME/.bash_history"

echo "Lab ready. Type the commands the instructions ask for; nothing here is permanent."

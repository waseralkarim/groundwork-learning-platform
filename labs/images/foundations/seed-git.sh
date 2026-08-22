#!/bin/bash
# Seeds the B10.1 object-model labs.
#
# Two things are needed before a learner can commit at all, and neither is the
# subject of this topic:
#
#   - an identity, or every `git commit` stops with "Please tell me who you
#     are". Set here so the topic can be about objects rather than about
#     configuring git.
#   - init.defaultBranch, because git otherwise prints a paragraph of advice on
#     every `git init` and the learner's first impression of the tool is a
#     warning they cannot act on.
#
# What is seeded beyond that is deliberately small: this topic is about what a
# repository *is*, and a large history would hide the four objects behind
# scale. One repository with three commits, one file that never changes, and
# one that changes every time.
set -euo pipefail

export LC_ALL=C

git config --global user.name "Lab Learner"
git config --global user.email "learner@lab.invalid"
git config --global init.defaultBranch main
git config --global advice.detachedHead false
# A fixed identity makes commit ids reproducible for anything that pins them,
# but the timestamps still move, so nothing in this topic asserts a commit id.

S=/tmp/git
rm -rf "$S"; mkdir -p "$S"

cat > "$S/README.txt" <<'EOF'
Material for the object-model labs.

  ledger/     a repository with three commits. One file (LICENSE) is identical
              in all three. One file (balance.txt) changes in every commit.
              That contrast is the point: look at what the object store does
              with each of them.

Everything here is a normal repository. Nothing is hidden and nothing is
special-cased -- `git cat-file` and `find .git/objects` tell you the whole
truth about it.
EOF

# ---------------------------------------------------------------- ledger repo
R="$S/ledger"
mkdir -p "$R"
cd "$R"
git init -q

# LICENSE never changes. It should appear as ONE blob, referenced by all three
# trees -- the cleanest demonstration that Git stores snapshots with reuse and
# not a chain of diffs.
cat > LICENSE <<'EOF'
Copyright (c) 2024 Example Ltd.
All rights reserved.
EOF

cat > balance.txt <<'EOF'
opening balance: 0
EOF

git add -A
git commit -q -m "Open the ledger"

cat > balance.txt <<'EOF'
opening balance: 0
deposit: 120
EOF
git add -A
git commit -q -m "Record the first deposit"

mkdir -p accounts
cat > accounts/payable.txt <<'EOF'
invoice 8871: 45
EOF
cat > balance.txt <<'EOF'
opening balance: 0
deposit: 120
payable: 45
EOF
git add -A
git commit -q -m "Add accounts payable"

# A branch that points at the middle commit, so "a branch is a file containing
# forty bytes" can be checked against a ref that is NOT the current one.
git branch before-payables HEAD~1

cd "$S"
chmod -R a+rX "$S"

---
topic: topic.searching-text
section: commands
title: The flags worth knowing
order: 4
mode: do
---

## grep

```bash
grep -q PATTERN file       # quiet: exit status only, stops at first match
grep -c PATTERN file       # count of matching LINES (not matches)
grep -n PATTERN file       # line numbers
grep -v PATTERN file       # invert
grep -i PATTERN file       # case insensitive
grep -w PATTERN file       # whole words only
grep -x PATTERN file       # whole lines only
grep -F 'literal' file     # no metacharacters — for patterns from data
grep -E 'a+|b?' file       # extended regex
grep -r PATTERN dir/       # recursive
grep -l PATTERN files      # just the filenames that matched
grep -L PATTERN files      # the ones that did NOT
grep -A3 -B1 PATTERN file  # context lines after and before
grep -o PATTERN file       # print only the matched part
grep -e -foo file          # a pattern starting with a hyphen
```

`-c` counts **lines**, not occurrences. For occurrences use `grep -o pat file |
wc -l`, which is a genuinely different number when a line matches twice.

`-l` and `-L` are the pair to reach for when auditing: "which config files
mention this setting" and "which ones are missing it" are usually the same
question asked twice.

## Exit status, used deliberately

```bash
if grep -q PATTERN file; then ...          # branch on it
grep PATTERN file || true                  # I do not care — comment why
count=$(grep -c PATTERN file || true)      # zero is a valid answer
grep -q PATTERN file; case $? in
  0) echo found ;;
  1) echo "not present" ;;
  *) echo "grep failed" >&2; exit 1 ;;
esac
```

The `case` form is the only one that separates "absent" from "broken". Worth it
whenever the file might not exist.

## awk

```bash
awk '{print $2}'                    # second whitespace-separated field
awk '{print $NF}'                   # last field — survives columns added left
awk '{print $(NF-1)}'               # second from the end
awk -F, '{print $3}'                # comma-delimited
awk -F: '$3 >= 1000 {print $1}'     # a field comparison
awk 'NR > 1'                        # skip a header
awk 'NR==1 {next} {sum += $2} END {print sum}'
awk '/ERROR/ {n++} END {print n+0}' # count matches; +0 forces 0 not empty
awk '{n[$4]++} END {for (k in n) print n[k], k}'   # group by a field
awk -v threshold=500 '$5 > threshold'             # pass a shell value in
```

`-v` is how a shell variable reaches awk. **Do not interpolate one into the
program text** — that is the same class of problem as an unquoted expansion, and
a value containing a quote or a slash breaks or rewrites the program.

`END {print n+0}` rather than `END {print n}` because an unset awk variable
prints as empty, not zero, and an empty count in a report reads as a missing
value rather than a good result.

## sed

```bash
sed 's/old/new/'           # first match per line
sed 's/old/new/g'          # all matches
sed -E 's/[0-9]+/N/g'      # extended regex
sed -n '/PATTERN/p'        # print only matching lines (-n suppresses the rest)
sed -n '5,10p'             # a line range
sed '/^#/d'                # delete lines
sed '1d'                   # delete the first line
sed 's|/usr/local|/opt|'   # any delimiter — avoids escaping slashes
sed -i.bak 's/a/b/' file   # in place, keeping a .bak copy
```

Prefer `[^"]*` over `.*` when matching between delimiters — `.*` is greedy and
will run to the last one on the line.

`sed -i` is not really in place: it writes a new file and renames it, changing
the inode and breaking hard links. That matters for a bind-mounted config or
anything watched by inode.

## cut, and when it is right

```bash
cut -d, -f2,4 file         # a real delimited file
cut -d: -f1 /etc/passwd    # a real delimited file
cut -c1-8 file             # fixed character positions
```

Never `cut -d' '` on command output. Runs of spaces produce empty fields, the
failure is silent, and `awk '{print $2}'` is the same length to type.

## sort, uniq and the counting idiom

```bash
sort | uniq -c | sort -rn        # frequency, most common first
sort -u                          # unique, no counts
sort -k2,2 -n                    # numeric sort on field 2 only
sort -t, -k3,3                   # a delimited file
```

`uniq` only collapses **adjacent** duplicates, so it is always preceded by
`sort`. `-k2,2` means "from field 2 to field 2" — without the second number the
key runs to the end of the line, which is the most common `sort` surprise.

`LC_ALL=C sort` makes byte-order sorting explicit. This image has only `C`,
`C.utf8` and `POSIX` locales so the difference is not visible here — on a
machine with a full locale set, collation changes which lines are adjacent and
therefore what `uniq` collapses.

## Reading them back

```bash
grep -c ''                  # count lines, including empty ones
awk 'END{print NR}' file    # the same, one process
wc -l < file                # fastest, and wrong if the last line has no newline
```

Those three disagree on a file whose final line is unterminated, which real logs
produce when a process is killed mid-write.

:::try{lab=the-search-that-killed-the-script}
:::

:::objective{id=OBJ-B08.3.4}
:::

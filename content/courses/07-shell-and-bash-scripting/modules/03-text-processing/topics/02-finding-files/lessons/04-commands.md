---
topic: topic.finding-files
section: commands
title: The predicates and flags worth knowing
order: 4
mode: do
---

## Selecting

```bash
find DIR -name '*.log'          # quote it, or the shell globs it first
find DIR -iname '*.LOG'         # case insensitive
find DIR -path '*/cache/*'      # match against the whole path
find DIR -type f                # f file, d directory, l symlink
find DIR -size +100M            # larger than; also k, M, G
find DIR -empty                 # zero-length files or empty directories
find DIR -user app -group app
find DIR -perm -u+w             # at least these bits set
find DIR -maxdepth 2            # put global options FIRST — they are not positional
find DIR -mindepth 1            # skip DIR itself
```

Quoting the pattern is not optional. Unquoted, the shell expands `*.log`
against the current directory *before* find runs — which happens to work when
nothing matches, so the bug appears only when somebody runs the script from a
different directory.

## Time

```bash
find DIR -mtime +7        # more than 7 whole 24h periods — so 8 or more
find DIR -mtime -1        # less than one whole day
find DIR -mmin +60        # minutes; no day-boundary surprise
find DIR -newermt '-7 days'      # newer than a moment in time
find DIR ! -newermt '-7 days'    # older than it — the clear form
find DIR -newer reference.txt    # newer than a file's mtime
```

Prefer `-newermt` when the boundary matters. `-mtime` truncates to whole days,
so `+7` excludes a file that is seven days old, and a policy written from the
English phrase "older than a week" will usually mean `+6`.

`-mtime` is **modification** time. `-atime` may be meaningless on a `relatime`
or `noatime` mount, and `-ctime` is bumped by `chmod` and `chown` — so a
permissions fix can make an old file look new to a retention job.

## Combining

```bash
find . -name '*.log' -type f                  # implicit AND
find . \( -name '*.log' -o -name '*.txt' \)   # OR — parenthesise it
find . ! -name '*.tmp'                        # NOT
find . -name '*.log' ! -path '*/cache/*'
```

Parenthesise any `-o` that is followed by an action. Unparenthesised,
`-name A -o -name B -delete` deletes only the B files, because `-o` binds more
loosely than the implicit AND.

## Not descending

```bash
find . -path '*/node_modules' -prune -o -name '*.log' -print
find . \( -name node_modules -o -name .git \) -prune -o -print
```

The explicit `-print` is required: supplying any action removes the implicit
one, and without it find also prints the pruned directories themselves.

`-prune` never enters the directory, which is the difference from `! -path`.
On a tree where the excluded subtree holds most of the files, that is a
measurable speed-up rather than a stylistic choice.

## Acting

```bash
find . -name '*.log' -print                   # explicit
find . -name '*.log' -print0                  # NUL-separated, for xargs -0
find . -name '*.log' -printf '%p %s %TY\n'    # custom fields, GNU
find . -name '*.log' -delete                  # no shell involved
find . -name '*.log' -exec gzip {} +          # batched, status propagated
find . -name '*.log' -exec gzip {} \;         # one process each, status IGNORED
find . -name '*.log' -execdir gzip {} \;      # run in the file's own directory
find . -name '*.log' -ok rm {} \;             # prompts before each one
```

`-printf` is worth learning for reports: `%p` path, `%f` filename, `%s` size,
`%TY-%Tm-%Td` mtime, `%u` owner, `%y` type.

`-execdir` runs the command with the working directory set to the file's own,
which avoids a class of race where a path is renamed mid-walk.

## xargs

```bash
cmd | xargs -0 -r target --            # the safe default set
xargs -0        # NUL-separated input, pairs with -print0
xargs -r        # do not run at all on empty input (GNU)
xargs -n 20     # at most 20 arguments per invocation
xargs -I{} cmd {}   # template — implies ONE item per invocation
xargs -P 4      # four processes in parallel
xargs -t       # print each command before running it
```

`-t` is the dry-run-adjacent flag: it echoes each command to stderr as it runs,
which is how you find out what a complicated `xargs` is actually doing.

`-I` and `-P` interact badly with expectations: `-I` gives up batching, and `-P`
interleaves output from several processes so partial lines can mix.

## Reviewing before acting

```bash
# 1. compute the list once
find "$DIR" -type f -name '*.log' ! -newermt "-7 days" -print0 > /tmp/victims

# 2. review it
tr '\0' '\n' < /tmp/victims | head -20
printf 'total: %d\n' "$(tr -dc '\0' < /tmp/victims | wc -c)"

# 3. act on exactly that list
xargs -0 -r rm -- < /tmp/victims
```

Counting NULs is how you count NUL-separated records — `wc -l` counts newlines,
which is the thing you were avoiding.

## Checking exit status

```bash
find "$DIR" -name '*.log' -print0 > /tmp/list || echo "find had errors" >&2
set -o pipefail                     # so find's status survives a pipeline
echo "${PIPESTATUS[@]}"             # which stage failed
```

find returns 1 when it could not read part of the tree. In a pipeline that
status is discarded unless `pipefail` is set, so `find | xargs rm` silently
skips whatever it could not see.

:::try{lab=predicates-and-time}
:::

:::objective{id=OBJ-B08.4.7}
:::

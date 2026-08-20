---
topic: topic.concurrency-and-locking
section: commands
title: The forms worth knowing
order: 4
mode: do
---

## Locking a script

```bash
exec 9>/var/lock/myjob.lock          # open, and KEEP it open
flock -n 9 || exit 0                 # do not wait; another run is going
```

```bash
flock -n 9 || { echo "already running" >&2; exit 0; }   # say so
flock 9                                                  # wait indefinitely
flock -w 30 9 || { echo "timed out waiting" >&2; exit 1; }
flock -s 9                                               # SHARED: many readers
flock -u 9                                               # release early
```

Exit status is **1** when `-n` or `-w` gives up. Never `rm` the lock file.

## Locking a command, without touching the script

```bash
flock -n /var/lock/myjob.lock ./myjob.sh
flock -n /var/lock/myjob.lock -c 'pg_dump db | gzip > /srv/b.gz'
```

```crontab
*/5 * * * * flock -n /var/lock/report.lock /opt/jobs/report.sh
```

The crontab form is the one to reach for first: no change to the script, and the
guard is visible where the schedule is.

## Other exclusion primitives

```bash
mkdir /var/lock/myjob.d 2>/dev/null || exit 0     # atomic; goes stale
rmdir /var/lock/myjob.d                            # in a trap

set -o noclobber                                   # atomic create-if-absent
: > /var/lock/myjob.lock || exit 0                 # fails if it exists

pgrep -x myjob >/dev/null && exit 0                # a guess, not a lock
```

`noclobber` gives you an atomic create, and inherits the PID file's staleness
problem — the file survives a crash.

## Time limits

```bash
timeout 30 ./importer                  # TERM after 30s;  rc 124 on timeout
timeout -k 5 30 ./importer             # then KILL 5s later — the guarantee
timeout -s INT 30 ./importer           # send something else
timeout --foreground 30 ./cmd          # when it must keep the terminal

status=$?
case $status in
  0)   ;;
  124) echo "exceeded the time limit" >&2 ;;
  137) echo "killed after refusing to stop" >&2 ;;   # 128 + 9
  *)   echo "failed with $status" >&2 ;;
esac
```

Bare `timeout` sends a signal a process may ignore. **`-k` is what makes it a
guarantee.**

## Retrying

```bash
retry() {
  local -i attempts=${RETRIES:-5} delay=1 n=1
  until "$@"; do
    local status=$?
    [ "$n" -ge "$attempts" ] && { echo "giving up after $n: $*" >&2; return "$status"; }
    sleep "$(( delay + RANDOM % delay ))"          # backoff WITH jitter
    delay=$(( delay < 32 ? delay * 2 : 32 ))       # capped
    n=$(( n + 1 ))
  done
}

retry curl -fsS --max-time 10 "$URL" -o "$OUT"
```

`--max-time` matters as much as the retry: without a per-attempt limit, one hung
attempt eats the whole budget.

```bash
curl --retry 5 --retry-delay 2 --retry-max-time 60 --retry-all-errors "$URL"
```

`curl` has this built in, and its `--retry` only covers transient failures unless
`--retry-all-errors` is given.

## Making an operation safe to repeat

```bash
mkdir -p "$DIR"                                  # not mkdir
ln -sfn "$TARGET" "$LINK"                        # replaces an existing link
rsync -a --delete "$SRC/" "$DEST/"               # converges
grep -qxF "$LINE" "$FILE" || echo "$LINE" >> "$FILE"

# write beside, verify, rename — a reader sees old or new, never half
tmp=$(mktemp "$DEST.XXXXXX")
produce > "$tmp"
[ -s "$tmp" ] || { rm -f "$tmp"; echo "empty output" >&2; exit 1; }
mv -f "$tmp" "$DEST"
```

`mv` within one filesystem is a `rename(2)` and is **atomic**. Across
filesystems it is a copy, and it is not — so keep the temporary file in the
destination's own directory, which is also why `mktemp "$DEST.XXXXXX"` rather
than `mktemp` in `/tmp`.

## Inspecting a lock

```bash
flock -n 9 9>/var/lock/myjob.lock && echo free || echo held
fuser -v /var/lock/myjob.lock          # who holds it — absent on this image
ls -li /var/lock/myjob.lock            # the inode number
lsof /var/lock/myjob.lock              # also absent here
```

The inode number is the useful one when a lock is behaving strangely: if it has
changed since the holder started, somebody deleted and recreated the file.

:::try{lab=watch-two-runs-collide}
:::

:::objective{id=OBJ-B08.8.2}
:::

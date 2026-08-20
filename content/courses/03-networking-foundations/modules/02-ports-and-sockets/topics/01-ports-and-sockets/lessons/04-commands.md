---
topic: topic.ports-and-sockets
section: commands
title: ss and nc as instruments
order: 4
mode: do
---

:::objective{id=OBJ-A03.2.2}
Identify what is listening on a machine — on which addresses and ports, and
which process owns each socket.
:::

## What is listening here?

```bash
ss -tlnp                 # TCP, listening, numeric, with processes
ss -ulnp                 # the same for UDP
ss -tulnp                # both at once — the one to type
```

The flags are worth learning as a unit: `-t` TCP, `-u` UDP, `-l` listening only,
`-n` numeric (do not resolve names, which is slow and sometimes wrong), `-p`
processes.

Without `-n`, `ss` turns 443 into `https` and every address into a hostname,
which looks friendly and hides the numbers you are trying to read.

:::try{lab=what-is-listening run="ss -tlnp" title="Every listening socket in this container"}
Note the `Local Address` column. One of these is on a loopback address you did
not configure — a resolver the runtime put there — and the address it is bound
to decides who can reach it.
:::

## What is connected?

```bash
ss -tn                        # established TCP, numeric
ss -tan                       # all states
ss -tan state time-wait
ss -tan state close-wait      # if this is large, it is an application bug
ss -s                         # a summary: totals per state
```

Filters can be much more specific than people expect:

```bash
ss -tn dst 10.0.1.5           # connections to one host
ss -tn dport = :443           # connections to one port
ss -tn '( dport = :443 or sport = :443 )'
ss -tn state established '( dport = :5432 )' | wc -l    # open DB connections
```

That last one answers "how many connections is this process holding to the
database" without touching the application or its metrics.

## Testing a port

```bash
nc -z -w 2 10.0.1.5 5432; echo $?     # 0 = open, 1 = refused or timed out
nc -z -w 2 -v 10.0.1.5 5432           # -v prints which it was
nc -l 0.0.0.0 9000                     # listen, to test from the other side
curl -sv telnet://10.0.1.5:5432        # curl's version, useful in minimal images
```

`nc -z` connects and immediately closes. The exit status alone cannot
distinguish refused from timed out — add `-v`, or watch how long it takes.
Instant is a refusal; several seconds is a timeout, and they mean opposite
things.

:::try{lab=bound-to-the-wrong-address run="ss -tln" title="Two listeners, two different reaches"}
The lab starts one listener on `127.0.0.1` and one on `0.0.0.0`, then connects
to both from the container's own external address. One succeeds and one is
refused, and the difference is a single field in this output.
:::

## Reading /proc directly

```bash
head -3 /proc/net/tcp
```

```text
sl  local_address rem_address   st tx_queue rx_queue ...
 1: 0100007F:2328 00000000:0000 0A ...
 2: 0100007F:2328 0100007F:81A8 01 ...
```

Addresses are hex and **little-endian**: `0100007F` reads as `7F.00.00.01` =
`127.0.0.1`. Ports are hex and big-endian: `2328` = 9000, `81A8` = 33192. The
`st` column is the state: `0A` is LISTEN, `01` is ESTABLISHED, `06` is
TIME-WAIT.

You would not normally read this by hand — `ss` exists — but it is where `ss`
gets its data, and knowing that is useful when you are in a container with no
`ss` and only `cat`.

## Queues and counters

```bash
ss -tln                                       # Send-Q on a LISTEN row = backlog
cat /proc/sys/net/core/somaxconn              # the ceiling on that
cat /proc/sys/net/ipv4/ip_local_port_range    # ephemeral ports
nstat -az TcpExtListenOverflows TcpExtListenDrops
grep -A1 '^Tcp:' /proc/net/snmp               # ActiveOpens, PassiveOpens, AttemptFails, OutRsts
```

`ListenOverflows` rising means the accept queue filled and connections were
dropped silently — the client sees a timeout and the server looks healthy, which
is one of the harder failures to attribute without this counter.

`OutRsts` in `/proc/net/snmp` counts resets *this machine sent*. A rising rate
usually means connection attempts to ports with nothing bound, which on a server
is either a scanner or a client using a stale configuration.

## The order to check things in

```bash
ss -tlnp | grep :<port>       # 1. is anything listening, and on which address?
nc -z -v -w 2 <host> <port>   # 2. from where you actually need it to work
ss -tan | grep :<port>        # 3. what state are the connections in?
nstat -az TcpExtListenOverflows   # 4. is the queue overflowing?
```

Step 1 answers "is it bound at all, and to the right address" — which is the
answer more often than anything else. Step 2 must be run from the machine that
is failing, not from the server; running it locally is how the loopback-binding
bug survives an entire investigation.

:::checkpoint
1. What do `Recv-Q` and `Send-Q` mean on a row in state LISTEN?
2. How do you tell a refusal from a timeout with `nc`?
3. What does a large and growing `CLOSE-WAIT` count tell you, and whose bug is
   it?
4. Why must the connectivity test be run from the failing client rather than
   the server?
:::

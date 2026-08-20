---
topic: topic.ports-and-sockets
section: production
title: The failures this causes, and what to do about them
order: 5
mode: explain
---

:::objective{id=OBJ-A03.2.8}
Diagnose a service that is running and unreachable, from the socket table and a
connection attempt.
:::

## "It works on the box"

The single most common networking bug in deployment, and it is one line of
configuration.

```bash
# on the server
ss -tlnp | grep :9000
LISTEN 0 4096 127.0.0.1:9000 0.0.0.0:* users:(("app",pid=812,fd=6))
```

`127.0.0.1` and not `0.0.0.0`. Anything from another machine gets a reset, and
every local test passes.

It happens because binding to loopback is the *responsible* default for a
development server, so frameworks choose it: Flask, Rails, Vite, `python -m
http.server`, and most database packages ship listening on loopback only. The
setting then survives into a deployment where it is wrong.

In containers it has an extra twist. A process bound to `127.0.0.1` inside a
container is bound to the *container's* loopback, which nothing outside the
container shares — so `-p 8080:9000` forwards to a port that will refuse it.
"Published the port and it still refuses" is this bug, and the fix is `0.0.0.0`
inside the container.

:::warning{scope=production}
The corollary is worth stating too: binding `0.0.0.0` on a machine with a
management interface, a VPN, or a cloud metadata network exposes the service on
all of them. On a host with public addressing, `0.0.0.0` plus a missing firewall
rule is how databases end up on the internet. Bind to the interface the service
should be reachable on, or bind `0.0.0.0` and mean it.
:::

## Ports that are already taken

```text
bind: Address already in use
```

Two different causes and the fix differs:

```bash
ss -tlnp | grep :8080          # is something actually listening?
ss -tan  | grep :8080          # or is it a lingering TIME-WAIT / CLOSE-WAIT?
```

If a process holds it, the question is which — often an old copy of the same
service that did not exit, or a second replica scheduled onto the same host.

If nothing is listening but the address is still in use, the previous socket is
in `TIME-WAIT` and the kernel is holding the tuple. `SO_REUSEADDR` — which most
servers set — allows binding over it, and a service that does not set it cannot
restart within sixty seconds of stopping. That is worth knowing before you spend
a deploy window on it.

## Running out of ports, which is rarer than claimed

A client exhausts ephemeral ports only when it opens tens of thousands of
connections **to one destination**:

```bash
cat /proc/sys/net/ipv4/ip_local_port_range        # 32768 60999 — about 28000
ss -tan state time-wait | wc -l
ss -tn dst 10.0.1.5 | wc -l                        # to one destination
```

The four-tuple has to be unique overall, so the same source port can be reused
for a different destination. The limit binds per `(destination address,
destination port)` pair, not per client.

When it does bind, the answer is almost never to widen the range. It is
connection pooling or keep-alive: a client making 20000 short-lived connections
a minute to one service is doing something the protocol offers a better way to
do, and every one of those connections also costs a TIME-WAIT for a minute
afterwards.

## Health checks are connections

Every readiness probe, load-balancer health check and orchestrator liveness
check is a connection to a port, and they fail in exactly the ways above:

- **Refused** — the process is not listening yet, or is bound to the wrong
  address. If the probe runs on localhost inside the pod and the service is
  bound to loopback, the probe passes and real traffic fails.
- **Timeout** — the process is listening and not accepting, which usually means
  the accept queue is full or the event loop is blocked. A check that only tests
  whether the port is open reports healthy while every real request queues.
- **Reset mid-check** — the process is crashing on accept, which a plain TCP
  check will not distinguish from success.

Which is why a TCP-connect check is the weakest useful health check. An HTTP
check that exercises a real path is worth much more, and it is the difference
between "the port is open" and "the service can do its job".

:::predict{question="A service has thousands of sockets in CLOSE-WAIT and is slowly failing. What is happening, and whose problem is it?"}
The application is not calling `close()`, and it is your code.

`CLOSE-WAIT` means the peer sent a FIN — they are done — and the local kernel is
waiting for the application to close its end. The kernel cannot proceed on its
own and there is no timeout: a socket in `CLOSE-WAIT` stays there until the
process closes it or exits.

Every one of those sockets holds a file descriptor. The count only goes up, and
when it reaches the process's `RLIMIT_NOFILE` the service stops being able to
open anything — new connections, files, log handles — and fails in ways that
look nothing like a socket leak.

The usual causes are an error path that returns without closing, a connection
pool that discards without closing, or a response handler that never runs
because an exception escaped. `ss -tan state close-wait` groups them by peer,
which usually points at the specific client or backend involved.

The contrast with `TIME-WAIT` is the thing to keep straight. `TIME-WAIT` is on
the side that closed *first*, it is correct, it expires by itself in about a
minute, and thousands of them on a busy client are normal. `CLOSE-WAIT` is on
the side that has *not* closed, it never expires, and one is one too many if the
count is growing.
:::

## What to alert on

```promql
# accept queue overflowing — the server looks healthy, clients time out
rate(node_netstat_TcpExt_ListenOverflows[5m]) > 0

# sockets the application is failing to close
node_sockstat_TCP_inuse                       # with a CLOSE-WAIT breakdown

# connection attempts failing
rate(node_netstat_Tcp_AttemptFails[5m])

# resets we are sending — usually connections to ports with nothing bound
rate(node_netstat_Tcp_OutRsts[5m])
```

`ListenOverflows` is the one most often missing, and it is the one that explains
the otherwise inexplicable combination of a healthy server and timing-out
clients.

What not to alert on: total socket count, or `TIME-WAIT` count. Both scale with
legitimate traffic and produce alerts that get muted.

## The five things worth remembering

1. A bind claims an address as well as a port, and `127.0.0.1` is why it works
   locally.
2. A connection is four numbers, so one listening port serves everybody.
3. A client's port limit is per destination, and pooling is the fix rather than
   a wider range.
4. `TIME-WAIT` is correct and expires; `CLOSE-WAIT` is your bug and does not.
5. Refused proves the network worked. A timeout proves nothing.

:::checkpoint
1. Why does publishing a container port not help if the process bound to
   `127.0.0.1`?
2. What are the two different causes of "Address already in use"?
3. Why is a TCP-connect health check weaker than an HTTP one?
4. Which counter explains a healthy-looking server whose clients are timing out?
:::

---
topic: topic.ports-and-sockets
section: core-concepts
title: Sockets, bindings and the four-tuple
order: 2
mode: explain
---

:::objective{id=OBJ-A03.2.1}
Explain what a port identifies, and why an address alone cannot deliver a packet
to a process.
:::

## Two numbers, two jobs

An address gets a packet to a machine. A port gets it to a socket on that
machine. Neither is sufficient alone, and the pair is what everything else is
built on.

Ports are 16 bits — 0 to 65535 — and they are namespaced by protocol. TCP port
53 and UDP port 53 are different sockets, which is why DNS uses both without
conflict.

The conventional divisions:

| Range | Name | Meaning in practice |
|---|---|---|
| 0–1023 | Well-known | Historically needed privilege to bind. 22, 53, 80, 443 |
| 1024–49151 | Registered | Assigned to applications by convention. 3306, 5432, 6379 |
| 49152–65535 | Dynamic | Reserved for ephemeral use by the standard |

Linux ignores the last row and uses `32768–60999` for ephemeral ports by
default. That is worth knowing because the ranges overlap: a service listening
on 40000 can find that port already taken by an outbound connection.

:::objective{id=OBJ-A03.2.3}
Distinguish binding to a loopback address from binding to all addresses, and
predict who can connect in each case.
:::

## Binding claims an address as well as a port

`bind()` takes both, and the address is the part people forget:

```bash
nc -l 127.0.0.1 9000    # only this machine can connect
nc -l 0.0.0.0   9000    # every address this machine has
nc -l 10.0.1.5  9000    # that one address only
```

The kernel matches an incoming packet against the socket's *full* address. A
packet for `10.0.1.5:9000` does not match a socket bound to `127.0.0.1:9000`,
so nothing is listening as far as that packet is concerned and the kernel sends
a reset — which the client reports as connection refused.

`0.0.0.0` is the wildcard: every address the machine currently has, and any it
gains later. That is why it is the usual choice for a service that should be
reachable, and why binding a *specific* address is subtly fragile — an address
added by DHCP or a second interface after start-up will not be served.

:::warning
Binding to `127.0.0.1` is the *safe* default, and that is exactly why it causes
so much trouble. Development servers, database defaults and many frameworks
choose it deliberately so that a service on a laptop is not exposed to the
coffee shop. The setting then survives into a deployment where it is wrong, and
the failure appears only from another machine — never in local testing, never
in a unit test, and never in the logs.
:::

## What `ss` shows, column by column

```text
State  Recv-Q Send-Q  Local Address:Port  Peer Address:Port  Process
LISTEN 0      1           127.0.0.1:9000        0.0.0.0:*    users:(("nc",pid=10,fd=3))
ESTAB  0      0           127.0.0.1:9000    127.0.0.1:33192
```

- **State** — LISTEN has no peer; ESTAB has a full four-tuple.
- **Local Address:Port** — what the socket bound. `0.0.0.0` means every address.
- **Peer Address:Port** — `0.0.0.0:*` on a listening socket means "anyone".
- **Recv-Q / Send-Q** — bytes queued, *except* on a listening socket, where
  `Recv-Q` is connections waiting to be accepted and `Send-Q` is the backlog
  limit. That reuse of two columns for different meanings catches everyone once.
- **Process** — needs `-p`, and shows only processes you own unless you are
  root.

:::objective{id=OBJ-A03.2.4}
Interpret a connection's four-tuple, and explain how one listening port serves
many simultaneous clients.
:::

## A connection is four numbers, not one port

```text
203.0.113.9:51001 → 10.0.1.5:443
203.0.113.9:51002 → 10.0.1.5:443
198.51.100.4:33771 → 10.0.1.5:443
```

Three connections, one destination port, all distinct — because the kernel
identifies a connection by source address, source port, destination address and
destination port together. Two of these share a source address and differ only
in source port, and that is enough.

So a server does not "run out of port 443". A listening socket accepts a
connection and the kernel creates a *new* socket for it with the full
four-tuple; the listener goes straight back to waiting. The limits on a busy
server are file descriptors, memory and CPU — not ports.

:::objective{id=OBJ-A03.2.5}
Explain where ephemeral ports come from, and what bounds the number of
connections a client can hold open.
:::

## The client's limit, which is not 65535

An outbound connection needs a source port, and the client does not choose one —
the kernel picks from a range:

```bash
cat /proc/sys/net/ipv4/ip_local_port_range     # 32768 60999
```

That is about 28000 ports. The number people quote is "you can only make 65535
connections", and it is wrong in both directions.

**It is smaller than 65535**, because the range is not the whole space.

**And it is per destination, not per client.** The four-tuple only has to be
unique overall, so a source port can be reused for a different destination. A
client can hold 28000 connections to one server *and* 28000 to another at the
same time — the constraint binds per `(destination address, destination port)`
pair.

Which means running out of ephemeral ports is a real failure and a specific one:
it happens when a single client opens tens of thousands of connections to a
single destination, typically because connections are not being reused. The fix
is almost always connection pooling or keep-alive rather than tuning the range.

## The one-sentence version

A port identifies a socket, a bind claims an address as well as a port, and a
connection is four numbers — which is why one listening port serves everybody
and a busy client can still run out of ports to one destination.

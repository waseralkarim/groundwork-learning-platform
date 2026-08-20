---
topic: topic.tcp-and-udp
section: core-concepts
title: What each protocol actually does
order: 2
mode: explain
---

:::objective{id=OBJ-A03.3.1}
Explain what a transport protocol adds above an address and a port, and what IP
alone does not promise.
:::

## IP promises almost nothing

A packet handed to IP may be delivered, or lost when a queue fills; delivered
twice, if something retransmitted; or delivered out of order, if two packets took
different paths. IP reports none of this to the sender.

Everything above it is a response to that. The transport layer's minimum job is
to say *which socket* on the destination machine a packet is for — that is
ports, and it is all UDP adds beyond a checksum. TCP adds the rest.

:::objective{id=OBJ-A03.3.2}
Distinguish what TCP guarantees from what UDP does not, and name the cost of
each guarantee.
:::

## What TCP adds, and what each addition costs

**A connection.** Both ends agree it exists, established by a three-way
handshake — SYN, SYN-ACK, ACK. The cost is a full round trip before any data
moves, and state on both machines for as long as it lasts. On a 50ms link that
is 50ms spent before the first byte, which is why connection reuse matters so
much.

**Ordering.** Bytes arrive in the order they were sent. The cost is
**head-of-line blocking**: if segment 5 is lost, segments 6 through 20 sit in
the receiver's buffer, already arrived, undeliverable, until 5 is retransmitted.
Everything waits for the slowest thing.

**Retransmission.** Unacknowledged data is sent again. The cost is that loss
becomes latency instead of failure — a lossy link makes TCP slow rather than
broken, which is usually what you want and occasionally is not.

**Flow control.** The receiver advertises a window saying how much it can
accept, so a fast sender cannot overwhelm a slow one. The cost is throughput
bounded by the window divided by the round-trip time, which is why
high-bandwidth long-distance transfers need window scaling.

**Congestion control.** The sender slows down when it sees loss, on the
assumption that loss means a queue somewhere filled. The cost is that a link
which drops packets for *other* reasons — a poor wireless signal — is treated as
congested, and TCP backs off when it should not.

UDP has none of these, and therefore none of these costs.

## The stream, and why it has no messages

TCP is a **byte stream**. It has no concept of a message boundary.

```text
sender:   write("HELLO")  write("WORLD")
receiver: read() -> "HELLOWORLD"        # one read
          or    -> "HEL", "LOWORLD"     # three reads
```

Nothing is wrong in either case. TCP promises the bytes and their order and
nothing about how they are grouped, so every protocol built on TCP must define
its own framing: a length prefix, a delimiter, or a terminator. HTTP uses
`Content-Length` or chunked encoding for exactly this reason.

UDP is the opposite. A datagram arrives whole or not at all, and its boundaries
are preserved — one `sendto()` becomes one `recvfrom()`. That is a genuine
advantage for message-shaped work, and the reason DNS, syslog and most metrics
protocols use it.

:::objective{id=OBJ-A03.3.3}
Identify TCP and UDP sockets and their states, and explain why UDP has no LISTEN
state.
:::

## Why `ss` shows UNCONN

:::diagram{src=../diagrams/no-listen-state.mmd caption="TCP has states because a connection exists to be in one. UDP does not"}

```bash
ss -tln     # LISTEN 0 1 127.0.0.1:9000 0.0.0.0:*
ss -uln     # UNCONN 0 0 127.0.0.1:9400 0.0.0.0:*
```

`LISTEN` describes a socket waiting for something to be established. UDP has
nothing to establish, so its bound sockets are simply *unconnected*: they have a
local address and port, no peer, and no history.

The consequences are practical. A TCP server can tell you how many clients it
has and when each connected. A UDP server cannot — it has received some
datagrams from some addresses, and there is no state that says whether any
sender still exists.

:::objective{id=OBJ-A03.3.4}
Explain what "connected" means for a UDP socket, and what it changes about which
datagrams arrive.
:::

## A connected UDP socket, which is a local fiction

`connect()` on a UDP socket sends no packets. It records a peer address locally,
and it does two things:

- The socket may use `send()` instead of `sendto()`, since the destination is
  now fixed.
- **The kernel delivers only datagrams from that peer.** Everything from any
  other address or port is discarded before the application sees it.

That second point is the one that bites. A UDP server that connects its socket
to the first client it hears from — a common convenience, so replies are easy —
silently ignores every other client from then on.

```bash
ss -uan
UNCONN 0 0    127.0.0.1:9400      0.0.0.0:*         # accepts from anyone
ESTAB  0 0    127.0.0.1:9400   127.0.0.1:47326      # only from this peer
```

`ss` reports the connected socket as `ESTAB`, which looks like a TCP connection
and is not one. Nothing was negotiated and the peer has no idea. It is a filter
on the receiving side.

:::warning
This is a real class of production bug and it is hard to see from either end.
The senders succeed — `sendto()` returning means the datagram reached the
kernel, nothing more — and the receiver simply gets fewer messages than it
should. A `ss -uan` showing `ESTAB` with a real peer on what should be a
multi-client service is the whole diagnosis.
:::

## The one-sentence version

IP may lose, duplicate or reorder anything; TCP repairs all of it at the cost of
a round trip, per-connection state and head-of-line blocking; UDP repairs none
of it and preserves message boundaries; and a "connected" UDP socket is a local
filter that silently discards everyone else.

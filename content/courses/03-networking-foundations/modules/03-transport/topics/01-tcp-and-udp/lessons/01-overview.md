---
topic: topic.tcp-and-udp
section: overview
title: Two answers to the same problem
order: 1
mode: explain
---

IP makes one promise, and it is a weak one: it will *try* to deliver a packet to
an address. Packets may be lost, duplicated, delivered out of order, or take
different paths and arrive in the wrong sequence. Nothing tells the sender.

Everything above IP exists to deal with that, and there are exactly two common
answers. TCP repairs all of it and charges you. UDP repairs none of it and
charges nothing.

## The specific things this explains

- Why `ss` shows `LISTEN` for a TCP socket and `UNCONN` for a UDP one
- Why a UDP server can receive a message from one client and then silently
  ignore every other client
- Why a connection to a closed TCP port fails instantly and a UDP one appears to
  succeed
- Why "we are losing about 3% of our metrics" is a sentence you will hear, and
  where the loss actually happens
- Why video calls tolerate loss and file transfers cannot
- Why one lost packet can stall an entire HTTP/2 connection

:::diagram{src=../diagrams/what-tcp-adds.mmd caption="Everything TCP adds, and the fact that all of it costs something"}

:::callback
From **Ports and Sockets**: a connection is identified by a four-tuple and a
bind claims an address as well as a port. That was TCP's world. UDP uses the
same addresses and ports and has no connections at all, which changes what the
socket table can even show you.
:::

## The difference, in one command

```bash
ss -tln          # TCP:  LISTEN 0 1 127.0.0.1:9000 0.0.0.0:*
ss -uln          # UDP:  UNCONN 0 0 127.0.0.1:9400 0.0.0.0:*
```

`LISTEN` means a socket is waiting for connections. `UNCONN` means a socket is
bound to a port and there is no such thing as a connection to wait for.

That is not a cosmetic difference in wording. A TCP server knows how many
clients it has, when each arrived and when each left. A UDP server knows only
that datagrams keep turning up.

:::predict{question="A UDP server receives one message from a client and then never receives anything from any other client, though the senders report success. What happened?"}
The server's socket became *connected*, and everything from a different peer is
now being discarded by the kernel before the application sees it.

UDP has no connections on the wire, but a socket can be connected locally with
`connect()`. That sends nothing at all — it is a purely local act that fixes the
peer address, so the socket may use `send()` instead of `sendto()`, and, more
consequentially, the kernel delivers only datagrams from that peer to it.

Many simple UDP servers do this after the first message so they can reply
conveniently. The result is a server that works perfectly with one client and
silently ignores the rest.

The senders report success because `sendto()` returning is not evidence of
anything. It means the datagram was handed to the kernel. There is no
acknowledgement, no connection, and nothing that could tell the sender its
message was dropped at the far end.

`ss -uan` shows it plainly: a UDP socket that has been connected has a real
peer address instead of a wildcard, and `ss` reports it as `ESTAB` rather than
`UNCONN`. That is the whole diagnosis, and you will produce it deliberately in
the second lab.
:::

## What each protocol costs

| | TCP | UDP |
|---|---|---|
| Setup | A round trip before any data | None. First packet carries data |
| Delivery | Guaranteed, or the connection fails | Best effort. Silence on failure |
| Order | Preserved | Not preserved |
| Boundaries | None — it is a byte stream | Preserved — a datagram arrives whole |
| Fast sender | Flow-controlled | Will overrun the receiver |
| Lost packet | Retransmitted; everything behind it waits | Gone. Nothing waits |
| State | On both ends, per connection | None |

The last two rows are why the choice is not simply "TCP is better". A voice call
would rather drop one 20ms sample than stall for 200ms retransmitting it, and a
DNS query is one small message that is cheaper to repeat than to establish a
connection for.

## How to work through it

Concepts, mechanism, tools, production. Four labs, all of them running real
sockets in your container: see the two socket types side by side and read what
`ss` says about each; make a UDP server lose messages on purpose and then fix
it; watch the kernel's own connection counters move as you succeed and fail; and
finally diagnose a service losing datagrams for three different reasons.

The second lab is the one worth doing carefully. Losing messages silently is
UDP's defining property, and producing it deliberately is the fastest way to
stop being surprised by it.

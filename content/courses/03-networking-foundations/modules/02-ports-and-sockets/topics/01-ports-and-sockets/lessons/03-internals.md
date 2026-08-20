---
topic: topic.ports-and-sockets
section: internals
title: States, queues and the three failures
order: 3
mode: explain
---

:::objective{id=OBJ-A03.2.6}
Trace a TCP connection through its states, and say what a build-up in each state
indicates.
:::

## The states you will actually meet

:::diagram{src=../diagrams/tcp-states.mmd caption="The path a connection takes, and what a pile-up in each state means"}

```bash
ss -tan                      # every TCP socket, with state
ss -tan state established
ss -tan state time-wait | wc -l
ss -s                        # a summary, including the time-wait count
```

| State | Meaning | A build-up means |
|---|---|---|
| **LISTEN** | Waiting for connections | Nothing — this is a server |
| **SYN-SENT** | We sent a SYN, no reply yet | The far end is not answering. Firewall, or down |
| **SYN-RECV** | Handshake half done | A SYN flood, or an application not accepting fast enough |
| **ESTABLISHED** | Open, both ends agreed | Nothing, unless the count is near a limit |
| **FIN-WAIT** | We closed, waiting for them | The peer is slow to close |
| **CLOSE-WAIT** | **They closed, we have not** | **An application bug** — it is not calling `close()` |
| **TIME-WAIT** | We closed first, holding the tuple | Normal on a busy client. Rarely a problem |
| **LAST-ACK** | Closing, waiting for the final ack | Usually transient |

Two of those rows are worth the whole table.

**TIME-WAIT is normal and people try to eliminate it.** Whichever side closes
first holds the four-tuple for about 60 seconds — twice the maximum segment
lifetime — so that a delayed duplicate packet from the old connection cannot be
mistaken for part of a new one using the same tuple. Thousands of them on a busy
client is expected. The internet is full of advice to enable
`tcp_tw_recycle` to reduce them; that option was removed from Linux because it
broke connections from behind NAT, and reaching for it is a reliable sign of a
misdiagnosis.

**CLOSE-WAIT is the opposite: always a bug, and always yours.** The peer sent a
FIN and the kernel is waiting for the local application to call `close()`. The
kernel cannot proceed without it and there is no timeout. A count that only ever
goes up means a file descriptor leak, and the service will eventually run out of
descriptors and stop accepting anything.

## The queues behind a listening socket

There are two, and confusing them is common:

```text
SYN arrives ──▶ [ SYN queue ]  ──handshake completes──▶ [ accept queue ] ──▶ accept()
                tcp_max_syn_backlog                      backlog, capped by somaxconn
```

```bash
cat /proc/sys/net/ipv4/tcp_max_syn_backlog   # 1024 — half-open connections
cat /proc/sys/net/core/somaxconn             # 4096 — ceiling on the accept queue
ss -tln                                      # Send-Q on a LISTEN row is the backlog
```

The **accept queue** holds completed connections the application has not yet
accepted. Its size is the `backlog` argument the application passed to
`listen()`, capped by `somaxconn`. When it fills, new connections are dropped —
silently by default, which is why the symptom is a client timeout with a server
that looks healthy.

That silent drop has a counter:

```bash
netstat -s | grep -i 'listen queue'
# or
nstat -az TcpExtListenOverflows TcpExtListenDrops
```

A rising `ListenOverflows` means the application is not calling `accept()` fast
enough. Raising the backlog buys queueing, not throughput — if the application
is the bottleneck, a longer queue converts refusals into slow responses and
nothing more.

:::objective{id=OBJ-A03.2.7}
Distinguish connection refused, timeout and connection reset, and say what each
one proves about the path.
:::

## Three failures, three diagnoses

| Symptom | What happened | What it proves |
|---|---|---|
| **Connection refused** | The machine replied with a TCP reset | The packet arrived and was answered. **The network works.** Nothing is bound to that address and port |
| **Connection timed out** | Nothing came back at all | Ambiguous. A firewall dropping silently, a wrong route, or a host that is down |
| **Connection reset by peer** | An established connection was torn down | It worked and then stopped. The application crashed, a proxy timed out, or a middlebox intervened |
| **No route to host** | ARP for the next hop failed | The routing decision was made and the next hop did not answer |

The distinction that saves the most time is the first against the second.
**Refused is good news**: routing works, the host is up, no firewall dropped it,
and the fault is a binding or a process that is not running. **Timeout is bad
news** precisely because it eliminates nothing.

The timing is part of the evidence too. A refusal comes back in milliseconds; a
timeout takes seconds because the client retransmits its SYN before giving up —
`tcp_syn_retries`, six by default, which is why a dead host takes over two
minutes to fail rather than failing instantly.

## Privileged ports, and why containers changed

Binding a port below 1024 historically required root or `CAP_NET_BIND_SERVICE`.
That is now a tunable:

```bash
cat /proc/sys/net/ipv4/ip_unprivileged_port_start   # 1024 traditionally, 0 in many containers
```

Docker sets it to 0 in recent versions, so an unprivileged process in a
container can bind port 80. That is a real improvement — the old options were to
run as root, grant a capability, or run on 8080 and translate — and it is worth
checking rather than assuming, because it explains why the same image behaves
differently on two hosts.

:::callback
From **User Space and the Kernel**: capabilities are what the kernel checks
rather than your uid, and `CAP_NET_BIND_SERVICE` is the one that governs low
ports. `ip_unprivileged_port_start` moves the line the capability is checked
against, which is why a container can now do without it.
:::

## The one-sentence version

Connections move through states you can read live, `CLOSE-WAIT` is your bug and
`TIME-WAIT` is not, a listening socket has two queues and the second one drops
silently, and refused-versus-timeout is the most informative distinction in
network debugging.

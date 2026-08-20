---
topic: topic.tcp-and-udp
section: internals
title: Counters, refusals, and where datagrams die
order: 3
mode: explain
---

:::objective{id=OBJ-A03.3.5}
Interpret the kernel's TCP and UDP counters, and relate them to the outcomes of
individual connection attempts.
:::

## The kernel counts every outcome

```bash
grep -A1 '^Tcp:' /proc/net/snmp
grep -A1 '^Udp:' /proc/net/snmp
nstat -az | grep -E 'ActiveOpens|PassiveOpens|AttemptFails|OutRsts'
```

The TCP fields worth knowing:

| Counter | Meaning |
|---|---|
| `ActiveOpens` | Connections **this machine initiated** |
| `PassiveOpens` | Connections **this machine accepted** |
| `AttemptFails` | Outbound attempts that failed |
| `EstabResets` | Established connections torn down by a reset |
| `CurrEstab` | Currently established, right now |
| `RetransSegs` | Segments retransmitted |
| `OutRsts` | Resets **this machine sent** |

They compose, and the arithmetic is exact. Three successful outbound
connections and one to a closed port produce:

```text
ActiveOpens  4      # all four attempts
AttemptFails 1      # the one that failed
PassiveOpens 3      # the three the listener accepted
OutRsts      1      # the reset we sent back to ourselves
```

`ActiveOpens − AttemptFails = PassiveOpens` when both ends are the same machine,
which is a satisfying check that you are reading them correctly.

Two are worth putting on a dashboard. `RetransSegs` as a proportion of `OutSegs`
is a genuine network-quality signal — a rising rate means the path is losing
packets, and it is one of the few numbers that distinguishes "the network is
bad" from "the application is slow". `OutRsts` rising on a server usually means
connections to ports with nothing bound: a scanner, or a client with stale
configuration.

The UDP fields are shorter because there is less to count:

| Counter | Meaning |
|---|---|
| `InDatagrams` / `OutDatagrams` | Received and sent |
| `NoPorts` | Arrived at a port with **nothing bound** |
| `RcvbufErrors` | **Dropped because the receive buffer was full** |
| `InErrors` | Malformed, bad checksum, other errors |

`RcvbufErrors` is the important one and it is almost never watched. It is where
"we seem to be losing metrics" actually lives.

:::objective{id=OBJ-A03.3.6}
Distinguish how TCP and UDP report a port with nothing bound, and say what the
sender learns in each case.
:::

## How each protocol says "nothing is here"

:::diagram{src=../diagrams/how-each-refuses.mmd caption="Both notice. Only one of them tells the sender"}

**TCP**: the kernel replies with a RST. The sender's `connect()` fails
immediately with "connection refused", and both machines count it —
`AttemptFails` on the client, `OutRsts` on the server. The sender knows, in
milliseconds, with certainty.

**UDP**: the kernel counts `NoPorts` and may send an ICMP port-unreachable
message. But `sendto()` has already returned success — it returned when the
datagram was handed to the kernel, long before anything was delivered — so there
is nothing to report the failure *to*. An unconnected socket usually never sees
the ICMP at all.

```bash
nc -z -w 2 127.0.0.1 9999           # TCP: fails at once, exit 1
printf 'x' | nc -u -w 1 127.0.0.1 9999   # UDP: succeeds. Nothing was listening
```

That asymmetry is the practical difference between the two protocols, and it is
worth stating bluntly: **a successful UDP send is not evidence of anything.** It
means the kernel accepted the datagram. Whether anything received it is not
knowable from the sending side without the application layer building its own
acknowledgement — which is what every reliable UDP protocol ends up doing.

## Where datagrams actually die

Four places, roughly in order of how often they are the cause:

**The receiver's buffer filled.** The application was not reading fast enough,
the socket's receive buffer overflowed, and the kernel dropped what would not
fit. Counted in `RcvbufErrors`, invisible to the sender, and the usual cause of
steady low-percentage loss.

```bash
ss -uanm                              # -m shows buffer sizes and usage
cat /proc/sys/net/core/rmem_max       # the ceiling an application may ask for
cat /proc/sys/net/core/rmem_default
grep -A1 '^Udp:' /proc/net/snmp       # RcvbufErrors
```

**The socket was connected to somebody else.** Discarded before the application
sees them, and counted nowhere useful.

**Nothing was bound.** `NoPorts`, and the sender is not told.

**The network dropped them.** Which UDP does nothing about, by design.

:::warning{scope=production}
Raising the receive buffer with `SO_RCVBUF` — and `net.core.rmem_max` to permit
it — is the standard first fix for `RcvbufErrors`, and it buys burst tolerance
rather than throughput. If the application is *persistently* slower than the
send rate, a bigger buffer delays the loss and does not prevent it. The fix then
is a faster reader, or fewer messages.
:::

:::objective{id=OBJ-A03.3.7}
Evaluate a protocol choice for a given workload, and state what it gives up.
:::

## Choosing, with the trade named

| Workload | Choice | Why, and what is given up |
|---|---|---|
| Web, APIs, databases | TCP | Correctness matters more than latency. Accept the handshake |
| DNS queries | UDP, TCP fallback | One small message; a handshake would double the cost. Falls back when the answer is too big |
| Metrics, syslog | UDP | High volume, individually worthless, must never block the application. Accepts loss |
| Voice and video | UDP | A late packet is useless; retransmitting a 20ms sample helps nobody |
| File transfer | TCP | Every byte matters and none of them are urgent |
| Service discovery, NTP | UDP | Small, repeatable, cheap to retry at the application layer |

The pattern: **UDP when messages are small, independent, and better lost than
late.** TCP when they are large, ordered, or must not be lost. And where UDP is
chosen but reliability is needed anyway — QUIC, most game protocols — the
application rebuilds acknowledgements and retransmission itself, so that it can
choose *which* things to make reliable rather than having ordering imposed on
everything.

:::callback
From **Ports and Sockets**: `Recv-Q` on a listening TCP socket is the accept
queue, and when it fills the kernel drops connections silently. UDP's
`RcvbufErrors` is the same shape of failure — a queue the application is not
draining fast enough — and it is equally silent. Different protocol, same
lesson: look for the queue.
:::

## The one-sentence version

The kernel counts every connection outcome and every dropped datagram; TCP tells
the sender when a port is closed and UDP does not; and most UDP loss happens in
the receiver's own buffer, silently, where nobody is looking.

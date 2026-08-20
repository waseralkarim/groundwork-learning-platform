---
topic: topic.tcp-and-udp
section: production
title: Where the choice shows up
order: 5
mode: explain
---

## "We are losing about 3% of our metrics"

The most common UDP complaint in infrastructure, and the loss is almost never in
the network.

```bash
awk '/^Udp:/ { n++; if (n==2) print "NoPorts=" $3, "RcvbufErrors=" $6 }' /proc/net/snmp
ss -uanm | grep -A1 :8125
```

The order to check, and what each finding means:

| Finding | What happened | Fix |
|---|---|---|
| `RcvbufErrors` rising | The receiver was too slow; the buffer overflowed | Bigger `SO_RCVBUF`, a faster reader, or fewer messages |
| `NoPorts` rising | Datagrams arriving for a port with nothing bound | The collector is down, or on a different port |
| Socket in `ESTAB` | It is connected to one peer and ignoring everyone else | Fix the server; do not connect the socket |
| None of the above | It really is the network | Now go and look at the network |

`RcvbufErrors` is the answer most of the time, and the shape gives it away:
loss that is proportional to load, steady, and worse during bursts. Genuine
network loss is usually not so tidily correlated with your own traffic.

Raising the buffer is the right first move and it buys *burst tolerance*:

```bash
sysctl -w net.core.rmem_max=16777216      # permit applications to ask for more
# and the application must actually request it with SO_RCVBUF
```

Both halves are required. Raising `rmem_max` alone changes nothing if the
application never asks. And if the reader is *persistently* slower than the send
rate, a bigger buffer postpones the loss rather than preventing it — at that
point the answer is a faster reader, sampling, or aggregation at the source.

## Health checks over UDP do not work

A TCP health check connects, and a successful connection proves something is
listening. There is no UDP equivalent:

```bash
nc -u -z -w 1 10.0.1.5 8125; echo $?     # almost always 0, whatever is there
```

The send succeeds because the kernel accepted the datagram. Nothing on the far
side is required to exist.

So a UDP service has to be checked at the application layer — send a request the
service is required to answer, and wait for the answer. DNS is checkable because
a query has a reply. StatsD is not, because nothing ever replies, which is why
UDP metrics pipelines are so often broken for weeks without anyone noticing.

The practical consequence in Kubernetes: a `readinessProbe` cannot use UDP, and
a UDP Service will happily route traffic to a pod that is not listening. Expose
a small HTTP endpoint from the same process and probe that instead.

## Connection reuse, and why the handshake matters

Every new TCP connection costs a round trip before any data moves, and TLS adds
one or two more. On a 50ms path that is 50ms — or 150ms with TLS — spent
achieving nothing, per connection.

```bash
ss -tan state time-wait | wc -l              # a proxy churning connections
nstat -az | grep -E 'ActiveOpens|CurrEstab'  # opens per second vs concurrent
```

`ActiveOpens` climbing rapidly while `CurrEstab` stays low means connections are
being created and destroyed constantly rather than reused — the signature of a
client with keep-alive disabled or a pool that is too small. Fixing it removes
latency, CPU, and the TIME-WAIT accumulation, all at once.

:::predict{question="A team moves a metrics pipeline from UDP to TCP to stop losing datagrams. What is likely to happen?"}
They stop losing metrics and start having outages.

UDP's defining property is that it never blocks the application. `sendto()`
hands the datagram to the kernel and returns; if the collector is slow, absent,
or overwhelmed, the datagrams are dropped and the application carries on at full
speed. Losing metrics is the *failure mode being chosen* — it is a deliberate
trade, and it keeps a monitoring problem from becoming a production one.

TCP removes the loss and replaces it with backpressure. If the collector slows
down, its receive window shrinks; the sender's buffer fills; and then `write()`
blocks, or the queue grows without bound, or the application starts allocating
until it is OOM-killed. A monitoring outage becomes an application outage,
which is a much worse failure.

If loss genuinely matters, the answers in order: fix the buffer overflow that is
actually causing it, which is usually a receiver that cannot keep up; aggregate
at the source so there are fewer messages; or use TCP **with a bounded queue and
an explicit drop policy**, so the application still never blocks and you have
chosen where the loss happens.

The general rule worth carrying: when a system is designed to shed load,
"fixing" the shedding without fixing the capacity just moves the failure
somewhere less convenient.
:::

## Head-of-line blocking, and why HTTP/3 exists

TCP delivers bytes in order, so a lost segment stalls everything behind it.
For one HTTP/1.1 request per connection that is invisible. For HTTP/2, which
multiplexes many streams over *one* TCP connection, a single lost packet stalls
every stream on it — including ones whose data had already arrived.

HTTP/3 moves to QUIC, which runs over UDP and implements ordering per stream
rather than per connection. That is the whole reason it exists, and it is a good
illustration of the pattern: when TCP's guarantees are too coarse, protocols
move to UDP and rebuild the parts they want.

## What to alert on

```promql
rate(node_netstat_Udp_RcvbufErrors[5m]) > 0       # the receiver is too slow
rate(node_netstat_Udp_NoPorts[5m]) > 0            # nothing bound where traffic arrives
rate(node_netstat_Tcp_RetransSegs[5m])
  / rate(node_netstat_Tcp_OutSegs[5m]) > 0.02     # genuine network loss
rate(node_netstat_Tcp_AttemptFails[5m])           # outbound connections failing
```

`RetransSegs` as a proportion of `OutSegs` is one of the few metrics that
genuinely distinguishes a network problem from an application one. A rising
ratio means the path is losing packets; a flat one means it is not, whatever
anybody is claiming in the incident channel.

## The five things worth remembering

1. A successful UDP send proves the kernel accepted the datagram and nothing
   else.
2. `ss` shows UNCONN for UDP because there is no connection to be in a state
   about — and `ESTAB` on a UDP socket means it is ignoring everyone else.
3. Most UDP loss is `RcvbufErrors` on the receiver, not the network.
4. UDP cannot be health-checked at the transport layer; it needs an
   application-level request and reply.
5. Switching a load-shedding path to TCP moves the failure into your
   application.

:::checkpoint
1. What are the four places a datagram can die, and which is most common?
2. Why can a readiness probe not use UDP?
3. What does `ActiveOpens` rising while `CurrEstab` stays flat tell you?
4. Why does HTTP/2 suffer from one lost packet more than HTTP/1.1 did?
:::

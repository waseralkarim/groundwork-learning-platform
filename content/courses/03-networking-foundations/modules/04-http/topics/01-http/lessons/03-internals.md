---
topic: topic.http
section: internals
title: Framing, keep-alive, and where the time goes
order: 3
mode: explain
---

:::objective{id=OBJ-A03.4.4}
Explain the three ways a client can know where a response body ends, and what
happens when the framing is wrong.
:::

## Three ways to end a body

TCP gives a byte stream with no boundaries, so HTTP has to say where a message
stops. There are exactly three mechanisms.

**`Content-Length`.** Read exactly that many bytes.

```text
HTTP/1.1 200 OK
Content-Length: 5

hello
```

Simple, and it requires knowing the size before sending the first byte — which
means buffering the whole response, or knowing the file size in advance.

**`Transfer-Encoding: chunked`.** A sequence of size-prefixed chunks, ending
with a chunk of size zero:

```text
HTTP/1.1 200 OK
Transfer-Encoding: chunked

5
hello
6
 world
0

```

Each size is in hexadecimal, on its own line, followed by that many bytes. This
is how a response can begin before its length is known — streamed output, a
generated report, a slow database query rendered as it arrives.

**Neither.** Read until the connection closes. This is HTTP/1.0 behaviour and it
has a serious flaw: a truncated response is indistinguishable from a complete
one, because both end with a closed connection. It also makes keep-alive
impossible, since the close *is* the delimiter.

## What wrong framing does

Not an error. Exactly what it was told:

| Fault | Client behaviour |
|---|---|
| `Content-Length` too **large** | Waits for bytes that never come, until its own timeout |
| `Content-Length` too **small** | Stops early; the remaining bytes are read as the start of the *next* response |
| Chunked, missing final `0` chunk | Waits for a terminator that never arrives |
| Both `Content-Length` and chunked | Ambiguous — a known request-smuggling vector, and rejected by careful proxies |

The second is the most dangerous, and worth dwelling on. On a keep-alive
connection the client is reading a stream; if it stops one response short, the
leftover bytes become the beginning of the next one. The failure lands on a
*different request*, often for a different user, and the error is a parse
failure that has nothing to do with the request that caused it.

That is also the shape of **request smuggling**: a front-end proxy and a
back-end server disagreeing about where one message ends and the next begins,
so an attacker can prefix somebody else's request. It is why the "both headers
present" row is a security matter rather than a tidiness one.

:::objective{id=OBJ-A03.4.7}
Explain what keep-alive changes, and why connection reuse dominates HTTP
performance.
:::

## Keep-alive

In HTTP/1.1 the connection stays open by default and carries request after
request. `Connection: close` on either side ends it after the current exchange.

The arithmetic is what makes it matter. Every new connection costs a TCP
handshake — one round trip — plus a TLS handshake if it is HTTPS, which is one
or two more. On a 50ms path:

```text
without keep-alive:  50ms TCP + 100ms TLS + 50ms request = 200ms per request
with keep-alive:                              50ms request =  50ms per request
```

Four times the latency, for identical work. It is usually the largest single
performance property of an HTTP client, and it is almost always a configuration
default rather than a code change.

```bash
ss -tan state time-wait | wc -l              # churn leaves these behind
nstat -az | grep -E 'ActiveOpens|CurrEstab'  # opens/s versus concurrent
```

`ActiveOpens` climbing fast while `CurrEstab` stays flat means connections are
being created and destroyed rather than reused — the signature of keep-alive
disabled or a connection pool too small. It also connects to the previous
topic's arithmetic: each closed connection holds a TIME-WAIT tuple for a minute,
and a busy client to a single destination can exhaust its ephemeral ports doing
this.

:::callback
From **Ports and Sockets**: an ephemeral port budget of about 28000 binds *per
destination address and port*. A client hammering one service without keep-alive
is exactly the case that reaches it, and the TIME-WAIT sockets left behind
consume the budget faster than the concurrent connection count suggests.
:::

:::objective{id=OBJ-A03.4.6}
Interpret a client's timing breakdown, and attribute latency to a specific phase
of the request.
:::

## Where the time went

```bash
curl -s -o /dev/null -w '
  dns      %{time_namelookup}
  connect  %{time_connect}
  tls      %{time_appconnect}
  ttfb     %{time_starttransfer}
  total    %{time_total}
' https://api.example.com/health
```

The values are cumulative from the start, so the phases are the differences:

| Phase | Computed as | A large value means |
|---|---|---|
| DNS | `time_namelookup` | Resolver slow or unreachable |
| TCP | `connect − namelookup` | Network latency, or a saturated accept queue |
| TLS | `appconnect − connect` | Handshake cost — certificate chain, weak crypto |
| **Server** | `starttransfer − appconnect` | **The application is slow.** This is TTFB |
| Transfer | `total − starttransfer` | A large body, or a slow link |

That one command separates "the network is slow" from "the server is slow" from
"DNS is slow", and it takes a second. It is the first thing to run when someone
reports that a service is slow, and it very often ends the investigation.

A worked example: `connect 0.002`, `starttransfer 2.41`, `total 2.43`. The
network is fine — two milliseconds to connect — and the server took two and a
half seconds to produce the first byte. Nothing about the network needs
investigating, and the packet capture somebody was about to take would have
shown nothing.

## The one-sentence version

A body ends by length, by chunk terminator, or by connection close; wrong
framing is obeyed rather than rejected, and lands on the next request; keep-alive
removes one to three round trips per request; and `curl -w` attributes latency to
a phase in one command.

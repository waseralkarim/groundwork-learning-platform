---
topic: topic.http
section: overview
title: It is just text, and almost nobody has looked at it
order: 1
mode: explain
---

Every service you operate speaks HTTP. Health checks are HTTP. Ingress rules
route on HTTP. Your metrics are scraped over HTTP, your dashboards are HTTP,
and most of your incidents are described in status codes.

And almost nobody has seen one. HTTP is reached through a library, in a language
that hides it, and when something goes wrong the evidence is a stack trace
rather than the exchange.

It is text. You can write one by hand, and in this topic you will.

## The specific things this explains

- Why a request hangs forever instead of failing, and whose fault that is
- Why `Content-Length` being wrong is worse than being absent
- Why one server can serve two hundred different sites on one address
- Why a 301 is dangerous and a 302 is not
- Why the difference between 4xx and 5xx decides your retry policy
- Why `curl` timing is the fastest way to attribute latency

## What is actually on the wire

Here is a complete request, captured from `curl`, with the line endings made
visible:

:::terminal{title="GET /path?q=1, exactly as it arrived"}
$ cat -A /tmp/request
GET /path?q=1 HTTP/1.1^M$
Host: 127.0.0.1:8080^M$
User-Agent: curl/8.14.1^M$
Accept: */*^M$
^M$
:::

`^M$` is a carriage return followed by a line feed. Every line ends with both,
and the last line is *empty* — a bare CRLF that says "the headers are finished".

That blank line is load-bearing. A server reads headers until it sees CRLF CRLF,
and a proxy or client that emits bare line feeds instead of CRLF will be
misparsed by something eventually.

:::diagram{src=../diagrams/request-response.mmd caption="Four parts each way, and the blank line is one of them"}

:::callback
From **TCP and UDP**: TCP is a byte stream with no message boundaries — what you
write in three calls may arrive in one read. So every protocol on TCP must
define its own framing, and HTTP's is exactly this: CRLF CRLF ends the headers,
and a header then says how long the body is. When that framing is wrong, the
consequences are this topic's most instructive lab.
:::

## The question that turns out to matter most

A response arrives. The client has the headers. How does it know when the body
has finished?

:::predict{question="A server sends `Content-Length: 100` and then only 5 bytes of body. What does the client do?"}
It waits. Then it keeps waiting.

`Content-Length: 100` is an instruction: read exactly 100 bytes. The client
reads 5, has 95 outstanding, and blocks on the socket waiting for the rest.
Nothing is wrong from its point of view — it was told the body is 100 bytes and
it is doing what it was told.

Eventually the client's own timeout fires, and the error it reports is a
timeout, which points at the network or a slow server. Neither is true. The
server finished responding immediately and lied about the size.

`curl -m 3` shows it precisely: `size_download` is 5, the status is 200, and
`curl` exits 28 — operation timed out — on a response that arrived instantly.

The mirror case is a `Content-Length` that is too *small*: the client stops
early, treats the remaining bytes as the start of the next response on that
keep-alive connection, and produces a parse error that has nothing to do with
the request that actually caused it. That one is worse, because the damage lands
on a different request.

Both are why `Content-Length` being wrong is more dangerous than being absent.
Absent has a defined behaviour — read until the connection closes. Wrong makes
the client confidently do the wrong thing.
:::

:::diagram{src=../diagrams/where-body-ends.mmd caption="Three answers, and one of them fails silently"}

## How to work through it

Concepts, mechanism, tools, production. Four labs, all of them serving real HTTP
from your container with `nc` and fetching it with `curl`: write a response by
hand and read the request that came back; serve status codes and follow a
redirect; break the body framing three ways and watch what each does; and
finally diagnose four broken exchanges from the bytes alone.

By the end, `curl -v` should read like a sentence rather than a wall of arrows.

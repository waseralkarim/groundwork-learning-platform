---
topic: topic.http
section: commands
title: curl as an instrument
order: 4
mode: do
---

:::objective{id=OBJ-A03.4.8}
Diagnose an HTTP failure from the raw exchange rather than from the
application's logs.
:::

## Seeing the exchange

```bash
curl -v http://host/path          # request and response headers
curl -sv http://host/path 2>&1    # quiet the progress meter, keep the trace
curl -I http://host/path          # HEAD — headers only
curl --trace-ascii - http://host/path   # every byte, both directions
```

In `-v` output, `>` is what curl sent and `<` is what came back. `*` lines are
curl's own commentary — DNS, connection reuse, TLS.

`--trace-ascii` is the one to reach for when the headers are not the problem.
It shows the bytes, including the framing, which is where the interesting
failures live.

:::try{lab=http-by-hand run="curl -sv http://127.0.0.1:8080/ 2>&1 | head -20" title="A request, as curl sends it"}
Nothing is listening on 8080 yet — the lab starts a listener first and then has
you read the request it captured, byte for byte, including the line endings.
:::

## Serving one by hand

```bash
printf 'HTTP/1.1 200 OK\r\nContent-Length: 5\r\n\r\nhello' \
  | nc -l 127.0.0.1 8080
```

That is a complete, standards-compliant HTTP server for exactly one request.
Writing responses by hand is the fastest way to understand why a client behaves
as it does — and to reproduce a broken server's behaviour when you need to test
a client against it.

```bash
# capture what the client sent, while replying
printf 'HTTP/1.1 204 No Content\r\n\r\n' \
  | nc -l 127.0.0.1 8080 > /tmp/request
cat -A /tmp/request           # ^M$ marks CR LF
```

`cat -A` is what makes the line endings visible, and they matter: HTTP requires
CRLF, and a bare LF will be tolerated by some parsers and rejected by others.

## Status, timing and redirects

```bash
curl -s -o /dev/null -w '%{http_code}\n' http://host/path
curl -sL -o /dev/null -w '%{num_redirects} %{url_effective}\n' http://host/old
curl -s -o /dev/null -w 'connect=%{time_connect} ttfb=%{time_starttransfer} total=%{time_total}\n' http://host/
```

`-L` follows redirects; without it you see the 301 itself, which is usually what
you want when debugging. `%{num_redirects}` and `%{url_effective}` tell you how
many hops and where it ended — a redirect loop shows up as curl stopping at its
maximum with the same URL repeating.

`-w` is the timing instrument from the previous lesson, and it is worth putting
in a shell function you can type without thinking.

:::try{lab=where-does-the-body-end run="curl -s -m 3 -o /dev/null -w 'code=%{http_code} size=%{size_download}\n' http://127.0.0.1:8105/" title="A response that lies about its length"}
The status is 200 and the download stops short, and curl exits 28 — timed out —
on a response that arrived instantly. The lab builds that server in one line.
:::

## Headers, methods and bodies

```bash
curl -H 'Host: shop.example.com' http://10.0.1.5/        # test an ingress rule by IP
curl -H 'Authorization: Bearer TOKEN' https://api/orders
curl -X POST -H 'Content-Type: application/json' -d '{"a":1}' https://api/orders
curl --resolve api.example.com:443:10.0.1.5 https://api.example.com/   # right Host, chosen IP
```

`--resolve` is the one worth remembering. It sends the correct `Host` *and* the
correct TLS SNI while connecting to an address you choose — which is how you
test one backend behind a load balancer, or a new deployment before DNS moves.
`-H 'Host: …'` alone does not fix SNI, so it fails on HTTPS.

## When it hangs

```bash
curl -m 5 http://host/path                    # always bound the wait
curl -sv -m 5 http://host/path 2>&1 | tail -20
ss -tan | grep :80                            # is the connection even established?
```

A hang has three shapes and they are distinguishable:

- **No connection** — stuck at `Trying …`. That is TCP, not HTTP: routing, a
  firewall, or nothing listening.
- **Connected, no response** — the request was sent and nothing came back. The
  server accepted and is not answering: a full accept queue, a blocked
  application, or a slow upstream.
- **Response started, never finished** — headers arrived and the body did not.
  Almost always framing: a `Content-Length` larger than the body, or chunked
  encoding with no terminating chunk.

The third is the one people misdiagnose as a network problem, because "it timed
out" sounds like one.

:::checkpoint
1. In `curl -v` output, what do `>`, `<` and `*` mean?
2. How do you test an ingress rule when you only have the backend's IP address?
3. Which timing value isolates the server's own processing time?
4. What are the three shapes of a hang, and which one is a framing bug?
:::

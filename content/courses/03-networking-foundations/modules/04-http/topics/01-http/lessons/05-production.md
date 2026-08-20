---
topic: topic.http
section: production
title: Status codes as an operational signal
order: 5
mode: explain
---

## The 4xx/5xx split decides what you do

It is the most useful distinction in operating HTTP services, and dashboards
routinely blur it into "error rate".

**4xx is the client's fault**, and repeating the request will fail identically.
A rising 4xx rate is a client population doing something wrong — a bad
deployment of a caller, an expired credential, a scanner probing paths — and
retrying is wasted work. It usually does not deserve a page.

**5xx is yours**, and the same request might succeed later. It deserves an alert
and it deserves retries.

Two exceptions worth knowing, because both are 4xx and both are yours:

- **401 spiking** usually means a credential expired or a token issuer broke,
  and the clients are behaving correctly.
- **429 spiking** means your own rate limits are engaging. That is either the
  limit doing its job or being set wrong, and it is the one 4xx that says
  something about capacity.

```promql
sum by (status) (rate(http_requests_total[5m]))
sum(rate(http_requests_total{status=~"5.."}[5m]))
  / sum(rate(http_requests_total[5m]))          # the ratio that should page
```

Alert on the 5xx *ratio* rather than the count — a count scales with traffic and
produces alerts that get muted at 3am for reasons nobody remembers.

## 502, 503 and 504 name where the failure was

All three come from a proxy, not from your application, and they are three
different diagnoses:

| Code | What the proxy is saying | In a cluster |
|---|---|---|
| **502** | I reached an upstream and it refused, or sent something I could not parse | The pod is up and not serving, or is crashing on accept |
| **503** | I had nowhere to send it | No endpoints — every pod failing readiness, or the selector matches nothing |
| **504** | An upstream accepted and did not answer in time | The application is slow, or hung |

That table turns a status code into a first hypothesis before any logs are read.
502 and 504 point at the application; 503 points at readiness or service
configuration. And in all three cases the application's own logs may be silent,
because in the 503 case it never received the request at all.

:::warning{scope=production}
Retry policy interacts with the method. Retrying a timed-out `POST` may create a
second order, because a timeout does not say whether the request was processed —
only that no answer arrived. Retries should be limited to idempotent methods
unless the API provides an idempotency key. A service mesh or load balancer
configured to retry everything on 5xx is a duplicate-charge incident waiting for
its first slow afternoon.
:::

## Health checks are HTTP requests, and they fail like HTTP requests

A readiness probe is a `GET` with a timeout. Everything in this topic applies:

- A probe with **no timeout shorter than the interval** stacks up if the
  application is slow, and the probe traffic itself becomes load.
- A probe that returns 200 as soon as the HTTP server is listening tests
  nothing. It should check the things the service needs — database, cache,
  leader election.
- A probe hitting `127.0.0.1` inside the pod tests loopback rather than the
  path real traffic uses, so a service bound to loopback passes and serves
  nobody.
- A probe on a **liveness** endpoint that checks a *dependency* restarts every
  replica during that dependency's incident, turning degradation into an outage.

The last one is the most expensive mistake in the list, and it is made by
copying the readiness endpoint into the liveness field.

:::predict{question="A service returns 200 for every health check and users get 502s. What is happening?"}
The probe and the users are not testing the same path.

The likeliest cause is a probe that checks something narrower than real traffic.
It hits `/healthz`, which returns a constant, while real requests go through
routing, authentication, a database call and serialisation — any of which can be
broken while `/healthz` is fine.

The second likeliest is a binding or address difference. A probe against
`127.0.0.1` inside the pod succeeds when the process is bound to loopback and
real traffic, arriving at the pod IP, is refused — and refused connections
become 502 at the proxy.

The third is timing. A 502 means the proxy reached an upstream and got a refusal
or an unparseable answer, so it happens *per request* — the process may be
crashing and restarting between probes, healthy each time the probe lands and
absent when a request arrives. Restart counts and the proxy's error log
timestamps distinguish that quickly.

What settles it in about a minute is making the probe's request yourself, from
where the proxy is, with the same `Host` header, and comparing it against
`/healthz`:

```bash
curl -sv -m 5 -H 'Host: api.example.com' http://<pod-ip>:8080/healthz
curl -sv -m 5 -H 'Host: api.example.com' http://<pod-ip>:8080/orders/42
```

If the first works and the second does not, the probe is too shallow — which is
a check that needs deepening rather than a network to investigate.
:::

## Reading a slow service

```bash
curl -s -o /dev/null -w 'connect=%{time_connect} tls=%{time_appconnect} ttfb=%{time_starttransfer} total=%{time_total}\n' https://api/x
```

The phase with the time in it is the phase to investigate, and this is the
fastest way to stop three teams looking at three unrelated things:

- Large `connect` — network or a full accept queue on the server.
- Large `tls − connect` — handshake cost. A long certificate chain, or CPU.
- Large `ttfb − appconnect` — **the application**. Nothing else needs
  investigating yet.
- Large `total − ttfb` — a big body or a slow link, not the application's
  thinking time.

Run it from where the problem is reported, not from where it is convenient.

## The five things worth remembering

1. HTTP is text, and the blank line that ends the headers is part of the format.
2. Wrong framing is obeyed, not rejected — and a short `Content-Length` damages
   the *next* request on a keep-alive connection.
3. 4xx will fail again; 5xx might not. That decides retries and alerts.
4. 502/503/504 say where the failure was before you read a log.
5. `curl -w` attributes latency to a phase in one command.

:::checkpoint
1. Which status class should page you, and which usually should not?
2. What does a 503 from an ingress controller suggest about the pods behind it?
3. Why should a liveness probe not check a downstream dependency?
4. Which timing value isolates the application's own processing?
:::

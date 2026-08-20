---
topic: topic.http
section: core-concepts
title: The four parts, twice
order: 2
mode: explain
---

:::objective{id=OBJ-A03.4.1}
Describe the shape of an HTTP request and response, and identify each part in a
raw exchange.
:::

## A request

```text
GET /orders/42?expand=items HTTP/1.1
Host: api.example.com
Authorization: Bearer eyJ…
Accept: application/json

```

Four parts, and the fourth is easy to miss:

1. **The request line** — method, target, version. The target is a path and
   query, not a URL: the hostname is not on this line.
2. **Headers** — `Name: value`, one per line. Names are case-insensitive and
   order does not matter.
3. **A blank line**, ending the headers. Mandatory.
4. **A body**, if the method has one.

## A response

```text
HTTP/1.1 200 OK
Content-Type: application/json
Content-Length: 27

{"id":42,"status":"open"}
```

The same shape. The status line carries a code and a reason phrase, and the
reason phrase is decorative — `HTTP/1.1 200 Fine` is as valid as `200 OK`, and
no client reads it.

## Methods, and the property that matters operationally

| Method | Body | Idempotent | Safe |
|---|---|---|---|
| GET | no | yes | yes |
| HEAD | no | yes | yes |
| PUT | yes | **yes** | no |
| DELETE | no | **yes** | no |
| POST | yes | **no** | no |
| PATCH | yes | no | no |

**Idempotent** means repeating it has the same effect as doing it once, and it
is the property that decides whether a client may retry automatically. `PUT
/orders/42` twice leaves one order; `POST /orders` twice may leave two. That is
why load balancers and clients retry GET and PUT on a timeout and generally do
not retry POST — a timeout does not say whether the request was processed.

**Safe** means it does not change anything, which is why GET may be cached,
prefetched and logged with its full URL. Putting a state change behind a GET —
`GET /orders/42/delete` — breaks all three assumptions at once, and a crawler
or a prefetching browser will eventually find it.

:::objective{id=OBJ-A03.4.2}
Identify the status code classes, and say what each tells a client to do next.
:::

## Status codes, by what they mean for the caller

:::diagram{src=../diagrams/status-classes.mmd caption="The 4xx/5xx split is the one that changes what you do"}

| Code | Meaning | What the caller should do |
|---|---|---|
| 200 | OK | Nothing |
| 201 | Created | Read `Location` for the new resource |
| 204 | No Content | Success; there is no body — do not parse one |
| 301 | Moved Permanently | Update the stored URL. **May be cached forever** |
| 302 / 307 | Found / Temporary Redirect | Follow this time; do not remember it |
| 304 | Not Modified | Use the cached copy |
| 400 | Bad Request | Fix the request. Retrying unchanged cannot help |
| 401 | Unauthorized | Authenticate. It means *unauthenticated* |
| 403 | Forbidden | Authenticated and not allowed. Do not retry |
| 404 | Not Found | The path or resource does not exist |
| 429 | Too Many Requests | Back off. Read `Retry-After` |
| 500 | Internal Server Error | The server broke. A retry may work |
| 502 | Bad Gateway | A proxy could not reach the upstream |
| 503 | Service Unavailable | Temporarily down. `Retry-After` may say when |
| 504 | Gateway Timeout | A proxy waited and gave up |

**The 4xx/5xx distinction is the one to internalise.** 4xx means the request was
wrong and repeating it will fail identically — so retrying is wasted work and
alerting on it usually means alerting on somebody else's bad client. 5xx means
the server failed and the same request might succeed later — so retries are
reasonable and an alert is warranted.

**502, 503 and 504 are proxy answers** and they say where the failure was. 502:
the upstream refused or gave something unparseable. 503: nothing available to
send it to. 504: the upstream accepted and did not answer in time. In a
Kubernetes cluster those three map to no endpoints, a failing readiness probe,
and a slow application respectively — which is a diagnosis before you have read
a single log line.

:::warning
A 301 is close to permanent. Browsers and proxies cache it aggressively and
often indefinitely, so a mistaken 301 keeps redirecting clients long after the
server stops sending it. Use 302 or 307 unless you are certain, and be
especially careful with a redirect that depends on anything conditional.
:::

:::objective{id=OBJ-A03.4.5}
Distinguish the Host header's role from the address the connection was made to.
:::

## Host, and why one address serves hundreds of sites

The connection reaches a machine by address. The `Host` header says which
*site* the request is for:

```text
GET /index.html HTTP/1.1
Host: shop.example.com
```

Same address, same port, same server process — and `Host` decides which
configuration handles it. That is virtual hosting, it is mandatory in HTTP/1.1,
and it is what makes shared hosting and Kubernetes Ingress possible.

The operational consequences show up constantly:

- **Ingress rules match on `Host`.** A request that reaches the right cluster
  with the wrong `Host` gets a 404 from the ingress controller, not from your
  application — and your application logs nothing at all.
- **Testing by IP address bypasses it.** `curl http://10.0.1.5/` sends
  `Host: 10.0.1.5`, matches no rule, and fails in a way that says nothing about
  whether the service works. `curl -H 'Host: shop.example.com' http://10.0.1.5/`
  is the test you meant.
- **TLS has its own version of this** — SNI, sent during the handshake before
  any HTTP exists — which is why a certificate can be wrong even though the
  `Host` header is right.

## The one-sentence version

A request is a request line, headers, a blank line and maybe a body; the status
code's *class* tells the caller what to do; the method's idempotency decides
whether a retry is safe; and `Host` decides which site answers, independently of
which machine was reached.

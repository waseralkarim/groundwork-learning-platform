---
topic: topic.addresses-subnets-and-routes
section: internals
title: The decision every packet triggers
order: 3
mode: explain
---

:::objective{id=OBJ-A03.1.5}
Interpret a routing table, and predict which route the kernel will choose for a
given destination.
:::

## The table, line by line

```bash
ip route
```

```text
default via 10.0.1.1 dev eth0 proto dhcp metric 100
10.0.1.0/24 dev eth0 proto kernel scope link src 10.0.1.5
10.8.0.0/24 dev wg0 scope link
172.17.0.0/16 dev docker0 proto kernel scope link src 172.17.0.1
```

Each line is: **destination**, optionally **via** a gateway, out of an
**interface**, with some metadata.

- **`default`** is `0.0.0.0/0` — every destination. Its prefix length is zero,
  which is what makes it lose to everything else.
- **`via 10.0.1.1`** means "not directly reachable; hand it to this router".
- **`scope link`** with no `via` means the opposite: this network is *directly
  attached*, reachable by ARP with no router involved. The kernel adds these
  automatically when you configure an address, which is what `proto kernel`
  records.
- **`src 10.0.1.5`** is the source address to use when sending on this route,
  which matters on a machine with several addresses.
- **`metric 100`** breaks ties between routes of the *same* prefix length. It
  never overrides a longer prefix.

:::objective{id=OBJ-A03.1.6}
Explain longest-prefix match, and what the default route is for.
:::

## Longest prefix wins, and order is irrelevant

:::diagram{src=../diagrams/the-routing-decision.mmd caption="What happens to a packet before it reaches a wire"}

For a destination, the kernel finds **every** route that matches and picks the
one with the longest prefix — the most specific. Not the first in the list;
routing tables are not firewall rules and their order carries no meaning.

With the table above, a packet for `10.8.0.7`:

| Route | Matches? | Prefix |
|---|---|---|
| `0.0.0.0/0` | yes | 0 |
| `10.0.1.0/24` | no | — |
| `10.8.0.0/24` | **yes** | **24** |
| `172.17.0.0/16` | no | — |

Two routes match and the /24 wins, so the packet goes out `wg0`.

This is why the default route is written as a prefix of length zero rather than
being a special case: it matches everything and loses to anything, so it is the
answer only when nothing more specific exists.

It is also why adding a more specific route is how you override a default —
which is exactly what a VPN client does, and the source of a whole class of
"I connected to the VPN and lost access to X".

## Ask the kernel rather than reasoning about it

```bash
ip route get 10.8.0.7
ip route get 8.8.8.8
ip route get 10.0.1.200
```

```text
10.8.0.7 dev wg0 src 10.8.0.2 uid 1000
8.8.8.8 via 10.0.1.1 dev eth0 src 10.0.1.5 uid 1000
```

`ip route get` runs the actual lookup and reports the outcome: the interface,
the gateway if any, and the source address that would be used. It removes the
step where you read a table and reason incorrectly about it, and it is the first
command to reach for in any reachability question.

When nothing matches at all — not even a default — it says so:

```text
$ ip route get 8.8.8.8
RTNETLINK answers: Network is unreachable
```

That is a distinct failure from a packet that left and got no answer, and the
distinction is the most useful triage step in this topic:

| Symptom | Meaning |
|---|---|
| **Network is unreachable** | No matching route. The packet never left the machine |
| **No route to host** | A route existed; ARP for the next hop got no reply |
| **Connection refused** | The packet arrived and something actively said no |
| **Timeout** | The packet may have arrived. Nothing came back |

The first two are local problems you can fix on this machine. The third means
the network worked perfectly. The fourth is the only genuinely ambiguous one.

:::objective{id=OBJ-A03.1.7}
Explain what NAT does to a packet and what it costs.
:::

## NAT: rewriting the source, and remembering that you did

:::diagram{src=../diagrams/nat.mmd caption="One public address, many private hosts, and a table that has to remember every one"}

A container at `172.17.0.2` sends a packet to a public server. That source
address is private and unroutable, so a reply could never come back. The host
rewrites the source to its own public address and a port it picks, records the
mapping, and forwards it. When the reply arrives it looks up the port, rewrites
the destination back, and delivers it.

Three consequences worth carrying:

**NAT is state.** The mapping table is memory on the router, one entry per
connection, with an idle timeout. Lose it — a reboot, a failover, a conntrack
table filling up — and every connection through it dies at once, because the
replies no longer have anywhere to go.

**Inbound connections do not work by default.** There is no mapping until an
outbound packet creates one, so nothing outside can initiate. Port forwarding —
`-p 8080:80` — is a permanent, manually-created mapping, which is exactly why
publishing a port needs two numbers.

**The server sees the wrong address.** Every client behind one NAT looks like
one address, which breaks per-client rate limiting and IP allow-lists, and is
why `X-Forwarded-For` exists.

:::callback
From **Namespaces**: a network namespace has its own interfaces, addresses and
routing table, and `-p 8080:80` is a forwarding rule between the host's
namespace and the container's rather than an instruction to "open" anything.
That rule is NAT, and this is what it is doing.
:::

## The one-sentence version

Every packet triggers a lookup that finds every matching route and takes the
most specific one; the default route wins only when nothing else matches; and
NAT is a rewrite plus a table that has to remember it.

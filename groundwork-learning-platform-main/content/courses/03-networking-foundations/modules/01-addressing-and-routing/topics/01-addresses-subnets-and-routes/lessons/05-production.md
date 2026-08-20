---
topic: topic.addresses-subnets-and-routes
section: production
title: Where address planning goes wrong
order: 5
mode: explain
---

Nearly every serious networking problem you will meet in infrastructure comes
from one of three things: a range that was too small, two ranges that overlap,
or a route somebody added without realising what it would beat.

## Ranges that were too small

A subnet cannot be resized without renumbering everything in it, and the cost of
that grows with age. So the failure mode is always the same: a range that was
generous in year one and is full in year three, with a hundred things hard-coded
against it.

The arithmetic is worth doing deliberately at the start:

| Block | Hosts | Reasonable for |
|---|---|---|
| /24 | 254 | A small service subnet |
| /22 | 1022 | A subnet you expect to grow |
| /20 | 4094 | A VPC subnet, per availability zone |
| /16 | 65534 | A whole VPC, or a Kubernetes pod CIDR |

Kubernetes is where this bites hardest, because a cluster consumes addresses at
a rate people do not expect. Every pod gets one, the node CIDR is usually a /24
per node — 254 pods, whatever the node can actually run — and the cluster CIDR
has to cover every node's /24 at once. A /16 cluster CIDR gives you 256 nodes,
which sounds like plenty until it is not, and changing it means rebuilding the
cluster.

:::warning{scope=production}
Pick ranges far larger than you need, from parts of `10.0.0.0/8` nobody else is
using. Private address space is free and effectively unlimited; renumbering is
neither. The only real constraint is not colliding with something you might one
day have to connect to.
:::

## Ranges that overlap

Two networks using the same private range cannot be joined. Not "with
difficulty" — the routing is genuinely ambiguous, and there is no configuration
that resolves it. Somebody renumbers, or the connection does not happen.

This arrives in predictable ways: an acquisition, a partner VPN, a second cloud
account, a Kubernetes cluster whose pod CIDR happens to match the corporate
network. `192.168.0.0/16` and `10.0.0.0/16` are the two most contested ranges on
earth because they are the two defaults.

Docker's own defaults are worth knowing for this reason. It allocates bridges
from `172.17.0.0/16` upwards, which is inside `172.16.0.0/12` — a range some
corporate networks also use. A machine whose VPN hands it `172.17.0.0/16` will
find that Docker has already claimed it, and the symptom is that containers can
reach the internet and not the office.

## Routes somebody added

A VPN client adds routes. Which routes it adds is the difference between a
useful VPN and a support ticket.

```text
# Before
default via 192.168.1.1 dev wlan0
192.168.1.0/24 dev wlan0 scope link

# After connecting, "split tunnel"
default via 192.168.1.1 dev wlan0
192.168.1.0/24 dev wlan0 scope link
10.0.0.0/8 via 10.8.0.1 dev wg0            <- corporate traffic only

# After connecting, "full tunnel"
0.0.0.0/1 via 10.8.0.1 dev wg0             <- these two beat the default
128.0.0.0/1 via 10.8.0.1 dev wg0              because they are longer
default via 192.168.1.1 dev wlan0
```

The full-tunnel trick is worth recognising because it looks like nonsense until
you know the rule. `0.0.0.0/1` and `128.0.0.0/1` between them cover every
address, and both have a prefix length of 1 — longer than the default route's 0.
So they win, everything goes over the tunnel, and the original default route is
left untouched for when the VPN disconnects.

:::predict{question="You connect to the corporate VPN and your application immediately loses its database connection. The database is at 10.24.3.10. Why?"}
The VPN added a route for `10.0.0.0/8`, and your database is inside it.

Before connecting, `10.24.3.10` matched only the default route and went out via
the local gateway to wherever it actually lives — a cloud VPC, a peered network,
a NAT gateway. The VPN's route is a /8, which is very much longer than /0, so
every address in `10.0.0.0/8` now goes down the tunnel instead.

The corporate network on the other end has never heard of `10.24.3.10`. The
packets arrive there and are dropped, and the symptom is a connection that
worked ten seconds ago timing out.

`ip route get 10.24.3.10` before and after connecting shows it in one line each
way, which is why that command is the first thing to run rather than the last.

The fixes are all about specificity. Add a more specific route for the database
— a /32 via the original gateway beats the VPN's /8. Or ask for a VPN profile
that pushes only the ranges it actually serves. The general lesson is that a VPN
client rewrites your routing table, and "I connected to the VPN and X broke" is
almost always a route that now matches more specifically than the one X used to
use.
:::

## Reading somebody else's network

When you inherit a machine and need to understand its networking:

```bash
ip -br addr                      # what addresses, on what interfaces
ip route                         # what it knows how to reach
ip route get <the thing that matters>   # what it would actually do
ip neigh                         # who it has been talking to directly
```

Four commands, thirty seconds, and they answer more than any diagram. The
diagram describes what somebody intended; the routing table describes what the
machine will do.

Things worth noticing while you are there:

- **A `169.254.x.x` address** means DHCP failed and the interface gave up. Every
  other symptom on that machine is downstream of this.
- **Two default routes** with different metrics means failover — or a mistake,
  and which one is a real question.
- **A `/32` route to a single host** is almost always somebody working around a
  problem. It is worth finding out which.
- **An MTU below 1500** means a tunnel somewhere, and a specific failure mode
  where small packets work and large ones hang.

## The five things worth remembering

1. An address without a mask is unusable — the mask decides who is a neighbour.
2. Block size is `2^(32-prefix)`; the network is the address rounded down to a
   multiple of it, and the broadcast is one below the next block.
3. Longest prefix wins, and the order routes are listed in means nothing.
4. Overlapping private ranges cannot be joined, and choosing ranges generously
   at the start is free.
5. `ip route get` answers reachability questions that reading a table only
   invites you to answer wrongly.

:::checkpoint
1. Why does a full-tunnel VPN add `0.0.0.0/1` and `128.0.0.0/1` instead of
   changing the default route?
2. What happens when two networks you need to connect both use `10.0.0.0/16`?
3. How many /24s does a /16 cluster CIDR contain, and why does that number
   matter in Kubernetes?
4. What does an MTU below 1500 usually imply?
:::

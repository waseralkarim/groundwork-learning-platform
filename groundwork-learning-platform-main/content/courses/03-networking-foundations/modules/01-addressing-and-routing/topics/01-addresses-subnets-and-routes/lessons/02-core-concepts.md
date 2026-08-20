---
topic: topic.addresses-subnets-and-routes
section: core-concepts
title: Masks, blocks and the arithmetic
order: 2
mode: explain
---

:::objective{id=OBJ-A03.1.1}
Identify a machine's interfaces, addresses, prefix lengths, MTU and hardware
addresses from the machine itself.
:::

## An address belongs to an interface, not a machine

```bash
ip -o addr           # every address on every interface
ip -o link           # the interfaces themselves: MAC, MTU, state
```

```text
1: lo    inet 127.0.0.1/8 scope host lo
2: eth0  inet 172.24.0.2/16 brd 172.24.255.255 scope global eth0

2: eth0@if4829: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 …
   link/ether 1e:dc:2d:a9:6d:db brd ff:ff:ff:ff:ff:ff
```

Four things worth reading off that:

- **`/16`** — the prefix length. The first 16 bits are the network.
- **`brd 172.24.255.255`** — the broadcast address, which the kernel computed
  from the address and the mask. You can check its arithmetic.
- **`mtu 1500`** — the largest frame this interface will carry. Ordinary
  Ethernet; a VPN or a tunnel will be lower, and that difference causes a
  specific class of failure where small requests work and large ones hang.
- **`eth0@if4829`** — this is one end of a **veth pair**, and `if4829` is the
  interface index of the other end, in another namespace. That is the wire
  between a container and its host, and it is visible from inside.

`lo` at `127.0.0.1/8` is the loopback. The whole of `127.0.0.0/8` is loopback —
sixteen million addresses that all mean "this machine" — which is why Docker can
put its embedded DNS resolver on `127.0.0.11` without colliding with anything.

:::objective{id=OBJ-A03.1.2}
Explain what a subnet mask decides, and why an address without one is not
usable.
:::

## What the mask actually decides

Exactly one thing, and everything else follows from it: **which destinations are
directly reachable, and which need a router.**

When a machine sends a packet it compares the destination with each of its own
interfaces' networks. If the destination is inside one, the machine ARPs for the
destination's MAC address and sends the frame straight to it. If it is not, the
machine sends the frame to a router instead — addressed to the *router's* MAC,
but still carrying the *destination's* IP.

That is why an address with no mask is unusable: the machine cannot tell whether
any given destination is a neighbour.

## The arithmetic

The mask splits 32 bits. Everything you need comes from three numbers:

```text
address   10.0.1.5/26
block size  2^(32-26) = 64 addresses
network     the address rounded *down* to a multiple of 64
broadcast   network + 63
usable      network+1 … broadcast-1        (block size - 2)
```

Worked through: 10.0.1.5 with a /26. The block size is 64, and 5 rounded down to
a multiple of 64 is 0. So:

| | |
|---|---|
| network | 10.0.1.0 |
| broadcast | 10.0.1.63 |
| first usable | 10.0.1.1 |
| last usable | 10.0.1.62 |
| hosts | 62 |

And the same address with a /26 but a last octet of 99: 99 rounded down to a
multiple of 64 is 64, so that block runs 10.0.1.64 – 10.0.1.127, and 10.0.1.5 is
**not on it**. Two addresses in the same /24, both /26, on different networks.

:::objective{id=OBJ-A03.1.3}
Calculate the network address, broadcast address and usable host range of a CIDR
block.
:::

The prefix lengths worth memorising, because they are the ones you will meet:

| Prefix | Mask | Addresses | Hosts | Typical use |
|---|---|---|---|---|
| /32 | 255.255.255.255 | 1 | 1 | A single host, in a rule or a route |
| /30 | 255.255.255.252 | 4 | 2 | A point-to-point link |
| /29 | 255.255.255.248 | 8 | 6 | A tiny subnet |
| /26 | 255.255.255.192 | 64 | 62 | A small subnet |
| /24 | 255.255.255.0 | 256 | 254 | The default mental unit |
| /16 | 255.255.0.0 | 65536 | 65534 | A Docker bridge, a small VPC |
| /8 | 255.0.0.0 | 16777216 | 16777214 | An entire private range |

The pattern to internalise: every step of one in the prefix **halves** the block.
A /25 is half a /24; a /26 is a quarter. Going the other way, a /23 is two /24s.

:::warning
The "minus two" for network and broadcast applies to ordinary subnets and not
everywhere. A /31 has no network or broadcast address by convention and gives
you two usable hosts, which is why point-to-point links often use one. And a
/32 is a single address, used in routes and firewall rules to mean exactly one
host.
:::

:::objective{id=OBJ-A03.1.4}
Distinguish private from public address space, and explain why a container or a
home machine has a private address.
:::

## Private space, and why everything you own is in it

Three blocks are reserved for internal use and are not routed on the public
internet:

| Block | Size | Where you meet it |
|---|---|---|
| `10.0.0.0/8` | 16.7M | Corporate networks, VPCs, Kubernetes pod CIDRs |
| `172.16.0.0/12` | 1M | Docker's default bridges — `172.17.0.0/16` and up |
| `192.168.0.0/16` | 65K | Home routers, almost universally |

Because they are not routed publicly, everyone can use them at once. Your
container is `172.17.0.2`, and so is a container on a machine in another
country, and neither knows about the other.

That reuse is the whole point, and it is also the source of a specific and very
common failure: **two networks that both use `10.0.0.0/16` cannot be joined**.
Merge two companies, connect a VPN, peer two VPCs, and if their private ranges
overlap the routing becomes ambiguous and there is no configuration that fixes
it. Somebody has to renumber.

Worth knowing alongside them: `169.254.0.0/16` is link-local, which is what an
interface assigns itself when DHCP fails — so seeing a `169.254.x.x` address is
a diagnosis in itself. And cloud metadata services live at `169.254.169.254`,
which is why that address appears in so many security discussions.

## The one-sentence version

The prefix length splits an address into network and host, that split decides
which destinations are neighbours and which need a router, and every other
number in this topic — network, broadcast, host count — is arithmetic on it.

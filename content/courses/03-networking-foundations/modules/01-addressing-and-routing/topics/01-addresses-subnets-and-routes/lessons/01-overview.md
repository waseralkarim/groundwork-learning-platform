---
topic: topic.addresses-subnets-and-routes
section: overview
title: The number beside the address is the important one
order: 1
mode: explain
---

`10.0.1.5` tells you almost nothing. It does not say who this machine can reach
directly, which packets need a router, or whether another machine holding
`10.0.1.200` is a neighbour or a stranger.

`10.0.1.5/24` answers all three. The `/24` is where the meaning lives, and every
packet the machine sends triggers a decision based on it.

## The specific things this explains

- Why two machines on the same wire, with addresses that look adjacent, cannot
  reach each other
- Why `/26` gives you 62 hosts rather than 64
- Why a container's address is `172.17.0.2` and so is one on a completely
  different host
- Why "Network is unreachable" and "No route to host" and a timeout are three
  different failures
- What a VPN does to a routing table, and why it can break a database
  connection that was working a minute earlier
- Why NAT is state, and what happens when that state is lost

## The whole idea, in one picture

:::diagram{src=../diagrams/address-and-mask.mmd caption="The mask splits the address into 'which network' and 'which host on it'"}

An address is 32 bits. The prefix length says how many of the leading bits
identify the *network*; the rest identify the *host* within it. Everything else
in this topic follows mechanically:

- All host bits zero is the **network address** — it names the network.
- All host bits one is the **broadcast address** — it reaches every host on it.
- Everything between them is usable, which is why a block of 64 addresses gives
  you 62 hosts.

Change the mask and nothing about the address changes, but everything about its
meaning does.

:::predict{question="Two machines: 10.0.1.5/24 and 10.0.1.200/25. They are on the same physical network. Can they talk?"}
Not reliably, and the failure is asymmetric — which is what makes it maddening
to diagnose.

The first machine has a /24, so it believes its network is `10.0.1.0` to
`10.0.1.255`. `10.0.1.200` is inside that, so it treats the second machine as a
neighbour: ARP for its MAC address, send the frame directly, no router.

The second machine has a /25, so it believes its network is `10.0.1.128` to
`10.0.1.255`. `10.0.1.5` is *outside* it. So when it replies, it does not ARP
for the first machine — it sends the reply to its default gateway instead.

If the gateway is willing to route the packet back onto the same wire, it may
work with an ICMP redirect and some confusion. If it is not, or if there is no
route back, the first machine's packets arrive and the replies vanish.

One host sees requests going out and nothing coming back. The other sees
requests arriving and answers them normally. Both machines are behaving exactly
as configured, and the configuration is wrong on precisely one of them.

The lesson worth carrying: **when a connection works in one direction, suspect
the masks before you suspect anything else.**
:::

## What your own machine says

Every fact in this topic is readable from the machine you are on:

:::terminal{title="A container's own view of the network"}
$ ip -o -4 addr show eth0
2: eth0    inet 172.24.0.2/16 brd 172.24.255.255 scope global eth0

$ ip route
172.24.0.0/16 dev eth0 proto kernel scope link src 172.24.0.2
:::

Two lines, and they contain the address, the mask, the broadcast address, the
subnet, the interface, and the fact that there is **no default route** — which
means anything outside `172.24.0.0/16` is unreachable, and the kernel will say
so in exactly those words.

That is the environment your labs run in, and it is deliberate: an isolated lab
network has no route to anywhere. It makes the difference between "unreachable"
and "refused" and "timed out" something you can produce on purpose.

:::callback
From **Namespaces**: a network namespace has its own interfaces, addresses,
routing table and firewall rules — so a container's `eth0` is genuinely its own,
and two containers can both hold `172.17.0.2` without conflict. This topic is
about what is *inside* one of those namespaces.
:::

## How to work through it

Concepts, mechanism, tools, production. Four labs: read your own interface and
work out what it means; compute network, broadcast and host ranges until the
arithmetic is automatic; predict which route the kernel picks and then ask it;
and diagnose three hosts that cannot talk to each other, for three different
reasons that look identical from a ping.

The arithmetic in the second lab is the single most-used skill in this topic. It
comes up in every firewall rule, every VPC design, every Kubernetes cluster CIDR,
and it is worth being able to do without a calculator.

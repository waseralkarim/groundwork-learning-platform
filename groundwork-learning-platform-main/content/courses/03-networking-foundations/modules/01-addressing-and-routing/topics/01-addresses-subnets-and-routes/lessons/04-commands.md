---
topic: topic.addresses-subnets-and-routes
section: commands
title: Reading addresses and asking about routes
order: 4
mode: do
---

:::objective{id=OBJ-A03.1.8}
Diagnose an unreachable destination as a missing route, a wrong mask or an
overlapping subnet.
:::

## What am I, and where am I?

```bash
ip -o addr                       # every address, every interface
ip -o -4 addr show eth0          # just IPv4 on one interface
ip -o link                       # MAC, MTU, state, veth peer index
ip -br addr                      # the brief form, one line per interface
```

`ip -br addr` is the one to type when you just want to see the shape of a
machine — three columns, no wrapping, and it fits on a screen.

:::try{lab=read-your-address run="ip -o -4 addr show eth0" title="Your own address and mask"}
Read the `/16` and the `brd` value. The broadcast address is not stored
anywhere — the kernel computed it from the address and the prefix, and you can
check its arithmetic.
:::

## Where would a packet go?

```bash
ip route                         # the table
ip route get 10.0.5.7            # the actual lookup, for one destination
ip route get 8.8.8.8 from 10.0.1.5   # as if sent from a particular source
ip -6 route                      # the IPv6 table, which is separate
```

`ip route get` is the single most useful command here. It performs the lookup
the kernel would perform and reports the outcome — interface, gateway, source
address — with no room for you to misread a table.

:::try{lab=which-route-wins run="ip route get 8.8.8.8" title="Ask about a destination you cannot reach"}
This lab network has no default route, so the answer is `Network is
unreachable`. That is a specific failure with a specific meaning: no route
matched, and the packet never left.
:::

## Neighbours, and the layer below

```bash
ip neigh                         # the ARP cache: IP → MAC, and state
ip neigh show dev eth0
```

The ARP cache is how a machine turns "10.0.1.7 is a neighbour" into a frame it
can actually send. An entry in state `REACHABLE` means it has been confirmed
recently; `STALE` means it is being used but not verified; `FAILED` means ARP
got no reply, which is what produces "No route to host".

An empty cache is not a problem — entries are created on demand and expire.

## Counters, when you want to know whether anything moved at all

```bash
ip -s link show eth0             # RX/TX bytes, packets, errors, dropped
cat /proc/net/dev                # the same, for every interface
grep -A1 '^Tcp:' /proc/net/snmp  # protocol counters: opens, resets, retransmits
```

`ip -s link` answers "is this interface doing anything", which is worth
establishing before any deeper investigation. Rising `errors` or `dropped` is a
different problem from a routing mistake, and takes about two seconds to rule
out.

`/proc/net/snmp` is underused. `ActiveOpens` counts connections this machine
initiated, `PassiveOpens` counts ones it accepted, `AttemptFails` counts
connections that could not be established, and `RetransSegs` counts
retransmissions — a rising rate there is a genuine network problem rather than
an application one.

## Subnet arithmetic without a calculator

The block size is `2^(32 - prefix)`, the network address is the address rounded
down to a multiple of it, and the broadcast is the network plus block size minus
one:

```bash
# 10.42.7.99/26
#   block size 2^(32-26) = 64
#   99 rounded down to a multiple of 64 = 64
#   network   10.42.7.64
#   broadcast 10.42.7.127
#   usable    10.42.7.65 – 10.42.7.126   (62 hosts)
```

`ipcalc` and `sipcalc` do this for you where they are installed, and it is worth
being able to do the common prefixes in your head — /24, /25, /26, /30 — because
the moment you need it is usually the moment you have a plain shell.

:::warning
Two different tools mean two different things by "netmask". `ip` and modern
tooling use prefix length (`/26`); older tools, some cloud consoles and most
firewall appliances use dotted masks (`255.255.255.192`). They are the same
information. Wildcard masks — `0.0.0.63`, the bitwise inverse — appear in Cisco
ACLs and in some AWS documentation, and reading one as the other is a
long-standing source of rules that do the opposite of what was intended.
:::

## Triage, in order

```bash
ip -br addr                      # 1. do I have an address, and what mask?
ip route get <destination>       # 2. would a packet even leave, and how?
ip neigh                         # 3. if it is a neighbour, do we know its MAC?
ip -s link show <iface>          # 4. is anything moving, and are there errors?
```

Four commands, and they separate the four failures that all present as "it does
not work":

- No address, or a `169.254.x.x` one — DHCP failed, and nothing else matters yet.
- `Network is unreachable` — no route. Local, and fixable here.
- Neighbour in state `FAILED` — the route exists and the next hop is not
  answering.
- Everything looks right and nothing moves — now it is somebody else's network,
  and you have the evidence to say so.

:::checkpoint
1. Which command performs the actual route lookup rather than showing you a
   table to interpret?
2. What is the difference between "Network is unreachable" and "No route to
   host"?
3. How do you compute the broadcast address of `10.0.1.5/26` in your head?
4. What does a `169.254.x.x` address tell you immediately?
:::

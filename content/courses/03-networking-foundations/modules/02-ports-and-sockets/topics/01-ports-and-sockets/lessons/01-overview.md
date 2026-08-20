---
topic: topic.ports-and-sockets
section: overview
title: The service is running. It is also unreachable.
order: 1
mode: explain
---

Somebody deploys a service. It starts cleanly, its logs say `listening on
:9000`, and `ps` shows it running. From another machine, every connection is
refused.

Nothing is broken. The service bound to `127.0.0.1` instead of `0.0.0.0`, and
those are two different things in a way that no log line will ever mention.

## The specific things this explains

- Why "it works on my machine" is sometimes literally true and still useless
- How one listening port serves ten thousand simultaneous clients
- Why a client can run out of ports, and what the ceiling actually is
- Why thousands of sockets in `TIME-WAIT` are normal and thousands in
  `CLOSE-WAIT` are a bug in your code
- Why "connection refused" is good news and a timeout is not
- Why `-p 8080:80` needs two numbers

:::callback
From **Addresses, Subnets and Routes**: an address gets a packet to a machine,
and the routing decision is how it gets there. This topic is the second half —
once the packet has arrived, which of the hundred processes on that machine is
it for?
:::

## A port is the second half of the delivery

An address identifies an interface. A port identifies which socket on that
machine the packet belongs to. Together they are a *socket address*, and that
pair is what an application binds and a client connects to.

Ports are 16 bits, so 0–65535, and they are per protocol: TCP 53 and UDP 53 are
different sockets that different processes could hold.

## What is running here, right now

```bash
ss -tlnp
```

```text
State  Recv-Q Send-Q  Local Address:Port  Peer Address:Port  Process
LISTEN 0      4096       127.0.0.11:34925       0.0.0.0:*
LISTEN 0      1           127.0.0.1:9000        0.0.0.0:*    users:(("nc",pid=10,fd=3))
LISTEN 0      1             0.0.0.0:9100        0.0.0.0:*    users:(("nc",pid=14,fd=3))
```

Three listening sockets and three different stories. The first is Docker's
embedded DNS resolver, on a loopback address you did not know existed. The
second is reachable only from this machine. The third is reachable from
anywhere that can route to this machine — and the difference between the last
two is the whole of the first paragraph of this lesson.

:::diagram{src=../diagrams/bind-address.mmd caption="Three ways to bind, three different sets of people who can reach you"}

:::predict{question="A service binds 127.0.0.1:9000. You curl it from the same machine and it works. What happens when you curl the machine's own eth0 address on port 9000?"}
Connection refused, immediately.

The socket is bound to `127.0.0.1`, and the kernel matches incoming packets
against the address the socket claimed. A packet arriving for
`10.0.1.5:9000` does not match a socket bound to `127.0.0.1:9000` — so as far as
the kernel is concerned, nothing is listening on that address and port, and it
replies with a TCP reset.

The refusal is the interesting part. "Connection refused" means the packet
arrived and the machine actively answered — so routing worked, no firewall
dropped it, and the host is up. It is one of the most informative errors in
networking, and it points at the *binding* rather than the network.

Contrast that with a timeout, which means the packet may have arrived and
nothing came back at all — a firewall dropping silently, a wrong route, a host
that is down. Same symptom to a user, opposite diagnosis.

The fix is to bind `0.0.0.0` — every address — or the specific address the
service should be reachable on. And it is worth knowing why the wrong default is
so common: binding to loopback is the *safe* choice, so frameworks and
development servers pick it deliberately, and the setting survives into a
deployment where it is wrong.
:::

## One port, many clients

The other half of the topic is how a single listening port serves thousands of
connections at once. It works because a connection is not identified by a port
— it is identified by four numbers:

:::diagram{src=../diagrams/the-four-tuple.mmd caption="Three connections to one port, distinct because the source side differs"}

Source address, source port, destination address, destination port. Two
connections to the same server port are different connections because their
source ports differ, and the kernel demultiplexes on all four.

That is also where the client's limit comes from, and it is not the number
people expect.

## How to work through it

Concepts, mechanism, tools, production. Four labs, three of which run real
sockets in your container: find out what is listening and who owns it; produce
the "works locally, not from outside" failure deliberately and watch it refuse
you; open several connections to one port and read the four-tuples and the TCP
states as they change; and finally diagnose three services that are running and
unreachable for three different reasons.

Everything in this topic is observable with two commands — `ss` and `nc` — and
by the end both should feel like instruments rather than trivia.

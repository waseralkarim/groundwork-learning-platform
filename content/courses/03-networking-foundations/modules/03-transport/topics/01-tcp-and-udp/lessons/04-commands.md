---
topic: topic.tcp-and-udp
section: commands
title: Watching both protocols
order: 4
mode: do
---

:::objective{id=OBJ-A03.3.8}
Diagnose a UDP service that is silently losing messages.
:::

## Seeing the two socket types

```bash
ss -tln          # TCP listeners:  LISTEN
ss -uln          # UDP sockets:    UNCONN
ss -tuln         # both
ss -uan          # every UDP socket, including connected ones
ss -uanm         # add buffer sizes and usage
```

`ss -uan` is the one to reach for when a UDP service is behaving oddly. A socket
showing `ESTAB` with a real peer address is *connected*, and is therefore
ignoring everyone else.

:::try{lab=two-transports run="ss -tuln" title="Both protocols, side by side"}
Note the State column. TCP rows say LISTEN; UDP rows say UNCONN. There is no
LISTEN for UDP because there is nothing to establish.
:::

## Sending and receiving by hand

```bash
nc -l 127.0.0.1 9000                 # TCP listener
nc -u -l 127.0.0.1 9400              # UDP listener — connects to the first sender
nc -u -l -k 127.0.0.1 9400           # UDP listener that keeps accepting from anyone

printf 'hello\n' | nc -w 1 127.0.0.1 9000        # TCP
printf 'hello\n' | nc -u -w 1 127.0.0.1 9400     # UDP
```

The `-k` on the UDP listener is the difference between a server that hears
everybody and one that hears only its first correspondent. It is worth typing
both and watching the result.

```bash
nc -z    -w 2 127.0.0.1 9999; echo $?     # TCP:  1 — refused, immediately
nc -u -z -w 1 127.0.0.1 9999; echo $?     # UDP:  usually 0 — nothing was there
```

That pair is the whole difference in two lines. TCP tells you. UDP does not.

## The counters

```bash
grep -A1 '^Tcp:' /proc/net/snmp
grep -A1 '^Udp:' /proc/net/snmp

# a friendlier form, with deltas since the last call
nstat
nstat -az | grep -E 'ActiveOpens|PassiveOpens|AttemptFails|OutRsts|RetransSegs'
nstat -az | grep -E 'UdpNoPorts|UdpRcvbufErrors|UdpInDatagrams'
```

`/proc/net/snmp` has a header line and a values line for each protocol, in the
same order, which is what makes it awkward to read by eye:

```bash
awk '/^Udp:/ { n++; if (n==2) print "NoPorts=" $3, "RcvbufErrors=" $6 }' /proc/net/snmp
```

Take two samples and subtract. The absolute values grow from boot and mean
nothing on their own.

:::try{lab=counting-connections run="grep -A1 '^Tcp:' /proc/net/snmp" title="Every connection outcome, counted"}
`ActiveOpens` counts connections this machine started and `AttemptFails` counts
the ones that failed. The lab has you move both deliberately and check the
arithmetic.
:::

## Buffers, which is where UDP loss lives

```bash
ss -uanm                              # Recv-Q and the buffer sizes
cat /proc/sys/net/core/rmem_default   # default receive buffer
cat /proc/sys/net/core/rmem_max       # the ceiling an application may request
awk '/^Udp:/ { n++; if (n==2) print "RcvbufErrors=" $6 }' /proc/net/snmp
```

A rising `RcvbufErrors` means datagrams arrived and were thrown away because the
application had not read the previous ones. The sender saw success, the network
was fine, and the loss happened entirely inside the receiving machine.

That is the answer to most "we are losing about N% of our metrics" questions,
and it is invisible unless you look at this counter specifically.

## Triage for a lossy UDP service

```bash
ss -uln | grep :<port>                # 1. is anything bound at all?
ss -uan | grep :<port>                # 2. is the socket connected to one peer?
ss -uanm | grep -A1 :<port>           # 3. is Recv-Q backing up?
awk '/^Udp:/{n++; if(n==2) print}' /proc/net/snmp   # 4. NoPorts? RcvbufErrors?
```

Four commands and they separate the four ways a datagram dies: nothing bound,
socket connected to somebody else, receiver too slow, or lost in the network —
and only the last one is not your machine's fault.

:::checkpoint
1. What state does `ss` show for a bound UDP socket, and why is it not LISTEN?
2. What does a UDP socket in state `ESTAB` mean, and what is it doing to other
   senders?
3. Which counter records datagrams dropped because the reader was too slow?
4. Why does a successful UDP send tell you nothing?
:::

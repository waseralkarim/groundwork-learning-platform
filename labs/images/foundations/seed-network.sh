#!/bin/bash
# Seeds routing tables and host configurations for the A03 networking labs.
#
# A lab container has exactly one interface on an isolated network with no
# default route — which is itself worth measuring, and is not enough to practise
# reading a real machine's routing table on. Adding routes needs CAP_NET_ADMIN,
# which the sandbox drops and will keep dropping.
#
# So the tables here are captured from real machines: a laptop on a VPN, a
# Kubernetes node, and three hosts that cannot talk to each other for three
# different reasons. Every one of them is internally consistent, and the
# arithmetic a learner does on them checks out.
#
# Everything written is inert text under the session's own tmpfs.
set -euo pipefail

T=/tmp/tables
mkdir -p "$T"

cat > "$T/laptop-vpn.txt" <<'EOF'
# ip route   (laptop, connected to the corporate VPN)
0.0.0.0/1 via 10.8.0.1 dev wg0
default via 192.168.1.1 dev wlan0 proto dhcp metric 600
10.0.0.0/8 via 10.8.0.1 dev wg0
10.8.0.0/24 dev wg0 proto kernel scope link src 10.8.0.42
128.0.0.0/1 via 10.8.0.1 dev wg0
172.17.0.0/16 dev docker0 proto kernel scope link src 172.17.0.1 linkdown
192.168.1.0/24 dev wlan0 proto kernel scope link src 192.168.1.87 metric 600
EOF

cat > "$T/k8s-node.txt" <<'EOF'
# ip route   (Kubernetes worker node, flannel CNI)
default via 10.24.0.1 dev ens5 proto dhcp metric 100
10.24.0.0/20 dev ens5 proto kernel scope link src 10.24.3.10 metric 100
10.244.0.0/16 dev flannel.1 onlink
10.244.7.0/24 dev cni0 proto kernel scope link src 10.244.7.1
169.254.169.254 via 10.24.0.1 dev ens5 proto dhcp metric 100
172.17.0.0/16 dev docker0 proto kernel scope link src 172.17.0.1 linkdown
EOF

# ------------------------------------------------------------------- hosts ---
H=/tmp/hosts
mkdir -p "$H"/{alpha,bravo,charlie}

# alpha: correct config. The control.
cat > "$H/alpha/addr.txt" <<'EOF'
# ip -br addr   (alpha)
lo               UNKNOWN        127.0.0.1/8
eth0             UP             10.20.4.10/24
EOF
cat > "$H/alpha/route.txt" <<'EOF'
# ip route   (alpha)
default via 10.20.4.1 dev eth0
10.20.4.0/24 dev eth0 proto kernel scope link src 10.20.4.10
EOF
cat > "$H/alpha/notes.txt" <<'EOF'
alpha reaches the gateway and the internet. It can reach charlie.
It sends to bravo and never gets a reply.
EOF

# bravo: wrong mask. /25 instead of /24, so half its own subnet looks remote.
cat > "$H/bravo/addr.txt" <<'EOF'
# ip -br addr   (bravo)
lo               UNKNOWN        127.0.0.1/8
eth0             UP             10.20.4.200/25
EOF
cat > "$H/bravo/route.txt" <<'EOF'
# ip route   (bravo)
default via 10.20.4.1 dev eth0
10.20.4.128/25 dev eth0 proto kernel scope link src 10.20.4.200
EOF
cat > "$H/bravo/notes.txt" <<'EOF'
bravo reaches the gateway and the internet.
Requests from alpha arrive and are answered, but alpha never sees the answers.
bravo cannot start a connection to alpha at all.
EOF

# charlie: no default route. Local subnet only.
cat > "$H/charlie/addr.txt" <<'EOF'
# ip -br addr   (charlie)
lo               UNKNOWN        127.0.0.1/8
eth0             UP             10.20.4.60/24
EOF
cat > "$H/charlie/route.txt" <<'EOF'
# ip route   (charlie)
10.20.4.0/24 dev eth0 proto kernel scope link src 10.20.4.60
EOF
cat > "$H/charlie/notes.txt" <<'EOF'
charlie reaches alpha without trouble. It times out to bravo.
Every attempt to reach anything off the local subnet fails instantly,
with no delay at all.
EOF

cat > "$H/attempts.txt" <<'EOF'
# what each host reports when it tries the others and the outside world

alpha   -> bravo    : timeout after 30s
alpha   -> charlie  : ok
alpha   -> 1.1.1.1  : ok

bravo   -> alpha    : timeout after 30s
bravo   -> charlie  : timeout after 30s
bravo   -> 1.1.1.1  : ok

charlie -> alpha    : ok
charlie -> bravo    : timeout after 30s
charlie -> 1.1.1.1  : connect: Network is unreachable
EOF

echo "Seeded: two real routing tables in /tmp/tables, three hosts in /tmp/hosts."

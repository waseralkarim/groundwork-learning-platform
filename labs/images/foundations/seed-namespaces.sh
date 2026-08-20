#!/bin/bash
# Seed for the "Which isolation is missing?" challenge lab.
#
# The lab asks the learner to diagnose three workloads from evidence alone. We
# cannot actually run a hostPID or hostNetwork container from inside a tier-2
# sandbox — that is the whole point of the sandbox — so the evidence is
# captured output, laid out exactly as `kubectl exec` and `readlink` would have
# produced it on a real node.
#
# Everything here is inert text. Nothing in this file executes anything the
# learner writes, and nothing is written outside the session's own tmpfs.
set -euo pipefail

E=/tmp/evidence
mkdir -p "$E/host" "$E/alpha" "$E/bravo" "$E/charlie"

# ---------------------------------------------------------------- the node ---
cat > "$E/host/namespaces.txt" <<'EOF'
# readlink /proc/1/ns/*   (run on the node itself)
cgroup:[4026531835]
ipc:[4026531839]
mnt:[4026531841]
net:[4026531992]
pid:[4026531836]
time:[4026531834]
user:[4026531837]
uts:[4026531838]
EOF

cat > "$E/host/interfaces.txt" <<'EOF'
# ip -o link   (run on the node itself)
1: lo: <LOOPBACK,UP,LOWER_UP> mtu 65536
2: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500
3: docker0: <NO-CARRIER,BROADCAST,MULTICAST,UP> mtu 1500
4: cni0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1450
5: flannel.1: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1450
7: vethb41c9d2@if2: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1450
9: veth3f0aa71@if2: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1450
EOF

# ------------------------------------------------------------------ alpha ---
cat > "$E/alpha/namespaces.txt" <<'EOF'
# readlink /proc/self/ns/*   (run inside pod alpha)
cgroup:[4026532452]
ipc:[4026532451]
mnt:[4026532449]
net:[4026532454]
pid:[4026531836]
time:[4026531834]
user:[4026531837]
uts:[4026532450]
EOF

cat > "$E/alpha/processes.txt" <<'EOF'
# ps -eo pid,comm --no-headers | head -20   (run inside pod alpha)
      1 systemd
    412 systemd-journal
    588 containerd
    741 kubelet
   1104 containerd-shim
   1131 pause
   1180 etcd
   1244 kube-apiserver
   1298 kube-controller
   1355 kube-scheduler
   2011 containerd-shim
   2038 pause
   2094 coredns
   3477 containerd-shim
   3502 pause
   3560 nginx
   8455 containerd-shim
   8480 pause
   8531 python3
   8602 sh
# ps -e --no-headers | wc -l  ->  283
EOF

cat > "$E/alpha/interfaces.txt" <<'EOF'
# ip -o link   (run inside pod alpha)
1: lo: <LOOPBACK,UP,LOWER_UP> mtu 65536
2: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1450
EOF

# ------------------------------------------------------------------ bravo ---
cat > "$E/bravo/namespaces.txt" <<'EOF'
# readlink /proc/self/ns/*   (run inside pod bravo)
cgroup:[4026532611]
ipc:[4026532610]
mnt:[4026532608]
net:[4026531992]
pid:[4026532612]
time:[4026531834]
user:[4026531837]
uts:[4026532609]
EOF

cat > "$E/bravo/processes.txt" <<'EOF'
# ps -eo pid,comm --no-headers   (run inside pod bravo)
      1 metrics-agent
     14 metrics-agent
     31 sh
# ps -e --no-headers | wc -l  ->  3
EOF

cat > "$E/bravo/interfaces.txt" <<'EOF'
# ip -o link   (run inside pod bravo)
1: lo: <LOOPBACK,UP,LOWER_UP> mtu 65536
2: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500
3: docker0: <NO-CARRIER,BROADCAST,MULTICAST,UP> mtu 1500
4: cni0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1450
5: flannel.1: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1450
7: vethb41c9d2@if2: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1450
9: veth3f0aa71@if2: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1450
EOF

# ---------------------------------------------------------------- charlie ---
cat > "$E/charlie/namespaces.txt" <<'EOF'
# readlink /proc/self/ns/*   (run inside pod charlie)
cgroup:[4026532781]
ipc:[4026532778]
mnt:[4026532776]
net:[4026532783]
pid:[4026532780]
time:[4026531834]
user:[4026531837]
uts:[4026532777]
EOF

cat > "$E/charlie/processes.txt" <<'EOF'
# ps -eo pid,comm --no-headers   (run inside pod charlie)
      1 bash
     22 build-agent
     47 sh
# ps -e --no-headers | wc -l  ->  3
EOF

cat > "$E/charlie/interfaces.txt" <<'EOF'
# ip -o link   (run inside pod charlie)
1: lo: <LOOPBACK,UP,LOWER_UP> mtu 65536
2: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1450
EOF

cat > "$E/charlie/status.txt" <<'EOF'
# grep -E 'Uid|CapEff|CapBnd|NoNewPrivs|Seccomp' /proc/1/status   (inside charlie)
Uid:    0       0       0       0
CapEff: 000001ffffffffff
CapBnd: 000001ffffffffff
NoNewPrivs:     0
Seccomp:        0
EOF

cat > "$E/charlie/attempt.txt" <<'EOF'
# an engineer tried this inside charlie and reported that it worked
$ unshare --mount --pid --fork -- /bin/sh -c 'echo inner; readlink /proc/self/ns/pid'
inner
pid:[4026533104]
$ mount -t proc proc /mnt
$ echo $?
0
EOF

echo "Evidence ready: three workloads under /tmp/evidence, plus the node itself."

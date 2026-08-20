#!/bin/bash
# Seeds the PID 1 challenge.
#
# Starts one ordinary process running a plain wait loop. The comparison the lab
# asks for is against PID 1 — which in this container is the learner's own
# shell, exactly as it would be your application in a real container.
#
# Nothing here is simulated: PID 1 genuinely ignores SIGTERM because the kernel
# does not apply default signal actions to it, and the ordinary process
# genuinely dies from the same signal.
set -euo pipefail

cat > /tmp/ordinary-proc <<'BODY'
#!/bin/bash
# No signal handlers installed. Deliberately.
while true; do sleep 1; done
BODY
chmod +x /tmp/ordinary-proc

/tmp/ordinary-proc &
echo "An ordinary process is running. Compare how it and PID 1 respond to SIGTERM."

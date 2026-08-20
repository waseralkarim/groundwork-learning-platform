#!/bin/bash
# Seeds the A05.2 service-model and shared-responsibility labs.
#
# This topic has no instrument to read — you cannot measure a service model. So
# the labs are built around an artefact the learner produces and can be checked
# against: a responsibility matrix for one specific stack, then tested against
# real incidents.
#
# The design follows A04.4's blast-radius lab. "Is this least privilege" is
# unanswerable and "what does a compromise reach" is a list; likewise "who is
# responsible for security in the cloud" is a diagram nobody can check, and
# "who patches this specific component, who is paged when it fails, and what
# happens if nobody does" is a table.
#
# Everything here describes one application deployed four ways, so the learner
# compares like with like rather than comparing vendors.
set -euo pipefail

export LC_ALL=C

# --------------------------------------------------------------- deployments

D=/tmp/deployments
rm -rf "$D"; mkdir -p "$D"

cat > "$D/README.txt" <<'EOF'
One application — an HTTP API with a PostgreSQL database — deployed four ways.

Same code, same traffic, same data. What changes is where the boundary between
you and the provider sits.

For each deployment, work out for EVERY layer listed:

  - who applies the patch
  - who is paged when it breaks
  - what happens if nobody does anything

The layers are the same in all four. Only the answers move.
EOF

cat > "$D/1-colocation.txt" <<'EOF'
deployment 1: COLOCATION
you rent rack space and power. the hardware is yours.

  physical security        provider (the building)
  power and cooling        provider
  network to the internet  provider
  server hardware          YOU (you bought it, you replace it)
  firmware and BIOS        YOU
  hypervisor               YOU (if you run one)
  guest OS                 YOU
  OS patching              YOU
  container runtime        YOU
  application runtime      YOU
  application code         YOU
  database software        YOU
  database patching        YOU
  backups                  YOU
  data                     YOU
  access control           YOU
  configuration            YOU
EOF

cat > "$D/2-iaas.txt" <<'EOF'
deployment 2: IaaS
VMs from a cloud provider. postgres installed by you on one of them.

  physical security        provider
  power and cooling        provider
  network to the internet  provider
  server hardware          provider
  firmware and BIOS        provider
  hypervisor               provider
  guest OS                 YOU (they supply an image; you run it)
  OS patching              YOU
  container runtime        YOU
  application runtime      YOU
  application code         YOU
  database software        YOU
  database patching        YOU
  backups                  YOU
  data                     YOU
  access control           YOU
  configuration            YOU
EOF

cat > "$D/3-paas.txt" <<'EOF'
deployment 3: PaaS
managed kubernetes + managed postgres. you supply a container image.

  physical security        provider
  power and cooling        provider
  network to the internet  provider
  server hardware          provider
  firmware and BIOS        provider
  hypervisor               provider
  guest OS                 provider (node images)
  OS patching              SHARED - provider publishes, YOU choose when to roll
  container runtime        provider
  application runtime      YOU (whatever is in your image)
  application code         YOU
  database software        provider
  database patching        SHARED - provider patches, YOU pick the window
  backups                  SHARED - provider takes them, YOU verify restores
  data                     YOU
  access control           YOU
  configuration            YOU
EOF

cat > "$D/4-saas.txt" <<'EOF'
deployment 4: SaaS
you stopped running the application. a vendor provides the whole product.

  physical security        provider
  power and cooling        provider
  network to the internet  provider
  server hardware          provider
  firmware and BIOS        provider
  hypervisor               provider
  guest OS                 provider
  OS patching              provider
  container runtime        provider
  application runtime      provider
  application code         provider
  database software        provider
  database patching        provider
  backups                  provider (check the retention and the RPO)
  data                     YOU
  access control           YOU
  configuration            YOU
EOF

# ------------------------------------------------------------------ patches

P=/tmp/patches
rm -rf "$P"; mkdir -p "$P"

cat > "$P/advisories.txt" <<'EOF'
# Twelve advisories arriving in one week. For the PaaS deployment (3), decide
# for each: is it yours, the provider's, or shared?

A01  Linux kernel — local privilege escalation via io_uring
A02  OpenSSL — buffer overflow in certificate parsing, in your base image
A03  PostgreSQL — authentication bypass in a minor release
A04  Your application's JSON library — remote code execution
A05  Kubernetes API server — privilege escalation via a crafted request
A06  containerd — container escape
A07  Server firmware — speculative execution side channel
A08  Your application — an endpoint returns another tenant's records
A09  Your S3-equivalent bucket is publicly readable
A10  An IAM role in your account grants * on *
A11  The provider's control plane had a cross-tenant data exposure
A12  Your database has a password of "postgres"
EOF

# ---------------------------------------------------------------- incidents

I=/tmp/incidents
rm -rf "$I"; mkdir -p "$I"

cat > "$I/incidents.txt" <<'EOF'
# Five outages. For each: whose responsibility, and what would have prevented it?

INC-1
Your managed Kubernetes cluster's control plane was unavailable for 45 minutes.
Provider status page confirmed a regional control-plane incident. Your pods kept
serving traffic throughout. You could not deploy or scale during the window.

INC-2
Your managed PostgreSQL was unavailable for 3 hours. The provider applied a
mandatory minor-version patch. You had left the maintenance window at its
default of "any time".

INC-3
Customer data was exposed. Your object storage bucket had been public since it
was created 14 months ago. The provider's documentation defaults to private and
the bucket was created by a script that set public-read.

INC-4
Your application was down for 2 hours. A node image update from the provider
changed the default seccomp profile and your application used a syscall it
blocked. The provider announced the change 30 days in advance.

INC-5
Your SaaS CRM was unavailable for 6 hours. The vendor had a database failure.
Their SLA promises 99.9% monthly. You had no access to your data during the
outage and no ability to do anything about it.
EOF

# ------------------------------------------------------------- vendor claim

cat > "$I/vendor-diagram.txt" <<'EOF'
# From a vendor's marketing page. It is not wrong, and it is not the whole
# picture. Find what it leaves out.

    "SECURITY OF THE CLOUD vs SECURITY IN THE CLOUD"

    We are responsible for SECURITY OF THE CLOUD:
      - physical infrastructure
      - hardware and virtualisation
      - the managed services themselves

    You are responsible for SECURITY IN THE CLOUD:
      - your data
      - your access control
      - your configuration

    "With our managed services, we handle the undifferentiated heavy lifting
     so you can focus on your application."
EOF

echo "Seeded: /tmp/deployments, /tmp/patches, /tmp/incidents."

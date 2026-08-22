# Lab image: the Foundations track (A01 Computing Foundations, A02 Operating
# Systems, A03 Networking Foundations, A04 Security Foundations).
#
# Everything those labs need and nothing else. Each package here is used by a
# specific lab step — an unused tool in a lab image is extra attack surface
# handed to someone we have assumed is hostile.
#
# Three of the four courses cost almost nothing to add. A02 adds no packages at
# all: namespaces are read through /proc and util-linux, both of which A01
# already required. A03 adds netcat. A04 adds openssl, which was already here
# transitively via ca-certificates — named explicitly now that a whole course
# depends on it, because a transitive dependency is not a promise. A04 also adds
# openssh-client — the one package here bought for a single topic. `ssh-keygen`
# is where most engineers actually meet asymmetric cryptography, and reading a
# real authorized_keys entry is worth more than being shown one.
#
# A second image would be a second thing to build, scan and keep patched for no
# gain.

FROM debian:13-slim

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
      procps \
      util-linux \
      coreutils \
      file \
      binutils \
      gcc \
      libc6-dev \
      strace \
      libcap2-bin \
      iproute2 \
      netcat-openbsd \
      openssl \
      openssh-client \
      curl \
      less \
      bash \
      bats \
      ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Fixed uid so the broker can set User explicitly and tmpfs ownership lines up.
RUN groupadd --gid 10001 learner \
    && useradd --uid 10001 --gid 10001 --shell /bin/bash --home-dir /home/learner learner

COPY --chmod=0755 seed.sh /opt/lab/seed.sh
COPY --chmod=0755 seed-wrong-arch.sh /opt/lab/seed-wrong-arch.sh
COPY --chmod=0755 seed-pid1.sh /opt/lab/seed-pid1.sh
COPY --chmod=0755 seed-boundary.sh /opt/lab/seed-boundary.sh
COPY --chmod=0755 seed-namespaces.sh /opt/lab/seed-namespaces.sh
COPY --chmod=0755 seed-cgroups.sh /opt/lab/seed-cgroups.sh
COPY --chmod=0755 seed-scheduler.sh /opt/lab/seed-scheduler.sh
COPY --chmod=0755 seed-blockdev.sh /opt/lab/seed-blockdev.sh
COPY --chmod=0755 seed-init.sh /opt/lab/seed-init.sh
COPY --chmod=0755 seed-network.sh /opt/lab/seed-network.sh
COPY --chmod=0755 seed-hashing.sh /opt/lab/seed-hashing.sh
COPY --chmod=0755 seed-encryption.sh /opt/lab/seed-encryption.sh
COPY --chmod=0755 seed-tls.sh /opt/lab/seed-tls.sh
COPY --chmod=0755 seed-identity.sh /opt/lab/seed-identity.sh
COPY --chmod=0755 seed-layers.sh /opt/lab/seed-layers.sh
COPY --chmod=0755 seed-responsibility.sh /opt/lab/seed-responsibility.sh
COPY --chmod=0755 seed-domains.sh /opt/lab/seed-domains.sh
COPY --chmod=0755 seed-distro.sh /opt/lab/seed-distro.sh
COPY --chmod=0755 seed-packages.sh /opt/lab/seed-packages.sh
COPY --chmod=0755 seed-hierarchy.sh /opt/lab/seed-hierarchy.sh
COPY --chmod=0755 seed-environment.sh /opt/lab/seed-environment.sh
COPY --chmod=0755 seed-shell.sh /opt/lab/seed-shell.sh
COPY --chmod=0755 seed-pipes.sh /opt/lab/seed-pipes.sh
COPY --chmod=0755 seed-text.sh /opt/lab/seed-text.sh
COPY --chmod=0755 seed-find.sh /opt/lab/seed-find.sh
COPY --chmod=0755 seed-strict.sh /opt/lab/seed-strict.sh
COPY --chmod=0755 seed-functions.sh /opt/lab/seed-functions.sh
COPY --chmod=0755 seed-args.sh /opt/lab/seed-args.sh
COPY --chmod=0755 seed-lock.sh /opt/lab/seed-lock.sh
COPY --chmod=0755 seed-bats.sh /opt/lab/seed-bats.sh

# Lab helpers are compiled here rather than shipped as scripts. Both need real
# fork and real page-touching semantics, which a shell cannot provide — bash
# reaps its own children, and an untouched allocation never becomes RSS.
COPY make-zombie.c eat-memory.c share-pages.c spin.c /opt/lab/src/
RUN gcc -O2 -o /opt/lab/make-zombie /opt/lab/src/make-zombie.c     && gcc -O2 -o /opt/lab/eat-memory /opt/lab/src/eat-memory.c     && gcc -O2 -o /opt/lab/share-pages /opt/lab/src/share-pages.c     && gcc -O2 -o /opt/lab/spin /opt/lab/src/spin.c -lpthread     && chmod 0755 /opt/lab/make-zombie /opt/lab/eat-memory /opt/lab/share-pages /opt/lab/spin     && rm -rf /opt/lab/src

# Flush history after every command instead of at shell exit.
#
# The `command_ran` check reads ~/.bash_history to ask whether the learner used
# the tool the step is teaching. Bash writes that file when the shell *exits*,
# which is never during a session — so without this the check could not pass no
# matter what the learner typed. This goes in /etc/bash.bashrc rather than the
# learner's own dotfiles because tmpfs is mounted over /home/learner at start,
# masking anything baked in there.
#
# The prompt belongs here for the same reason. A container's setup commands run
# after the shell has already read its startup files, so a PS1 written to
# ~/.profile at seed time is read by nobody.
RUN printf '%s\n' \
      'shopt -s histappend' \
      'export HISTFILE=/home/learner/.bash_history' \
      'export PROMPT_COMMAND="history -a"' \
      "PS1='lab:\\w\$ '" \
    >> /etc/bash.bashrc

# The container runs read-only with tmpfs over /home/learner and /tmp, so
# anything the learner writes lives in RAM and dies with the session.
WORKDIR /home/learner
USER 10001:10001

CMD ["/bin/bash", "-l"]

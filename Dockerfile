# A small docker image to run a root-less sshd process as the 'git' user, and allow cloning/pushing
# a single git repo.
# This is intended to be run with minimal security permissions, hence the non-standard sshd_config
# The custom stuff all lives in /home/git/, and the repo itself lives in /home/git/repo
FROM debian:trixie-slim

EXPOSE 2222
ENTRYPOINT ["/home/git/bin/docker-entrypoint.sh"]

# We need a few things installed package-wise
# - python, to run our webhook emulator script
# - openssh-server, to run our userland sshd
# - git, to get access to the git-* commands (git-receive-pack, -upload-pack, etc)
RUN \
    --mount=type=cache,target=/var/cache/apt,sharing=locked \
    apt-get update \
    && apt-get install -y --no-install-recommends openssh-server git python3-minimal libpython3-stdlib

# We need to set up a 'git' (uid 1000) user with a minimal rootless sshd config
# Once we have everything in place, we'll switch to that USER in the image
RUN useradd -m -d /home/git -u 1000 git \
    && passwd -d git \
    && mkdir -p /var/run/sshd /home/git/.ssh /home/git/repo /home/git/config /home/git/secret /home/git/etc /home/git/bin \
    && chown -R git:git /home/git \
    && chmod 700 /home/git/.ssh /home/git/repo

ENV PATH=$PATH:/home/git/bin

USER git:git
WORKDIR /home/git

# silence warnings when we run git inside the entrypoint
RUN git config --global init.defaultBranch main

COPY sshd_config /home/git/etc/
COPY --chmod=755 send-webhook.py git-restrict.py docker-entrypoint.sh /home/git/bin/



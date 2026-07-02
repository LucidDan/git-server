FROM debian:trixie-slim

EXPOSE 22
ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]

RUN \
    --mount=type=cache,target=/var/cache/apt,sharing=locked \
    apt-get update \
    && apt-get install -y --no-install-recommends openssh-server git python3-minimal libpython3-stdlib \
    && useradd -m -d /home/git git \
    && passwd -d git \
    && mkdir -p /var/run/sshd /home/git/.ssh /repo /repo/config /repo/secret \
    && chown -R git:git /home/git /repo \
    && chmod 700 /home/git/.ssh

COPY sshd_config /etc/ssh/
COPY argocd-sync.py git-restrict.sh docker-entrypoint.sh /usr/local/bin/

RUN \
    chmod 0755 /usr/local/bin/argocd-sync.py /usr/local/bin/git-restrict.sh /usr/local/bin/docker-entrypoint.sh \
    && chown root:root /usr/local/bin/argocd-sync.py /usr/local/bin/git-restrict.sh /usr/local/bin/docker-entrypoint.sh



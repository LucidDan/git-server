#!/bin/bash
set -euo pipefail

SSH_DIR=/home/git/.ssh
AUTHORIZED_KEYS=${SSH_DIR}/authorized_keys

mkdir -p "$SSH_DIR"
chmod 700 "$SSH_DIR"

: > "$AUTHORIZED_KEYS"

if [ -d /keys/readonly ]; then
    for key in $(ls -1 /keys/readonly/); do
        echo "command=\"/usr/local/bin/git-restrict.sh ro\",no-port-forwarding,no-agent-forwarding,no-X11-forwarding,no-pty $(cat /keys/readonly/$key)" >> "$AUTHORIZED_KEYS"
    done
fi

if [ -d /keys/readwrite ]; then
    for key in $(ls -1 /keys/readwrite/); do
        echo "command=\"/usr/local/bin/git-restrict.sh rw\",no-port-forwarding,no-agent-forwarding,no-X11-forwarding,no-pty $(cat /keys/readwrite/$key)" >> "$AUTHORIZED_KEYS"
    done
fi

chmod 600 "$AUTHORIZED_KEYS"
chown -R git:git "$SSH_DIR"

if [ ! -d /repo/bootstrap.git ]; then
    git init --bare /repo/bootstrap.git
    cp /usr/local/bin/argocd-sync.py /repo/bootstrap.git/hooks/post-receive
    chmod +x /repo/bootstrap.git/hooks/post-receive
    chown -R git:git /repo/bootstrap.git
fi

exec /usr/sbin/sshd -D -e


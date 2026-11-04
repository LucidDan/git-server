#!/bin/bash
set -euo pipefail

SSH_DIR=/home/git/.ssh
ETC_DIR=/home/git/etc
SECRET_DIR=/home/git/secret
KEYS_DIR="${SECRET_DIR}/keys"
REPO_DIR=/home/git/repo
AUTHORIZED_KEYS=${SSH_DIR}/authorized_keys

mkdir -p "$SSH_DIR"
chmod 700 "$SSH_DIR"

: > "$AUTHORIZED_KEYS"

if [ -d "${KEYS_DIR}/readonly" ]; then
    for key in $(ls -1 "${KEYS_DIR}/readonly/"); do
        echo "restrict,command=\"/home/git/bin/git-restrict.py ro\" $(cat ${KEYS_DIR}/readonly/$key)" >> "$AUTHORIZED_KEYS"
    done
fi

if [ -d "${KEYS_DIR}/readwrite" ]; then
    for key in $(ls -1 "${KEYS_DIR}/readwrite/"); do
        echo "restrict,command=\"/home/git/bin/git-restrict.py rw\" $(cat ${KEYS_DIR}/readwrite/$key)" >> "$AUTHORIZED_KEYS"
    done
fi

chmod 600 "$AUTHORIZED_KEYS"

if [ -d "${REPO_DIR}/bootstrap.git" ]; then
    echo "Initial bootstrap repository already exists"
    ls -la "${REPO_DIR}/bootstrap.git"
else
    echo "Creating initial bootstrap repository"
    git init --bare "${REPO_DIR}/bootstrap.git"
fi

echo "Setting up webhook as a post-receive hook in the bootstrap repository"
cp /home/git/bin/send-webhook.py "${REPO_DIR}/bootstrap.git/hooks/post-receive"
chmod +x "${REPO_DIR}/bootstrap.git/hooks/post-receive"

if [ ! -f "${ETC_DIR}/ssh_host_ed25519_key" ]; then
  if [ -f "${SECRET_DIR}/ssh_host_ed25519_key" ]; then
    cp -f "${SECRET_DIR}/ssh_host_ed25519_key" "${ETC_DIR}/ssh_host_ed25519_key"
    ssh-keygen -f "${ETC_DIR}/ssh_host_ed25519_key" -y > "${ETC_DIR}/ssh_host_ed25519_key.pub"
  else
    ssh-keygen -q -N "" -t ed25519 -f "${ETC_DIR}/ssh_host_ed25519_key"
  fi
fi
if [ ! -f "${ETC_DIR}/ssh_host_rsa_key" ]; then
  if [ -f "${SECRET_DIR}/ssh_host_rsa_key" ]; then
    cp -f "${SECRET_DIR}/ssh_host_rsa_key" "${ETC_DIR}/ssh_host_rsa_key"
    ssh-keygen -f "${ETC_DIR}/ssh_host_rsa_key" -y > "${ETC_DIR}/ssh_host_rsa_key.pub"
  else
    ssh-keygen -q -N "" -t rsa -b 4096 -f "${ETC_DIR}/ssh_host_rsa_key"
  fi
fi

exec /usr/sbin/sshd -D -e -f "${ETC_DIR}/sshd_config"

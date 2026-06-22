#!/usr/bin/env bash
set -eu
GIT_MODE="$1"
cmd="${SSH_ORIGINAL_COMMAND:-}"
if [ -z "$cmd" ]; then
  echo "No command given. Interactive mode disabled" >&2
  exit 1
fi
set -- $cmd
git_cmd="$1"

case "${git_cmd}" in
  git-upload-pack|git-upload-archive)
    ;;
  git-receive-pack)
    if [ "$GIT_MODE" = "ro" ]; then
      echo "Push access denied" >&2
      exit 1
    fi
    if [ "$GIT_MODE" != "rw" ]; then
      echo "Unknown mode $GIT_MODE" >&2
      exit 1
    fi
    ;;
  *)
    echo "Interactive shell access disabled"
    exit 1
    ;;
esac

exec git-shell -c "$cmd"

#!/usr/bin/env python3

"""
Restrict git-shell commands and make sure the repo is valid.
"""

import os, sys
from pathlib import Path
from typing import NoReturn


def err(msg: str) -> NoReturn:
    sys.exit(msg)

cmd = os.environ.get("SSH_ORIGINAL_COMMAND", "").strip()
dbg = os.environ.get("DEBUG", "").lower() in {"true", "t", "1"}

def debug(msg: str) -> None:
    if dbg:
        print(msg, file=sys.stderr, flush=True)

debug(f"Received command: {cmd} (via {sys.argv})")

try:
    git_mode = sys.argv[1]
except IndexError:
    err(f"No git mode passed on command line: {sys.argv}")
if not cmd:
    err(f"No command passed, interactive mode disabled.")

if git_mode not in ("ro", "rw"):
    err(f"Unknown git mode: {git_mode}")
if cmd.startswith("git-receive-pack "):
    if git_mode == "ro":
        err("Push access denied")
    else:
        debug("Push access accepted")
elif not cmd.startswith(("git-upload-pack ", "git-upload-archive ")):
    err(f"Unknown command: {cmd}")
else:
    debug("Clone access accepted")

# Path is passed inside single quotes, so we can take the first non-option with quotes
args = cmd.split("'", maxsplit=2)
if len(args) < 2:
    err("No repository path provided")
if len(args) < 3:
    args.append("")

base_path = Path("/home/git/repo")
os.chdir(base_path)
repo_path = Path(args[1].lstrip("/")).absolute().resolve()
# Detect if they escaped (eg using '..')
if not repo_path.is_relative_to(base_path):
    err(f"Repository path is invalid: {repo_path}")
if not repo_path.is_dir():
    err(f"Repository does not exist: {repo_path}")

cmd_args = ["git-shell", "-c", f"{args[0]}'{repo_path}'{args[2]}"]
debug(f"Final command to pass to git-shell: {cmd_args}")
os.execv(
    "/usr/bin/git-shell",
    cmd_args,
)

#!/usr/bin/env python3

"""
Generate a gitlab-style webhook for argocd
This allows us to use the token-authenticated webhook api instead of needing a proper API user account to talk to the
full argocd API.
GitLab webhook format is a bit better and more clearly documented than GitHub so it made more sense.
Also the authentication is a bit simpler with just a header rather than HMAC stuff.
"""

import sys
import json
from pathlib import Path
from urllib import request
from typing import TypedDict, Literal
from concurrent.futures import ThreadPoolExecutor, as_completed
import subprocess
from ssl import _create_unverified_context

EMPTY_REF = "0" * 40


class AuthorDict(TypedDict, total=True):
    name: str
    email: str


class CommitDict(TypedDict, total=True):
    id: str
    message: str
    title: str
    timestamp: str
    url: str
    author: AuthorDict
    added: list[str]
    modified: list[str]
    removed: list[str]


class ProjectDict(TypedDict, total=True):
    id: int
    name: str
    web_url: str
    git_ssh_url: str
    git_http_url: str
    namespace: str
    path_with_namespace: str
    url: str
    ssh_url: str
    http_url: str
    visibility_level: int
    default_branch: str


class RepositoryDict(TypedDict, total=True):
    name: str
    url: str
    git_http_url: str
    git_ssh_url: str
    visibility_level: int


class PayloadDict(TypedDict, total=True):
    object_kind: Literal["push"]
    event_name: str
    before: str
    after: str
    ref: str
    ref_protected: bool
    checkout_sha: str
    message: str
    project: ProjectDict
    repository: RepositoryDict
    commits: list[CommitDict]
    total_commits_count: int
    push_options: dict


def get_config(name: str, *, secret: bool = False, default: str = "") -> str:
    p = Path("/repo/secret") if secret else Path("/repo/config")
    try:
        return (p / name).read_text().strip() or default
    except FileNotFoundError:
        if default:
            return default
        else:
            raise


def send_webhook(payload: PayloadDict, use_ssl: bool = False) -> bool:
    token = get_config("argocd-token", secret=True)
    host = get_config("argocd-host", default="argocd-server.argocd.svc.cluster.local")

    data = json.dumps(payload).encode("utf-8")

    with request.urlopen(
            request.Request(
                f"http://{host}/api/webhook" if not use_ssl else f"https://{host}/api/webhook",
                data=data,
                method="POST",
                headers={
                    "X-Gitlab-Event": "Push Hook",
                    "X-Gitlab-Token": token,
                    "Content-Type": "application/json",
                },
            ),
            context=_create_unverified_context() if use_ssl else None,
    ) as resp:
        if resp.status > 300:
            raise RuntimeError(
                f"Request failed with status {resp.status}: {resp.reason}"
            )
        return True


def git(cmd: str, *args: str) -> str:
    return subprocess.check_output(
        ["git", cmd, *args], text=True,
    ).strip()


def get_commit_files(commit_id: str) -> tuple[list[str], list[str], list[str]]:
    adds = []
    changes = []
    removes = []
    for line in git("diff-tree", "--no-commit-id", "--name-status", "-r", commit_id).splitlines():
        line = line.strip()
        if not line:
            continue
        cmd, _, filename = line.partition("\t")
        cmd = cmd.strip()
        filename = filename.strip()
        if cmd == "A":
            adds.append(filename)
        elif cmd == "M":
            changes.append(filename)
        elif cmd == "D":
            removes.append(filename)

    return adds, changes, removes


def get_commit(sha: str) -> CommitDict:
    result = git(
        "show",
        "-s",
       "--format=%H%x00%s%x00%b%x00%aI%x00%an%x00%ae",
        sha,
    )
    commit_id, title, message, timestamp, author_name, author_email = result.split("\0")

    adds, changes, removes = get_commit_files(commit_id)

    return {
        "id": commit_id,
        "title": title,
        "message": f"{title}\n\n{message}" if message else title,
        "timestamp": timestamp,
        "author": {
            "name": author_name,
            "email": author_email,
        },
        "added": adds,
        "modified": changes,
        "removed": removes,
        "url": "https://notavailable",
    }


def get_commits(first_commit: str, last_commit: str) -> list[CommitDict]:
    lines = git("rev-list", "--reverse", f"{first_commit}..{last_commit}").splitlines()

    return [get_commit(line) for line in lines]


def main() -> int:
    repo_name = Path.cwd().name
    host = get_config("git-server-hostname", default="git.git-server.svc.cluster.local")
    default_payload: PayloadDict = {
        "object_kind": "push",
        "event_name": "push",
        "ref_protected": False,
        "project": {
            "id": 1,
            "name": repo_name,
            # Note: we don't support https, but for argocd purposes,
            # it just wants the url to compare the hostname + repo path with its internal records
            "web_url": f"https://{host}/repo/{repo_name}",
            "default_branch": "main",
            "visibility_level": 0,
            "namespace": "repo",
            "path_with_namespace": f"repo/{repo_name}",
            "url": f"git@{host}:repo/{repo_name}.git",
            "git_http_url": f"https://{host}/repo/{repo_name}.git",
            "git_ssh_url": f"git@{host}:repo/{repo_name}.git",
            "http_url": f"https://{host}/repo/{repo_name}.git",
            "ssh_url": f"git@{host}:repo/{repo_name}.git",
        },
        "repository": {
            "name": repo_name,
            "url": f"git@{host}:repo/{repo_name}.git",
            "git_http_url": f"https://{host}/repo/{repo_name}.git",
            "git_ssh_url": f"git@{host}:repo/{repo_name}.git",
            "visibility_level": 0,
        },
        "push_options": {},
        "commits": [],
        "before": "",
        "after": "",
        "ref": "",
        "checkout_sha": "",
        "message": "",
        "total_commits_count": 0,

    }

    def make_payload(_old_commit: str, _new_commit: str, _ref: str) -> PayloadDict:
        commits = get_commits(_old_commit, _new_commit)
        return default_payload | {
            "before": _old_commit,
            "after": _new_commit,
            "ref": _ref,
            "checkout_sha": _new_commit,
            "message": commits[-1]["message"] if commits else "",
            "created": _old_commit == EMPTY_REF,
            "commits": commits,
            "total_commits_count": len(commits),
        }

    if len(sys.argv) > 1:
        # test mode: dump payload for test SHA passed in on command line
        print("Output:\n")
        print(json.dumps(make_payload(sys.argv[1], sys.argv[2], sys.argv[3]), indent=2))
        return 0

    # If there's at least one push to main, trigger a sync for all the apps
    with ThreadPoolExecutor(max_workers=5) as executor:
        results = set()
        for line in sys.stdin:
            old_commit, new_commit, ref = line.strip().split()
            if new_commit == EMPTY_REF:
                # skip deleted refs?
                continue
            results.add(executor.submit(send_webhook, make_payload(old_commit, new_commit, ref)))

        err = False
        for future in as_completed(results):
            try:
                future.result()
            except Exception as e:
                print(
                    f"Got error: {e}",
                    file=sys.stderr,
                    flush=True,
                )
                err = True
        return 1 if err else 0


if __name__ == "__main__":
    sys.exit(main())

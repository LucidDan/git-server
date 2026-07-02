#!/usr/bin/env python3
import sys
from pathlib import Path
from urllib import request
from concurrent.futures import ThreadPoolExecutor, as_completed
from ssl import _create_unverified_context


def get_config(name: str, *, secret: bool = False, default: str = "") -> str:
    p = Path("/repo/secret") if secret else Path("/repo/config")
    try:
        return (p / name).read_text().strip() or default
    except FileNotFoundError:
        if default:
            return default
        else:
            raise


def request_sync(app_name: str) -> bool:
    token = get_config("argocd-token", secret=True)
    host = get_config("argocd-host", default="argocd-server.argocd.svc.cluster.local")

    with request.urlopen(
        request.Request(
            f"https://{host}/api/v1/applications/{app_name}/sync",
            data=b"{}",
            method="POST",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
        ),
        context=_create_unverified_context(),
    ) as resp:
        if resp.status > 300:
            raise RuntimeError(
                f"Request failed with status {resp.status}: {resp.reason}"
            )
        return True


def main() -> int:
    apps = [x.strip() for x in get_config("argocd-apps").split(",")]

    # Ignore any line that isn't a push to main
    lines = [
        line
        for line in sys.stdin.readlines()
        if line.strip().endswith(" refs/heads/main")
    ]
    if not lines:
        # If there's no push to main, do nothing.
        return 0

    # If there's at least one push to main, trigger a sync for all the apps
    with ThreadPoolExecutor(max_workers=5) as executor:
        results = {executor.submit(request_sync, app): app for app in apps}
        err = False
        for future in as_completed(results):
            try:
                future.result()
            except Exception as e:
                print(
                    f"Got error for app '{results[future]}': {e}",
                    file=sys.stderr,
                    flush=True,
                )
                err = True
        return 1 if err else 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""
远程仓库 origin 指向校验 — 确保 origin 指向正确的 remote.
"""
import os
import subprocess
import sys

EXPECTED_REMOTES = {
    "": "https://github.com/starlink-awaken/omostation.git",
    "projects/knowledge/gbrain": "https://github.com/starlink-awaken/omostation-gbrain.git",
    "projects/cockpit": "https://github.com/starlink-awaken/omostation-cockpit.git",
    "projects/agora": "https://github.com/starlink-awaken/omostation-agora.git",
}


def _git(args, cwd):
    return subprocess.run(
        ["git", "-C", cwd, *args],
        capture_output=True,
        text=True,
        env={k: v for k, v in os.environ.items() if k not in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_OBJECT_DIRECTORY", "GIT_ALTERNATE_OBJECT_DIRECTORIES")},
    )


def main() -> int:
    root = _git(["rev-parse", "--show-toplevel"], ".").stdout.strip()
    if not root:
        return 0

    failed = 0
    for sub_path, expected_url in EXPECTED_REMOTES.items():
        repo_path = os.path.join(root, sub_path) if sub_path else root
        if not os.path.isdir(repo_path):
            continue

        result = _git(["remote", "get-url", "origin"], repo_path)
        if result.returncode != 0:
            continue

        actual = result.stdout.strip()
        ssh_expected = expected_url.replace("https://", "git@github.com:")

        if actual != expected_url and actual != ssh_expected:
            print(f"❌ {repo_path or 'root'} origin 指向异常: {actual}", file=sys.stderr)
            print(f"   应为: {expected_url}", file=sys.stderr)
            failed += 1

    return 1 if failed > 0 else 0


if __name__ == "__main__":
    sys.exit(main())

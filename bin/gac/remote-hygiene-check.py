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


def main() -> int:
    root = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        capture_output=True, text=True, check=True,
    ).stdout.strip()

    failed = 0
    for sub_path, expected_url in EXPECTED_REMOTES.items():
        repo_path = os.path.join(root, sub_path) if sub_path else root
        if not os.path.isdir(repo_path):
            continue

        result = subprocess.run(
            ["git", "-C", repo_path, "remote", "get-url", "origin"],
            capture_output=True, text=True,
        )
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

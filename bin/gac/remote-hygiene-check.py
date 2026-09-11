#!/usr/bin/env python3
"""
远程仓库 origin 指向校验 — 确保 origin 指向正确的 remote.

改进 (2026-09-11): 从 .gitmodules 动态读取 submodule url, 不再硬编码列表.
根仓库 origin 必须指向 omostation canonical.
"""
import os
import re
import subprocess
import sys


def _git(args, cwd):
    return subprocess.run(
        ["git", "-C", cwd, *args],
        capture_output=True,
        text=True,
        env={
            k: v
            for k, v in os.environ.items()
            if k
            not in (
                "GIT_DIR",
                "GIT_WORK_TREE",
                "GIT_INDEX_FILE",
                "GIT_OBJECT_DIRECTORY",
                "GIT_ALTERNATE_OBJECT_DIRECTIVES",
            )
        },
    )


def _read_gitmodules(root):
    """Read submodule path → url mappings from .gitmodules."""
    result = _git(
        [
            "config",
            "--file",
            ".gitmodules",
            "--get-regexp",
            r"^submodule\..*\.(path|url)$",
        ],
        root,
    )
    if result.returncode != 0:
        return {}
    sections = {}
    for line in result.stdout.splitlines():
        m = re.match(r"^submodule\.([^.]+)\.(path|url)\s+(\S+)$", line)
        if not m:
            continue
        section = m.group(1)
        field = m.group(2)
        value = m.group(3)
        if section not in sections:
            sections[section] = {}
        sections[section][field] = value
    result_map = {}
    for _section, fields in sections.items():
        if "path" in fields and "url" in fields:
            result_map[fields["path"]] = fields["url"]
    return result_map


def _normalize_https(url):
    """Convert SSH git@github.com: form to HTTPS and ensure .git suffix."""
    m = re.match(r"^git@github\.com:(.+)$", url)
    if m:
        url = f"https://github.com/{m.group(1)}"
    if not url.endswith(".git"):
        url = url + ".git"
    return url


def _matches(actual, expected):
    """Check if actual URL matches expected (allowing SSH ↔ HTTPS variation)."""
    if actual == expected:
        return True
    if _normalize_https(actual) == _normalize_https(expected):
        return True
    return False


def main():
    root = _git(["rev-parse", "--show-toplevel"], ".").stdout.strip()
    if not root:
        return 0

    canonical_root = "https://github.com/starlink-awaken/omostation.git"
    sub_expected = _read_gitmodules(root)

    failed = 0

    # Root check: origin must equal canonical
    result = _git(["remote", "get-url", "origin"], root)
    if result.returncode == 0:
        actual = result.stdout.strip()
        if not _matches(actual, canonical_root):
            print(
                f"❌ {root or 'root'} origin 指向异常: {actual}",
                file=sys.stderr,
            )
            print(f"   应为: {canonical_root}", file=sys.stderr)
            failed += 1

    for sub_path, expected_url in sub_expected.items():
        repo_path = os.path.join(root, sub_path)
        if not os.path.isdir(repo_path):
            continue
        result = _git(["remote", "get-url", "origin"], repo_path)
        if result.returncode != 0:
            continue
        actual = result.stdout.strip()
        if not _matches(actual, expected_url):
            print(
                f"❌ {repo_path} origin 指向异常: {actual}",
                file=sys.stderr,
            )
            print(f"   应为: {expected_url}", file=sys.stderr)
            failed += 1

    return 1 if failed > 0 else 0


if __name__ == "__main__":
    sys.exit(main())

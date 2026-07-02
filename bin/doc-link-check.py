#!/usr/bin/env python3
"""Check local Markdown links in workspace entry documents.

This intentionally scans the small, agent-facing documentation surface instead
of every historical note under .omo/. The goal is to keep the runnable contract
clean without turning archived knowledge into noisy gate failures.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from urllib.parse import unquote, urlsplit


WORKSPACE = Path(__file__).resolve().parents[1]
LINK_RE = re.compile(r"(?<!!)\[[^\]]+\]\(([^)]+)\)")
LOCAL_DOC_GLOBS = (
    "AGENTS.md",
    "CLAUDE.md",
    "README.md",
    "ARCHITECTURE.md",
    "LAYER-INDEX.md",
    "projects/AGENTS.md",
    "projects/*/AGENTS.md",
    "projects/*/CLAUDE.md",
    "projects/*/README.md",
)
IGNORED_SCHEMES = {
    "http",
    "https",
    "mailto",
    "app",
    "bos",
    "file",
}


def iter_docs() -> list[Path]:
    seen: set[Path] = set()
    docs: list[Path] = []
    for pattern in LOCAL_DOC_GLOBS:
        for path in WORKSPACE.glob(pattern):
            if not path.is_file():
                continue
            resolved = path.resolve()
            if resolved in seen:
                continue
            seen.add(resolved)
            docs.append(path)
    return sorted(docs)


def normalize_target(raw: str) -> str | None:
    target = raw.strip()
    if not target or target.startswith("#"):
        return None
    parsed = urlsplit(target)
    if parsed.scheme in IGNORED_SCHEMES:
        return None
    if parsed.scheme and parsed.scheme not in ("",):
        return None
    path = unquote(parsed.path)
    if not path:
        return None
    return path


def resolve_link(source: Path, target: str) -> Path:
    if target.startswith("/"):
        return WORKSPACE / target.lstrip("/")
    return (source.parent / target).resolve()


def check_file(path: Path) -> list[dict[str, object]]:
    findings: list[dict[str, object]] = []
    text = path.read_text(encoding="utf-8")
    line_starts = [0]
    for match in re.finditer(r"\n", text):
        line_starts.append(match.end())

    for match in LINK_RE.finditer(text):
        raw = match.group(1)
        target = normalize_target(raw)
        if target is None:
            continue
        resolved = resolve_link(path, target)
        if resolved.exists():
            continue
        # generated 派生物 (docs/generated/, gitignored): CI 无, 存在性由生成器保证
        # (project-layer-index --write 等), doc-link-check 不管 -> 跳过 (P0-fix 2026-07-02)
        try:
            if resolved.relative_to(WORKSPACE).parts[:2] == ("docs", "generated"):
                continue
        except ValueError:
            pass
        lineno = 1
        for idx, start in enumerate(line_starts, start=1):
            if start > match.start():
                break
            lineno = idx
        findings.append(
            {
                "file": str(path.relative_to(WORKSPACE)),
                "line": lineno,
                "target": raw,
                "resolved": str(resolved.relative_to(WORKSPACE))
                if resolved.is_relative_to(WORKSPACE)
                else str(resolved),
            }
        )
    return findings


def run() -> dict[str, object]:
    docs = iter_docs()
    findings: list[dict[str, object]] = []
    for doc in docs:
        findings.extend(check_file(doc))
    return {
        "ok": not findings,
        "files_scanned": len(docs),
        "broken_links": len(findings),
        "findings": findings,
    }


def run_files(paths: list[str]) -> dict[str, object]:
    """scope 模式: 只检查指定文件的链接 (worktree-aware, 避免子模块未 init 误报).

    用于 GaC gate 非-strict 模式: pre-commit 只查 staged 文档的链接,
    agent 没碰的文档既有断链不计 (CI strict 跑全量兜底).
    """
    seen: set[Path] = set()
    docs: list[Path] = []
    for raw in paths:
        path = WORKSPACE / raw
        if not path.is_file():
            continue
        resolved = path.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        docs.append(path)
    findings: list[dict[str, object]] = []
    for doc in docs:
        findings.extend(check_file(doc))
    return {
        "ok": not findings,
        "files_scanned": len(docs),
        "broken_links": len(findings),
        "findings": findings,
        "scoped": True,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Check local links in agent-facing Markdown docs")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON")
    parser.add_argument(
        "--files",
        nargs="*",
        default=[],
        help="scope 模式: 只查指定文件链接 (默认扫所有 agent-facing docs; GaC gate 非-strict 用此模式避免 worktree 子模块未 init 误报)",
    )
    args = parser.parse_args()

    result = run_files(args.files) if args.files else run()
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif result["ok"]:
        print(f"doc-link-check: PASS ({result['files_scanned']} files)")
    else:
        for finding in result["findings"]:
            print(
                f"{finding['file']}:{finding['line']}: broken link "
                f"{finding['target']} -> {finding['resolved']}"
            )
        print(f"doc-link-check: FAIL ({result['broken_links']} broken links)")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())

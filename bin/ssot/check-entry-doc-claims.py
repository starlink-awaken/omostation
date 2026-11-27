#!/usr/bin/env python3
"""入口文档的事实性断言核对 —— 死链 / 失效相对路径 / 未登记 BOS URI。

背景 (2026-11-27): 入口文档的真复审最初靠人读, 但绝大多数失真其实是**可机检的
客观事实** —— 链接指向不存在的文件、路径写错层级或缺前缀、URI 没进登记面。首次
全量审计在 109 份入口文档里扫出 86 条命中（校准判据后 67 条真失真）, 修完后归零。
本脚本把那次一次性审计变成可持续判据, 让同类漂移下次被**报出来**, 而不是靠某次
人工复审偶然撞上。

判定（只报可判定的客观失真, 不做文风判断）:
  1. dead_link          markdown 相对链接的目标不存在（跳过 http/mailto）
  2. missing_path      反引号包裹、形如文件路径且以已知后缀结尾, 但在
                       **子模块根** 与 **工作区根** 两个基准下都不存在
                       （仓内文档两种写法都存在, 单用其一会大量误报）
  3. unregistered_uri  `bos://...` 未出现在登记面
                       （projects/agora/etc/bos-services.yaml → capability-registry;
                       支持 `bos://domain/*` 通配写法）

刻意**不**算作失真的:
  - `.omo/state/**` / `.omo/_delivery/**`: 运行态面, 本就不入库
    （AGENTS.md §7: `.omo/state/system.yaml` 已摘库, 需按需物化）;
  - 无后缀或含 `*` 的反引号 token: 多是配置键/概念名, 不是路径。

默认 advisory: 有 finding 也 exit 0（只报告）。是否阻断由 registry 的 gate 标注
与调用方决定, 不靠本脚本的退出码隐式表达（`--block` 仅供本地显式使用）。

用法:
  python3 bin/ssot/check-entry-doc-claims.py [--json] [--surface project-entry]
                                        [--workspace PATH] [--block]
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
REGISTRY_REL = Path(".omo/_truth/registry/document-governance.yaml")
CAPABILITY_REGISTRY_REL = Path("docs/generated/capability-registry.yaml")

RUNTIME_STATE_PREFIXES = (".omo/state/", ".omo/_delivery/")
PATH_SUFFIXES = (
    ".md", ".py", ".yaml", ".yml", ".sh", ".toml", ".json",
    ".ts", ".tsx", ".js", ".jsx",
)
LINK_RE = re.compile(r"\[[^\]]*\]\(([^)]+)\)")
PATH_RE = re.compile(r"`([A-Za-z0-9_][A-Za-z0-9_./-]*/[A-Za-z0-9_./-]+)`")
URI_RE = re.compile(r"`(bos://[A-Za-z0-9_./*-]+)`")
PARENT_RE = re.compile(r"^(?:\.\./)+")

# 显式抑制的**已知非失真**, 每条须写理由 —— 让判据保持零噪声, 同时不把例外藏起来。
# 新增一条前先问: 它是不是真的错? 是就改文档, 不是才进这里并写明为什么。
SUPPRESSIONS: dict[tuple[str, str], str] = {
    # 同族 surface 的 fnmatch 模式 `projects/*/AGENTS.md` 会扫进测试夹具
    # (`*` 跨目录)。夹具描述的是**别的**布局, 不是本项目的入口文档。
    (
        "projects/knowledge/gbrain/test/fixtures/openclaw-reference-minimal/AGENTS.md",
        "skills/context-now/SKILL.md",
    ): "测试夹具内容, 非项目入口文档",
    # producer 已规范为 bos://memory/events/card_updated, consumer dual-accept
    # 遗留别名 bos://brain/events/card_updated（ADR-0372 D5 / ADR-0294）—— 文档
    # 就地写明了这一点, 属有意的 legacy 别名而非未登记项。
    (
        "projects/cockpit/AGENTS.md",
        "bos://brain/events/card_updated",
    ): "文档内已注明的 legacy dual-accept 别名",
}


# --------------------------------------------------------------------------- inputs


def _load_yaml(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def surface_patterns(workspace: Path, surface_id: str) -> list[str]:
    reg_path = workspace / REGISTRY_REL
    if not reg_path.is_file():
        return []
    reg = next(
        (d for d in yaml.safe_load_all(reg_path.read_text(encoding="utf-8")) if d and "surfaces" in d),
        {},
    )
    for surface in reg.get("surfaces", []):
        if surface.get("id") == surface_id:
            return list(surface.get("patterns", []))
    return []


def registered_uris(workspace: Path) -> set[str]:
    path = workspace / CAPABILITY_REGISTRY_REL
    if not path.is_file():
        return set()
    uris: set[str] = set()

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            for value in node.values():
                if isinstance(value, str) and value.startswith("bos://"):
                    uris.add(value)
                else:
                    walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    walk(_load_yaml(path).get("bos_services"))
    return uris


def uri_registered(uri: str, known: set[str]) -> bool:
    if uri.endswith("/*"):
        prefix = uri[:-1]
        return any(u.startswith(prefix) for u in known)
    return uri in known


def matched_docs(workspace: Path, patterns: list[str]) -> list[tuple[Path, Path]]:
    """[(子模块目录, 文档绝对路径)] —— 命中任一 pattern 的已跟踪文档。"""
    out = subprocess.run(
        ["git", "ls-tree", "-r", "HEAD", "--", "projects/"],
        cwd=workspace, capture_output=True, text=True,
    ).stdout
    links: dict[str, str] = {}
    for line in out.splitlines():
        meta, path = line.split("\t", 1)
        mode, _otype, sha = meta.split()
        if mode == "160000":
            links[path] = sha
    docs: list[tuple[Path, Path]] = []
    for repo, sha in sorted(links.items()):
        files = subprocess.run(
            ["git", "-C", str(workspace / repo), "ls-tree", "-r", "--name-only", sha],
            capture_output=True, text=True,
        ).stdout.split()
        for name in files:
            rel = f"{repo}/{name}"
            if not name.endswith((".md", ".markdown")):
                continue
            if any(fnmatch.fnmatchcase(rel, p) for p in patterns):
                docs.append((workspace / repo, workspace / rel))
    return docs


# ------------------------------------------------------------------------- checks


def check_doc(doc: Path, repo_root: Path, workspace: Path, known: set[str]) -> list[dict[str, str]]:
    text = doc.read_text(encoding="utf-8", errors="replace")
    found: list[dict[str, str]] = []

    for link in LINK_RE.findall(text):
        target = link.split("#")[0]
        if not target or target.startswith(("http:", "https:", "mailto:")):
            continue
        if PARENT_RE.sub("", target).startswith(RUNTIME_STATE_PREFIXES):
            continue
        if not (doc.parent / target).resolve().exists():
            found.append({"rule": "dead_link", "detail": link})

    for token in PATH_RE.findall(text):
        if token.startswith(("bos://", "http")) or "*" in token or not token.endswith(PATH_SUFFIXES):
            continue
        if PARENT_RE.sub("", token).startswith(RUNTIME_STATE_PREFIXES):
            continue
        if (repo_root / token).exists() or (workspace / token).exists():
            continue
        found.append({"rule": "missing_path", "detail": token})

    for uri in URI_RE.findall(text):
        if not uri_registered(uri, known):
            found.append({"rule": "unregistered_uri", "detail": uri})

    return found


# ---------------------------------------------------------------------------- main


def run(
    workspace: Path | None = None,
    surface: str = "project-entry",
    block: bool = False,
) -> tuple[dict[str, Any], int]:
    workspace = (workspace or REPO_ROOT).resolve()
    patterns = surface_patterns(workspace, surface)
    if not patterns:
        print(f"❌ surface {surface!r} 不存在或没有 patterns", file=sys.stderr)
        return {}, 2
    known = registered_uris(workspace)
    if not known:
        print(f"⚠️  读不到登记面 {CAPABILITY_REGISTRY_REL} —— URI 项跳过（不算通过）", file=sys.stderr)

    findings: list[dict[str, str]] = []
    suppressed: list[dict[str, str]] = []
    docs = matched_docs(workspace, patterns)
    for repo_root, doc in docs:
        rel = doc.relative_to(workspace).as_posix()
        for item in check_doc(doc, repo_root, workspace, known):
            entry = {"path": rel, "rule": item["rule"], "detail": item["detail"]}
            reason = SUPPRESSIONS.get((rel, item["detail"]))
            if reason:
                suppressed.append({**entry, "reason": reason})
            else:
                findings.append(entry)

    report = {
        "ok": not findings,
        "mode": "block" if block else "advisory",
        "surface": surface,
        "docs_scanned": len(docs),
        "registry_loaded": bool(known),
        "findings": findings,
        "suppressed": suppressed,
        "summary": {"total": len(findings), "suppressed": len(suppressed)},
    }
    return report, (1 if findings and block else 0)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="机器可读输出")
    parser.add_argument("--surface", default="project-entry", help="文档治理 surface id")
    parser.add_argument("--workspace", default=None, help="工作区根（默认脚本所在检出）")
    parser.add_argument("--block", action="store_true", help="有 finding 时 exit 1（默认只报告）")
    args = parser.parse_args(argv)
    report, rc = run(
        workspace=Path(args.workspace) if args.workspace else None,
        surface=args.surface,
        block=args.block,
    )
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(
            f"doc-claims[{args.surface}] docs={report['docs_scanned']} "
            f"findings={len(report['findings'])} mode={report['mode']}"
        )
        for f in report["findings"]:
            print(f"  ⚠️  [{f['rule']}] {f['path']}: {f['detail']}")
    return rc


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""BOS 路由对齐校验 CLI — ecos M1 YAML ↔ agora POC_SERVICES.

用法:
    python scripts/check-bos-alignment.py

退出码:
    0 = 完全对齐
    1 = 存在差异 (POC-only / YAML-only)
"""
from __future__ import annotations

import fnmatch
import re
import sys
from pathlib import Path

import yaml

# ── ANSI ────────────────────────────────────────────
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"
DIM = "\033[2m"

# ── 路径 ───────────────────────────────────────────
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
BOSROUTE_DIR = PROJECT_ROOT / "src" / "ecos" / "ssot" / "mof" / "m1" / "bosroute"
AGORA_BOS_RESOLVER_PATH = (
    Path("/Users/xiamingxing/Workspace/projects/agora/src/agora/mcp/bos_resolver.py")
)
_CANONICAL_PERSONA_BRIDGE_URI_PREFIX = "bos://persona/sot-bridge-persona/"


# ── 核心逻辑 ────────────────────────────────────────


def _extract_uri_from_name(name: str) -> str:
    name = str(name).strip().strip("\"'")
    if "→" in name:
        name = name.split("→", 1)[0].strip()
    return name.strip()


def _glob_match_uri(uri: str, pattern: str) -> bool:
    if "**" in pattern:
        return uri.startswith(pattern.replace("**", ""))
    return fnmatch.fnmatch(uri, pattern)


def collect_yaml_uris() -> list[dict]:
    results: list[dict] = []
    if not BOSROUTE_DIR.is_dir():
        print(f"{RED}❌ BOSROUTE_DIR 不存在: {BOSROUTE_DIR}{RESET}")
        return results
    for path in sorted(BOSROUTE_DIR.glob("BOSROUTE-*.yaml")):
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
        except Exception as exc:
            print(f"{DIM}  ⚠ YAML 解析失败: {path.name} — {exc}{RESET}")
            continue
        if not data:
            continue
        raw_name = data.get("name", "")
        if not raw_name:
            continue
        uri = _extract_uri_from_name(raw_name)
        results.append({
            "file": path.name,
            "uri": uri,
            "description": data.get("description", ""),
            "type": data.get("type", ""),
            "status": data.get("status", ""),
            "domain": data.get("domain", ""),
            "layer": data.get("layer", ""),
        })
    return results


def load_poc_services_from_file() -> dict[str, dict]:
    path = AGORA_BOS_RESOLVER_PATH
    if not path.exists():
        print(f"{RED}❌ POC_SERVICES 源文件不存在: {path}{RESET}")
        return {}
    source = path.read_text(encoding="utf-8")
    keys: list[str] = []

    # string literal keys: "bos://memory/kos/search":
    for m in re.finditer(r'''^\s{4}"(bos://[^"]+)":\s*BosService\(''', source, re.MULTILINE):
        keys.append(m.group(1))

    # f-string keys: f"{PREFIX}recall-entity":
    for m in re.finditer(r'''^\s{4}f"(?:\{[^}]+\})([^"]+)":\s*BosService\(''', source, re.MULTILINE):
        keys.append(_CANONICAL_PERSONA_BRIDGE_URI_PREFIX + m.group(1))

    return {k: {"uri": k} for k in keys}


def categorize(yaml_entries: list[dict], poc_uris: dict[str, dict]) -> dict:
    matched: list[tuple] = []
    poc_matched: set[str] = set()
    yaml_matched: set[int] = set()

    for idx, yaml_entry in enumerate(yaml_entries):
        yaml_uri = yaml_entry["uri"]
        for poc_uri in poc_uris:
            if _glob_match_uri(poc_uri, yaml_uri):
                matched.append((poc_uri, yaml_uri, yaml_entry["file"]))
                poc_matched.add(poc_uri)
                yaml_matched.add(idx)

    poc_only = [u for u in poc_uris if u not in poc_matched]
    yaml_only = [e for i, e in enumerate(yaml_entries) if i not in yaml_matched]

    return {
        "matched": matched,
        "poc_only": poc_only,
        "yaml_only": yaml_only,
        "summary": {
            "poc_total": len(poc_uris),
            "yaml_total": len(yaml_entries),
            "matched_count": len(matched),
            "poc_only_count": len(poc_only),
            "yaml_only_count": len(yaml_only),
        },
    }


# ── 输出 ────────────────────────────────────────────


def print_header(summary: dict) -> None:
    print()
    print(f"{BOLD}{'═' * 70}{RESET}")
    print(f"{BOLD}  BOS 路由对齐校验  —  YAML ↔ POC_SERVICES{RESET}")
    print(f"{BOLD}{'═' * 70}{RESET}")
    print(f"  📂 YAML 模式:      {CYAN}{summary['yaml_total']:>4}{RESET}")
    print(f"  📦 POC 路由:       {CYAN}{summary['poc_total']:>4}{RESET}")
    print(f"  ✅ 匹配:           {GREEN}{summary['matched_count']:>4}{RESET}")
    print(f"  🟡 YAML-only:      {YELLOW}{summary['yaml_only_count']:>4}{RESET}")
    print(f"  🔴 POC-only:       {RED if summary['poc_only_count'] else GREEN}{summary['poc_only_count']:>4}{RESET}")


def print_poc_only(poc_only: list[str]) -> None:
    if not poc_only:
        print(f"\n{GREEN}  ✅ 无 POC-only 路由{RESET}")
        return
    print(f"\n{RED}{BOLD}  🔴 POC-only (YAML 缺失) — {len(poc_only)} 条{RESET}")
    print(f"{DIM}  {'─' * 66}{RESET}")
    for i, uri in enumerate(poc_only, 1):
        print(f"  {RED}  {i:3d}. {uri}{RESET}")
    print()


def print_yaml_only(yaml_only: list[dict]) -> None:
    if not yaml_only:
        print(f"\n{GREEN}  ✅ 无 YAML-only 路由{RESET}")
        return
    print(f"\n{YELLOW}{BOLD}  🟡 YAML-only (POC 缺失) — {len(yaml_only)} 条{RESET}")
    print(f"{DIM}  {'─' * 66}{RESET}")
    for i, entry in enumerate(yaml_only, 1):
        tags = " ".join(
            t for t in [
                f"[{entry['layer']}]" if entry["layer"] else "",
                f"({entry['domain']})" if entry["domain"] else "",
                f"<{entry['status']}>" if entry["status"] else "",
            ] if t
        )
        print(f"  {YELLOW}  {i:3d}. {entry['uri']:50s}  {DIM}{tags}{RESET}")
        print(f"  {DIM}       └─ {entry['file']}{RESET}")
    print()


def print_matched(matched: list[tuple[str, str, str]]) -> None:
    if not matched:
        return
    shown = min(20, len(matched))
    print(f"\n{GREEN}{BOLD}  ✅ 匹配明细 (前 {shown}/{len(matched)}){RESET}")
    print(f"{DIM}  {'─' * 66}{RESET}")
    for poc_uri, yaml_uri, yaml_file in matched[:shown]:
        print(f"  {GREEN}  ✓ {poc_uri}{RESET}")
        print(f"  {DIM}      ← {yaml_uri:45s} ({yaml_file}){RESET}")
    if len(matched) > shown:
        print(f"  {DIM}  ... 还有 {len(matched) - shown} 条{RESET}")
    print()


def print_verdict(summary: dict) -> bool:
    has_gap = summary["poc_only_count"] > 0 or summary["yaml_only_count"] > 0
    gap_total = summary["poc_only_count"] + summary["yaml_only_count"]
    print(f"{BOLD}{'═' * 70}{RESET}")
    if has_gap:
        print(f"  {YELLOW}{BOLD}⚠️  发现 {gap_total} 处差异{RESET}")
        print(f"  {DIM}  ℹ  非阻塞告警 — 部分路由是仅 ecos 或仅 agora 的合法状态{RESET}")
    else:
        print(f"  {GREEN}{BOLD}✅  完全对齐 — 零差异{RESET}")
    print(f"{BOLD}{'═' * 70}{RESET}\n")
    return not has_gap


# ── 主入口 ──────────────────────────────────────────


def main() -> int:
    yaml_routes = collect_yaml_uris()
    if not yaml_routes:
        return 1
    print(f"  {GREEN}✓ {len(yaml_routes)} 个 YAML 路由{RESET}")

    poc_services = load_poc_services_from_file()
    if not poc_services:
        return 1
    print(f"  {GREEN}✓ {len(poc_services)} 条 POC 路由{RESET}")

    result = categorize(yaml_routes, poc_services)
    summary = result["summary"]

    print_header(summary)
    print_poc_only(result["poc_only"])
    print_yaml_only(result["yaml_only"])
    print_matched(result["matched"])
    fully_aligned = print_verdict(summary)

    return 0 if fully_aligned else 1


if __name__ == "__main__":
    sys.exit(main())

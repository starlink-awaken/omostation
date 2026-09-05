#!/usr/bin/env python3
"""check-mcp-bos-uri-completeness.py — BET-Y1Q4-T6-19

Validates that every registered MCP tool has complete URI data (tool_name,
server, transport) and that the tool/server names are unique across the
registry. Also cross-checks BOS domain URIs against the standard.

Exit codes:
  0 — all checks pass
  1 — missing required field (tool_name / server / project)
  2 — duplicate tool_name or server detected
  3 — BOS URI not in standard domains
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

WS = Path(__file__).resolve().parents[2]
MCP_DIR = WS / "projects/ecos/src/ecos/ssot/mof/m1/mcptool"
BOS_STANDARD = WS / ".omo/standards/bos-uri-domain-standard.md"


def _load_bos_domains_from_standard() -> set[str]:
    """从 bos-uri-domain-standard.md 解析所有 bos://<domain>/ 条目"""
    domains: set[str] = set()
    if not BOS_STANDARD.exists():
        return domains
    text = BOS_STANDARD.read_text(encoding="utf-8", errors="ignore")
    # 匹配 `bos://<name>/` 或 ``bos://<name>``
    for m in re.finditer(r"`bos://([a-z][a-z0-9_-]+)/`", text):
        domains.add(m.group(1))
    return domains


VALID_DOMAINS = _load_bos_domains_from_standard()


def _parse_simple_yaml(content: str) -> dict:
    """轻量 yaml 解析 — 仅 key: value 单层"""
    result: dict[str, str] = {}
    for line in content.splitlines():
        line_strip = line.rstrip()
        if not line_strip or line_strip.startswith("#"):
            continue
        if line_strip.startswith("  ") or line_strip.startswith("- "):
            continue
        if ":" in line_strip:
            key, _, value = line_strip.partition(":")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and value:
                result[key] = value
    return result


def check_mcp_completeness(workspace: Path):
    """返回 (issues, total, tools, servers)"""
    issues: list[str] = []
    if not MCP_DIR.exists():
        return issues, 0, 0, 0

    seen_tools: dict[str, str] = {}
    seen_servers: dict[str, str] = {}
    total = 0

    for yaml_file in sorted(MCP_DIR.glob("MCPTOOL-*.yaml")):
        total += 1
        try:
            content = yaml_file.read_text(encoding="utf-8")
            data = _parse_simple_yaml(content)
        except Exception as e:
            issues.append(f"{yaml_file.name}: parse error {e}")
            continue

        tool_id = data.get("id", yaml_file.stem)
        tool_name = data.get("tool_name", "").strip()
        server = data.get("server", "").strip()
        project = data.get("project", "").strip()
        transport = data.get("transport", "").strip()

        if not tool_name:
            issues.append(f"{tool_id}: tool_name empty")
        if not server:
            issues.append(f"{tool_id}: server empty")
        if not project:
            issues.append(f"{tool_id}: project empty")
        if not transport:
            issues.append(f"{tool_id}: transport empty")

        if tool_name:
            if tool_name in seen_tools:
                issues.append(f"{tool_id}: duplicate tool_name {tool_name!r} (also {seen_tools[tool_name]})")
            else:
                seen_tools[tool_name] = tool_id
        if server:
            if server in seen_servers:
                issues.append(f"{tool_id}: duplicate server {server!r} (also {seen_servers[server]})")
            else:
                seen_servers[server] = tool_id

    return issues, total, len(seen_tools), len(seen_servers)


def check_bos_uri_standard(workspace: Path):
    """校验 bos:// URI 引用的 domain 都在标准内, 返回 (issues, domains)"""
    issues: list[str] = []
    domains_seen: set[str] = set()
    if not BOS_STANDARD.exists():
        return issues, domains_seen  # standard not present, skip silently

    # 扫所有 yaml/md 文件里的 bos:// URI
    uri_re = re.compile(r"bos://([a-zA-Z0-9_-]+)/")
    for ext in ("*.yaml", "*.md"):
        for f in workspace.rglob(ext):
            if "/.git/" in str(f) or "/node_modules/" in str(f):
                continue
            try:
                content = f.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue
            for m in uri_re.finditer(content):
                domains_seen.add(m.group(1))

    for d in sorted(domains_seen):
        if d not in VALID_DOMAINS:
            issues.append(f"BOS domain {d!r} not in standard ({sorted(VALID_DOMAINS)})")

    return issues, domains_seen


def main() -> int:
    parser = argparse.ArgumentParser(description="MCP/BOS URI completeness check")
    parser.add_argument("--workspace", default=str(WS), help="workspace root")
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    parser.add_argument("--mcp-only", action="store_true", help="only check MCP tools")
    parser.add_argument("--bos-only", action="store_true", help="only check BOS URIs")
    parser.add_argument("--warn", action="store_true",
                        help="exit 0 even when issues found (audit-only mode)")
    args = parser.parse_args()

    ws = Path(args.workspace).resolve()
    mcp_issues, mcp_total, mcp_tools, mcp_servers = check_mcp_completeness(ws)
    bos_issues, bos_domains = check_bos_uri_standard(ws)

    all_issues = []
    if not args.bos_only:
        all_issues.extend(mcp_issues)
    if not args.mcp_only:
        all_issues.extend(bos_issues)

    if args.json:
        import json
        print(json.dumps({
            "mcp": {"total": mcp_total, "tools": mcp_tools, "servers": mcp_servers, "issues": mcp_issues},
            "bos": {"domains": sorted(bos_domains), "issues": bos_issues},
            "passed": not all_issues,
        }, indent=2, ensure_ascii=False))
    else:
        print(f"MCPTOOL 节点: {mcp_total} 个 (工具 {mcp_tools}, server {mcp_servers})")
        print(f"BOS domains:   {len(bos_domains)} 个 ({', '.join(sorted(bos_domains))})")
        print()
        if all_issues:
            print(f"❌ {len(all_issues)} 个问题:")
            for issue in all_issues:
                print(f"   - {issue}")
            if args.warn:
                print()
                print("⚠️  --warn 模式: 视作审计信号, 不阻断 (exit 0)")
                return 0
            # exit code by category
            if any("duplicate" in i for i in all_issues):
                return 2
            if any("not in standard" in i for i in all_issues):
                return 3
            return 1
        else:
            print("✅ 全部 PASS")

    return 0


if __name__ == "__main__":
    sys.exit(main())

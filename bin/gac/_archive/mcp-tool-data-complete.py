#!/usr/bin/env python3
"""mcp-tool-data-complete.py — 治本 MCPTOOL 节点数据完整性 (Round 4a)

19 个 MCPTOOL 节点 .tool_name / .server 字段是空字符串占位.
Round 4a 把它们填回真实值:
  - .tool_name 从 .name 派生 (MCPTOOL-COCKPIT-cards_check.yaml → cards_check,
    或 .tool_name 已有非空值则保留)
  - .server 从 .project 字段推导 (c2g / gbrain / metaos / omo / runtime / model-driven),
    或从 MCPTOOL-{SERVER}-xxx.yaml 文件名第一段推

约束 (P52/P72):
- 仅改空值字段, 非空保留
- 不动 type/name/id/description 等其他字段
- dry-run 默认
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

WS = Path(__file__).resolve().parents[1]
MCP_DIR = WS / "projects/ecos/src/ecos/ssot/mof/m1/mcptool"


def _parse_simple_yaml(content: str) -> dict:
    """轻量 yaml 解析 (仅 key: value 风格, 不依赖 PyYAML)"""
    result: dict[str, str] = {}
    in_props = False
    for line in content.splitlines():
        line_strip = line.rstrip()
        if not line_strip or line_strip.startswith("#"):
            continue
        # properties 块
        if line_strip == "properties:":
            in_props = True
            continue
        if in_props and not line_strip.startswith("  "):
            in_props = False
        if in_props:
            m = re.match(r"^\s+([a-z_]+):\s*(.*?)\s*$", line_strip)
            if m:
                key = m.group(1)
                val = m.group(2).strip()
                if val.startswith('"') and val.endswith('"'):
                    val = val[1:-1]
                elif val.startswith("'") and val.endswith("'"):
                    val = val[1:-1]
                result[key] = val
            continue
        # 顶层
        m = re.match(r"^([a-z_]+):\s*(.*?)\s*$", line_strip)
        if m:
            key = m.group(1)
            val = m.group(2).strip()
            if val.startswith('"') and val.endswith('"'):
                val = val[1:-1]
            elif val.startswith("'") and val.endswith("'"):
                val = val[1:-1]
            result[key] = val
    return result


def _derive_tool_name(mcp_id: str, props: dict) -> str:
    """tool_name 派生规则 (语义为端点, 例 'cards_check' / 'analysis'):

    1. props.tool_name 非空 → 保留

    2. 单段 prefix ID (MCPTOOL-C2G / MCPTOOL-ECOS / MCPTOOL-METAOS)
       单段 = 没 suffix 时, 使用 props.server (即 project)

    3. 多段 prefix (MCPTOOL-MODEL-DRIVEN): 用 prefix 转 lowercase
       e.g. MCPTOOL-MODEL-DRIVEN → 'model-driven'
            MCPTOOL-L4-KERNEL-DOMAIN → 'l4-kernel'
       (这种命名风格: prefix 表 server 类别, suffix 表工具名)
       这里特殊处理: 取 prefix + suffix 拼接转 lowercase

    4. 普通 prefix + suffix (MCPTOOL-GBRAIN-ANALYSIS) → suffix 转 lowercase
    """
    # 1. 已有非空
    if props.get("tool_name", "").strip():
        return props["tool_name"]

    # 2. 单段 prefix (MCPTOOL-XYZ) → 用 server
    m_single = re.match(r"^MCPTOOL-([A-Z]+)$", mcp_id)
    if m_single:
        return m_single.group(1).lower()  # e.g. METAOS → metaos

    # 3-4. 多段 prefix + suffix
    m = re.match(r"^MCPTOOL-([A-Z]+(?:-[A-Z]+)*)-(.+)$", mcp_id)
    if m:
        prefix, suffix = m.group(1), m.group(2)
        # 复合 prefix: L4-KERNEL, MODEL-DRIVEN → tool_name 用复合 prefix
        if "-" in prefix:
            return prefix.lower()  # L4-KERNEL → l4-kernel
        # 普通 prefix: 用 suffix (tool端点名)
        return suffix.lower()  # GBRAIN-ANALYSIS → analysis

    return mcp_id.lower()


def _derive_server(mcp_id: str, props: dict) -> str:
    """server 派生规则:
    1. props.server 非空 → 保留
    2. props.project 非空 → 保留
    3. 从 MCPTOOL-{prefix}-{suffix} 提取 prefix (lowercase)
    """
    if props.get("server", "").strip():
        return props["server"]
    if props.get("project", "").strip():
        return props["project"]
    # 3. 派生
    m = re.match(r"^MCPTOOL-([A-Z]+(?:-[A-Z]+)*)-(.+)$", mcp_id)
    if m:
        return m.group(1).lower()  # COCKPIT → cockpit
    # 4. 特殊映射
    special = {"GBRAIN": "gbrain", "MODEL-DRIVEN": "model-driven",
               "L4-KERNEL": "l4-kernel", "FORGE": "forge"}
    for prefix, server in special.items():
        if mcp_id.startswith(f"MCPTOOL-{prefix}"):
            return server
    return ""


def find_incomplete() -> list[tuple[Path, str, str, str, str]]:
    """返回 (path, current_tool_name, current_server, new_tool_name, new_server)

    跳过 (Round 4a ADR-0145):
      - MCPTOOL 集合 yaml (有 `tool_count` 或 `tools:` 字段):
        mof-validate 也跳过这些 (容器占位). 不强填 tool_name/server.
      - MCPTOOL 已有非空 tool_name + server: 跳过 (已经合规).
    """
    results: list[tuple] = []
    for f in sorted(MCP_DIR.glob("*.yaml")):
        content = f.read_text()
        # 跳过 MCPTOOL 集合 yaml (有 tool_count 或 tools: 列表)
        if re.search(r"^tool_count:\s*\d+", content, re.MULTILINE):
            continue
        if re.search(r"^tools:\s*$", content, re.MULTILINE):
            continue
        # 用正则找 id 行避免全 yaml 解析
        id_m = re.search(r"^id:\s*(.+)$", content, re.MULTILINE)
        if not id_m:
            continue
        mcp_id = id_m.group(1).strip()
        if not mcp_id.startswith("MCPTOOL-"):
            continue
        # 提取 properties.tool_name / properties.server
        tn_m = re.search(r"^\s*tool_name:\s*['\"]?(.*?)['\"]?\s*$", content, re.MULTILINE)
        sv_m = re.search(r"^\s*server:\s*['\"]?(.*?)['\"]?\s*$", content, re.MULTILINE)
        cur_tn = tn_m.group(1).strip() if tn_m else ""
        cur_sv = sv_m.group(1).strip() if sv_m else ""

        # 解析需要的最小字段
        proj_m = re.search(r"^project:\s*(.+)$", content, re.MULTILINE)
        proj_val = proj_m.group(1).strip() if proj_m else ""

        name_m = re.search(r"^name:\s*(.+)$", content, re.MULTILINE)
        name_val = name_m.group(1).strip() if name_m else ""

        # 计算新值 (仅当旧值为空时覆盖)
        new_tn = ""
        new_sv = ""
        if not cur_tn:
            new_tn = _derive_tool_name(mcp_id, {"tool_name": "", "name": name_val})
        if not cur_sv:
            new_sv = _derive_server(mcp_id, {"server": "", "project": proj_val})

        if (new_tn or new_sv) and (not cur_tn or not cur_sv):
            results.append((f, cur_tn, cur_sv, new_tn, new_sv))
    return results


def migrate_file(path: Path, cur_tn: str, cur_sv: str, new_tn: str, new_sv: str, apply: bool = False) -> bool:
    """单文件 migration, 返回 True 表示有改"""
    content = path.read_text()
    new_content = content
    if new_tn:
        # 替换 `tool_name: ""` 或 `tool_name:` (空值), 跟上下文
        new_content = re.sub(
            r"^(\s*)tool_name:\s*['\"]?['\"]?\s*$",
            rf"\1tool_name: '{new_tn}'",
            new_content,
            count=1,
            flags=re.MULTILINE,
        )
    if new_sv:
        new_content = re.sub(
            r"^(\s*)server:\s*['\"]?['\"]?\s*$",
            rf"\1server: '{new_sv}'",
            new_content,
            count=1,
            flags=re.MULTILINE,
        )
    if content == new_content:
        return False
    if apply:
        path.write_text(new_content)
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="应用修改 (默认 dry-run)")
    args = parser.parse_args()

    items = find_incomplete()
    if not items:
        print("✅ 所有 MCPTOOL 节点 tool_name 和 server 均有值")
        return 0

    print(f"发现 {len(items)} 个 MCPTOOL 节点有不完整字段")
    if not args.apply:
        print("(DRY-RUN, 加 --apply 才真改)")
    changed = 0
    for path, cur_tn, cur_sv, new_tn, new_sv in items:
        marker = "✓" if not args.apply else "→"
        ns = f"tool_name: '{new_tn}'" if new_tn else ""
        ss = f"server: '{new_sv}'" if new_sv else ""
        print(f"  {marker} {path.name}: {ns}  {ss}")
        if migrate_file(path, cur_tn, cur_sv, new_tn, new_sv, apply=args.apply):
            changed += 1

    print(f"\n{'已应用' if args.apply else 'DRY-RUN, 待 --apply'}: {changed}/{len(items)}")
    if not args.apply:
        print("\n推荐: uv run --with pyyaml python bin/gac/mcp-tool-data-complete.py --apply")
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""
sediment / precipitate — 沉淀引擎

将操作模式捕获为可复用 Skill（capture），并分析使用频率推荐候选（detect）。

合并自:
  - scripts/sediment-capture.sh
  - scripts/sediment-detect.sh

用法:
  python3 src/sediment.py --help
  python3 src/sediment.py --name my-skill --desc "describe" --steps '["step1"]'
  python3 src/sediment.py --list
  python3 src/sediment.py --approve <candidate-id>
"""

from __future__ import annotations

import argparse
import fcntl
import json
import subprocess
import sys
from datetime import UTC, date, datetime
from typing import cast

from forge.forge_config import FORGE_ROOT, REGISTRY  # type: ignore[import-not-found]

SKILLS_DIR = FORGE_ROOT / "skills"
SCRIPTS_DIR = FORGE_ROOT / "scripts"


# ── 注册表 I/O（带文件锁） ──────────────────────────────────────


def _load_registry() -> dict:
    """读取注册表 JSON（共享锁）。"""
    if not REGISTRY.exists():
        return {"tools": [], "event_log": []}
    with open(REGISTRY) as f:
        fcntl.flock(f, fcntl.LOCK_SH)
        data = json.load(f)
    return cast("dict", data)


def _save_registry(data: dict) -> None:
    """原子保存注册表（.tmp + rename + 排他锁）。"""
    tmp = REGISTRY.with_suffix(".json.tmp")
    tmp.write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    with open(REGISTRY, "a") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        tmp.rename(REGISTRY)


# ── 通用 ────────────────────────────────────────────────────────


def _today() -> str:
    return date.today().isoformat()


def _now_iso() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


# ── capture ─────────────────────────────────────────────────────


def capture(
    name: str,
    description: str,
    steps: list[str],
    example: str = "",
    dry_run: bool = False,
) -> int:
    """
    创建 skills/{name}/SKILL.md 并注册到 tools-registry.json。

    等价于 scripts/sediment-capture.sh 的全部逻辑。
    """
    if not name or not description or not steps:
        print("错误: --name, --desc, --steps 为必填参数")
        return 1

    today = _today()
    skill_dir = SKILLS_DIR / name
    skill_path = skill_dir / "SKILL.md"

    # 预览信息
    print("=== 捕获 Skill ===")
    print(f"  name:        {name}")
    steps_preview = "; ".join(steps[:3])
    print(f"  desc:        {description}")
    print(f"  steps:       {steps_preview}")
    print(f"  dry-run:     {dry_run}")
    print()

    if skill_dir.exists() and not dry_run:
        print(f"警告: Skill 目录已存在: {skill_dir}")
        print("   将覆盖已有文件")

    # ── 生成 SKILL.md 内容（与 shell 版本一致）──
    md_lines = [
        "---",
        f"name: {name}",
        f"description: {description}",
        "type: skill",
        f"created: {today}",
        "tags: [forge, captured]",
        "---",
        "",
        f"# {name}",
        "",
        "## 用途",
        description,
        "",
        "## 步骤",
    ]
    for i, step in enumerate(steps, 1):
        md_lines.append(f"{i}. {step}")

    if example:
        md_lines.extend(["", "## 示例", example])

    skill_content = "\n".join(md_lines) + "\n"

    # ── 检查注册表中是否已存在同名 skill ──
    reg = _load_registry()
    exists = any(t.get("id") == name for t in reg.get("tools", []))

    if dry_run:
        print("dry-run 模式，将创建:")
        print(f"  文件: {skill_path}")
        if not exists:
            print(f"  新注册 type:skill 条目 -> {REGISTRY.name}")
        else:
            print("  跳过注册（已存在）")
        print()
        # 只打印前 10 行预览
        print("=== SKILL.md 预览 ===")
        for line in md_lines[:10]:
            print(line)
        return 0

    # ── 创建技能目录 ──
    skill_dir.mkdir(parents=True, exist_ok=True)
    skill_path.write_text(skill_content, encoding="utf-8")
    print(f"已创建 {skill_path}")

    # ── 追加到注册表 ──
    if not exists:
        entry = {
            "id": name,
            "name": description,
            "type": "skill",
            "status": "active",
            "category": [],
            "capabilities": [description],
            "access": {
                "method": "skill",
                "location": f"skills/{name}/SKILL.md",
                "config_ref": "",
            },
            "source": {
                "type": "self-built",
                "provider": "sediment-capture",
                "url": "",
                "version_tracking": False,
            },
            "cost_model": "free",
            "health": "ok",
            "notes": f"Captured skill: {description}",
            "added": today,
            "updated": today,
            "_discovery": {
                "source": "sediment",
                "first_seen": today,
                "confidence": 0.8,
            },
        }
        reg.setdefault("tools", []).append(entry)

        # 写入 event_log
        reg.setdefault("event_log", []).append(
            {
                "type": "sediment:capture",
                "tool_id": name,
                "summary": f"Captured skill: {name}",
                "timestamp": _now_iso(),
            }
        )

        _save_registry(reg)
        print(f"已注册 {name} 到 {REGISTRY.name}")
    else:
        print(f"注册表中已存在同名 skill: {name}，跳过注册")

    # ── 触发 sync-registry ──
    sync_script = SCRIPTS_DIR / "sync-registry.sh"
    if sync_script.exists():
        try:
            subprocess.run(
                ["bash", str(sync_script)],
                capture_output=True,
                timeout=30,
            )
        except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
            pass  # 失败不阻塞

    return 0


# ── detect ──────────────────────────────────────────────────────


def detect(dry_run: bool = False) -> int:
    """
    分析 tools-registry.json 中的 telemetry 数据，输出沉淀候选。

    规则:
      - 同一工具使用次数 >= 3 次 -> 提示沉淀候选
    """
    candidates = []
    reg = _load_registry()
    tools = reg.get("tools", [])

    # 筛选有使用记录的工具
    used_tools = [t for t in tools if (t.get("telemetry") or {}).get("use_count", 0) > 0]
    used_tools.sort(key=lambda t: t["telemetry"]["use_count"], reverse=True)

    print("=== 频率检测分析 ===")
    print()
    print(f"工具有使用记录: {len(used_tools)}")
    print()

    if not used_tools:
        print("没有足够的 telemetry 数据。")
        print("建议：先使用 MCP server 的 search_tools / get_tool 积累数据")
        print("或等 2 周后再运行频率检测")
        return 0

    # 使用频率 Top 5
    print("使用频率 Top 5:")
    for t in used_tools[:5]:
        tel = t["telemetry"]
        print(f"  {tel['use_count']}次 | {t.get('id', '-')} ({t.get('name', '-')})")

    # 生成候选（>= 3 次）
    candidates = [t for t in used_tools if t["telemetry"]["use_count"] >= 3]
    print()
    print(f"沉淀候选: {len(candidates)} 个")
    for c in candidates:
        cid = c.get("id", "-")
        cc = c["telemetry"]["use_count"]
        print(f"  - {cid} ({cc}次使用) -> 建议沉淀为 skill")

    # 记录检测事件
    if not dry_run:
        reg.setdefault("event_log", []).append(
            {
                "type": "sediment:frequency_pattern",
                "tool_ids": [c.get("id", "") for c in candidates],
                "summary": "Frequency detection completed",
                "timestamp": _now_iso(),
            }
        )
        _save_registry(reg)

    return 0


def approve(candidate_id: str) -> int:
    """
    从注册表中查找工具信息，然后调用 capture 将其固化为 skill。
    """
    print(f"=== 批准候选: {candidate_id} ===")
    reg = _load_registry()
    tools = reg.get("tools", [])

    match = None
    for t in tools:
        if t.get("id") == candidate_id:
            match = t
            break

    if match is None:
        print(f"未找到工具: {candidate_id}")
        return 1

    tname = match.get("name", candidate_id)
    tdesc = (match.get("notes") or "")[:100]
    steps_raw = match.get("capabilities") or [f"使用 {tname}"]
    steps = steps_raw[:]  # 已经是 list

    return capture(
        name=candidate_id,
        description=f"Frequent tool: {tname} - {tdesc}",
        steps=steps,
    )


# ── CLI ─────────────────────────────────────────────────────────


def run(args: list[str] | None = None) -> int:
    """CLI 入口：解析参数并调度 capture / detect 子命令。"""
    parser = argparse.ArgumentParser(
        prog="sediment",
        description="Forge 沉淀引擎 — 捕获操作模式为 Skill 并检测高频候选",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "示例:\n"
            "  python3 src/sediment.py --name check-mcp --desc '查看 MCP 版本' "
            "--steps '[\"cd Workspace/agora && python3 -m agora version\"]'\n"
            "  python3 src/sediment.py --list\n"
            "  python3 src/sediment.py --approve some-tool\n"
        ),
    )

    # capture 参数
    parser.add_argument("--name", help="Skill 名称（kebab-case）")
    parser.add_argument("--desc", help="Skill 描述")
    parser.add_argument(
        "--steps",
        help='步骤数组 JSON，如 \'["step1", "step2"]\'',
    )
    parser.add_argument("--example", help="使用示例", default="")

    # detect / list 参数
    parser.add_argument(
        "--list",
        action="store_true",
        help="分析与列表沉淀候选（detect 模式）",
    )
    parser.add_argument("--approve", help="批准某个候选并固化为 skill")

    # 通用参数
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="只预览，不创建文件",
    )

    parsed = parser.parse_args(args or sys.argv[1:])

    # ── help ──
    if not parsed.name and not parsed.list and not parsed.approve:
        parser.print_help()
        return 0

    # ── approve ──
    if parsed.approve:
        return approve(parsed.approve)

    # ── list / detect ──
    if parsed.list:
        return detect(dry_run=parsed.dry_run)

    # ── capture ──
    if not all([parsed.name, parsed.desc, parsed.steps]):
        print("错误: --name, --desc, --steps 为必填参数")
        parser.print_help()
        return 1

    # 解析 steps JSON
    try:
        steps = json.loads(parsed.steps)
        if not isinstance(steps, list) or not all(isinstance(s, str) for s in steps):
            raise ValueError("steps 必须是字符串数组")
    except (json.JSONDecodeError, ValueError) as e:
        print(f"错误: --steps 必须是 JSON 字符串数组 ({e})")
        return 1

    return capture(
        name=parsed.name,
        description=parsed.desc,
        steps=steps,
        example=parsed.example,
        dry_run=parsed.dry_run,
    )


def main() -> int:
    return run()


if __name__ == "__main__":
    sys.exit(main())

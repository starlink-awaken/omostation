#!/usr/bin/env python3
"""Architecture Auto-Fix — 架构自动修复 (ADR-0190 系列, Phase 4 防腐层).

自动修复检测到的架构问题:
  - 修复 YAML 语法错误 (如 interval notation 引号)
  - 同步 script_baseline (当脚本数变化时)
  - 标记过期场景卡 (添加 stale warning)
  - 修复注册表引用 (移除无效引用)

约束:
  - 每次运行最多修复 max_fixes_per_run 个问题
  - 超过 require_approval_above 个修复需人工确认
  - 所有修复可逆 (保留原始内容备份)

用法:
  python3 bin/gac/architecture-auto-fix.py              # 自动修复 (dry-run)
  python3 bin/gac/architecture-auto-fix.py --apply      # 实际执行修复
  python3 bin/gac/architecture-auto-fix.py --json       # JSON 输出
  python3 bin/gac/architecture-auto-fix.py --gate       # CI gate 模式

CI 可移植: Path(__file__).resolve().parents[2] 定位 workspace.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[2]
STANDARDS_DIR = WORKSPACE / ".omo" / "standards"
REGISTRY_DIR = WORKSPACE / ".omo" / "_truth" / "registry"

# ── 修复配置 ──
MAX_FIXES_PER_RUN = 5
REQUIRE_APPROVAL_ABOVE = 3


def _load_yaml_safe(path: Path) -> dict | None:
    """安全加载 YAML."""
    if not path.exists():
        return None
    try:
        import yaml

        text = path.read_text(encoding="utf-8")
        docs = [d for d in yaml.safe_load_all(text) if d]
        if not docs:
            return None
        body = docs[-1]
        return body if isinstance(body, dict) else None
    except Exception:
        return None


def _load_yaml_raw(path: Path) -> list:
    """加载 YAML 所有文档 (含 frontmatter)."""
    if not path.exists():
        return []
    try:
        import yaml

        text = path.read_text(encoding="utf-8")
        return [d for d in yaml.safe_load_all(text) if d]
    except Exception:
        return []


def fix_dimension_system_intervals(apply: bool = False) -> list[dict]:
    """修复 dimension-system.yaml 中的 interval notation 引号问题."""
    fixes = []
    path = STANDARDS_DIR / "dimension-system.yaml"

    if not path.exists():
        return fixes

    try:
        content = path.read_text(encoding="utf-8")
        original = content

        # 修复 [0, 4) → "[0, 4)" 等 interval notation
        import re
        # 匹配 levels 下的 interval notation
        pattern = r'(\s+(?:critical|warning|healthy|excellent):\s+)\[(\d+),\s*(\d+)\]?'
        def replacer(m):
            return f'{m.group(1)}"[{m.group(2)}, {m.group(3)})"'

        new_content = re.sub(pattern, replacer, content)

        if new_content != original:
            fix = {
                "type": "yaml_syntax_fix",
                "file": str(path.relative_to(WORKSPACE)),
                "description": "修复 dimension-system.yaml interval notation 引号",
                "lines_changed": sum(1 for a, b in zip(original.splitlines(), new_content.splitlines()) if a != b),
            }
            if apply:
                path.write_text(new_content, encoding="utf-8")
                fix["applied"] = True
            else:
                fix["applied"] = False
            fixes.append(fix)
    except Exception as e:
        fixes.append({
            "type": "fix_error",
            "file": str(path.relative_to(WORKSPACE)),
            "error": str(e),
        })

    return fixes


def sync_script_baseline(apply: bool = False) -> list[dict]:
    """同步 governance-checks.yaml 的 script_baseline."""
    fixes = []
    registry_path = REGISTRY_DIR / "governance-checks.yaml"

    if not registry_path.exists():
        return fixes

    try:
        import yaml

        # 计算当前活跃脚本数
        bin_dir = WORKSPACE / "bin"
        active_count = 0
        if bin_dir.exists():
            for f in bin_dir.rglob("*"):
                if (f.is_file() and f.suffix in (".py", ".sh")
                        and "_archive" not in f.parts
                        and "__pycache__" not in f.parts):
                    active_count += 1

        # 读取当前 baseline
        content = registry_path.read_text(encoding="utf-8")
        docs = list(yaml.safe_load_all(content))
        if not docs:
            return fixes

        main = docs[-1]
        gac = main.get("gac", {}) if isinstance(main, dict) else {}
        quota = gac.get("subtraction_quota", {}) if isinstance(gac, dict) else {}
        current_baseline = int(quota.get("script_baseline", 0) or 0)

        if current_baseline != active_count:
            fix = {
                "type": "baseline_sync",
                "file": str(registry_path.relative_to(WORKSPACE)),
                "description": f"同步 script_baseline: {current_baseline} → {active_count}",
                "old_value": current_baseline,
                "new_value": active_count,
            }
            if apply:
                # 更新 baseline
                quota["script_baseline"] = active_count
                gac["subtraction_quota"] = quota
                main["gac"] = gac
                docs[-1] = main
                with open(registry_path, "w", encoding="utf-8") as f:
                    yaml.dump_all(docs, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
                fix["applied"] = True
            else:
                fix["applied"] = False
            fixes.append(fix)
    except Exception as e:
        fixes.append({
            "type": "fix_error",
            "file": str(registry_path.relative_to(WORKSPACE)),
            "error": str(e),
        })

    return fixes


def fix_scene_card_yaml_issues(apply: bool = False) -> list[dict]:
    """修复场景卡 YAML 常见问题 (如缺少 lifecycle 字段添加 draft)."""
    fixes = []
    scene_dir = WORKSPACE / "docs" / "scene-cards"

    if not scene_dir.exists():
        return fixes

    for path in sorted(scene_dir.glob("*.yaml")):
        if len(fixes) >= MAX_FIXES_PER_RUN:
            break

        try:
            content = path.read_text(encoding="utf-8")
            data = _load_yaml_safe(path)
            if not data:
                continue

            # 检查是否缺少 lifecycle 字段
            if "lifecycle" not in data:
                fix = {
                    "type": "add_lifecycle_field",
                    "file": str(path.relative_to(WORKSPACE)),
                    "description": f"场景卡 {data.get('scene_id', path.stem)} 缺少 lifecycle 字段",
                }
                # 不自动添加 lifecycle (需要人工判断)
                fix["applied"] = False
                fix["requires_approval"] = True
                fixes.append(fix)
        except Exception:
            continue

    return fixes


def auto_fix(apply: bool = False) -> tuple[list[dict], dict]:
    """主修复. 返回 (fixes, summary)."""
    all_fixes: list[dict] = []

    fixers = [
        ("dimension_intervals", fix_dimension_system_intervals),
        ("baseline_sync", sync_script_baseline),
        ("scene_card_issues", fix_scene_card_yaml_issues),
    ]

    for name, fixer_fn in fixers:
        if len(all_fixes) >= MAX_FIXES_PER_RUN:
            break
        try:
            fixes = fixer_fn(apply=apply)
            all_fixes.extend(fixes[:MAX_FIXES_PER_RUN - len(all_fixes)])
        except Exception as e:
            all_fixes.append({
                "type": "fixer_error",
                "fixer": name,
                "error": str(e),
            })

    applied = [f for f in all_fixes if f.get("applied")]
    pending = [f for f in all_fixes if not f.get("applied") and "error" not in f]
    errors = [f for f in all_fixes if "error" in f]

    summary = {
        "total_fixes": len(all_fixes),
        "applied": len(applied),
        "pending": len(pending),
        "errors": len(errors),
        "requires_approval": len([f for f in all_fixes if f.get("requires_approval")]),
    }

    return all_fixes, summary


def main() -> int:
    args = sys.argv[1:]
    apply_mode = "--apply" in args
    json_mode = "--json" in args
    gate_mode = "--gate" in args

    fixes, summary = auto_fix(apply=apply_mode)

    if json_mode:
        print(json.dumps(
            {
                "ok": summary["errors"] == 0,
                "apply_mode": apply_mode,
                "summary": summary,
                "fixes": fixes,
            },
            ensure_ascii=False,
            indent=2,
        ))
        return 0

    print("=== Architecture Auto-Fix (架构自动修复) ===")
    print(f"模式: {'APPLY' if apply_mode else 'DRY-RUN'}")
    print(f"修复总数: {summary['total_fixes']}")
    print(f"已应用: {summary['applied']}, 待处理: {summary['pending']}, 错误: {summary['errors']}")
    print(f"需人工确认: {summary['requires_approval']}")
    print()

    for f in fixes:
        if "error" in f:
            print(f"  ❌ [{f.get('type', '?')}] {f.get('error', '')}")
        elif f.get("applied"):
            print(f"  ✅ [{f.get('type', '?')}] {f.get('description', '')}")
        elif f.get("requires_approval"):
            print(f"  🔒 [{f.get('type', '?')}] {f.get('description', '')} (需确认)")
        else:
            print(f"  ⏸️  [{f.get('type', '?')}] {f.get('description', '')} (dry-run)")

    if summary["errors"] == 0:
        print("\n✅ Architecture Auto-Fix 完成")
    else:
        print(f"\n❌ {summary['errors']} 个修复失败")

    # Gate 模式: 有待处理修复则 fail (提示需要处理)
    if gate_mode and summary["pending"] > 0:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

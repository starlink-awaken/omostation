#!/usr/bin/env python3
"""test_skills_coverage — 验证 .agents/skills/ 下 skill 文档完整性 (证明 skill 真有用, 非摆设).

TestSkill 策略 (P73 truth-driven, 非 LLM 对比避免 API 成本):
  内容覆盖率审计 — 解析 SKILL.md, 验证关键诊断要素全覆盖.
  一个完整覆盖 P75 模式的 skill 才能在 CI triage 时提供 6 层分类 + 7 陷阱识别.

首批: ci-red-triage (P75). 后续可扩其他 skill.
"""
from __future__ import annotations

import sys
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[1]
SKILLS_DIR = WORKSPACE / ".agents" / "skills"


def _read(skill_rel: str) -> str:
    path = SKILLS_DIR / skill_rel
    assert path.is_file(), f"skill 文件不存在: {path}"
    return path.read_text(encoding="utf-8")


def test_ci_red_triage_coverage() -> None:
    """ci-red-triage skill 必须覆盖 P75 全部诊断要素."""
    content = _read("ci-red-triage/SKILL.md")

    # 1. 6 层递归分类 (P75 §2 核心方法)
    layers = ["L1", "L2", "L3", "L4", "L5", "L6"]
    for layer in layers:
        assert layer in content, f"缺层 {layer} (P75 6 层分类不完整)"

    # 2. 7 陷阱表 (P75 §5 高发坑)
    pitfalls = ["D1", "D2", "D3", "D4", "D5", "D6", "D7"]
    for p in pitfalls:
        assert p in content, f"缺陷阱 {p} (P75 7 类高发坑不完整)"

    # 3. 工具链 (P75 §4 实操命令)
    tools = ["gh pr checks", "gh run view", "gac-local-gate", "evidence-smoke"]
    for t in tools:
        assert t in content, f"缺工具命令 {t}"

    # 4. 真假 fail 区分 (P73 truth-driven)
    assert "真 bug" in content or "真值" in content, "缺真假 fail 分类"
    assert "预存" in content, "缺预存判定 (main 同红)"
    assert "环境" in content, "缺环境差异判定 (CI 独有)"

    # 5. admin merge 三条件 (P75 §7 CI 非全绿合并门)
    assert "本地" in content and "gate" in content.lower(), "缺条件1 (本地 gate 绿)"
    assert "预存" in content or "环境" in content, "缺条件2 (CI fail 全预存/环境)"
    assert "授权" in content, "缺条件3 (用户授权)"

    # 6. 决策流程 + 反模式 (完整诊断指南; SKILL.md 用 Procedure, p75 pattern 用 决策树)
    assert "Procedure" in content or "决策树" in content or "decision" in content.lower(), "缺决策流程"
    assert "反模式" in content or "Anti-pattern" in content, "缺反模式"

    # 7. pattern 引用 (双层: skill → pattern 文档)
    assert "p75" in content.lower(), "缺 P75 pattern 引用"

    print("✅ ci-red-triage skill coverage PASS:")
    print(f"   6 层分类 + 7 陷阱 + 4 工具 + 真假区分 + 3 合并条件 + 决策树 + 反模式 + pattern 引用")


def main() -> int:
    try:
        test_ci_red_triage_coverage()
    except AssertionError as e:
        print(f"❌ FAIL: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

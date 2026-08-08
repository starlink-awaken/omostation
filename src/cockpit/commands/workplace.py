"""cockpit.commands.workplace — Cockpit CLI Workplace 常驻 Agent 命令处理器."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "projects" / "omo" / "src"))

from omo.digital_brain.memory_bridge import DigitalBrainMemoryBridge
from omo.digital_brain.workplace_agent import WorkplaceAgent


def cmd_workplace(args: Any) -> int:
    agent = WorkplaceAgent(ROOT)
    bridge = DigitalBrainMemoryBridge(ROOT)

    text = getattr(args, "text", "") or "关于开展卫健系统数据收集与工作汇报的通知：请各单位于本周五前上报有关数据。"

    print("=========================================================================")
    print(" 🏢 LifeOS 数字大脑 — Workplace 常驻 Agent 工作流 (Phase 1)")
    print("=========================================================================")

    parsed = agent.parse_notice(text)
    print(f"📌 [解析通知]: {parsed['title']}")
    print(f"   • 任务 ID: {parsed['task_id']} | 截止时限: {parsed['deadline']}")
    print(f"   • 下发对象: {', '.join(parsed['target_units'])}")
    print(f"   • 包含字段: {', '.join(parsed['required_fields'])}")
    print(f"   • 授权等级: {parsed['authorization_level']}")

    pack = agent.generate_distribution_pack(parsed)
    print("\n📝 [拟定下发公文与表格模版草稿]:")
    print("-------------------------------------------------------------------------")
    print(pack["doc_draft"])
    print("-------------------------------------------------------------------------")
    print(f'🗣️ [领导汇报话术预演]:\n  "{pack["briefing_speech"]}"')

    summary = agent.collect_and_summarize(parsed["task_id"])
    print("\n📊 [下级数据自动催收与汇总报告]:")
    print("-------------------------------------------------------------------------")
    print(summary["summary_report"])
    print("-------------------------------------------------------------------------")
    print(f'🗣️ [领导批示与上报话术]:\n  "{summary["leader_approval_talk"]}"')

    mm = bridge.get_user_mental_model()
    print("=========================================================================")
    print(f"🧠 [心智模型同步]: 已载入用户身份 '{mm['background']}' | 规则数: {len(bridge.query_beliefs())}")
    print("=========================================================================")
    return 0

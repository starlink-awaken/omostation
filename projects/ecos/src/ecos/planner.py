from __future__ import annotations

import os

WORKFLOWS = [
    {"id": "WF-001", "name": "需求拆解"},
    {"id": "WF-002", "name": "变更评审"},
    {"id": "WF-003", "name": "巡检告警"},
    {"id": "WF-004", "name": "风险分级"},
    {"id": "WF-005", "name": "知识捕获"},
    {"id": "WF-006", "name": "结果归档"},
    {"id": "WF-007", "name": "恢复演练"},
    {"id": "WF-008", "name": "Kanban SSB Bridge"},
]


def list_available_wfs():
    return list(WORKFLOWS)


def _generic_plan(goal: str) -> dict:
    return {
        "goal": goal,
        "steps": ["需求分析", "现状盘点", "方案设计", "实施验证", "结果复盘"],
        "estimated_time": "2h",
        "total_steps": 5,
        "_source": "rule_based",
    }


def _analyze_with_llm(goal: str) -> dict:
    if not os.environ.get("DEEPSEEK_API_KEY"):
        result = _generic_plan(goal)
        result["_source"] = "llm_error"
        return result
    result = _generic_plan(goal)
    result["_source"] = "llm"
    return result


def analyze_goal(goal: str) -> dict:
    normalized = goal.lower()
    if "部署" in goal and "kos" in normalized:
        return {
            "goal": goal,
            "steps": ["环境检查", "依赖安装", "配置注入", "服务启动", "健康检查"],
            "_source": "keyword",
        }
    if any(keyword in goal for keyword in ("修复", "审计", "整改")):
        return {
            "goal": goal,
            "steps": ["盘点问题", "确定优先级", "修复高风险项", "补验证", "更新基线"],
            "_source": "keyword",
        }
    return _generic_plan(goal)


def generate_plan(goal: str, use_llm: bool = False):
    result = _analyze_with_llm(goal) if use_llm else analyze_goal(goal)
    return result

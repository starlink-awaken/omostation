"""KOS Self API — L4自我层读写。

数据存储: SQLite (~/.kos/self/self.db) with changelog
Backup/backward compat: ~/.kos/self/profile.json
"""

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, cast

import yaml

from kos.self import db  # type: ignore[import-not-found]

SELF_DIR = Path.home() / ".kos" / "self"
PROFILE_PATH = SELF_DIR / "profile.json"
SKILL_FEEDBACK_PATH = SELF_DIR / "skill_feedback.json"
SKILL_REGISTRY_PATH = SELF_DIR / "skills.json"

# Path to domain knowledge_links.yaml (kos/domain/self/knowledge_links.yaml)
KNOWLEDGE_LINKS_PATH = Path(__file__).resolve().parent.parent.parent / "domain" / "self" / "knowledge_links.yaml"

DEFAULT_PROFILE: dict[str, Any] = {
    "version": "v1",
    "person": "老王",
    "roles": [
        {
            "role_id": "role:weijiwei",
            "name": "卫健委信息科工程师",
            "priority": 1,
            "values": ["稳定性 > 新功能", "合规 > 效率"],
            "time_window": "工作日 09:00-18:00",
            "communication_style": "简洁正式",
            "tags": ["政务", "技术管理"],
        },
        {
            "role_id": "role:personal-dev",
            "name": "个人技术开发者/架构师",
            "priority": 2,
            "values": ["架构先行", "理论驱动", "红蓝对抗"],
            "time_window": "晚上+周末",
            "communication_style": "深度技术讨论",
            "tags": ["AI OS", "系统架构"],
        },
        {
            "role_id": "role:family",
            "name": "家庭角色",
            "priority": 3,
            "values": ["低心智负担", "可托管"],
            "time_window": "周末",
            "communication_style": "轻松",
            "tags": ["家事", "孩子"],
        },
    ],
    "vision": {
        "long_term": "蜂群智能体系 — 多人+多Agent集体智慧网络",
        "mid_term": "Workspace 联邦式 AI OS 在个人层面跑通",
        "current_okrs": {
            "Q2_2026": [
                {"kr": "架构收敛 — 4+1+3方案定稿", "progress": 100},
                {"kr": "eCOS Phase 10 全链路稳定", "progress": 100},
                {"kr": "知识管道全自动化", "progress": 60},
                {"kr": "多Agent协作初版跑通", "progress": 0},
            ]
        },
    },
    "principles": [
        {"name": "架构先行，理论驱动", "weight": 0.9, "source_axiom": "逻辑自洽比功能堆砌更重要"},
        {"name": "红蓝对抗，安全第一", "weight": 1.0, "source_axiom": "不可逆操作必须经双人验证"},
        {"name": "隐私绝不外泄", "weight": 1.0, "source_axiom": "私人信息绝对不外泄"},
        {"name": "成本敏感，零token优先", "weight": 0.8, "source_axiom": "资源有限"},
        {"name": "持久对象优于临时运行", "weight": 0.7, "source_axiom": "运行时状态不是唯一真相"},
    ],
    "frameworks": {
        "thinking_stack": "第一性原理 → 理论 → 框架 → 架构 → 场景 → 应用",
        "workflow": "审计 → 规划 → Review → 执行 → 测试 → 再审计 → 清零",
        "output_preference": {"format": "架构图 + 决策卡片 + 可执行步骤 + 验证命令"},
        "verification_driven": True,
        "validation_pattern": "先B后A",
    },
}


def _ensure_dir() -> None:
    SELF_DIR.mkdir(parents=True, exist_ok=True)


def _read_profile() -> dict[str, Any]:
    """Read profile from SQLite; fallback to JSON if empty; create default if nothing."""
    _ensure_dir()

    # Attempt migration from JSON if SQLite is empty
    db.migrate_from_json()

    data = db.load_profile()
    if data:
        return data

    # Fallback: read from JSON
    if PROFILE_PATH.exists():
        try:
            with open(PROFILE_PATH, encoding="utf-8") as f:
                data = json.load(f)
            if data:
                db.save_profile(data)
                return cast("dict[str, Any]", data)
        except (json.JSONDecodeError, OSError):
            pass

    # Create default
    db.save_profile(DEFAULT_PROFILE)
    return dict(DEFAULT_PROFILE)


def _write_profile(data: dict[str, Any]) -> None:
    """Write profile to SQLite + JSON for backward compat."""
    _ensure_dir()
    db.save_profile(data)


def get_profile() -> dict[str, Any]:
    """读取完整画像。不存在时创建默认profile。附带认知框架的知识链接。"""
    profile = _read_profile()
    profile["frameworks"] = cognitive_frameworks()
    return profile


def update_profile(data: dict[str, Any]) -> dict[str, Any]:
    """合并更新画像。记录变更历史。返回更新后的完整profile。"""
    current = _read_profile()
    old_data = dict(current)  # snapshot for changelog

    _deep_merge(current, data)
    current["updated_at"] = datetime.now().isoformat()
    current["version"] = "v1"

    _write_profile(current)

    # Record changes in changelog
    for key, new_val in data.items():
        old_val = old_data.get(key)
        # Only record if value actually changed
        if old_val != new_val:
            db.record_change(key, old_val, new_val)

    return current


def get_profile_history(limit: int = 20) -> list[dict[str, Any]]:
    """返回画像变更历史，按时间倒序。"""
    return db.get_profile_history(limit=limit)


def _deep_merge(base: dict, update: dict) -> None:
    for key, value in update.items():
        if key in base and isinstance(base[key], dict) and isinstance(value, dict):
            _deep_merge(base[key], value)
        else:
            base[key] = value


def _load_knowledge_links() -> dict[str, list[dict[str, Any]]]:
    """Load knowledge_links.yaml and index links by framework key."""
    try:
        with open(KNOWLEDGE_LINKS_PATH, encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except (FileNotFoundError, yaml.YAMLError):
        return {}

    links_by_framework: dict[str, list[dict[str, Any]]] = {}
    for group in data.get("links", {}).values():
        for link in group:
            mapped_to = link.get("mapped_to", "")
            # Extract framework key from "self.cognitive_frameworks.<key>"
            if mapped_to.startswith("self.cognitive_frameworks."):
                key = mapped_to.split(".")[-1]
                links_by_framework.setdefault(key, []).append(
                    {
                        "name": link["name"],
                        "source": link["source"],
                        "tags": link.get("tags", []),
                        "description": link.get("description", ""),
                    }
                )
    return links_by_framework


def cognitive_frameworks() -> dict[str, Any]:
    """返回认知框架配置及其关联知识链接。"""
    profile = _read_profile()
    frameworks = profile.get("frameworks", {})
    knowledge_links = _load_knowledge_links()

    result: dict[str, Any] = {}
    for key, value in frameworks.items():
        entry: dict[str, Any] = {"config": value}
        matched = knowledge_links.get(key, [])
        if matched:
            entry["_knowledge_links"] = matched
        result[key] = entry
    return result


def get_current_role(context_hint: str = "") -> dict[str, Any]:
    """按时间窗口判断当前角色。工作日白天→最高优先级；非工作时间→个人/家庭。"""
    profile = _read_profile()
    roles = profile.get("roles", [])
    if not roles:
        return {"role_id": "role:unknown", "name": "未知角色", "priority": 0}
    now = datetime.now()
    is_weekend = now.weekday() >= 5
    current_hour = now.hour
    is_work_hours = 9 <= current_hour < 18 and not is_weekend

    if context_hint:
        for role in roles:
            if context_hint in role.get("tags", []) or context_hint in role.get("name", ""):
                return dict(role)

    sorted_roles = sorted(roles, key=lambda r: r.get("priority", 99))
    if is_work_hours:
        for role in sorted_roles:
            tw = role.get("time_window", "")
            if "工作日" in tw:
                return dict(role)
    return dict(sorted_roles[0])


def get_vision_summary() -> str:
    """返回愿景摘要字符串，用于Agent prompt注入。"""
    profile = _read_profile()
    vision = profile.get("vision", {})
    principles = profile.get("principles", [])
    frameworks = profile.get("frameworks", {})

    current_role = get_current_role()
    role_name = current_role.get("name", "未知")
    role_values = current_role.get("values", [])

    lines = [
        f"# L4 Self Context — {profile.get('person', '用户')}",
        f"当前角色: {role_name}",
        f"角色价值观: {', '.join(role_values)}",
        "",
        "## 愿景",
        f"长期: {vision.get('long_term', '')}",
        f"中期: {vision.get('mid_term', '')}",
        "",
        "## 核心原则",
    ]
    for p in sorted(principles, key=lambda x: x.get("weight", 0), reverse=True):
        lines.append(f"- [{p.get('weight', 0):.1f}] {p['name']}: {p.get('source_axiom', '')}")

    lines.extend(
        [
            "",
            "## 认知框架",
            f"思维栈: {frameworks.get('thinking_stack', '')}",
            f"工作流: {frameworks.get('workflow', '')}",
            f"验证驱动: {'是' if frameworks.get('verification_driven') else '否'}",
        ]
    )

    okrs = vision.get("current_okrs", {})
    if okrs:
        lines.append("\n## 当前OKR")
        for quarter, krs in okrs.items():
            lines.append(f"{quarter}:")
            for kr in krs:
                pct = kr.get("progress", 0)
                bar = "█" * (pct // 10) + "░" * (10 - pct // 10)
                lines.append(f"  [{bar}] {pct}% {kr.get('kr', '')}")

    return "\n".join(lines)


def _read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return default


def _write_json(path: Path, data: Any) -> None:
    _ensure_dir()
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _tokenize(text: str) -> set[str]:
    return {token for token in re.findall(r"[\w\u4e00-\u9fff]+", text.lower()) if len(token) > 1}


def _skill_text(skill: dict[str, Any]) -> str:
    return " ".join(
        [
            str(skill.get("name", "")),
            str(skill.get("description", "")),
            " ".join(str(tag) for tag in skill.get("tags", [])),
        ]
    ).strip()


def load_skill_registry() -> list[dict[str, Any]]:
    """Load user-defined skill registry entries."""
    raw = _read_json(SKILL_REGISTRY_PATH, [])
    if not isinstance(raw, list):
        return []
    return [entry for entry in raw if isinstance(entry, dict) and entry.get("name")]


def register_skill(skill_definition: dict[str, Any]) -> dict[str, Any]:
    """Persist a lightweight skill definition for routing."""
    registry = load_skill_registry()
    filtered = {
        key: value for key, value in skill_definition.items() if key in {"name", "description", "tags", "location"}
    }
    if not filtered.get("name"):
        return {"status": "error", "error": "skill_definition.name is required"}
    registry = [entry for entry in registry if entry.get("name") != filtered["name"]]
    registry.append(filtered)
    _write_json(SKILL_REGISTRY_PATH, registry)
    return {"status": "ok", "skill": filtered}


def record_skill_feedback(skill_name: str, accepted: bool, reason: str = "") -> dict[str, Any]:
    """Persist feedback so repeated rejections lower routing priority."""
    feedback = _read_json(SKILL_FEEDBACK_PATH, {})
    entry = feedback.setdefault(skill_name, {"accepted": 0, "rejected": 0, "reasons": []})
    bucket = "accepted" if accepted else "rejected"
    entry[bucket] = int(entry.get(bucket, 0)) + 1
    if reason:
        entry.setdefault("reasons", []).append(
            {"accepted": accepted, "reason": reason, "recorded_at": datetime.now().isoformat()}
        )
        entry["reasons"] = entry["reasons"][-10:]
    _write_json(SKILL_FEEDBACK_PATH, feedback)
    return {"status": "ok", "skill_name": skill_name, "accepted": accepted}


def route_skills(
    task_description: str,
    available_skills: list[dict[str, Any]] | None = None,
    context_hint: str = "",
    available_tools: list[str] | None = None,
    limit: int = 5,
) -> dict[str, Any]:
    """Route a task to the most relevant skills using role tags + feedback."""
    current_role = get_current_role(context_hint=context_hint)
    feedback = _read_json(SKILL_FEEDBACK_PATH, {})
    skills = [*load_skill_registry(), *(available_skills or [])]
    if not skills:
        return {"current_role": current_role, "matches": []}

    query_tokens = _tokenize(task_description)
    role_tokens = _tokenize(current_role.get("name", "")) | {
        token.lower() for token in current_role.get("tags", []) if isinstance(token, str)
    }
    tool_tokens = {tool.lower() for tool in (available_tools or [])}
    scored: list[dict[str, Any]] = []
    seen: set[str] = set()
    for skill in skills:
        name = str(skill.get("name", "")).strip()
        if not name or name in seen:
            continue
        seen.add(name)
        tags = {str(tag).lower() for tag in skill.get("tags", [])}
        text = _skill_text(skill).lower()
        text_tokens = _tokenize(text)
        query_hits = sorted(query_tokens & text_tokens)
        tag_hits = sorted(tag for tag in tags if tag and tag in task_description.lower())
        role_hits = sorted(role_tokens & (tags | text_tokens))
        tool_hits = sorted(tool_tokens & tags)
        entry_feedback = feedback.get(name, {})
        penalty = int(entry_feedback.get("rejected", 0)) * 5
        score = len(query_hits) * 6 + len(tag_hits) * 6 + len(role_hits) * 4 + len(tool_hits) * 2 - penalty
        if current_role.get("name", "") in text:
            score += 3
        if not query_hits and not tag_hits and not role_hits and score <= 0:
            continue
        scored.append(
            {
                "name": name,
                "description": skill.get("description", ""),
                "tags": sorted(tags),
                "score": score,
                "reasons": {
                    "query_hits": query_hits,
                    "tag_hits": tag_hits,
                    "role_hits": role_hits,
                    "tool_hits": tool_hits,
                    "rejected_count": int(entry_feedback.get("rejected", 0)),
                },
            }
        )
    scored.sort(key=lambda item: (-item["score"], item["name"]))
    return {
        "current_role": current_role,
        "task_description": task_description,
        "matches": scored[: max(limit, 1)],
    }


def skill_router(
    action: str,
    task_description: str = "",
    context_hint: str = "",
    available_skills: list[dict[str, Any]] | None = None,
    available_tools: list[str] | None = None,
    limit: int = 5,
    skill_definition: dict[str, Any] | None = None,
    skill_name: str = "",
    accepted: bool = True,
    reason: str = "",
) -> dict[str, Any]:
    """Unified entrypoint for the MCP skill-router tool."""
    if action == "route":
        return route_skills(
            task_description=task_description,
            available_skills=available_skills,
            context_hint=context_hint,
            available_tools=available_tools,
            limit=limit,
        )
    if action == "feedback":
        return record_skill_feedback(skill_name=skill_name, accepted=accepted, reason=reason)
    if action == "register":
        return register_skill(skill_definition or {})
    return {"status": "error", "error": f"Unsupported action: {action}"}

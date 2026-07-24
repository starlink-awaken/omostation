"""Action Registry — 工作流 action 声明式注册

每个 action 是一个可调用的 (params: dict) → dict 函数。
通过 register_action() 注册，外部可扩展。
替代 executor.py 中 12 个 if/elif 硬编码。
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any, Callable

H = Path.home()

# ── 注册表 ──

_registry: dict[str, dict[str, Any]] = {}
_aliases: dict[str, str] = {}

NAMESPACE_PREFIXES = ("ecos.ecos.", "ecos.", "infra.")

# ── 公共类型 ──

ActionHandler = Callable[[dict], dict]
"""Action handler: (params) -> {"passed": bool, "summary": str}"""


# ── 注册 / 解析 API ──


def register_action(
    name: str,
    handler: ActionHandler,
    *,
    aliases: list[str] | None = None,
    description: str = "",
) -> None:
    """注册一个 workflow action

    Args:
        name: action 名称 (在 workflow YAML 的 step.action 中使用)
        handler: 可调用 (params) -> dict, 返回 {"passed": bool, "summary": str}
        aliases: 可选别名列表
        description: 描述
    """
    _registry[name] = {
        "handler": handler,
        "description": description,
    }
    if aliases:
        for a in aliases:
            _aliases[a] = name


# ── 惰性注册 ──
_builtins_registered = False


def _ensure_builtins_registered() -> None:
    """惰性注册内置 action — 避免 import 时副作用"""
    global _builtins_registered
    if _builtins_registered:
        return
    _builtins_registered = True
    _register_builtins()


# resolve_action / list_actions / get_action 都先触发惰性注册


def resolve_action(action: str) -> ActionHandler | None:
    _ensure_builtins_registered()
    for prefix in NAMESPACE_PREFIXES:
        if action.startswith(prefix):
            action = action[len(prefix) :]
            break
    resolved = _aliases.get(action, action)
    entry = _registry.get(resolved)
    if entry is None:
        return None
    return entry["handler"]


def list_actions() -> list[dict[str, str]]:
    _ensure_builtins_registered()
    return [
        {"name": name, "description": info["description"]}
        for name, info in _registry.items()
    ]


def get_action(name: str) -> dict[str, Any] | None:
    _ensure_builtins_registered()
    resolved = _aliases.get(name, name)
    return _registry.get(resolved)


# ── 内部：subprocess 辅助 ──


def _run(cmd: list[str], timeout: int = 30) -> subprocess.CompletedProcess | None:
    """运行 subprocess 并返回结果，失败时返回 None"""
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except FileNotFoundError:
        return None
    except subprocess.TimeoutExpired:
        return None


def _ok(summary: str = "") -> dict:
    return {"passed": True, "summary": summary or "✅"}


def _fail(summary: str = "", details: str = "") -> dict:
    result = {"passed": False, "summary": summary or "❌"}
    if details:
        result["details"] = details
    return result


def _check_run(cmd: list[str], timeout: int = 30) -> dict:
    """运行 subprocess，成功返回 ok，失败时包含详细错误信息"""
    path_str = cmd[0] if cmd else "?"
    r = _run(cmd, timeout=timeout)
    if r is None:
        return _fail(
            summary=f"命令未找到: {path_str}",
            details=f"请确保脚本已安装: {' '.join(cmd)}",
        )
    if r.returncode != 0:
        details = (r.stderr or r.stdout or "").strip()[:300]
        return _fail(
            summary=f"命令失败 (exit={r.returncode})",
            details=details or f"返回码: {r.returncode}",
        )
    return _ok(summary=r.stdout.strip()[:200] or "✅")


# ── 内置 action 注册 ──


def _register_builtins() -> None:
    """注册所有内置 subprocess action

    每个 action 是 ~/.ecos/scripts/ 或 ~/bin/ecos 下的 CLI 包装。
    各 parser 逻辑不同（JSON/returncode/stdout 字符串匹配），
    因此各自独立注册而非统一模板。
    """

    register_action(
        "health_check",
        _action_health_check,
        description="健康检查: 所有核心服务健康状态",
    )

    register_action(
        "domain_validate_all", _action_domain_validate_all, description="域全量校验"
    )

    register_action(
        "domain_audit",
        _action_domain_audit,
        description="漂移检测: 域状态漂移扫描",
        aliases=["drift_detection"],
    )

    register_action(
        "domain_check_refs",
        _action_domain_check_refs,
        description="引用检查: 跨域引用完整性",
        aliases=["reference_check"],
    )

    register_action(
        "domain_sync",
        _action_domain_sync,
        description="域索引同步",
        aliases=["sync_domain_index", "index_sync"],
    )

    register_action("bos_validate", _action_bos_validate, description="BOS URI 校验")

    register_action(
        "domain_routes",
        _action_domain_routes,
        description="路由缓存更新",
        aliases=["update_routes", "routes_update"],
    )

    # ── 向后兼容: system_health_check → health_check ──
    register_action(
        "system_health_check",
        _action_health_check,
        description="(别名) 系统健康检查",
        aliases=[],
    )

    # ── 子工作流: 工作流内调用另一个工作流 ──
    register_action(
        "workflow_run",
        _action_workflow_run,
        description="执行子工作流 — 在 YAML 中通过 workflow 字段指定",
        aliases=["sub_workflow"],
    )

    register_action(
        "complete_quest",
        _action_complete_quest,
        description="家庭任务: 结算 Quest 并累加积分",
    )


def _action_workflow_run(params: dict) -> dict:
    """执行子工作流

    参数通过 params 传入:
      params = {"name": "WORKFLOW-ECOS-DAILY-HEALTH", ...}
    或 step 中定义:
      step:
        action: workflow_run
        workflow: WORKFLOW-ECOS-DAILY-HEALTH
    """
    sub_name = params.get("name") or params.get("workflow", "")
    if not sub_name:
        return {"passed": False, "summary": "子工作流: 未指定 workflow 名称"}

    try:
        from ecos.workflow.executor import execute_m1_workflow

        result = execute_m1_workflow(sub_name)
        ok = result.get("failed", 0) == 0
        summary = (
            result.get("error")
            or f"子工作流 {sub_name}: {result.get('passed', 0)}✅ {result.get('failed', 0)}❌"
        )
        return {
            "passed": ok,
            "summary": summary,
            "sub_result": {
                "workflow": sub_name,
                "passed": result.get("passed", 0),
                "failed": result.get("failed", 0),
            },
        }
    except Exception as e:  # defensive fallback
        return {"passed": False, "summary": f"子工作流执行失败: {e}"}


def _action_health_check(params: dict) -> dict:
    r = _run(
        ["python3", str(H / ".ecos" / "scripts" / "ecos-health-check.py"), "--json"]
    )
    if r is None:
        script_path = H / ".ecos" / "scripts" / "ecos-health-check.py"
        return _fail(
            summary="健康检查脚本未安装",
            details=f"请创建脚本: {script_path} 或使用 step.command 自定义命令",
        )
    try:
        data = json.loads(r.stdout)
        ok = all(c.get("pass", True) for c in data.get("results", []))
        return {"passed": ok, "summary": f"健康检查: {'✅' if ok else '❌'}"}
    except Exception:  # defensive fallback
        return _fail(
            summary="健康检查解析失败",
            details=r.stderr.strip()[:300] or r.stdout.strip()[:300],
        )


def _action_domain_validate_all(params: dict) -> dict:
    return _check_run(["python3", str(H / "bin" / "ecos"), "domain", "validate-all"])


def _action_domain_audit(params: dict) -> dict:
    return _check_run(["python3", str(H / "bin" / "ecos"), "domain", "audit"])


def _action_domain_check_refs(params: dict) -> dict:
    return _check_run(["python3", str(H / "bin" / "ecos"), "domain", "check-refs"])


def _action_domain_sync(params: dict) -> dict:
    return _check_run(
        ["python3", str(H / "bin" / "ecos"), "domain", "sync"], timeout=10
    )


def _action_bos_validate(params: dict) -> dict:
    return _check_run(["python3", str(H / "bin" / "ecos"), "domain", "bos-validate"])


def _action_domain_routes(params: dict) -> dict:
    return _check_run(
        ["python3", str(H / "bin" / "ecos"), "domain", "routes"], timeout=10
    )


def _action_complete_quest(params: dict) -> dict:
    """结算 Quest 并累加积分

    从 trigger_event 中获取 quest_id：
      params = {"trigger_event": {"payload": {"quest_id": 12, ...}}}
    或者直接传入：
      params = {"quest_id": 12, ...}
    """
    event = params.get("trigger_event", {})
    payload = event.get("payload", {}) if isinstance(event, dict) else {}

    quest_id = params.get("quest_id") or payload.get("quest_id")
    try:
        quest_id = int(quest_id)
    except (TypeError, ValueError):
        return {
            "passed": False,
            "summary": f"complete_quest: 无效的 quest_id ({quest_id})",
        }

    cur = Path(__file__).resolve()
    workspace_root = None
    for parent in cur.parents:
        if (parent / ".omo").is_dir() or (parent / "projects").is_dir():
            if parent.name != "projects":
                workspace_root = parent
                break
    if not workspace_root:
        workspace_root = cur.parents[5]

    db_path = workspace_root / "projects" / "family-hub" / "family_hub.db"
    if not db_path.exists():
        return {"passed": False, "summary": f"数据库不存在: {db_path}"}

    import sqlite3

    try:
        conn = sqlite3.connect(str(db_path), timeout=2.0)
        conn.row_factory = sqlite3.Row

        # 1. 查找 Quest
        quest = conn.execute(
            "SELECT reward, assignee, type, title FROM quests WHERE id = ? AND completed = 0",
            (quest_id,),
        ).fetchone()
        if not quest:
            conn.close()
            # 如果已经完成了，为了幂等性，我们也判定为成功
            return {
                "passed": True,
                "summary": f"complete_quest: Quest {quest_id} 已在先前完成过",
            }

        reward = quest["reward"]
        assignee = quest["assignee"]
        q_type = quest["type"]
        title = quest["title"]

        # 2. 标记完成
        conn.execute("UPDATE quests SET completed = 1 WHERE id = ?", (quest_id,))

        # 3. 积分累加
        if q_type in ("household", "responsibility"):
            conn.execute(
                "UPDATE profiles SET responsibilityPoints = responsibilityPoints + ? WHERE role = ?",
                (reward, assignee),
            )
        elif q_type in ("learning", "wisdom"):
            conn.execute(
                "UPDATE profiles SET wisdomPoints = wisdomPoints + ? WHERE role = ?",
                (reward, assignee),
            )
        else:
            conn.execute(
                "UPDATE profiles SET responsibilityPoints = responsibilityPoints + ? WHERE role = ?",
                (reward, assignee),
            )

        # 4. 等级重算
        conn.execute(
            """
            UPDATE profiles 
            SET level = 1 + (wisdomPoints + responsibilityPoints) / 100 
            WHERE role = ?
        """,
            (assignee,),
        )

        # 5. 日志记入
        conn.execute(
            "INSERT INTO logs (message, type, timestamp) VALUES (?, ?, datetime('now'))",
            (
                f"{assignee} completed quest: {title} (ID={quest_id}) for {reward} points",
                "quest_completion",
            ),
        )

        conn.commit()
        conn.close()
        return {
            "passed": True,
            "summary": f"complete_quest: 成功结算 Quest {quest_id} ({title})，为 {assignee} 奖励 {reward} 积分",
        }
    except Exception as e:  # defensive fallback
        return {"passed": False, "summary": f"complete_quest 失败: {str(e)}"}


# 惰性注册（在 _ensure_builtins_registered() 中触发）

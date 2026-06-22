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


def resolve_action(action: str) -> ActionHandler | None:
    """根据 action 名称解析出对应的 handler

    自动处理:
    - 命名空间前缀剥离 (ecos.ecos.X → X)
    - 别名映射 (system_health_check → health_check)
    """
    # 剥离命名空间前缀
    for prefix in NAMESPACE_PREFIXES:
        if action.startswith(prefix):
            action = action[len(prefix):]
            break

    # 别名映射
    resolved = _aliases.get(action, action)

    entry = _registry.get(resolved)
    if entry is None:
        return None
    return entry["handler"]


def list_actions() -> list[dict[str, str]]:
    """列出所有已注册 action"""
    return [
        {"name": name, "description": info["description"]}
        for name, info in _registry.items()
    ]


def get_action(name: str) -> dict[str, Any] | None:
    """获取单个 action 信息"""
    resolved = _aliases.get(name, name)
    return _registry.get(resolved)


# ── 内部：subprocess 辅助 ──


def _run(cmd: list[str], timeout: int = 30) -> subprocess.CompletedProcess:
    """运行 subprocess 并返回结果"""
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)


def _ok(summary: str = "") -> dict:
    return {"passed": True, "summary": summary or "✅"}


def _fail(summary: str = "") -> dict:
    return {"passed": False, "summary": summary or "❌"}


# ── 内置 action 注册 ──


def _register_builtins() -> None:
    """注册所有内置 subprocess action

    每个 action 是 ~/.ecos/scripts/ 或 ~/bin/ecos 下的 CLI 包装。
    各 parser 逻辑不同（JSON/returncode/stdout 字符串匹配），
    因此各自独立注册而非统一模板。
    """

    register_action("health_check", _action_health_check,
                    description="健康检查: 所有核心服务健康状态")

    register_action("domain_validate_all", _action_domain_validate_all,
                    description="域全量校验")

    register_action("domain_audit", _action_domain_audit,
                    description="漂移检测: 域状态漂移扫描",
                    aliases=["drift_detection"])

    register_action("domain_check_refs", _action_domain_check_refs,
                    description="引用检查: 跨域引用完整性",
                    aliases=["reference_check"])

    register_action("domain_sync", _action_domain_sync,
                    description="域索引同步",
                    aliases=["sync_domain_index", "index_sync"])

    register_action("bos_validate", _action_bos_validate,
                    description="BOS URI 校验")

    register_action("domain_routes", _action_domain_routes,
                    description="路由缓存更新",
                    aliases=["update_routes", "routes_update"])

    # ── 向后兼容: system_health_check → health_check ──
    register_action("system_health_check", _action_health_check,
                    description="(别名) 系统健康检查",
                    aliases=[])


def _action_health_check(params: dict) -> dict:
    r = _run(["python3", str(H / ".ecos" / "scripts" / "ecos-health-check.py"), "--json"])
    try:
        data = json.loads(r.stdout)
        ok = all(c.get("pass", True) for c in data.get("results", []))
        return {"passed": ok, "summary": f"健康检查: {'✅' if ok else '❌'}"}
    except Exception:
        return {"passed": False, "summary": "健康检查解析失败"}


def _action_domain_validate_all(params: dict) -> dict:
    r = _run(["python3", str(H / "bin" / "ecos"), "domain", "validate-all"])
    ok = "0❌" in r.stdout or "0 failed" in r.stdout.lower()
    return {"passed": ok, "summary": "域校验完成"}


def _action_domain_audit(params: dict) -> dict:
    r = _run(["python3", str(H / "bin" / "ecos"), "domain", "audit"])
    return {"passed": r.returncode == 0, "summary": "漂移检测完成"}


def _action_domain_check_refs(params: dict) -> dict:
    r = _run(["python3", str(H / "bin" / "ecos"), "domain", "check-refs"])
    return {"passed": r.returncode == 0, "summary": "引用检查完成"}


def _action_domain_sync(params: dict) -> dict:
    r = _run(["python3", str(H / "bin" / "ecos"), "domain", "sync"], timeout=10)
    return {"passed": r.returncode == 0, "summary": "索引同步完成"}


def _action_bos_validate(params: dict) -> dict:
    r = _run(["python3", str(H / "bin" / "ecos"), "domain", "bos-validate"])
    return {"passed": r.returncode == 0, "summary": "BOS校验完成"}


def _action_domain_routes(params: dict) -> dict:
    r = _run(["python3", str(H / "bin" / "ecos"), "domain", "routes"], timeout=10)
    return {"passed": r.returncode == 0, "summary": "路由缓存更新"}


# ── 启动时注册内置 action ──
_register_builtins()

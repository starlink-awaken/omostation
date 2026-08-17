""" "Forge Guardrails 适配器 — MCP 可靠性层

基于 Forge (https://github.com/antoinezambelli/forge) 的 Guardrails 设计理念。
Forge 通过 5 个 Guardrails 组件将 8B 模型的 Agent 准确率从 52.7% 提升到 86.5%。

本模块实现 Forge 风格的 Guardrails 中间件，注入 codeanalyze 的 MCP Server。
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, cast

logger = logging.getLogger(__name__)


@dataclass
class GuardrailConfig:
    """Guardrails 配置"""

    rescue_parsing: bool = True
    retry_nudge: bool = True
    step_enforcement: bool = True
    error_recovery: bool = True
    max_retries: int = 3
    max_nudges: int = 5
    required_steps: list[str] = field(default_factory=list)


@dataclass
class GuardrailStats:
    """统计信息"""

    rescued_parses: int = 0
    retry_nudges: int = 0
    step_violations: int = 0
    error_recoveries: int = 0
    total_calls: int = 0
    total_errors: int = 0


_default_config = GuardrailConfig()
_stats = GuardrailStats()


def configure(config: GuardrailConfig | None = None) -> None:
    """配置 Guardrails。"""
    global _default_config
    if config:
        _default_config = config


def get_stats() -> GuardrailStats:
    """获取统计信息。"""
    return _stats


def reset_stats() -> None:
    """重置统计。"""
    global _stats
    _stats = GuardrailStats()


# ── 1. Rescue Parsing（救援解析）──


def rescue_json(text: str) -> dict | None:
    """尝试解析并修复格式错误的 JSON。

    Forge 风格的 Rescue Parsing：
    1. 直接解析
    2. 修复常见格式问题后重试
    3. 用正则提取 JSON 块
    4. 全部失败返回 None
    """
    import json
    import re

    if not text:
        return None

    # Step 1: 直接解析
    try:
        return cast("dict[str, Any]", json.loads(text))
    except json.JSONDecodeError:
        pass

    # Step 2: 去除 markdown fence
    cleaned = re.sub(r"^```(?:json)?\s*\n?", "", text.strip(), flags=re.MULTILINE)
    cleaned = re.sub(r"\n```\s*$", "", cleaned, flags=re.MULTILINE)
    try:
        result = cast("dict[str, Any]", json.loads(cleaned))
        _stats.rescued_parses += 1
        return result
    except json.JSONDecodeError:
        pass

    # Step 3: 提取 {} 或 [] 包围的内容
    for pattern in [r"\{[^{}]*\}", r"\[[^\[\]]*\]"]:
        for match in re.finditer(pattern, cleaned, re.DOTALL):
            try:
                result = cast("dict[str, Any]", json.loads(match.group()))
                _stats.rescued_parses += 1
                return result
            except json.JSONDecodeError:
                continue

    return None


# ── 2. Retry Nudge（重试提示）──


def check_missing_steps(
    tool_calls: list[dict],
    required: list[str],
) -> list[str]:
    """检查是否缺失必要步骤。

    返回缺失的工具名称列表。
    """
    called = set()
    for tc in tool_calls:
        name = tc.get("name") or tc.get("function", {}).get("name", "")
        called.add(name)

    missing_steps = []
    for step in required:
        if step not in called:
            missing_steps.append(step)

    if missing_steps:
        logger.warning(f"缺失步骤: {missing_steps}")
        _stats.step_violations += 1

    return missing_steps


# ── 3. Error Recovery（错误恢复）──


def retry_on_error(
    func: Callable[..., dict],
    args: tuple = (),
    kwargs: dict | None = None,
    max_retries: int = 2,
) -> dict:
    """带自动重试的工具调用封装。

    如果工具抛出异常，最多重试 2 次。
    符合 Forge 的 Error Recovery Guardrail。
    """
    kwargs = kwargs or {}
    last_error = None

    for attempt in range(max_retries + 1):
        try:
            if attempt > 0:
                logger.info(f"重试第 {attempt} 次...")
                _stats.error_recoveries += 1
            return func(*args, **kwargs)
        except Exception as e:
            last_error = str(e)
            logger.warning(f"调用失败 (attempt {attempt + 1}): {e}")
            if attempt < max_retries:
                time.sleep(0.5 * (attempt + 1))

    return {"status": "error", "error": last_error, "format_version": "codeanalyze-v1"}


# ── Guards 装饰器 ──


def guardrail(
    required_steps: list[str] | None = None,
    max_retries: int | None = None,
    rescue: bool = True,
) -> Callable:
    """Forge 风格的工具调用防护装饰器。

    用法:
        @guardrail(required_steps=["analyze", "export"])
        def my_tool(path: str): ...
    """

    def decorator(func: Callable) -> Callable:
        cfg = GuardrailConfig(
            step_enforcement=bool(required_steps),
            error_recovery=True,
            rescue_parsing=rescue,
            max_retries=max_retries or _default_config.max_retries,
            required_steps=required_steps or [],
        )

        def wrapper(*args: Any, **kwargs: Any) -> dict:
            _stats.total_calls += 1

            # 执行工具调用（带重试）
            result = retry_on_error(func, args, kwargs, max_retries=cfg.max_retries)

            # Rescue Parsing: 如果结果是字符串而非 dict，尝试修复 JSON
            if isinstance(result, str) and cfg.rescue_parsing:
                rescued = rescue_json(result)
                if rescued is not None:
                    _stats.rescued_parses += 1
                    result = rescued

            # Step Enforcement: 检查结果是否包含必要步骤
            if cfg.step_enforcement and isinstance(result, dict):
                # 检查返回数据中是否包含了所有必需步骤
                result_keys = set(str(k) for k in result.keys())
                missing = [s for s in cfg.required_steps if s not in result_keys]
                if missing:
                    _stats.step_violations += 1
                    result["_missing_steps"] = missing
                    result["_guardrail_warning"] = f"缺失步骤: {missing}"

            return result

        return wrapper

    return decorator

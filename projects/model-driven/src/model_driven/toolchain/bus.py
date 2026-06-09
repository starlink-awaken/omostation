"""
model_driven.toolchain.bus — 模型驱动工具链总线

统一管理和路由所有模型驱动工具：
- 工具注册/发现
- 工具执行路由
- 结果聚合
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any

import yaml


class ToolStatus(Enum):
    """工具状态"""

    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
    DEPRECATED = "deprecated"


@dataclass
class ToolResult:
    """工具执行结果"""

    tool_name: str
    success: bool
    message: str = ""
    data: Any = None
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    executed_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    duration_ms: float = 0.0


@dataclass
class ToolDefinition:
    """工具定义"""

    name: str
    description: str
    category: str = ""  # design/generate/derive/validate/connect/compile/evolve/monitor/deploy/observe/report/archive
    status: ToolStatus = ToolStatus.AVAILABLE
    version: str = "1.0.0"
    tags: list[str] = field(default_factory=list)


class ToolchainBus:
    """工具链总线 — 所有模型驱动工具的统一入口"""

    def __init__(self):
        self._tools: dict[str, Callable] = {}
        self._definitions: dict[str, ToolDefinition] = {}
        self._history: list[ToolResult] = []

    def register(
        self,
        name: str,
        func: Callable,
        definition: ToolDefinition,
    ) -> None:
        """注册工具"""
        self._tools[name] = func
        self._definitions[name] = definition

    def unregister(self, name: str) -> bool:
        """注销工具"""
        if name in self._tools:
            del self._tools[name]
            del self._definitions[name]
            return True
        return False

    def list_tools(self, category: str | None = None) -> list[ToolDefinition]:
        """列出工具"""
        tools = list(self._definitions.values())
        if category:
            tools = [t for t in tools if t.category == category]
        return tools

    def list_categories(self) -> list[str]:
        """列出所有工具类别"""
        return sorted(set(d.category for d in self._definitions.values()))

    def get_tool(self, name: str) -> tuple[Callable | None, ToolDefinition | None]:
        """获取工具"""
        return self._tools.get(name), self._definitions.get(name)

    def execute(self, tool_name: str, **kwargs) -> ToolResult:
        """执行工具"""
        func, definition = self.get_tool(tool_name)
        if func is None:
            return ToolResult(
                tool_name=tool_name,
                success=False,
                message=f"工具不存在: {tool_name}",
            )

        start = datetime.now(UTC)
        try:
            result_data = func(**kwargs)
            duration = (datetime.now(UTC) - start).total_seconds() * 1000

            tool_result = ToolResult(
                tool_name=tool_name,
                success=True,
                message="执行成功",
                data=result_data,
                duration_ms=round(duration, 2),
            )
        except (TypeError, ValueError) as e:
            duration = (datetime.now(UTC) - start).total_seconds() * 1000
            tool_result = ToolResult(
                tool_name=tool_name,
                success=False,
                message=f"参数错误: {e}",
                errors=[str(e)],
                duration_ms=round(duration, 2),
            )
        except Exception as e:
            duration = (datetime.now(UTC) - start).total_seconds() * 1000
            tool_result = ToolResult(
                tool_name=tool_name,
                success=False,
                message=f"执行失败: {e}",
                errors=[str(e)],
                duration_ms=round(duration, 2),
            )

        self._history.append(tool_result)
        return tool_result

    def get_history(self, limit: int = 50) -> list[ToolResult]:
        """获取执行历史"""
        return self._history[-limit:]

    def get_stats(self) -> dict[str, Any]:
        """获取工具统计"""
        total = len(self._history)
        if total == 0:
            return {"total_executions": 0, "success_rate": 0, "avg_duration_ms": 0}

        success_count = sum(1 for r in self._history if r.success)
        avg_duration = sum(r.duration_ms for r in self._history) / total

        return {
            "total_executions": total,
            "success_rate": round(success_count / total * 100, 1),
            "avg_duration_ms": round(avg_duration, 2),
            "tools_count": len(self._tools),
            "categories": self.list_categories(),
        }

    # ── 持久化 ──────────────────────────────────

    def save_history(self, state_dir: str | None = None) -> bool:
        """持久化工具执行历史"""
        from pathlib import Path

        if state_dir is None:
            from model_driven._paths import get_state_dir

            state_dir = str(get_state_dir())

        file_path = Path(state_dir) / "toolchain-history.yaml"
        try:
            data = {
                "history": [
                    {
                        "tool_name": r.tool_name,
                        "success": r.success,
                        "message": r.message,
                        "errors": r.errors,
                        "warnings": r.warnings,
                        "executed_at": r.executed_at,
                        "duration_ms": r.duration_ms,
                    }
                    for r in self._history
                ]
            }
            with open(file_path, "w") as f:
                yaml.dump(data, f, allow_unicode=True, sort_keys=False)
            return True
        except (OSError, yaml.YAMLError):
            return False

    def load_history(self, state_dir: str | None = None) -> list[ToolResult]:
        """从文件加载工具执行历史"""
        from pathlib import Path

        if state_dir is None:
            from model_driven._paths import get_state_dir

            state_dir = str(get_state_dir())

        file_path = Path(state_dir) / "toolchain-history.yaml"
        if not file_path.exists():
            return []

        try:
            with open(file_path) as f:
                data = yaml.safe_load(f)
        except (OSError, yaml.YAMLError):
            return []

        results = []
        for rd in (data or {}).get("history", []):
            results.append(
                ToolResult(
                    tool_name=rd["tool_name"],
                    success=rd.get("success", False),
                    message=rd.get("message", ""),
                    errors=rd.get("errors", []),
                    warnings=rd.get("warnings", []),
                    executed_at=rd.get("executed_at", ""),
                    duration_ms=rd.get("duration_ms", 0.0),
                )
            )
        return results

"""
OntoDerive 生态接口协议 v2
==========================
使用 ABC(抽象基类)替代 typing.Protocol，支持 isinstance() 编译期验证。
"""

from abc import ABC, abstractmethod
from typing import Any


class DeriveInterface(ABC):
    """Minerva/Sophia/eCOS 可消费的推导引擎接口"""

    @abstractmethod
    def derive(self) -> dict[str, Any]: ...

    @abstractmethod
    def check(self) -> list[dict[str, Any]]: ...

    @abstractmethod
    def generate_report(self) -> str: ...

    def analyze(self, goal: str = "", context: str = "") -> dict[str, Any]:
        """全量分析：derive + check + toolforge"""
        summary = self.derive()
        checks = self.check()
        return {"summary": summary, "checks": checks, "goal": goal, "context": context}


class ToolForgeInterface(ABC):
    """Sophia 可消费的工具匹配接口"""

    @abstractmethod
    def select(self, goal: str, context: str = "", top_n: int = 5, mode: str = "keyword") -> list[dict[str, Any]]: ...

    @abstractmethod
    def match(self, goal: str, context: str = "", limit: int = 3, mode: str = "keyword") -> dict[str, Any]: ...

    @abstractmethod
    def to_inference_guide(self, goal: str, context: str = "", mode: str = "keyword") -> str: ...


class PipelineObservable(ABC):
    """eCOS 可观察的管道事件接口"""

    @abstractmethod
    def on_stage_start(self, stage: str, context: dict[str, Any]) -> None: ...

    @abstractmethod
    def on_stage_end(self, stage: str, result: dict[str, Any]) -> None: ...

    @abstractmethod
    def on_error(self, stage: str, error: Exception) -> None: ...


class PipelineStage(ABC):
    """管道阶段基类"""

    name: str = ""

    @abstractmethod
    def run(self, ctx: dict[str, Any]) -> dict[str, Any]: ...

    def before(self, ctx: dict[str, Any]) -> None:
        pass

    def after(self, ctx: dict[str, Any], result: dict[str, Any]) -> None:
        pass

    def on_error(self, ctx: dict[str, Any], error: Exception) -> None:
        pass


class AnalysisResult:
    """Minerva/Sophia 可消费的统一分析结果"""

    def __init__(self, summary: dict, checks: list[dict], toolforge_matches: list[dict] | None = None) -> None:
        self.summary = summary
        self.checks = checks
        self.toolforge_matches = toolforge_matches or []
        self.passed = all(c.get("passed", False) for c in checks)

    def to_dict(self) -> dict[str, Any]:
        return {
            "summary": self.summary,
            "checks": self.checks,
            "toolforge_matches": self.toolforge_matches,
            "passed": self.passed,
        }

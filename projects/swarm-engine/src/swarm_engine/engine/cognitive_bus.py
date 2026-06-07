from __future__ import annotations

# ruff: noqa: RUF001, RUF002, RUF003
from ._compat import InferenceOracle

"""
---
Type: Module
Status: ACTIVE
Layer: L3
Authority: nucleus/Z-Core/L0-Genome/R0-ACT-SYS-AX01-05_microkernel_fractal_axiom.md
---
"""


import asyncio
import importlib
import inspect
import json
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Any

# =============================================================================
# 0. 形式化摘要 ≝
# =============================================================================
# Microkernel_Component ≡ System_Bus
# 内涵 ≝ {Routing, Scheduling, Communication}
# 外延 ≝ {m | m ∈ Z-Microkernel ∧ orchestrates(m, Communication)}
# 功能 ⊢ {RouteMessages, ScheduleTasks, ManageBus}
# =============================================================================

"""
---
Type: Infrastructure
Status: ACTIVE
Version: 1.3.0
Owner: '@Sage'
Authority: nucleus/Z-Spore/dna/R0-ACT-SYS-AX01-09_cognitive_cpu_axiom.md
Layer: L3
Constraint: "[!!] COGNITIVE_CENTER"
---
"""
# 🧠 语义总线 (Cognitive Bus - CB-01) v1.3.0
# 职责: 物理实现"语义 CPU"的跨模式调度。
# 合并历史: v1.1.2 (set_persona) + v1.0.1 (scribe/distill) → v1.2.0 → v1.3.0 (LLM 集成)

_log = logging.getLogger(__name__)
VALID_PERSONAS = frozenset(["@Builder", "@Devil", "@Sage", "@Keeper", "@Board"])


VALID_PERSONAS = frozenset(["@Builder", "@Devil", "@Sage", "@Keeper", "@Board"])


class CognitiveBus:
    """[!!] 系统的语义中枢：统一分发推理请求"""

    def __init__(self, mode: str = "Possession") -> None:
        self.status = "active"  # was super().__init__(metadata_path=...)
        self.mode = mode  # "Possession" or "Self"
        self.config = importlib.import_module("nucleus.Z_Spore.engine.env_resolver").Config
        self.active_persona = "@Sage"

    def validate_internal_state(self) -> bool:
        """校验总线连通性"""
        return True

    # --- 🎭 人格切换 ---

    def set_persona(self, persona_name: str) -> None:
        """切换推理人格。有效值: @Builder / @Devil / @Sage / @Keeper / @Board"""
        if persona_name not in VALID_PERSONAS:
            raise ValueError(f"Unknown persona '{persona_name}'. Valid: {sorted(VALID_PERSONAS)}")
        self.active_persona = persona_name
        _log.info("🎭 [CognitiveBus] 意识流已切换至: {persona_name}")

    # --- 🛠️ 语义接口 (S-CPU Interfaces) ---

    def think(
        self,
        prompt: str,
        context: dict[str, Any] | None = None,
        schema: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        """
        核心推理接口 — 产生认知输出

        模式行为:
        - Possession 模式: 打印请求信号到控制台，返回 None（等待外部 AI 响应）
        - Self 模式: 调用内部 LLM 适配器，返回推理结果字典

        参数:
            prompt: 推理提示词
            context: 可选的上下文信息（仅 Self 模式使用）
            schema: 可选的响应模式约束（仅 Self 模式使用）

        返回:
            - Possession 模式: None（表示请求已发送，等待外部 AI）
            - Self 模式: Dict[str, Any] 包含 LLM 响应结果
              可能包含: {"status": "success", "response": "...", ...}

        示例:
            >>> bus = CognitiveBus(mode="Self")
            >>> result = bus.think("What is the meaning of life?")
            >>> _log.info(result["response"])

            >>> bus = CognitiveBus(mode="Possession")
            >>> bus.think("Execute this task")  # Prints request, returns None
        """
        self._constraint_check(f"THINK: {prompt[:30]}...")
        persona_prompt = f"[System Persona: {self.active_persona}]\n{prompt}"

        if self.mode == "Possession":
            _log.info("\n📡 [CognitiveBus] >>> MODE: POSSESSION <<<")
            _log.info("   [Persona]: %s", self.active_persona)
            _log.info("   [Request]: %s", prompt)
            if schema:
                _log.info("   [Schema]: %s", schema)
            # Possession 模式：打印请求并返回 None
            # 调用方应通过其他渠道（如 stdin/out）与外部 AI 交互
            return None
        else:
            # Self 模式：调用内部 LLM
            return self._call_internal_adapter(persona_prompt, context, schema)

    def scribe(self, intent: str, constraints: list | None = None) -> dict[str, Any]:
        """逻辑转录接口 — 将意图结构化并写入认知拓扑记录。
        返回 {"intent": ..., "constraints": ..., "persona": ...} 供上游写入拓扑节点。
        """
        self._constraint_check(f"SCRIBE: {intent[:30]}...")
        record = {
            "intent": intent,
            "constraints": constraints or [],
            "persona": self.active_persona,
            "mode": self.mode,
        }
        if self.mode == "Possession":
            _log.info("📝 [CognitiveBus] SCRIBE → {intent[:60]}")
        return record

    def distill(self, raw_data: Any, focus: str = "Logic") -> dict[str, Any]:
        """语义压缩接口 — 从原始数据提炼核心洞察。
        Self 模式调用 LLM；Possession 模式打印信号并返回 pass-through 结构。
        """
        self._constraint_check(f"DISTILL: {focus}")
        if self.mode == "Possession":
            _log.info("🔬 [CognitiveBus] DISTILL [focus={focus}] — awaiting host agent cognition")
            return {"focus": focus, "raw": raw_data, "distilled": None, "mode": "Possession"}

        # Self 模式：调用 LLM 进行语义压缩
        prompt = (
            f"Distill the following data with focus on '{focus}'. "
            f"Return a concise insight in JSON with keys: summary, key_points (list), confidence.\n\n"
            f"Data: {json.dumps(raw_data) if not isinstance(raw_data, str) else raw_data}"
        )
        result = self._call_internal_adapter(prompt, context=None, schema={"type": "json_object"})
        return {"focus": focus, "distilled": result.get("response"), "mode": "Self"}

    def _resolve_oracle_result(self, result: Any) -> dict[str, Any]:
        if not inspect.isawaitable(result):
            return result

        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(result)

        with ThreadPoolExecutor(max_workers=1) as executor:
            return executor.submit(asyncio.run, result).result()

    def _call_internal_adapter(
        self, prompt: str, context: dict[str, Any] | None, schema: dict[str, Any] | None
    ) -> dict[str, Any]:
        """Self 模式的内部 LLM 调用 — 通过 InferenceOracle 执行。"""
        _log.info(f"⚙️ [S-CPU] 发起 LLM 调用 [persona={self.active_persona}]...")
        try:
            # TODO-migrate: from nucleus.Z_Microkernel.infrastructure.oracle.inference_oracle import InferenceOracle

            oracle = InferenceOracle.get_instance()
            # 兼容旧版参数
            kwargs = {}
            if context:
                kwargs["context"] = context
            if schema:
                kwargs["schema"] = schema

            res = self._resolve_oracle_result(oracle.infer(prompt, **kwargs))

            if res.get("status") == "success":
                return {
                    "response": res.get("content"),
                    "status": "success",
                    "usage": res.get("usage", {}),
                }
            else:
                _log.warning(f"⚠️ [S-CPU] Oracle inference failed: {res.get('message')}")
                return {"status": "error", "response": f"[ERROR] {res.get('message')}"}
        except ImportError:
            _log.info("⚠️ [S-CPU] InferenceOracle 不可用，降级至 mock 响应。")
            return {"status": "degraded", "response": f"[DEGRADED] {prompt[:60]}"}


# 模块级全局单例
Bus = CognitiveBus()

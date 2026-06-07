from __future__ import annotations

# ruff: noqa: RUF001, RUF003
from ._compat import Gateway

"""
---
Type: Module
Status: ACTIVE
Layer: L3
Authority: nucleus/Z-Core/L0-Genome/R0-ACT-SYS-AX01-10_holographic_metadata_axiom.md
---
"""


import json
import logging
import os
import time
import urllib.error
import urllib.request
from typing import Any

# =============================================================================
# 0. 形式化摘要 ≝
# =============================================================================
# Execution_Organ ≡ Task_Executor
# 内涵 ≝ {Execute, Orchestrate, Manage}
# 外延 ≝ {e | e ∈ D-Execution ∧ executes(e, Tasks)}
# 功能 ⊢ {ExecuteTasks, ManageBus, RemoteCognition}
# =============================================================================

"""
---
Type: Organ
Status: ACTIVE
Version: 1.0.0
Owner: '@Gemini-CLI'
Authority: organs/D-Execution/AGENTS.md
Layer: L4
Constraint: "[!!] ANTHROPIC_PROTOCOL_ENFORCEMENT"
Summary: "Anthropic 协议突触驱动，支持 Longcat 等 Anthropic 兼容供应商。"
---
"""
# 🔌 Anthropic 突触驱动 (Anthropic Synapse Driver)
# 职责: 对接 Anthropic 协议的 LLM 服务（如 Longcat, Claude 原生），提供高阶认知算力。

_log = logging.getLogger(__name__)


class AnthropicSynapse:
    """B-OS Anthropic 协议语义算力突触"""

    def __init__(
        self,
        api_key: str = os.environ.get("BOS_ANTHROPIC_KEY", ""),
        base_url: str = os.environ.get("BOS_ANTHROPIC_URL", "https://api.anthropic.com"),
    ) -> None:
        self.status = "active"  # was super().__init__(metadata_path=...)
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.version = "2023-06-01"

    @staticmethod
    def _constraint_check(_constraint: str) -> None:
        pass

    def _http_request(self, endpoint: str, data: dict) -> dict:
        """执行 Anthropic 协议的 HTTP 请求"""
        url = f"{self.base_url}{endpoint}"
        try:
            req = urllib.request.Request(url)  # noqa: S310
            req.add_header("x-api-key", self.api_key)
            req.add_header("anthropic-version", self.version)
            req.add_header("Content-Type", "application/json")

            body = json.dumps(data).encode("utf-8")
            with urllib.request.urlopen(req, data=body, timeout=60) as response:  # noqa: S310
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            error_body = e.read().decode("utf-8", errors="replace")
            return {"status": "error", "message": f"HTTP {e.code}: {error_body}"}
        except (json.JSONDecodeError, OSError) as e:
            _log.error("%s: %s", type(e).__name__, e)
            return {"status": "error", "message": str(e)}

    def generate(self, model: str, prompt: str, system: str | None = None, max_tokens: int = 4096) -> dict[str, Any]:
        """执行推理生成 (Messages API)"""
        self._constraint_check(f"generate: {model}")

        payload = {
            "model": model,
            "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system:
            payload["system"] = system

        start_time = time.time()
        res = self._http_request("/v1/messages", payload)
        duration_ms = int((time.time() - start_time) * 1000)

        if "content" in res and isinstance(res["content"], list):
            text = res["content"][0].get("text", "")
            return {
                "status": "success",
                "content": text,
                "metadata": {
                    "model": model,
                    "tokens_in": res.get("usage", {}).get("input_tokens", 0),
                    "tokens_out": res.get("usage", {}).get("output_tokens", 0),
                    "latency_ms": duration_ms,
                },
            }
        return {
            "status": "error",
            "message": res.get("message", "Unknown error or invalid response format"),
        }

    def sync_to_gateway(self, model_list: list[str] | None = None) -> None:
        """将可用模型同步至 CognitiveGateway"""
        if not model_list:
            model_list = ["claude-3-5-sonnet-20240620", "claude-3-opus-20240229"]

        try:
            # TODO-migrate: from nucleus.Z_Microkernel.gateways.cognitive_gateway import Gateway

            for m in model_list:
                # 基础打分逻辑
                iq = 9.0 if "opus" in m or "sonnet" in m else 8.0

                card = {
                    "model_id": f"anthropic-{m}",
                    "provider": "longcat" if "longcat" in self.base_url else "anthropic",
                    "iq_score": iq,
                    "cost_per_1k": 0.015,  # 预估均价
                    "latency_avg": 1200,
                    "quota_remains": 1.0,
                    "is_free": 0,
                    "specialties": ["reasoning", "coding", "agentic"],
                }
                Gateway.register_model(card)
        except (TypeError, ValueError, AttributeError) as e:
            _log.error("[!] AnthropicSynapse failed to sync with Gateway: %s", e)

    def validate_internal_state(self) -> bool:
        return bool(self.api_key and len(self.api_key) > 10)


if __name__ == "__main__":
    # 快捷测试
    api_key = os.environ.get("BOS_ANTHROPIC_KEY", "MOCK")
    url = os.environ.get("BOS_ANTHROPIC_URL", "https://api.longcat.chat/anthropic")
    synapse = AnthropicSynapse(api_key=api_key, base_url=url)
    _log.info("Anthropic Synapse (Longcat) Status: %s", synapse.validate_internal_state())

from __future__ import annotations

# ruff: noqa: RUF003

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
# 功能 ⊢ {ExecuteTasks, ManageWorkspace, OrchestrateAgents}
# =============================================================================

"""
---
Type: Organ
Status: ACTIVE
Version: 1.0.0
Owner: '@Claude-Code'
Authority: organs/D-Execution/AGENTS.md
Layer: L4
Constraint: "[!!] OLLAMA_SYNAPSE_LOCAL_ONLY"
---
"""
# 🔌 Ollama 突触驱动 (Ollama Synapse Driver)
# 职责: 对接本地 Ollama 服务，将本地 LLM 算力并入利维坦认知网格。

_log = logging.getLogger(__name__)


class OllamaSynapse:
    """B-OS 本地语义算力突触"""

    def __init__(self, host: str = os.environ.get("BOS_OLLAMA_URL", "http://localhost:11434")) -> None:
        self.status = "active"  # was super().__init__(metadata_path=...)
        self.host = host
        self.api_generate = f"{host}/api/generate"
        self.api_embeddings = f"{host}/api/embeddings"
        self.api_tags = f"{host}/api/tags"

    @staticmethod
    def _constraint_check(_constraint: str) -> None:
        pass

    def _http_request(self, url: str, data: dict | None = None) -> dict:
        """通用的 HTTP 请求封装"""
        try:
            req = urllib.request.Request(url)  # noqa: S310
            req.add_header("Content-Type", "application/json")

            body = json.dumps(data).encode("utf-8") if data else None
            with urllib.request.urlopen(req, data=body, timeout=60) as response:  # noqa: S310
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.URLError as e:
            return {"status": "error", "message": f"Ollama connection failed: {e}"}
        except (json.JSONDecodeError, OSError) as e:
            _log.error("%s: %s", type(e).__name__, e)
            return {"status": "error", "message": str(e)}

    def discover_models(self) -> list[dict[str, Any]]:
        """发现本地已拉取的模型"""
        self._constraint_check("discover_models")
        res = self._http_request(self.api_tags)
        if "models" in res:
            return res["models"]
        return []

    def generate(
        self, model: str, prompt: str, system: str | None = None, options: dict | None = None
    ) -> dict[str, Any]:
        """执行推理生成"""
        self._constraint_check(f"generate: {model}")

        payload = {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "system": system or "You are a helpful assistant within the B-OS (SharedBrain) ecosystem.",
            "options": options or {},
        }

        start_time = time.time()
        res = self._http_request(self.api_generate, payload)
        duration_ms = int((time.time() - start_time) * 1000)

        if "response" in res:
            return {
                "status": "success",
                "content": res["response"],
                "metadata": {
                    "model": model,
                    "tokens": res.get("eval_count", 0),
                    "latency_ms": duration_ms,
                },
            }
        return {"status": "error", "message": res.get("message", "Unknown error")}

    def get_embeddings(self, model: str, prompt: str) -> dict[str, Any]:
        """生成向量嵌入"""
        self._constraint_check(f"embeddings: {model}")

        payload = {
            "model": model,
            "prompt": prompt,
        }

        res = self._http_request(self.api_embeddings, payload)

        if "embedding" in res:
            return {
                "status": "success",
                "embedding": res["embedding"],
                "metadata": {"model": model},
            }
        return {"status": "error", "message": res.get("message", "Unknown error")}

    def sync_to_gateway(self) -> None:
        """将本地发现的模型同步至 CognitiveGateway"""
        models = self.discover_models()
        if not models:
            return

        try:
            from .organs.engine.cognitive_gateway import Gateway  # type: ignore[import-not-found]

            for m in models:
                name = m.get("name", "unknown")
                # 基础打分逻辑 (Leviathan v2.0 启发式映射)
                iq = 6.0
                specs = ["general"]

                if "llama3" in name.lower():
                    iq = 7.8
                    specs = ["reasoning", "general"]
                elif "qwen" in name.lower():
                    iq = 7.5
                    specs = ["code", "general"]
                elif "phi3" in name.lower() or "mistral" in name.lower():
                    iq = 7.0
                    specs = ["fast", "general"]

                card = {
                    "model_id": f"ollama-{name}",
                    "provider": "ollama-local",
                    "iq_score": iq,
                    "cost_per_1k": 0.0,  # 本地算力对 EU 免费
                    "latency_avg": 500,  # 预估延迟
                    "quota_remains": 1.0,
                    "is_free": 1,
                    "specialties": specs,
                }
                Gateway.register_model(card)
        except (TypeError, ValueError, AttributeError):
            _log.info("[!] OllamaSynapse failed to sync with Gateway: {e}")

    def validate_internal_state(self) -> bool:
        """检查 Ollama 服务是否在线"""
        try:
            with urllib.request.urlopen(self.host, timeout=2) as response:  # noqa: S310
                return response.status == 200
        except OSError as e:
            _log.error("%s: %s", type(e).__name__, e)
            return False


if __name__ == "__main__":
    synapse = OllamaSynapse()
    _log.info("Ollama Synapse Online: {synapse.validate_internal_state()}")
    if synapse.validate_internal_state():
        _log.info("Models: {synapse.discover_models()}")

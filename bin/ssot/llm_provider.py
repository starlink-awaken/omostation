#!/usr/bin/env python3
"""llm_provider.py — LLM 提供方适配器（aetherforge BOS + omlxc 回退）

依据 .omo/_knowledge/patterns/doc-l0-mof-mapping-governance.md Wave 2:
OntoEKG 的 LLM 增强层可注入后端。默认 aetherforge（BOS MCP proxy），
服务未部署/未运行/超时时优雅降级到 omlxc，两者都不可用时返回 None。

用法:
    from llm_provider import llm_classify
    note = llm_classify({"name": "adr", "count": 640})
"""

import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

AETHERFORGE_URI = os.environ.get(
    "AETHERFORGE_BOS_URI", "bos://memory/aetherforge/mcp-server"
)
OMLXC_BASE = os.environ.get("OMLXC_BASE_URL", "http://127.0.0.1:8000/v1")
OMLXC_MODEL = os.environ.get("OMLXC_MODEL", "GLM-4.7-Flash-MLX-8bit")


def _aetherforge_call(prompt: str, timeout: int = 15) -> str | None:
    """通过 agora BOS 网关调用 aetherforge MCP（HTTP proxy 模式）。

    网关地址由 AGORA_BASE_URL 指定（默认 localhost:8090）。失败返回 None。
    """
    base = os.environ.get("AGORA_BASE_URL", "http://127.0.0.1:8090").rstrip("/")
    url = f"{base}/bos/{AETHERFORGE_URI}"
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {"name": "generate", "arguments": {"prompt": prompt}},
    }
    try:
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode())
        result = data.get("result", {})
        if isinstance(result, dict):
            for item in result.get("content", []):
                if item.get("type") == "text":
                    return item["text"]
        return str(result)
    except (urllib.error.URLError, OSError, json.JSONDecodeError):
        return None


def _omlxc_call(prompt: str, timeout: int = 30) -> str | None:
    """回退: omlxc OpenAI 兼容端点。失败返回 None。"""
    payload = {
        "model": OMLXC_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 128,
    }
    try:
        req = urllib.request.Request(
            f"{OMLXC_BASE}/chat/completions",
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode())
        return data["choices"][0]["message"]["content"]
    except (urllib.error.URLError, OSError, KeyError, IndexError, json.JSONDecodeError):
        return None


def llm_classify(concept: dict, backend: str = "auto") -> str | None:
    """对候选概念做语义分类（返回一句分类说明）。

    backend: auto(先 aetherforge 后 omlxc) / aetherforge / omlxc / none
    none 或无后端可用返回 None（调用方保持规则式基线）。
    """
    name = concept.get("name", "?")
    count = concept.get("count", 0)
    dim = concept.get("dimension", "?")
    prompt = (
        f"在模型驱动治理体系中，概念 '{name}'（出现 {count} 次，dimension={dim}）"
        f"应归类到哪个领域？用一句话回答。"
    )
    if backend == "none":
        return None
    if backend in ("auto", "aetherforge"):
        note = _aetherforge_call(prompt)
        if note:
            return note.strip()
        if backend == "aetherforge":
            return None
    if backend in ("auto", "omlxc"):
        return _omlxc_call(prompt)
    return None


if __name__ == "__main__":
    # 自检: 打印可用后端
    probe = {"name": "adr", "count": 640, "dimension": "X3", "surface": "L3"}
    note = llm_classify(probe, backend="none")
    print(f"none 后端: {note!r} (应 None)")

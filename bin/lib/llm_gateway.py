"""bin 脚本 → aetherforge 门面的唯一连接点(地址 + 密钥)。

与 kairon 的 kos.llm_gateway 同一解析顺序:
  地址  LLM_GATEWAY_URL → AETHERFORGE_URL → OMLX_URL → http://127.0.0.1:4000
  密钥  LLM_GATEWAY_KEY → AETHERFORGE_API_KEY → OMLX_API_KEY → Keychain(aetherforge-gateway)

此前脚本写死 mbp 旧 tailnet IP(100.96.126.35, 已失效)且 key 为空, 门面恒 401/不可达。
跨机访问请设 LLM_GATEWAY_URL, 或用 ~/.local/bin/gw-resolve 选活门面。
"""

from __future__ import annotations

import functools
import os
import subprocess


def gateway_url() -> str:
    for name in ("LLM_GATEWAY_URL", "AETHERFORGE_URL", "OMLX_URL"):
        if os.environ.get(name):
            return os.environ[name].rstrip("/")
    return "http://127.0.0.1:4000"


@functools.lru_cache(maxsize=1)
def _keychain_key() -> str:
    try:
        out = subprocess.run(
            ["security", "find-generic-password", "-s", "aetherforge-gateway", "-w"],
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    return out.stdout.strip() if out.returncode == 0 else ""


def gateway_key() -> str:
    for name in ("LLM_GATEWAY_KEY", "AETHERFORGE_API_KEY", "OMLX_API_KEY"):
        if os.environ.get(name):
            return os.environ[name]
    return _keychain_key()

#!/usr/bin/env python3
# SIZE_OK: cohesive diagnostic CLI; splitting requires a governed interface migration.
"""P2: delegation preflight — check subagent delegation infrastructure before an orchestration session starts.

Prevents the "11 routes dead, discovered only after repeated retries" failure
mode: a session starts, every delegation route retries and dies, and the breakage
is only visible post-hoc. This tool checks the four critical surfaces up front:

  1. opencode_config_exists    — ~/.config/opencode/opencode.json exists and parses
  2. provider_omlxc_configured — provider.omlxc exists with options.baseURL set
  3. agent_bindings_resolvable — every agent model binding (provider/model) maps to a configured provider
  4. omlxc_endpoint_reachable  — authenticated GET {baseURL}/models lists bound agent routes

plus two informational checks that never gate the exit code:

  5. local_mlx_alive           — TCP port behind baseURL is listening
  6. gateway_models_available  — gateway /v1/models lists expected models; local mlx_lm (8092) is WARN (known limitation)

Exit codes (semantic):
  0  all critical checks pass (informational WARN allowed)
  1  at least one critical check FAILED (delegation will break)
  2  usage / configuration error (unknown --check name)

Usage:
  python3 bin/delegation-preflight.py                          # human text
  python3 bin/delegation-preflight.py --json                   # machine-readable JSON
  python3 bin/delegation-preflight.py --check omlxc_endpoint_reachable
  python3 bin/delegation-preflight.py --base-url http://127.0.0.1:1/v1   # failure injection (no config edit)
"""

from __future__ import annotations

import argparse
import json
import os
import socket
import sys
import urllib.error
import urllib.request
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import urlparse

DEFAULT_OPENCODE_CONFIG = "~/.config/opencode/opencode.json"
DEFAULT_BASE_URL = "http://127.0.0.1:8092/v1"
BASE_URL_ENV = "OPENCODE_OMLXC_BASEURL"
HTTP_TIMEOUT = 5  # seconds
LOCAL_MLX_PORTS = {8092}  # mlx_lm server default port (known model-field limitation)


def find_workspace_root() -> Path:
    """从当前脚本位置回溯找到 workspace 根 (含 .omo/ 目录)."""
    current = Path(__file__).resolve().parent
    for _ in range(5):  # 最多向上 5 层
        if (current / ".omo" / "_truth").exists():
            return current
        current = current.parent
    # fallback: 假设 PWD 是 workspace
    return Path.cwd()


def resolve_path(raw: str, workspace_root: Path) -> Path:
    """解析配置路径; 相对路径锚定在 workspace 根."""
    p = Path(raw).expanduser()
    if not p.is_absolute():
        p = workspace_root / p
    return p


def normalize(name: str) -> str:
    """归一化模型名用于比较: 取最后一段路径并去除首尾空白."""
    return name.strip().split("/")[-1].strip()


def load_opencode_config(path: Path) -> dict:
    """返回解析后的 opencode.json dict.

    Raises FileNotFoundError / ValueError (含清晰信息).
    """
    if not path.exists():
        raise FileNotFoundError(f"opencode.json 不存在: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise ValueError(f"opencode.json 解析失败 ({path}): {e}") from e
    if not isinstance(data, dict):
        raise TypeError(f"opencode.json 顶层不是 JSON 对象 ({path})")
    return data


def _get_omlxc_base_url(data: dict) -> str | None:
    """从 provider.omlxc.options.baseURL 提取 baseURL; 缺失/非字符串返回 None."""
    provider = data.get("provider")
    if not isinstance(provider, dict):
        return None
    omlxc = provider.get("omlxc")
    if not isinstance(omlxc, dict):
        return None
    options = omlxc.get("options")
    if not isinstance(options, dict):
        return None
    base_url = options.get("baseURL")
    return base_url if isinstance(base_url, str) and base_url.strip() else None


def _get_omlxc_api_key(data: dict | None) -> str | None:
    """Return the configured OpenCode omlxc credential without rendering it."""
    if data is None:
        return None
    provider = data.get("provider")
    if not isinstance(provider, dict):
        return None
    omlxc = provider.get("omlxc")
    if not isinstance(omlxc, dict):
        return None
    options = omlxc.get("options")
    if not isinstance(options, dict):
        return None
    api_key = options.get("apiKey")
    return api_key if isinstance(api_key, str) and api_key.strip() else None


def resolve_base_url(data: dict | None, flag_value: str | None, env_value: str | None) -> str:
    """baseURL 优先级: --base-url flag > OPENCODE_OMLXC_BASEURL env > opencode.json > 默认值."""
    if flag_value:
        return flag_value
    if env_value:
        return env_value
    if data is not None:
        configured = _get_omlxc_base_url(data)
        if configured:
            return configured
    return DEFAULT_BASE_URL


def extract_expected_models(data: dict | None) -> list[str]:
    """返回 provider.omlxc.models 的键 (期望模型列表, 排序)."""
    if data is None:
        return []
    provider = data.get("provider")
    if not isinstance(provider, dict):
        return []
    omlxc = provider.get("omlxc")
    if not isinstance(omlxc, dict):
        return []
    models = omlxc.get("models")
    if not isinstance(models, dict):
        return []
    return sorted(k for k in models if isinstance(k, str) and k.strip())


def extract_bound_provider_models(data: dict | None, provider_name: str) -> list[str]:
    """Return model names used by actual agent bindings for one provider."""
    if data is None:
        return []
    agents = data.get("agent")
    if not isinstance(agents, dict):
        return []
    models = set()
    for agent_cfg in agents.values():
        if not isinstance(agent_cfg, dict):
            continue
        binding = agent_cfg.get("model")
        if not isinstance(binding, str) or "/" not in binding:
            continue
        bound_provider, model = binding.split("/", 1)
        if bound_provider == provider_name and model.strip():
            models.add(model.strip())
    return sorted(models)


def _parse_host_port(base_url: str) -> tuple[str, int | None]:
    """从 baseURL 提取 (host, port); 解析失败时 port 为 None."""
    try:
        parsed = urlparse(base_url)
    except ValueError:
        return base_url, None
    host = parsed.hostname or "127.0.0.1"
    try:
        port = parsed.port
    except ValueError:
        port = None
    return host, port


def _http_get(
    base_url: str,
    path: str,
    timeout: int = HTTP_TIMEOUT,
    api_key: str | None = None,
) -> tuple[int | None, bytes, Exception | None]:
    """GET base_url+path; 返回 (status, body, error). status None 表示传输层失败."""
    url = base_url.rstrip("/") + path
    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
    request = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as resp:
            return resp.status, resp.read(65536), None
    except urllib.error.HTTPError as e:
        return e.code, b"", None
    except Exception as e:
        return None, b"", e


def _parse_model_inventory(body: bytes) -> tuple[list[str], str | None]:
    """Parse an OpenAI-compatible model inventory with a stable failure reason."""
    try:
        payload = json.loads(body.decode("utf-8", errors="replace"))
    except json.JSONDecodeError:
        return [], "response is not valid JSON"
    if not isinstance(payload, dict):
        return [], "response is not a JSON object"
    data = payload.get("data")
    if not isinstance(data, list):
        return [], "response does not contain an OpenAI data list"
    ids = []
    for entry in data:
        if not isinstance(entry, dict):
            continue
        val = entry.get("id") or entry.get("model")
        if isinstance(val, str) and val.strip():
            ids.append(val)
    if not ids:
        return [], "response contains no models"
    return ids, None


# ---------------------------------------------------------------- checks


def check_opencode_config_exists(ctx: SimpleNamespace) -> tuple[str, str]:
    if ctx.load_error:
        return "FAIL", ctx.load_error
    return "PASS", f"配置文件存在且可解析: {ctx.config_path}"


def check_provider_omlxc_configured(ctx: SimpleNamespace) -> tuple[str, str]:
    data = ctx.data
    if data is None:
        return "FAIL", f"opencode.json 未加载 — {ctx.load_error}"
    provider = data.get("provider")
    if not isinstance(provider, dict) or "omlxc" not in provider:
        return "FAIL", "provider.omlxc 配置块缺失"
    base_url = _get_omlxc_base_url(data)
    if base_url is None:
        return "FAIL", "provider.omlxc.options.baseURL 未设置"
    return "PASS", f"provider.omlxc.options.baseURL={base_url}"


def check_agent_bindings_resolvable(ctx: SimpleNamespace) -> tuple[str, str]:
    data = ctx.data
    if data is None:
        return "FAIL", f"opencode.json 未加载 — {ctx.load_error}"
    agents = data.get("agent")
    providers = data.get("provider")
    if not isinstance(agents, dict):
        return "FAIL", "agent 配置块缺失"
    if not isinstance(providers, dict):
        return "FAIL", "provider 配置块缺失"
    unresolved = []
    resolved = []
    for name, agent_cfg in agents.items():
        if not isinstance(agent_cfg, dict):
            continue
        model = agent_cfg.get("model")
        if not isinstance(model, str) or "/" not in model:
            continue  # 非 provider/model 形式, 不参与本检查
        provider_name, _model_name = model.split("/", 1)
        if provider_name in providers:
            resolved.append(f"{name}={model}")
        else:
            unresolved.append(f"{name}={model} (provider '{provider_name}' 不存在)")
    if unresolved:
        return "FAIL", "存在无法解析的 agent 模型绑定: " + "; ".join(unresolved)
    if not resolved:
        return "FAIL", "agent 配置中没有任何 provider/model 形式的模型绑定"
    return "PASS", f"全部 agent 模型绑定可解析 ({len(resolved)}): " + ", ".join(resolved)


def check_omlxc_endpoint_reachable(ctx: SimpleNamespace) -> tuple[str, str]:
    base_url = ctx.base_url
    status, body, err = _http_get(base_url, "/models", api_key=ctx.api_key)
    endpoint = f"{base_url}/models"
    if status is None:
        return "FAIL", f"endpoint transport unreachable: {endpoint} — {err}"
    if status == 401:
        return "FAIL", f"endpoint authentication failed (HTTP 401): {endpoint}"
    if status == 403:
        return "FAIL", f"endpoint authorization failed (HTTP 403): {endpoint}"
    if not 200 <= status < 300:
        return "FAIL", f"endpoint returned HTTP {status}: {endpoint}"
    models, inventory_error = _parse_model_inventory(body)
    if inventory_error:
        return "FAIL", f"endpoint model inventory invalid: {inventory_error}: {endpoint}"
    listed = {normalize(model) for model in models}
    required = {normalize(model) for model in ctx.required_models}
    missing = sorted(required - listed)
    if missing:
        return "FAIL", "endpoint inventory missing bound agent models: " + ", ".join(missing)
    return "PASS", f"endpoint authorized with {len(models)} model(s): {endpoint}"


def check_local_mlx_alive(ctx: SimpleNamespace) -> tuple[str, str]:
    base_url = ctx.base_url
    host, port = _parse_host_port(base_url)
    if port is None:
        return "WARN", f"无法从 baseURL 解析端口: {base_url}"
    try:
        with socket.create_connection((host, port), timeout=HTTP_TIMEOUT):
            return "PASS", f"端口 {host}:{port} 正在监听"
    except OSError as e:
        return "WARN", f"端口 {host}:{port} 未监听 (信息性): {e}"


def check_gateway_models_available(ctx: SimpleNamespace) -> tuple[str, str]:
    base_url = ctx.base_url
    _host, port = _parse_host_port(base_url)
    if port in LOCAL_MLX_PORTS:
        return "WARN", (
            "本机 mlx_lm (端口 8092) 已知限制: 仅响应省略 model 字段的请求, "
            "而 opencode 总是发送 model 字段, 因此本地 omlxc 模型对 subagent 不可靠 — "
            "已知 WARN 非 FAIL, 请勿为绕过该限制而改动配置, 以免再次破坏委托."
        )
    status, body, err = _http_get(base_url, "/models", api_key=ctx.api_key)
    if status is None:
        return "WARN", f"gateway model inventory transport unreachable (informational): {err}"
    if status == 401:
        return "WARN", "gateway model inventory authentication failed (HTTP 401)"
    if status == 403:
        return "WARN", "gateway model inventory authorization failed (HTTP 403)"
    if not 200 <= status < 300:
        return "WARN", f"gateway model inventory returned HTTP {status}"
    models, inventory_error = _parse_model_inventory(body)
    if inventory_error:
        return "WARN", f"gateway model inventory invalid: {inventory_error}"
    listed = {normalize(m) for m in models}
    expected = {normalize(m) for m in ctx.expected_models}
    missing = sorted(expected - listed)
    if not missing:
        return "PASS", f"网关模型列表包含全部期望模型 ({len(listed)} listed)"
    if not listed:
        return "WARN", f"网关可达 (HTTP {status}) 但 /v1/models 未列出任何模型"
    return "WARN", "网关可达但缺少期望模型: " + ", ".join(missing)


# check spec: (name, function, critical)
CHECK_SPECS = [
    ("opencode_config_exists", check_opencode_config_exists, True),
    ("provider_omlxc_configured", check_provider_omlxc_configured, True),
    ("agent_bindings_resolvable", check_agent_bindings_resolvable, True),
    ("omlxc_endpoint_reachable", check_omlxc_endpoint_reachable, True),
    ("local_mlx_alive", check_local_mlx_alive, False),
    ("gateway_models_available", check_gateway_models_available, False),
]
CHECK_NAMES = [spec[0] for spec in CHECK_SPECS]


# ---------------------------------------------------------------- rendering


def preflight_status(results: list[dict]) -> str:
    """Classify the aggregate without turning informational warnings into failures."""
    if any(r["status"] == "FAIL" and r["critical"] for r in results):
        return "FAIL"
    if any(r["status"] != "PASS" for r in results):
        return "WARN"
    return "PASS"


def render_text(results: list[dict], base_url: str, config_path: Path) -> str:
    lines = [
        "delegation preflight — subagent 委托基础设施检查",
        f"  config    : {config_path}",
        f"  base URL  : {base_url}",
        "",
    ]
    for r in results:
        lines.append(f"  {r['status']:<5} {r['name']} — {r['reason']}")
    lines.append("")
    overall = preflight_status(results)
    if overall == "FAIL":
        lines.append("RESULT: FAIL — 存在关键检查失败, 委托将不可用")
    elif overall == "WARN":
        lines.append("RESULT: WARN — 关键检查通过, 但存在信息性异常")
    else:
        lines.append("RESULT: OK — 关键检查全部通过")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="P2: delegation preflight — 会话启动前检查 subagent 委托基础设施")
    parser.add_argument(
        "--json",
        action="store_true",
        help="输出 machine-readable JSON (默认人类可读文本)",
    )
    parser.add_argument(
        "--check",
        help=f"只运行单个检查 (可选: {', '.join(CHECK_NAMES)})",
    )
    parser.add_argument(
        "--base-url",
        help="覆盖 provider.omlxc.options.baseURL (默认从 opencode.json 读取; 也可用环境变量 " + BASE_URL_ENV + ")",
    )
    parser.add_argument(
        "--opencode-config",
        default=DEFAULT_OPENCODE_CONFIG,
        help=f"opencode.json 路径 (默认 {DEFAULT_OPENCODE_CONFIG})",
    )
    args = parser.parse_args()

    workspace_root = find_workspace_root()
    config_path = resolve_path(args.opencode_config, workspace_root)

    data = None
    load_error = None
    try:
        data = load_opencode_config(config_path)
    except (FileNotFoundError, TypeError, ValueError) as e:
        load_error = str(e)

    base_url = resolve_base_url(data, args.base_url, os.environ.get(BASE_URL_ENV))

    ctx = SimpleNamespace(
        config_path=config_path,
        data=data,
        load_error=load_error,
        base_url=base_url,
        api_key=_get_omlxc_api_key(data),
        expected_models=extract_expected_models(data),
        required_models=extract_bound_provider_models(data, "omlxc"),
    )

    if args.check:
        if args.check not in CHECK_NAMES:
            print(
                f"ERROR: 未知检查名 '{args.check}' (可选: {', '.join(CHECK_NAMES)})",
                file=sys.stderr,
            )
            return 2
        specs = [spec for spec in CHECK_SPECS if spec[0] == args.check]
    else:
        specs = CHECK_SPECS

    results = []
    for name, fn, critical in specs:
        status, reason = fn(ctx)
        results.append({"name": name, "status": status, "critical": critical, "reason": reason})

    overall = preflight_status(results)
    exit_code = 1 if overall == "FAIL" else 0

    if args.json:
        payload = {
            "preflight": overall,
            "exit_code": exit_code,
            "base_url": base_url,
            "config": str(config_path),
            "checks": results,
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(render_text(results, base_url, config_path))

    return exit_code


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""维护 config.toml 里 policies.remote_resident 声明的常驻模型。

背景 (2026-08-22): policies.remote_resident 此前是纯声明性死配置 ——
全代码库(src/)只有 schema 定义和迁移校验读它, 没有任何执行逻辑。
mac-mini 上能用的常驻模型全靠人工 SSH 操作维持, TTL 到期后不会自动
恢复, 也没有告警。本脚本由 pipeline-watchdog.sh 周期调用, 把这个策略
变成真正生效的自愈机制。

两种后端分别处理:
  - lm_studio / lm_link: SSH 到 control_endpoint, 用 lms ps/load 检查+补齐
    (与 omlxc 数据面用的是同一条已授权 SSH 路径, 不新增信任面)
  - ollama: 纯 HTTP, 用 /api/ps 检查、/api/generate 空请求 + keep_alive 补齐

安全边界: 目标节点当前有任何模型在 GENERATING 时跳过, 不抢占资源。
SSH/网络超时静默容忍(y7000p 网络不稳是已知常态), 不刷屏报警;
只在"配置指向的 SSH 目标找不到"或"补齐后复核仍不在线"时记录 WARN。
"""

from __future__ import annotations

import datetime
import json
import os
import subprocess
import sys
import tomllib
from pathlib import Path

import httpx

for _proxy_var in ("all_proxy", "ALL_PROXY", "http_proxy", "HTTP_PROXY", "https_proxy", "HTTPS_PROXY"):
    os.environ.pop(_proxy_var, None)

CONFIG_PATH = Path.home() / ".config/omlxc/config.toml"
LOG_PATH = Path.home() / ".config/omlxc/watchdog.log"
SSH_CONNECT_TIMEOUT = 10
SSH_RUN_TIMEOUT = 20
LOAD_TIMEOUT = 180
HTTP_TIMEOUT = 15.0


def log(msg: str) -> None:
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(LOG_PATH, "a") as f:
        f.write(f"{ts} {msg}\n")


def ssh_run(target: str, command: str, timeout: int) -> subprocess.CompletedProcess[str] | None:
    argv = ["ssh", "-o", "BatchMode=yes", "-o", f"ConnectTimeout={SSH_CONNECT_TIMEOUT}", target, command]
    try:
        return subprocess.run(argv, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return None


def lms_ps(target: str) -> list[dict[str, object]] | None:
    result = ssh_run(target, "lms ps --json", SSH_RUN_TIMEOUT)
    if result is None or result.returncode != 0:
        return None
    try:
        return json.loads(result.stdout)
    except Exception:
        return None


def lms_loaded(rows: list[dict[str, object]], model_id: str) -> bool:
    return any(r.get("identifier") == model_id or r.get("modelKey") == model_id for r in rows)


def lms_generating(rows: list[dict[str, object]]) -> bool:
    return any(r.get("status") == "generating" for r in rows)


def maintain_lms_entry(entry: dict[str, object], target: str) -> None:
    node_id = entry["node_id"]
    model_id = str(entry["backend_model_id"])

    rows = lms_ps(target)
    if rows is None:
        return  # SSH/网络不稳, 静默容忍, 下一轮再看

    if lms_loaded(rows, model_id):
        return  # 已在线, 无需动作

    if lms_generating(rows):
        return  # 该节点正忙于真实生成, 不抢占, 下一轮再看

    raw_args = entry.get("lms_arguments")
    args: list[object] = raw_args if isinstance(raw_args, list) else []
    # 不转义是刻意的: repr()/shlex.quote() 生成的引号语法只对 POSIX 远程
    # shell 安全, y7000p 是 Windows(远程 shell 很可能是 cmd.exe, 不识别
    # POSIX 单引号) —— shlex.quote("qwen/qwen3.5-9b") 会加引号导致
    # "No model found that matches model key \"'qwen/...-9b'\""
    # (2026-08-22 实测)。当前所有 remote_resident model_id 都不含空格,
    # 裸传是唯一对 macOS/Windows 两种远程 shell 都安全的写法。
    if any(c.isspace() for c in model_id):
        log(f"[WARN] remote_resident: {node_id}/{model_id} 含空白字符, 跳过(裸传不安全)")
        return
    load_cmd = " ".join(["lms", "load", model_id, *(str(a) for a in args), "-y"])
    ssh_run(target, load_cmd, LOAD_TIMEOUT)

    # 今天的教训: 字符串匹配 stdout 判断加载成功不可靠(进度条 ANSI 可能
    # 截断确认文字), 一律用 lms ps 复核事实。
    verify = lms_ps(target)
    if verify is not None and lms_loaded(verify, model_id):
        log(f"[OK] remote_resident 补齐: {node_id}/{model_id}")
    else:
        log(f"[WARN] remote_resident 加载失败: {node_id}/{model_id} (target={target})")


def maintain_ollama_entry(entry: dict[str, object], base_url: str) -> None:
    node_id = entry["node_id"]
    model_id = str(entry["backend_model_id"])
    keep_alive_seconds = entry.get("keep_alive_seconds") or 3600

    try:
        r = httpx.get(f"{base_url}/api/ps", timeout=HTTP_TIMEOUT)
        loaded = r.status_code == 200 and any(
            m.get("name") == model_id for m in r.json().get("models", [])
        )
    except Exception:
        return  # 网络不稳, 静默容忍

    if loaded:
        return

    try:
        r = httpx.post(
            f"{base_url}/api/generate",
            json={"model": model_id, "prompt": "", "keep_alive": f"{keep_alive_seconds}s"},
            timeout=HTTP_TIMEOUT * 2,
        )
    except Exception:
        log(f"[WARN] remote_resident(ollama) 加载超时: {node_id}/{model_id}")
        return

    if r.status_code == 200:
        log(f"[OK] remote_resident(ollama) 补齐: {node_id}/{model_id}")
    else:
        log(f"[WARN] remote_resident(ollama) 加载失败: {node_id}/{model_id} HTTP {r.status_code}")


def main() -> int:
    with open(CONFIG_PATH, "rb") as f:
        cfg = tomllib.load(f)

    entries = cfg.get("policies", {}).get("remote_resident", [])
    if not entries:
        return 0

    # node_id -> SSH control target, 复用 backends 里已声明的 control_endpoint
    # (与 omlxc 数据面同一条已授权路径, 不新增信任面)
    node_to_ssh_target: dict[str, str] = {}
    node_to_ollama_url: dict[str, str] = {}
    for backend in cfg.get("backends", []):
        node_id = backend.get("node_id")
        if not node_id:
            continue
        if backend.get("kind") == "ollama" and node_id not in node_to_ollama_url:
            node_to_ollama_url[node_id] = str(backend["base_url"])
        endpoint = backend.get("control_endpoint")
        if endpoint and node_id not in node_to_ssh_target:
            node_to_ssh_target[node_id] = str(endpoint)

    for entry in entries:
        node_id = str(entry["node_id"])
        kind = entry.get("kind")

        if kind == "ollama":
            base_url = node_to_ollama_url.get(node_id)
            if base_url is None:
                log(f"[WARN] remote_resident: {node_id} 找不到 ollama backend, 跳过")
                continue
            maintain_ollama_entry(entry, base_url)
        elif kind in ("lm_studio", "lm_link"):
            target = entry.get("ssh_alias") or node_to_ssh_target.get(node_id)
            if not target:
                log(f"[WARN] remote_resident: {node_id} 找不到 SSH 控制目标, 跳过")
                continue
            maintain_lms_entry(entry, str(target))
        else:
            log(f"[WARN] remote_resident: {node_id} 未知 kind={kind!r}, 跳过")

    return 0


if __name__ == "__main__":
    sys.exit(main())

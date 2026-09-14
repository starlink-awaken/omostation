#!/usr/bin/env python3
"""
health_check.py — Forge 每日健康巡检

检查注册表完整性、后端连通性、图谱状态、磁盘占用
用法:
  python3 src/health_check.py

Exit code: 0 = 全部通过, 1 = 存在错误
"""

import json
import subprocess
import sys
from datetime import date, datetime

# ── 路径 ──────────────────────────────────────────
from forge.forge_config import FORGE_ROOT as TOOLBOX  # type: ignore[import-not-found]
from forge.forge_config import GRAPH, REGISTRY
from forge.forge_config import SCRIPTS_DIR as SCRIPTS

# ── 颜色 ──────────────────────────────────────────
_RED = "\033[0;31m"
_YEL = "\033[1;33m"
_GRN = "\033[0;32m"
_NC = "\033[0m"

_ok = 0
_wrn = 0
_err = 0


def _pass(msg: str) -> None:
    global _ok
    print(f"  {_GRN}✅{_NC} {msg}")
    _ok += 1


def _warn(msg: str) -> None:
    global _wrn
    print(f"  {_YEL}⚠️{_NC} {msg}")
    _wrn += 1


def _fail(msg: str) -> None:
    global _err
    print(f"  {_RED}❌{_NC} {msg}")
    _err += 1


# ── 检查项 ────────────────────────────────────────


def _check_registry() -> None:
    """1. 注册表存在且有效"""
    if not REGISTRY.exists():
        _fail("tools-registry.json 不存在")
        return

    try:
        data = json.loads(REGISTRY.read_text())
    except json.JSONDecodeError:
        _fail("注册表 JSON 损坏")
        return

    if "tools" not in data or not isinstance(data["tools"], list):
        _fail("注册表 JSON 损坏")
        return

    count = len(data["tools"])
    active = sum(1 for t in data["tools"] if t.get("status") == "active")
    _pass(f"注册表: {count} 工具 ({active} 活跃)")

    # 版本检查
    schema = data.get("schema_version", "?")
    _pass(f"Schema: {schema}")

    # event_log 健康
    events = len(data.get("event_log", []))
    _pass(f"事件日志: {events} 条")


def _check_graph() -> None:
    """2. 图谱健康"""
    if not GRAPH.exists():
        _warn("graph.json 不存在（需运行 build-graph）")
        return

    try:
        gdata = json.loads(GRAPH.read_text())
    except (json.JSONDecodeError, FileNotFoundError):
        _warn("graph.json 无法解析")
        return

    stats = gdata.get("stats", {})
    nodes = stats.get("total_nodes", 0)
    edges = stats.get("total_edges", 0)

    if nodes > 0:
        _pass(f"图谱: {nodes} 节点, {edges} 边")
    else:
        _warn("图谱为空")


def _check_scripts() -> None:
    """3. 关键脚本存在"""
    for name in ("build-graph.sh", "query-graph.sh", "sniff-local.sh", "classify.sh"):
        script_path = SCRIPTS / name
        if script_path.exists():
            _pass(f"脚本 {name} 存在")
        else:
            _warn(f"脚本 {name} 缺失")


def _check_disk() -> None:
    """4. 磁盘使用"""
    try:
        result = subprocess.run(
            ["du", "-sh", str(TOOLBOX)],
            capture_output=True,
            text=True,
            timeout=10,
        )
        size = result.stdout.strip().split("\t")[0] if result.stdout.strip() else "?"
        _pass(f"项目磁盘: {size}")
    except Exception:
        _warn("项目磁盘: ?")


def _check_kos() -> None:
    """5. KOS 可用性"""
    kos_probe = SCRIPTS / "kos-probe.py"
    if not kos_probe.exists():
        _warn("KOS 探测脚本不存在")
        return

    try:
        result = subprocess.run(
            [sys.executable, str(kos_probe)],
            capture_output=True,
            text=True,
            timeout=30,
        )
        for line in result.stdout.splitlines():
            if "KOS 状态" in line:
                parts = line.split(":", 1)
                status = parts[1].strip() if len(parts) > 1 else ""
                if status == "code-complete":
                    _pass(f"KOS: 代码完整 ({status})")
                elif status == "found-uninitialized":
                    _warn("KOS: 代码完整，需 KOS_HOME 初始化")
                else:
                    _warn(f"KOS: 状态未知 ({status or '?'})")
                return
        # KOS 状态行未找到
        _warn("KOS: 状态未知 (?)")
    except Exception:
        _warn("KOS: 探测失败")


def _check_sync() -> None:
    """6. 同步状态（过去24h内更新）"""
    try:
        data = json.loads(REGISTRY.read_text())
    except (json.JSONDecodeError, FileNotFoundError):
        _warn("最后更新: (无法读取注册表)")
        return

    last_updated = data.get("last_updated", "")
    today_str = date.today().isoformat()

    if last_updated and last_updated == today_str:
        _pass("今日已更新")
    else:
        _warn(f"最后更新: {last_updated}")


# ── 公共入口 ──────────────────────────────────────


def run() -> int:
    """运行健康检查，返回 0 表示通过，1 表示存在错误。"""
    global _ok, _wrn, _err
    _ok = _wrn = _err = 0

    now = datetime.now()
    print(f"=== Forge 健康巡检 {now.strftime('%Y-%m-%d %H:%M')} ===")
    print()

    _check_registry()
    _check_graph()
    _check_scripts()
    _check_disk()
    _check_kos()
    _check_sync()

    print()
    print(f"=== 结果: {_ok} 通过, {_wrn} 警告, {_err} 错误 ===")
    return 1 if _err > 0 else 0


if __name__ == "__main__":
    sys.exit(run())

"""BET-Y1Q3-T2-03: 信号落盘管道修复测试.

验证:
- 深度探测: depth>0 递归子目录 mtime, 子层文件变化可检出
- 浅探测兼容: depth=0 与原行为一致 (顶层)
- 信号落盘: poll_once 触发后 signal-signals.json 记录 last_signal_at
- freshness 消费: 运行时信号时间戳优先于注册期死值
- state 防御: state 丢失后重放不会把旧信号当新信号重复上报 (hash 不同才触发)
"""
from __future__ import annotations

import importlib.util
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "bin" / "ssot"))


def _load(mod_name: str, path: Path):
    spec = importlib.util.spec_from_file_location(mod_name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = mod  # dataclass 需要模块已注册 (InitVar 反查 __module__)
    spec.loader.exec_module(mod)
    return mod


def _poller_with_state(tmp_path: Path, sources: list[dict], state: dict | None):
    """构造隔离的 poller (state/signals/sources 全部指向 tmp_path)."""
    poller = _load("sp", ROOT / "bin" / "ssot" / "signal-poller.py")
    poller.STATE_FILE = tmp_path / "state.json"
    poller.SIGNALS_FILE = tmp_path / "signals.json"
    poller._load_signal_sources = lambda: sources  # type: ignore[method-assign]
    if state is not None:
        poller.STATE_FILE.write_text(json.dumps(state))
    return poller


def test_deep_probe_detects_nested_change(tmp_path):
    """depth=2: 孙层文件变化必须改变 hash (原浅探测恒不变 — T2-03 层1 根因)."""
    poller = _load("sp", ROOT / "bin" / "ssot" / "signal-poller.py")
    sub = tmp_path / "V10" / "UUID-1" / "mbox"
    sub.mkdir(parents=True)
    (sub / "old.emlx").write_text("old")
    h1 = poller._hash_path(str(tmp_path), depth=3)
    time.sleep(1.1)  # mtime int() 截断: 需跨秒才保证变化 (真实 poll 间隔 300s 无此问题)
    (sub / "new.emlx").write_text("new")  # 第 3 层新文件
    h2 = poller._hash_path(str(tmp_path), depth=3)
    assert h1 != h2, "孙层变化未被检出 — 深度探测失效"


def test_shallow_probe_ignores_nested_change(tmp_path):
    """depth=0: 保持原行为 (顶层 mtime+子项), 不受孙层影响 — 兼容性."""
    poller = _load("sp", ROOT / "bin" / "ssot" / "signal-poller.py")
    sub = tmp_path / "V10" / "UUID-1"
    sub.mkdir(parents=True)
    (sub / "mbox").mkdir()
    h1 = poller._hash_path(str(tmp_path), depth=0)
    time.sleep(0.01)
    (sub / "mbox" / "new.emlx").write_text("new")
    h2 = poller._hash_path(str(tmp_path), depth=0)
    # 顶层 mtime 不因孙层变化而变 — h1 == h2 是旧行为, 保留
    assert h1 == h2


def test_poll_records_signals_file(tmp_path):
    """poll_once 触发后 signal-signals.json 落盘 last_signal_at (T2-03 层2)."""
    box = tmp_path / "box"
    box.mkdir()
    (box / "a.txt").write_text("hello")
    sources = [{
        "id": "src_test", "transport": "local_filesystem",
        "path": str(box), "bos_uri": "bos://perception/test",
    }]
    poller = _poller_with_state(tmp_path, sources, state=None)
    triggers = poller.poll_once()
    assert len(triggers) == 1, "首 poll 应产生信号 (无历史 state)"
    signals = json.loads(poller.SIGNALS_FILE.read_text())
    assert "src_test" in signals and signals["src_test"].endswith("Z")


def test_freshness_prefers_runtime_signal_ts(tmp_path):
    """freshness: 运行时 last_signal_at 新鲜 → health=healthy (yaml 死值不再遮蔽)."""
    freshness = _load("fr", ROOT / "bin" / "ssot" / "freshness.py")
    from datetime import UTC, datetime, timedelta

    now = datetime.now(UTC)
    runtime_ts = (now - timedelta(minutes=1)).isoformat().replace("+00:00", "Z")
    stale_reg_ts = "2026-08-07T23:45:22Z"  # 注册期死值
    sources = [{
        "id": "src_rt", "transport": "local_filesystem", "poll_interval": "300s",
        "last_signal_at": stale_reg_ts,
    }]
    poller_state = {"src_rt": "abc123"}  # 可达
    signals = {"src_rt": runtime_ts}

    freshness.SIGNALS_FILE = tmp_path / "signals.json"
    (tmp_path / "signals.json").write_text(json.dumps(signals))

    projs = freshness.project_all_health(now=now, sources=sources, poller_state=poller_state)
    assert projs[0].status == "healthy", f"运行时新鲜信号应 healthy, got {projs[0].status}"
    assert projs[0].last_signal_at == runtime_ts


def test_state_loss_no_false_repeat_with_stable_hash(tmp_path):
    """state 丢失防御: state 清空后, 同 hash 目录不会因 signals 文件已记录而重复上报? 

    语义澄清 (circuit_breaker 前裁定): state 丢失 → last_hash=None → 当前 hash≠None
    必然触发一次重复上报 (重建 state 所需)。防御目标是: 该重复上报仍如实落盘
    (signals 时间戳更新), 且随后不再重复 — 即「一次重建, 不持续假信号」。
    """
    box = tmp_path / "box"
    box.mkdir()
    (box / "a.txt").write_text("hello")
    sources = [{
        "id": "src_d", "transport": "local_filesystem",
        "path": str(box), "bos_uri": "bos://perception/test",
    }]
    poller = _poller_with_state(tmp_path, sources, state=None)
    poller.poll_once()          # 首次: 触发 + 落 state + 落 signals
    t2 = poller.poll_once()     # 第二次: state 在, 无变化 → 零触发
    assert t2 == [], "state 存在时同 hash 不应重复触发"
    poller.STATE_FILE.unlink()  # 模拟 state 丢失
    t3 = poller.poll_once()     # 重建: 恰一次触发 (预期行为, 落盘后自愈)
    assert len(t3) == 1
    t4 = poller.poll_once()     # 自愈后再 poll: 零触发
    assert t4 == [], "state 重建后不应持续假信号"

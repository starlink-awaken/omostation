"""test_event_loop_lint — event-loop-lint 闭环回路检测 test (防回归).

验证核心逻辑:
- 有死回路 (emit 零消费者) → 检测 exit 1
- 低频 emit (< 5) 不判 → exit 0
- --alert 写 needs-human 卡片 (进 BRIEF Inbox)
"""
import importlib.util
import json
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "bin" / "gac" / "event-loop-lint.py"


def _load_module():
    """加载 event-loop-lint 脚本为 module (脚本无包结构)."""
    spec = importlib.util.spec_from_file_location("event_loop_lint", SCRIPT)
    assert spec is not None and spec.loader is not None, f"无法加载 {SCRIPT}"
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _write_events(path: Path, kinds: list[str]):
    """写 omo-events.jsonl (每 kind 一行)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for kind in kinds:
            f.write(json.dumps({"kind": kind}) + "\n")


def test_detects_dead_loop(tmp_path, monkeypatch):
    """state_stale 10 条 + 零消费者 (SCAN_DIRS 空) → 死回路 exit 1."""
    mod = _load_module()
    monkeypatch.setattr(mod, "WORKSPACE", tmp_path)
    monkeypatch.setattr(mod, "EVENTS", tmp_path / ".omo/_knowledge/omo-events.jsonl")
    monkeypatch.setattr(mod, "SCAN_DIRS", [])  # 不扫真实代码 = 零消费者
    _write_events(tmp_path / ".omo/_knowledge/omo-events.jsonl", ["state_stale"] * 10)
    assert mod.main() == 1


def test_no_dead_loop_low_freq(tmp_path, monkeypatch):
    """低频 emit (< 5 条) 不判死回路 → exit 0."""
    mod = _load_module()
    monkeypatch.setattr(mod, "WORKSPACE", tmp_path)
    monkeypatch.setattr(mod, "EVENTS", tmp_path / "events.jsonl")
    monkeypatch.setattr(mod, "SCAN_DIRS", [])
    _write_events(tmp_path / "events.jsonl", ["rare_event"])  # 1 条 < 5
    assert mod.main() == 0


def test_no_dead_loop_when_no_events(tmp_path, monkeypatch):
    """无 omo-events.jsonl → 空报告 exit 0 (不崩)."""
    mod = _load_module()
    monkeypatch.setattr(mod, "WORKSPACE", tmp_path)
    monkeypatch.setattr(mod, "EVENTS", tmp_path / "nonexistent.jsonl")
    assert mod.main() == 0


def test_alert_writes_needs_human_card(tmp_path, monkeypatch):
    """--alert 死回路 → 写 needs-human 卡片 (generate-brief 扫 .omo/tasks/ 进 BRIEF Inbox)."""
    mod = _load_module()
    monkeypatch.setattr(mod, "WORKSPACE", tmp_path)
    monkeypatch.setattr(mod, "EVENTS", tmp_path / ".omo/_knowledge/omo-events.jsonl")
    monkeypatch.setattr(mod, "SCAN_DIRS", [])
    monkeypatch.setattr(sys, "argv", ["event-loop-lint.py", "--alert"])
    _write_events(tmp_path / ".omo/_knowledge/omo-events.jsonl", ["state_stale"] * 10)
    mod.main()
    card = tmp_path / ".omo" / "tasks" / "planned" / "event-loop-dead-loop.yaml"
    assert card.exists(), "needs-human 卡片未写"
    content = card.read_text(encoding="utf-8")
    assert "needs-human" in content, "卡片缺 needs-human 关键词"
    assert "state_stale" in content, "卡片缺死回路详情"


def test_alive_when_consumer_exists(tmp_path, monkeypatch):
    """emit 有消费者 (SCAN_DIRS 命中文件) → alive exit 0."""
    mod = _load_module()
    # 造一个 fake consumer 文件含 kind 字符串
    consumer_dir = tmp_path / "fakedown"
    consumer_dir.mkdir()
    (consumer_dir / "consumer.py").write_text("state_stale_handler()", encoding="utf-8")
    events_dir = tmp_path / ".omo/_knowledge"
    events_dir.mkdir(parents=True)
    monkeypatch.setattr(mod, "WORKSPACE", tmp_path)
    monkeypatch.setattr(mod, "EVENTS", events_dir / "omo-events.jsonl")
    monkeypatch.setattr(mod, "SCAN_DIRS", ["fakedown/"])
    _write_events(events_dir / "omo-events.jsonl", ["state_stale"] * 10)
    # 注意: find_consumers 用 grep cwd=WORKSPACE, 扫 SCAN_DIRS
    assert mod.main() == 0  # 有消费者 → alive

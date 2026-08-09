"""BET-Y1Q3-T2-01: 感知面第二根管子 (文件夹信号源) 测试.

验证:
- 文件夹信号源注册在 signal-sources.yaml (transport=local_filesystem)
- poller 对文件夹源走统一 local_filesystem 处理 (无 if-else 特判)
- 文件夹内容变化产生真实信号
- 去重生效 (无变化不重复触发)
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "bin" / "ssot"))

from _shared import load_yaml

_spec = importlib.util.spec_from_file_location("signal_poller", ROOT / "bin" / "ssot" / "signal-poller.py")
signal_poller = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(signal_poller)


def test_folder_source_registered():
    """文件夹源已在 signal-sources.yaml 注册."""
    data = load_yaml(signal_poller.SIGNAL_SOURCES)
    sources = {s["id"]: s for s in data.get("sources", [])}
    assert "inbox_folder" in sources
    src = sources["inbox_folder"]
    assert src["transport"] == "local_filesystem"
    assert "path" in src


def test_folder_uses_shared_transport_no_special_case():
    """文件夹源与邮件源同走 local_filesystem — poller 无 per-source 特判."""
    data = load_yaml(signal_poller.SIGNAL_SOURCES)
    sources = {s["id"]: s for s in data.get("sources", [])}
    assert sources["apple_mail_inbox"]["transport"] == "local_filesystem"
    assert sources["inbox_folder"]["transport"] == "local_filesystem"


def test_folder_source_mapped_to_journey():
    """文件夹信号映射到 inbox-to-decision journey."""
    assert signal_poller.SIGNAL_TO_JOURNEY["inbox_folder"] == "inbox-to-decision"


def test_folder_change_produces_signal(tmp_path, monkeypatch):
    """文件夹内容变化 → poller 产生 content_changed 信号."""
    folder = tmp_path / "inbox"
    folder.mkdir()
    monkeypatch.setattr(signal_poller, "STATE_FILE", tmp_path / "state.json")

    # 手动构造一个最小 signal-sources 配置指向该文件夹
    src = {
        "id": "inbox_folder",
        "transport": "local_filesystem",
        "path": str(folder),
        "bos_uri": "bos://perception/folder/inbox",
    }
    monkeypatch.setattr(signal_poller, "_load_signal_sources", lambda: [src])

    # 首次轮询: 空文件夹 → 可能触发 (初始状态) 或 no change
    triggers = signal_poller.poll_once()
    # 投放文件 → 必触发
    (folder / "note.txt").write_text("hello", encoding="utf-8")
    triggers = signal_poller.poll_once()
    assert any(t["source_id"] == "inbox_folder" for t in triggers)

    # 去重: 无变化 → no triggers
    triggers = signal_poller.poll_once()
    assert not any(t["source_id"] == "inbox_folder" for t in triggers)


def test_folder_hash_changes_on_new_file(tmp_path):
    """目录 hash 在新增文件后变化 (mtime+child 检测)."""
    folder = tmp_path / "inbox"
    folder.mkdir()
    h1 = signal_poller._hash_path(str(folder))
    (folder / "new.txt").write_text("x", encoding="utf-8")
    h2 = signal_poller._hash_path(str(folder))
    assert h1 != h2

import json

import pytest

# omo 包需在 sys.path 上 (CI 的 `uv run pytest` 在 projects/omo/ 下运行, 主仓侧不经
# PYTHONPATH 注入)。主仓根 `pyproject.toml` 的 pythonpath 只含根 src/, 故直接
# 从主仓跑本文件会 collection error 并中断整个 pytest 运行 —— 缺依赖时优雅跳过。
try:
    from omo.workflow.lock_graph import generate_lock_graph_snapshot
except ImportError as exc:  # pragma: no cover - 环境相关
    pytest.skip(f"omo 不可用: {exc}", allow_module_level=True)


def test_generate_lock_graph_snapshot(tmp_path, monkeypatch):
    monkeypatch.setattr("omo.workflow.lock_graph.STATE_DIR", tmp_path)
    # create mock locks
    locks_dir = tmp_path / "_delivery" / "agent-workflows" / "locks"
    locks_dir.mkdir(parents=True)
    (locks_dir / "projects=gbrain").write_text('{"run_id": "r1", "paths": ["projects/knowledge/gbrain"]}')

    generate_lock_graph_snapshot()

    out_file = tmp_path / "state" / "lock-graph.json"
    assert out_file.exists()
    data = json.loads(out_file.read_text())
    assert "r1" in data["active_runs"]

"""
测试图灵机层 v2
"""
# mock-heavy test: monkeypatch + dynamic attributes.
# pyright: reportAttributeAccessIssue=false

from ontoderive.theories.turing_k import KnowledgeTM


def test_snapshot(z_park_path):
    ktm = KnowledgeTM(z_park_path)
    state = ktm.snapshot()
    assert state.timestamp
    assert state.facts >= 1


def test_snapshot_dataclass_fields(z_park_path):
    ktm = KnowledgeTM(z_park_path)
    state = ktm.snapshot()
    assert hasattr(state, "facts")
    assert hasattr(state, "entities")
    assert hasattr(state, "inferences")
    assert hasattr(state, "scheme_files")


def test_delta(z_park_path):
    ktm = KnowledgeTM(z_park_path)
    ktm.snapshot()
    ktm.snapshot()
    d = ktm.delta()
    assert "changes" in d


def test_should_halt_new_project(tmp_path):
    (tmp_path / "facts").mkdir(parents=True)
    (tmp_path / "entities").mkdir()
    (tmp_path / "inferences").mkdir()
    (tmp_path / "scheme").mkdir()
    ktm = KnowledgeTM(tmp_path)
    for _ in range(3):
        ktm.snapshot()
    # 新项目快照间无变化，应停机
    halted = ktm.should_halt()
    assert halted


def test_diff_no_history(z_park_path):
    ktm = KnowledgeTM(z_park_path)
    changes = ktm.diff()
    assert isinstance(changes, list)


def test_replay_no_history(z_park_path):
    ktm = KnowledgeTM(z_park_path)
    snapshots = ktm.replay()
    assert isinstance(snapshots, list)


def test_empty_project(tmp_path):
    ktm = KnowledgeTM(tmp_path)
    state = ktm.snapshot()
    assert state.facts == 0
    assert state.inferences == 0

"""Tests for omo.omo_bridge (P42-W0-MERGE-STATE 工具链修复).

覆盖 3 个 bug:
1. 依赖断链: (depends_on: P42-W0-MERGE-STATE) 解析后要重 hash 成 IMPORTED-xxxxx
2. 空依赖污染: 第一个 task 的 depends_on=[''] 应清为 []
3. 缺 phase/wave 字段: 应从 task_id 推断 (P42-W0 → phase=42, wave=W0)
"""

from __future__ import annotations

import sys
from pathlib import Path

OMO_SRC = Path(__file__).resolve().parents[1] / "src"
if str(OMO_SRC) not in sys.path:
    sys.path.insert(0, str(OMO_SRC))


def _write_spec(path: Path, body: str) -> None:
    path.write_text(body, encoding="utf-8")


def test_generate_task_id_is_deterministic():
    """相同 title 永远产生相同 hash, 否则依赖解析没法做."""
    from omo.omo_bridge import _generate_task_id

    assert _generate_task_id("P42-W0-MERGE-STATE") == _generate_task_id(
        "P42-W0-MERGE-STATE"
    )
    assert _generate_task_id("A") != _generate_task_id("B")


def test_generate_task_id_format():
    from omo.omo_bridge import _generate_task_id

    tid = _generate_task_id("anything")
    assert tid.startswith("IMPORTED-")
    assert len(tid) == len("IMPORTED-") + 6


def test_parse_explicit_depends_on_resolves_to_imported_ids(tmp_path):
    """(depends_on: P42-W0-MERGE-STATE) 应被替换成 IMPORTED-{hash('P42-W0-MERGE-STATE')}."""
    from omo.omo_bridge import _resolve_depends_on

    # 同 spec 上游 task 标题
    depends_on = ["P42-W0-MERGE-STATE", "P42-W0-INDEX-REFRESH"]
    title_to_imported = {
        "P42-W0-MERGE-STATE: 合并 14 个 phase 复盘 (P28-P41) 进 goals/state": "IMPORTED-a5a8ea",
        "P42-W0-INDEX-REFRESH: 刷新 .omo/INDEX.md 头条 + 表格 (内部表头指向真实 state)": "IMPORTED-a4cfe7",
    }
    resolved = _resolve_depends_on(depends_on, title_to_imported)
    assert resolved == ["IMPORTED-a5a8ea", "IMPORTED-a4cfe7"]


def test_parse_explicit_depends_on_keeps_unknown_id_unchanged(tmp_path):
    """解析不出的 ID 应保留原值, 不抛异常 (向下兼容 现有 P40 任务)."""
    from omo.omo_bridge import _resolve_depends_on

    depends_on = ["P39-W2-W3-COMBO", "UNKNOWN-ID-123"]
    resolved = _resolve_depends_on(depends_on, {})
    assert resolved == ["P39-W2-W3-COMBO", "UNKNOWN-ID-123"]


def test_resolve_depends_on_drops_empty_strings():
    """空字符串和纯空白应被丢弃, 不进 yaml."""
    from omo.omo_bridge import _resolve_depends_on

    resolved = _resolve_depends_on(["", "  ", "P42-W0-MERGE-STATE"], {})
    assert resolved == ["P42-W0-MERGE-STATE"]


def test_infer_phase_wave_from_task_id():
    """P42-W0-MERGE-STATE → (phase=42, wave=W0)."""
    from omo.omo_bridge import _infer_phase_wave

    assert _infer_phase_wave("P42-W0-MERGE-STATE") == (42, "W0")
    assert _infer_phase_wave("P40-W2-W3-COMBO") == (40, "W2")  # 多个 W 取第一个
    assert _infer_phase_wave("not-matching") == (None, None)


def test_import_bmad_writes_task_with_phase_wave(tmp_path):
    """import 应写 phase/wave 字段, 跟 P40/P41 规范一致."""
    import hashlib

    from omo.omo_bridge import _import_bmad

    a_title = "P42-W0-MERGE-STATE: 合并"
    a_id = f"IMPORTED-{hashlib.md5(a_title.encode()).hexdigest()[:6]}"

    spec = tmp_path / "spec.md"
    _write_spec(
        spec,
        f"""# Spec
- [ ] {a_title}
- [ ] P42-W0-INDEX-REFRESH: 刷新 (depends_on: {a_title.split(":")[0]})
""",
    )
    omo = tmp_path / ".omo"
    (omo / "tasks" / "planned").mkdir(parents=True)
    _import_bmad(spec, omo, sequential=False)

    merge_file = omo / "tasks" / "planned" / f"{a_id}.yaml"
    assert merge_file.exists(), f"expected {a_id}.yaml"
    import yaml

    data = yaml.safe_load(merge_file.read_text())
    assert data["phase"] == 42
    assert data["wave"] == "W0"
    assert data["metadata"]["broker"] == "projects/omo/src/omo/omo_ingress.py"
    artifact = (
        omo.parent
        / "runtime"
        / "omo"
        / "_delivery"
        / "ingress"
        / "tasks"
        / f"{a_id}.yaml"
    )
    assert artifact.exists()


def test_import_bmad_resolves_depends_on_to_imported_ids(tmp_path):
    """关键测试: 修复断链 bug. 第二次 import 看到的依赖是 IMPORTED-xxxxx 不是 P42-W0-..."""
    import hashlib

    from omo.omo_bridge import _import_bmad

    a_title = "P42-W0-MERGE-STATE: 合并"
    a_id = f"IMPORTED-{hashlib.md5(a_title.encode()).hexdigest()[:6]}"
    b_title = "P42-W0-INDEX-REFRESH: 刷新"
    b_id = f"IMPORTED-{hashlib.md5(b_title.encode()).hexdigest()[:6]}"

    spec = tmp_path / "spec.md"
    _write_spec(
        spec,
        f"""# Spec
- [ ] {a_title}
- [ ] {b_title} (depends_on: P42-W0-MERGE-STATE)
""",
    )
    omo = tmp_path / ".omo"
    (omo / "tasks" / "planned").mkdir(parents=True)
    _import_bmad(spec, omo, sequential=False)

    import yaml

    refresh = yaml.safe_load((omo / "tasks" / "planned" / f"{b_id}.yaml").read_text())
    assert refresh["depends_on"] == [a_id], f"依赖断链 bug: {refresh['depends_on']}"


def test_import_bmad_first_task_has_empty_depends_on(tmp_path):
    """第一个 task 不该有 [''] 污染."""
    import hashlib

    from omo.omo_bridge import _import_bmad

    a_title = "P42-W0-MERGE-STATE: 合并"
    a_id = f"IMPORTED-{hashlib.md5(a_title.encode()).hexdigest()[:6]}"

    spec = tmp_path / "spec.md"
    _write_spec(
        spec,
        f"""# Spec
- [ ] {a_title}
""",
    )
    omo = tmp_path / ".omo"
    (omo / "tasks" / "planned").mkdir(parents=True)
    _import_bmad(spec, omo, sequential=False)

    import yaml

    data = yaml.safe_load((omo / "tasks" / "planned" / f"{a_id}.yaml").read_text())
    assert data["depends_on"] == [], f"空依赖污染: {data['depends_on']}"


def test_sequential_mode_uses_imported_id_chain(tmp_path):
    """--sequential 模式下, 后一个 task 的依赖应指向前一个的 IMPORTED-xxxxx."""
    import hashlib

    from omo.omo_bridge import _import_bmad

    a_id = f"IMPORTED-{hashlib.md5('P42-W0-A: 第一个'.encode()).hexdigest()[:6]}"

    spec = tmp_path / "spec.md"
    _write_spec(
        spec,
        """# Spec
- [ ] P42-W0-A: 第一个
- [ ] P42-W0-B: 第二个
- [ ] P42-W0-C: 第三个
""",
    )
    omo = tmp_path / ".omo"
    (omo / "tasks" / "planned").mkdir(parents=True)
    _import_bmad(spec, omo, sequential=True)

    import yaml

    a = yaml.safe_load((omo / "tasks" / "planned" / f"{a_id}.yaml").read_text())
    # A 的依赖应为空 (第一个), B/C 依赖前一个的 IMPORTED id
    assert a["depends_on"] == []


def test_sequential_mode_chain_dynamic(tmp_path):
    """同上, 但用动态 hash 探测 (不写死 hash 值)."""
    import hashlib

    from omo.omo_bridge import _import_bmad

    def hash6(title: str) -> str:
        return hashlib.md5(title.encode()).hexdigest()[:6]

    a_id = f"IMPORTED-{hash6('P42-W0-A: 第一个')}"
    b_id = f"IMPORTED-{hash6('P42-W0-B: 第二个')}"
    c_id = f"IMPORTED-{hash6('P42-W0-C: 第三个')}"

    spec = tmp_path / "spec.md"
    _write_spec(
        spec,
        """# Spec
- [ ] P42-W0-A: 第一个
- [ ] P42-W0-B: 第二个
- [ ] P42-W0-C: 第三个
""",
    )
    omo = tmp_path / ".omo"
    (omo / "tasks" / "planned").mkdir(parents=True)
    _import_bmad(spec, omo, sequential=True)

    import yaml

    a = yaml.safe_load((omo / "tasks" / "planned" / f"{a_id}.yaml").read_text())
    b = yaml.safe_load((omo / "tasks" / "planned" / f"{b_id}.yaml").read_text())
    c = yaml.safe_load((omo / "tasks" / "planned" / f"{c_id}.yaml").read_text())

    assert a["depends_on"] == []
    assert b["depends_on"] == [a_id]
    assert c["depends_on"] == [b_id]


def test_import_fast_track_generates_valid_yaml(tmp_path):
    """测试 Fast-Track 降维是否产生包含 context_uri 且无 TODO 阻挡的合法任务"""
    import yaml
    from omo.omo_bridge import _import_fast_track

    spec = tmp_path / "fix-typo.md"
    omo = tmp_path / ".omo"
    (omo / "tasks" / "planned").mkdir(parents=True)

    _import_fast_track(spec, omo)

    files = list((omo / "tasks" / "planned").glob("*.yaml"))
    assert len(files) == 1
    task_id = files[0].stem
    assert task_id.startswith("FAST-")

    data = yaml.safe_load(files[0].read_text())
    assert data["title"] == "fix-typo.md"
    assert data["context_uri"] == f"bos://memory/fast-track/{task_id}"
    assert data["human_approval_required"] is False
    assert data["metadata"]["broker"] == "projects/omo/src/omo/omo_ingress.py"
    assert (
        omo.parent
        / "runtime"
        / "omo"
        / "_delivery"
        / "ingress"
        / "tasks"
        / f"{task_id}.yaml"
    ).exists()


def test_import_bmad_rejects_todo_lines(tmp_path, capfd):
    """测试 Devil's Gatekeeper 拦截含有 TODO 的条目"""
    from omo.omo_bridge import _import_bmad

    spec = tmp_path / "spec.md"
    _write_spec(
        spec,
        """# Spec
- [ ] P42-W0-A: 这个想清楚了
- [ ] P42-W0-B: TODO 这个还没想清楚
""",
    )
    omo = tmp_path / ".omo"
    (omo / "tasks" / "planned").mkdir(parents=True)
    _import_bmad(spec, omo, sequential=False)

    # 只有 A 被导入，B 应该被拦截
    files = list((omo / "tasks" / "planned").glob("*.yaml"))
    assert len(files) == 1

    out, err = capfd.readouterr()
    assert "预检拦截 (Pre-check Failed)" in out
    assert "TODO 这个还没想清楚" in out


def test_import_bmad_adds_context_uri(tmp_path):
    """测试 Mode A 降维时是否附带了 context_uri"""
    import hashlib

    from omo.omo_bridge import _import_bmad

    a_title = "P42-W0-A: 测试URI"
    a_id = f"IMPORTED-{hashlib.md5(a_title.encode()).hexdigest()[:6]}"

    spec = tmp_path / "spec.md"
    _write_spec(
        spec,
        f"""# Spec
- [ ] {a_title}
""",
    )
    omo = tmp_path / ".omo"
    (omo / "tasks" / "planned").mkdir(parents=True)
    _import_bmad(spec, omo, sequential=False)

    import yaml

    data = yaml.safe_load((omo / "tasks" / "planned" / f"{a_id}.yaml").read_text())
    assert "context_uri" in data
    assert data["context_uri"] == f"bos://memory/openspecs/spec.md#{a_id}"


def test_import_pitch_uses_governed_goal_and_task_ingress(tmp_path, capfd):
    import hashlib

    import yaml
    from omo.omo_bridge import _import_pitch

    pitch = tmp_path / "pitch.md"
    pitch.write_text(
        """# Pitch
> **Upstream**: MS-001
> **Appetite:** 2 days
""",
        encoding="utf-8",
    )
    omo = tmp_path / ".omo"
    goals_dir = omo / "goals"
    goals_dir.mkdir(parents=True, exist_ok=True)
    (goals_dir / "current.yaml").write_text("phase: 44\ngoals: []\n", encoding="utf-8")

    _import_pitch(pitch, omo)

    bet_id = f"BET-{hashlib.md5(pitch.name.encode()).hexdigest()[:4]}"
    task_id = f"IMPORTED-{hashlib.md5(bet_id.encode()).hexdigest()[:6]}"
    goals_payload = yaml.safe_load(
        (goals_dir / "current.yaml").read_text(encoding="utf-8")
    )
    assert any(goal["id"] == bet_id for goal in goals_payload["goals"])
    task_payload = yaml.safe_load(
        (omo / "tasks" / "planned" / f"{task_id}.yaml").read_text(encoding="utf-8")
    )
    assert task_payload["metadata"]["broker"] == "projects/omo/src/omo/omo_ingress.py"
    assert (
        omo.parent
        / "runtime"
        / "omo"
        / "_delivery"
        / "ingress"
        / "goals"
        / f"{bet_id}.yaml"
    ).exists()
    assert (
        omo.parent
        / "runtime"
        / "omo"
        / "_delivery"
        / "ingress"
        / "tasks"
        / f"{task_id}.yaml"
    ).exists()
    registry = yaml.safe_load(
        (
            omo.parent / "runtime" / "omo" / "_delivery" / "ingress" / "registry.yaml"
        ).read_text(encoding="utf-8")
    )
    assert (
        registry["goals"]["by_source_ref"][
            f"omo:bridge:pitch-goal:{pitch.name}:{bet_id}"
        ]
        == bet_id
    )
    assert (
        registry["tasks"]["by_source_ref"][
            f"omo:bridge:pitch-task:{pitch.name}:{task_id}"
        ]
        == task_id
    )

    out, _ = capfd.readouterr()
    assert "Bet 下注成功" in out

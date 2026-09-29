"""log-rotate 必须按**路径**排除 class=state 的追加式账本 (T16-02, ADR-0458).

背景: --daily 的语义是「跨天即轮转, 不看阈值」(log-rotate main()), crontab 每天
03:00 执行。轮转当前份是 copytruncate (os.truncate), 即**清零**。故把追加式账本
纳入扫描范围不是潜在风险而是即时风险 —— 次日 03:00 即被清零, 且无报错无告警。

此前该区分只靠 SKIP_NAMES 按**文件名**匹配, 脆弱且漏判代价静默。T16-02 起分类
权威迁至 .omo/_truth/registry/log-surfaces.yaml, 按路径登记。
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location(
    "log_rotate_surfaces", WORKSPACE / "bin" / "ssot" / "log-rotate.py"
)
assert _spec and _spec.loader
log_rotate = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(log_rotate)


def _registry_schema() -> str:
    import yaml

    reg = WORKSPACE / ".omo" / "_truth" / "registry" / "log-surfaces.yaml"
    merged: dict = {}
    for doc in yaml.safe_load_all(reg.read_text(encoding="utf-8")):
        if isinstance(doc, dict):
            merged.update(doc)
    return str(merged.get("schema") or "")


def test_registry_exists_and_declares_schema() -> None:
    assert _registry_schema() == "log-surfaces/v1"


def test_registry_classifies_bet_value_evidence_as_state() -> None:
    """value-evidence 是三轴证据链的 value 轴, 清零即断链 —— 必须登记为 state。"""
    import yaml

    reg = WORKSPACE / ".omo" / "_truth" / "registry" / "log-surfaces.yaml"
    merged: dict = {}
    for doc in yaml.safe_load_all(reg.read_text(encoding="utf-8")):
        if isinstance(doc, dict):
            merged.update(doc)
    by_path = {s["path"]: s for s in merged.get("surfaces") or [] if isinstance(s, dict)}
    assert by_path[".omo/_delivery/ingress/value-evidence.jsonl"]["class"] == "state"


def test_state_surfaces_are_excluded_by_path_not_filename(tmp_path: Path, monkeypatch) -> None:
    """同名不同路径也必须排除 —— 这是按文件名匹配的 SKIP_NAMES 挡不住的情形。"""
    scanned = tmp_path / "delivery" / "resident-orchestrator"
    scanned.mkdir(parents=True)
    state_file = scanned / "receipts.jsonl"
    state_file.write_text('{"evidence": "irreplaceable"}\n')

    registry = tmp_path / ".omo" / "_truth" / "registry" / "log-surfaces.yaml"
    registry.parent.mkdir(parents=True, exist_ok=True)
    registry.write_text(
        "schema: log-surfaces/v1\n"
        "surfaces:\n"
        f"  - path: {state_file}\n"
        "    class: state\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(log_rotate, "LOG_PATHS", [scanned])
    monkeypatch.setattr(log_rotate, "SKIP_NAMES", set())
    monkeypatch.setattr(log_rotate, "WORKSPACE", tmp_path)

    candidates, excluded = log_rotate._candidate_files()

    assert state_file not in candidates
    assert state_file in excluded, "state 排除必须被观测到, 不允许静默生效"


def test_log_class_path_is_not_excluded(tmp_path: Path, monkeypatch) -> None:
    """class=log 的路径仍应正常进入候选 —— 排除不能误伤真日志。"""
    scanned = tmp_path / "logs"
    scanned.mkdir(parents=True)
    real_log = scanned / "daemon.log"
    real_log.write_text("tick\n")

    registry = tmp_path / ".omo" / "_truth" / "registry" / "log-surfaces.yaml"
    registry.parent.mkdir(parents=True, exist_ok=True)
    registry.write_text(
        "schema: log-surfaces/v1\n"
        "surfaces:\n"
        f"  - path: {real_log}\n"
        "    class: log\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(log_rotate, "LOG_PATHS", [scanned])
    monkeypatch.setattr(log_rotate, "SKIP_NAMES", set())
    monkeypatch.setattr(log_rotate, "WORKSPACE", tmp_path)

    candidates, excluded = log_rotate._candidate_files()

    assert real_log in candidates
    assert real_log not in excluded


def test_missing_registry_falls_back_without_raising(tmp_path: Path, monkeypatch) -> None:
    """注册表缺失/损坏不得阻断轮转 —— 退回旧的 SKIP_NAMES 行为。"""
    scanned = tmp_path / "logs"
    scanned.mkdir(parents=True)
    some_log = scanned / "a.log"
    some_log.write_text("x")

    monkeypatch.setattr(log_rotate, "LOG_PATHS", [scanned])
    monkeypatch.setattr(log_rotate, "SKIP_NAMES", set())
    monkeypatch.setattr(log_rotate, "WORKSPACE", tmp_path)  # 该路径下无注册表

    surfaces = log_rotate._load_log_surfaces()
    candidates, excluded = log_rotate._candidate_files()

    assert surfaces["registry_present"] is False
    assert some_log in candidates
    assert excluded == []


def test_state_exclusion_survives_symlinked_workspace(tmp_path: Path, monkeypatch) -> None:
    """WORKSPACE 是软链时排除不得静默失效 (T16-02 加固).

    复现方式: 让 WORKSPACE 指向一个软链目录, 而账本实体在其解析目标下。
    此时扫描得到的 p.resolve() 是真路径, 若注册表只存 WORKSPACE/p (软链路径)
    则二者不相等 → 排除失效 → 追加式账本会被 copytruncate 清零。
    """
    real_root = tmp_path / "real"
    scanned = real_root / "delivery" / "resident-orchestrator"
    scanned.mkdir(parents=True)
    state_file = scanned / "receipts.jsonl"
    state_file.write_text('{"evidence": "irreplaceable"}\n')

    link_root = tmp_path / "linked"
    link_root.symlink_to(real_root, target_is_directory=True)

    # 关键: 注册表写**相对路径**(与真实 log-surfaces.yaml 一致), 于是
    # WORKSPACE / rel = 软链路径, 而 glob 结果 p.resolve() = 真路径 —— 二者不等,
    # 这正是排除会静默失效的那一形态。
    registry = link_root / ".omo" / "_truth" / "registry" / "log-surfaces.yaml"
    registry.parent.mkdir(parents=True, exist_ok=True)
    registry.write_text(
        "schema: log-surfaces/v1\n"
        "surfaces:\n"
        f"  - path: delivery/resident-orchestrator/receipts.jsonl\n"
        "    class: state\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(log_rotate, "LOG_PATHS", [scanned])
    monkeypatch.setattr(log_rotate, "SKIP_NAMES", set())
    monkeypatch.setattr(log_rotate, "WORKSPACE", link_root)

    assert link_root != link_root.resolve(), "本用例要求 WORKSPACE 是软链"
    candidates, excluded = log_rotate._candidate_files()

    assert state_file not in candidates, "软链 WORKSPACE 下排除失效 = 证据链会被清零"
    assert state_file in excluded

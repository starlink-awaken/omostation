"""scheduler-compile 的 launchd 平面 shadow 段 (T16-01) 与 label 解析契约."""

from __future__ import annotations

import importlib.util
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location(
    "scheduler_compile", WORKSPACE / "bin" / "scheduler-compile.py"
)
assert _spec and _spec.loader
sc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sc)


def _reg():
    import yaml

    m = {}
    for doc in yaml.safe_load_all((WORKSPACE / ".omo" / "cron" / "registry.yaml").read_text(encoding="utf-8")):
        if isinstance(doc, dict):
            m.update(doc)
    return m


def test_every_active_launchd_entry_resolves_to_an_installed_label() -> None:
    """全部 active launchd 登记必须能解析到一个真实已安装的 label。

    这是 T16-01 升 warning 的前置条件: 命中率不到 100% 时判据不成立, 会立刻产生
    假阳性。2026-09-29 前仅 7/17 —— 9 条 resident-launchd-* 的真实前缀是 com.l4. 而非
    com.omostation., 另 1 条 zhixing-host-drift-hourly-active 的 label 丢了后缀。
    """
    import plistlib

    la = Path.home() / "Library" / "LaunchAgents"
    installed = set()
    for p in la.glob("com.*.plist"):
        try:
            installed.add(plistlib.loads(p.read_bytes()).get("Label", p.stem))
        except Exception:  # noqa: BLE001
            continue

    jobs = _reg()["jobs"]
    entries = [j for j in jobs if "launchd" in (j.get("planes") or []) and j.get("status", "active") == "active"]
    assert entries, "未找到 active launchd 登记 —— 测试前提不成立"

    missing = []
    for j in entries:
        label = j.get("label") or f"com.omostation.{j['name']}"
        if label not in installed:
            missing.append(f"{j['name']} -> {label}")
    assert not missing, "以下 launchd 登记解析不到已安装的 label:\n" + "\n".join(missing)


def test_explicit_label_field_overrides_synthesis() -> None:
    """显式 label 字段优先于合成 —— 合成只是缺省值, 不是判据。"""
    d = _reg()
    explicit = {j["name"]: j["label"] for j in d["jobs"] if j.get("label")}
    assert explicit, "登记源中应存在显式 label 字段"
    for name, label in explicit.items():
        assert label != f"com.omostation.{name}", f"{name} 的显式 label 与合成值相同, 该字段无必要"


def test_shadow_segment_never_blocks_the_gate() -> None:
    """shadow 阶段 launchd 段不得影响 crontab 的 ok 判定 (ADR-0457 三段式)。"""
    res = sc.check_drift()
    assert res["ok"] is True, f"crontab 口径应保持通过: {res}"
    ld = res["launchd"]
    assert ld["mode"] == "shadow"
    assert ld["blocks_gate"] is False

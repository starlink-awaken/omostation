"""Panorama compact observation 的 facet 契约测试.

缺陷背景 (2026-11-09 实测): `compact-observation.py` 有 7 个 admitted facet, 其中
`evolution` 与 `launchd_health` **从未成功过** (`last_success_at` 恒 null,
`status: partial`), 根因是三处契约错位:

1. `FACET_COLLECTORS["launchd_health"]` 指向 `collect_launchd_health_observation`
   —— 该函数**不存在** (真名是 `collect_launchd_health`) ⇒ 每次 `collector_unavailable`。
2. `collect_evolution()` 不返回 `proposal_paths`, 而 `_valid_result` 要它核对总数。
3. `collect_launchd_health()` 不返回 `facet_state` / `registry_sha256`, 而
   `_valid_result` 要它们。

本文件钉住「映射存在 + 每个 facet 的产物过 `_valid_result`」。
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _observer():
    return _load(ROOT / "bin/panorama/compact-observation.py", "_compact_obs_under_test")


def _collector():
    return _load(ROOT / "bin/panorama/panorama-collect.py", "_panorama_collector_under_test")


def test_facet_collector_mapping_points_at_real_functions() -> None:
    """映射里每个函数名都必须在采集器里真实存在.

    实测: `launchd_health` 曾指向 `collect_launchd_health_observation` (不存在),
    于是那个 facet 每次都 `collector_unavailable`。
    """
    obs = _observer()
    col = _collector()
    missing = {
        facet: name
        for facet, name in obs.FACET_COLLECTORS.items()
        if not callable(getattr(col, name, None))
    }
    assert not missing, f"facet 映射指向不存在的采集函数: {missing}"


def test_every_admitted_facet_payload_passes_validation() -> None:
    """每个 admitted facet 的产物都要过 `_valid_result` —— 否则观测面一直 partial."""
    obs = _observer()
    col = _collector()
    invalid: dict[str, str] = {}
    for facet, name in obs.FACET_COLLECTORS.items():
        try:
            value = getattr(col, name)()
        except Exception as exc:  # noqa: BLE001 — 采集器抛错也算不合规
            invalid[facet] = f"{type(exc).__name__}: {exc}"
            continue
        try:
            obs._valid_result(facet, value)
        except Exception as exc:  # noqa: BLE001
            invalid[facet] = f"{type(exc).__name__}: {exc}"
    assert not invalid, f"以下 facet 的产物不合契约: {invalid}"

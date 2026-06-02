from __future__ import annotations

from pathlib import Path

import pytest

from scripts.omo_debt_execution import build_execution_record, execution_record_path, run_slug_from_ref


def test_execution_record_helpers_build_run_scoped_paths(tmp_path: Path) -> None:
    omo_dir = tmp_path / ".omo"
    dispatch_run_ref = ".omo/debt/dispatch/runs/2026-06-10T00-00-00Z.yaml"

    assert run_slug_from_ref(dispatch_run_ref) == "2026-06-10T00-00-00Z"
    assert execution_record_path(omo_dir, dispatch_run_ref, "SB_DECOMPOSITION") == (
        omo_dir / "debt" / "dispatch" / "executions" / "2026-06-10T00-00-00Z" / "SB_DECOMPOSITION.yaml"
    )
    assert build_execution_record(
        item_id="SB_DECOMPOSITION",
        dispatch_run_ref=dispatch_run_ref,
        reviewed_at="2026-06-11T12:00:00Z",
    ) == {
        "item_id": "SB_DECOMPOSITION",
        "dispatch_run_ref": dispatch_run_ref,
        "action": "revalidate",
        "reviewed_at": "2026-06-11T12:00:00Z",
    }


def test_run_slug_from_ref_rejects_non_yaml_dispatch_refs() -> None:
    with pytest.raises(ValueError, match="dispatch run ref"):
        run_slug_from_ref(".omo/debt/dispatch/runs/not-a-yaml.txt")

"""Shared fixtures for OMO test suite.

Provides reusable test infrastructure: temp .omo directory, YAML fixture
writers, and mock time utilities.

Also ensures the external ``scripts/`` package (``sync_omo_state``,
``phase3_acceptance``, ``cost_track_org``, etc.) is on ``sys.path``.

Collection hooks
----------------
- ``requires_real_omo`` marker — applied to tests in ``tests/archive/`` and
  tests that read real workspace ``.omo/`` state.  Skipped when the real
  ``.omo`` directory does not exist at the workspace root.
"""
from __future__ import annotations

import fnmatch
import sys
from pathlib import Path
from typing import Any

import pytest
import yaml


# Ensure Workspace root is on sys.path so ``scripts.*`` imports resolve
_ws_root = Path(__file__).resolve().parents[3]
if str(_ws_root) not in sys.path:
    sys.path.insert(0, str(_ws_root))


@pytest.fixture
def omo_dir(tmp_path: Path) -> Path:
    """Create a temporary `.omo` directory with standard sub-tree.

    The returned path points to a directory containing `.omo/` with
    ``_control/``, ``_truth/``, ``tasks/planned/``, ``tasks/active/``,
    and ``debt/`` subdirectories — common scaffolding for OMO unit tests.
    """
    d = tmp_path / ".omo"
    (d / "_control" / "governance-overlay").mkdir(parents=True, exist_ok=True)
    (d / "_truth" / "governance-overlay").mkdir(parents=True, exist_ok=True)
    (d / "tasks" / "planned").mkdir(parents=True, exist_ok=True)
    (d / "tasks" / "active").mkdir(parents=True, exist_ok=True)
    (d / "debt" / "dashboard").mkdir(parents=True, exist_ok=True)
    (d / "debt" / "evidence").mkdir(parents=True, exist_ok=True)
    return d


@pytest.fixture(scope="session")
def omo_test_dir() -> Path:
    """Return path to a minimal .omo test directory with real fixture data.

    The directory is generated once per session by
    ``tests/fixtures/minimal_omo.generate()`` and includes a debt registry,
    three synthetic debt items (DEBT-TEST-001 … 003) with X1/X2/X3 fields,
    a minimal ``_truth/registry/debt.yaml``, and placeholder ref files.

    Idempotent — re-running re-generates in place.
    """
    from tests.fixtures.minimal_omo import generate

    return generate()


@pytest.fixture
def write_yaml(omo_dir: Path) -> Any:
    """Return a helper that writes YAML files relative to ``omo_dir``.

    Usage::

        write_yaml("_control/governance-overlay/current.yaml", {"key": "val"})
    """
    def _write(rel_path: str, data: dict[str, Any]) -> Path:
        full_path = omo_dir / rel_path
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_text(yaml.dump(data, allow_unicode=True, sort_keys=False))
        return full_path
    return _write


# ---------------------------------------------------------------------------
# Marker registration & collection-time skip for real-OMO-dependent tests
# ---------------------------------------------------------------------------

def pytest_configure(config: pytest.Config) -> None:
    """Register the ``requires_real_omo`` marker."""
    config.addinivalue_line(
        "markers",
        "requires_real_omo: test requires real workspace .omo state; "
        "skipped when ~/Workspace/.omo does not exist.",
    )


def pytest_addoption(parser: pytest.Parser) -> None:
    """Allow opting into real-workspace .omo tests."""
    parser.addoption(
        "--run-real-omo",
        action="store_true",
        default=False,
        help="run tests that require the real workspace .omo state",
    )


def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> None:
    """Mark tests that depend on real .omo state and skip if unavailable.

    Rules
    -----
    * All items under ``tests/archive/`` are marked ``requires_real_omo``.
    * The following **top-level** test modules are also marked:
      - ``test_architecture_baseline_phase15_phase16.py``
      - ``test_fusion_optimization_docs.py``
      - ``test_external_omo_reroot.py``
      - ``test_worker_mechanism_consistency.py``
      - ``test_provider_plane.py``
      - ``test_omo_verification_contract.py``
      - Any module matching ``test_phase*.py`` (covers ``*_execution``,
        ``*_docs``, and all remaining phase-* test files).
    * Items that **already carry** ``skip``, ``skipif``, or ``xfail`` are
      left untouched.
    * When the real ``.omo/`` state directory is missing the required
      structure, all ``requires_real_omo`` items receive a ``skip`` marker.
    """
    _omo_root = _ws_root / ".omo"
    _run_real_omo = bool(config.getoption("--run-real-omo"))

    # Determine whether real .omo state is present.
    # We consider state "present" when the .omo directory exists and contains
    # at least one of the well-known sub-structures that real-state tests
    # depend on (state/, plans/, _control/, _truth/, tasks/).
    _omo_present = _omo_root.is_dir() and any(
        (_omo_root / sub).is_dir()
        for sub in ("state", "plans", "_control", "_truth", "tasks")
    )

    # -- Built-in skip-like markers that we should respect -------------------
    _ALREADY_SKIP = {"skip", "skipif", "xfail"}

    # -- Explicit module names (basenames) -----------------------------------
    # These modules house integration-style tests that require real .omo
    # workspace state (e.g. file-based registries, actual subprocess CLI
    # entry points, existing phase artifacts, etc.)
    # They are ALWAYS skipped unless --run-real-omo is passed.
    _EXPLICIT_MODULES = frozenset({
        "test_architecture_baseline_phase15_phase16.py",
        "test_fusion_optimization_docs.py",
        "test_external_omo_reroot.py",
        "test_worker_mechanism_consistency.py",
        "test_provider_plane.py",
        "test_omo_verification_contract.py",
        "test_omo_debt_cli.py",
        "test_omo_debt_docs.py",
        "test_omo_debt_metrics.py",
        "test_omo_debt_outputs.py",
        "test_omo_experience.py",
        "test_omo_admission.py",
        "test_phase9_space_registry.py",
        "test_phase9_identity_admission_contract.py",
        "test_phase9_rollout_governance.py",
        "test_phase9_runtime_boundary_refactor.py",
        "test_active_task_schema.py",
        "test_all_active_tasks_pass_current_task_schema.py",
        "test_kairon_makefile.py",
        "test_phase11_ci_baseline.py",
        "test_phase11_wave2_ci_baseline.py",
        "test_phase11_wave2_path_debt.py",
        "test_phase11_wave4_governance_ci.py",
        "test_phase4_wave2_docs.py",
        "test_phase6_entry_hardening_packet_docs.py",
        "test_phase8_wave1_closeout_docs.py",
        "test_phase10_cross_root_rules.py",
        "test_phase10_wave2_normalization.py",
        "test_phase10_wave3_matrix.py",
        "test_phase10_wave4_cross_space.py",
        "test_governance_workflow.py",
    })

    for item in items:
        fspath = str(item.fspath)
        basename = item.fspath.basename
        testname = item.name

        # Skip items that already have a skip/skipif/xfail marker
        if any(item.get_closest_marker(m) for m in _ALREADY_SKIP):
            continue

        # -- Decide whether this item needs real .omo state ------------------
        needs_omo = False

        # 1. All tests under tests/archive/
        if "/tests/archive/" in fspath:
            needs_omo = True

        # 2. Explicitly named modules (always skip in CI, re-enable with --run-real-omo)
        elif basename in _EXPLICIT_MODULES:
            needs_omo = True

        # 3. Any test_phase*.py module (not already matched above)
        elif fnmatch.fnmatch(basename, "test_phase*.py"):
            needs_omo = True

        # 4. Specific integration test functions that need real .omo workspace
        #    (calls dispatch_task() which requires _truth/registry/workers.yaml)
        elif basename == "test_omo_automation.py" and testname in (
            "test_sync_omo_state_script_runs_from_repo_root",
            "test_dispatch_task_launch_redacts_stdout_log",
            "test_dispatch_task_and_worker_status_use_custom_omo_root",
            "test_dispatch_task_uses_supplied_now_for_dispatch_identity_and_start_time",
            "test_dispatch_task_launch_marks_dispatch_active_and_updates_lease",
            "test_install_all_bridges_defaults_to_wrapper_only_without_running_legacy_installers",
            "test_install_all_bridges_can_opt_into_legacy_installers",
            "test_dispatch_task_creates_packet_and_preclaims_task",
            "test_task_promote_apply_moves_task_and_writes_envelope",
            "test_task_promote_apply_rolls_back_when_sync_fails",
            "test_task_governance_overlay_run_next_writes_run_artifact",
            "test_task_governance_overlay_run_next_dispatches_first_active_pending_target",
            "test_task_governance_overlay_run_next_launches_dispatched_task_when_scope_is_declared",
        ):
            needs_omo = True

        elif basename == "test_worker_lifecycle.py" and testname in (
            "test_dispatch_task_launch_handles_quoted_prompt_without_shell_breakage",
            "test_dispatch_prompt_includes_required_deliverables_when_task_declares_them",
            "test_dispatch_task_creates_checkpoint_and_reclaim_artifacts",
            "test_worker_status_command_prints_checkpoint_summary",
            "test_update_dispatch_checkpoint_records_step_and_refreshes_lease",
            "test_worker_admission_eval_command_prints_decision",
            "test_reclaim_task_reassigns_from_checkpoint_context",
            "test_write_handoff_index_links_dispatch_checkpoint_reclaim_and_review",
        ):
            needs_omo = True

        # -- Apply marker and optionally skip --------------------------------
        if needs_omo:
            item.add_marker(pytest.mark.requires_real_omo)
            if not _omo_present:
                item.add_marker(
                    pytest.mark.skip(
                        reason="requires real .omo workspace state; workspace .omo not found"
                    )
                )
            elif not _run_real_omo:
                item.add_marker(
                    pytest.mark.skip(
                        reason=(
                            "requires real .omo workspace state; "
                            "pass --run-real-omo to enable"
                        )
                    )
                )

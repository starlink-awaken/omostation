"""P110-G: omo_governance_surfaces_gates 子模块 (从 omo_governance_surfaces.py 提取).

F7114ABA 治本: report.py 依赖的纯 helper 提取到独立 sibling,
消除 child → parent circular import.

parent (omo_governance_surfaces.py) re-export child 在文件头 (行18-62),
helper 定义在后 (行69+) — child 无法安全反向 import parent helper
(parent 部分初始化时 helper 未绑定). 提取到 leaf sibling 破环.

业务 (14 pure helpers):
  - _asset_ref_to_top_level / _top_level_entries (路径处理)
  - _check_goals_runtime_entry (goals runtime symlink 校验)
  - _read_c2g_governance_refs (c2g task_builder 动态加载)
  - _has_*_gate × 8 (pre-commit gate 检测)
  - _candidate_roots / resolve_governance_workspace_root (workspace 定位)

纯函数, 仅依赖 stdlib (Path, sys). 无 circular 风险 (leaf sibling).

向后兼容: omo_governance_surfaces.py re-export 全部, 调用点不破.
"""

from __future__ import annotations

import sys
from pathlib import Path


def _asset_ref_to_top_level(ref: str) -> str:
    normalized = ref.strip().strip("/")
    if normalized.startswith(".omo/"):
        normalized = normalized[len(".omo/") :]
    if normalized == ".omo":
        return ""
    return normalized.split("/", 1)[0] if normalized else ""


def _top_level_entries(omo_dir: Path) -> list[str]:
    ignored = {".DS_Store", "__pycache__", ".omo"}
    return sorted(
        entry.name for entry in omo_dir.iterdir() if entry.name not in ignored
    )


def _check_goals_runtime_entry(omo_dir: Path) -> tuple[dict[str, object], list[str]]:
    goals_path = omo_dir / "goals"
    truth_goals_path = omo_dir / "_truth" / "goals"
    summary: dict[str, object] = {
        "path": str(goals_path),
        "truth_path": str(truth_goals_path),
        "exists": goals_path.exists(),
        "is_symlink": goals_path.is_symlink(),
        "resolves_to_truth": False,
        "current_exists": (goals_path / "current.yaml").exists()
        if goals_path.exists()
        else False,
    }
    issues: list[str] = []
    if not goals_path.exists():
        issues.append("goals runtime entry missing: .omo/goals")
        return summary, issues
    if not goals_path.is_symlink():
        issues.append(
            "goals runtime entry must be a symlink: .omo/goals -> .omo/_truth/goals"
        )
        return summary, issues
    try:
        summary["resolves_to_truth"] = (
            goals_path.resolve() == truth_goals_path.resolve()
        )
    except FileNotFoundError:
        summary["resolves_to_truth"] = False
    if not summary["resolves_to_truth"]:
        issues.append("goals runtime entry resolves to unexpected target")
    if not summary["current_exists"]:
        issues.append("goals runtime entry missing current.yaml")
    return summary, issues


def _read_c2g_governance_refs(workspace_root: Path) -> tuple[list[str], list[str]]:
    issues: list[str] = []
    refs: list[str] = []
    c2g_src = workspace_root / "projects" / "c2g" / "src"
    if not c2g_src.exists():
        issues.append("projects/c2g/src missing")
        return refs, issues
    sys.path.insert(0, str(c2g_src))
    try:
        from c2g.task_builder import build_ecos_task  # type: ignore

        task = build_ecos_task(
            "SURFACE-CHECK",
            "surface check",
            source_docs=["governance"],
            evidence_required=["evidence"],
            test_plan=["verify"],
        )
        refs = list(task.get("governance_refs", []))
        if not refs:
            issues.append("c2g task builder returned empty governance_refs")
        metadata = task.get("metadata", {})
        if metadata.get("ingress_plane") != "projects/c2g":
            issues.append("c2g task builder ingress_plane metadata mismatch")
    except Exception as exc:  # pragma: no cover - defensive
        issues.append(f"failed to load c2g governance refs: {exc}")
    finally:
        if sys.path and sys.path[0] == str(c2g_src):
            sys.path.pop(0)
    return refs, issues


def _has_direct_io_gate(workspace_root: Path) -> bool:
    precommit = workspace_root / ".pre-commit-config.yaml"
    if not precommit.exists():
        return False
    text = precommit.read_text(encoding="utf-8")
    return "omo-direct-io-gate" in text and "lint direct-omo-io" in text


def _has_task_policy_gate(workspace_root: Path) -> bool:
    precommit = workspace_root / ".pre-commit-config.yaml"
    if not precommit.exists():
        return False
    text = precommit.read_text(encoding="utf-8")
    return "omo-task-policy-gate" in text and "lint task-policy" in text


def _has_mutation_surface_gate(workspace_root: Path) -> bool:
    precommit = workspace_root / ".pre-commit-config.yaml"
    if not precommit.exists():
        return False
    text = precommit.read_text(encoding="utf-8")
    return "omo-mutation-surface-gate" in text and "lint mutation-surfaces" in text


def _has_internal_write_profile_gate(workspace_root: Path) -> bool:
    precommit = workspace_root / ".pre-commit-config.yaml"
    if not precommit.exists():
        return False
    text = precommit.read_text(encoding="utf-8")
    return (
        "omo-internal-write-profile-gate" in text
        and "lint internal-write-profiles" in text
    )


def _has_state_plane_asset_gate(workspace_root: Path) -> bool:
    precommit = workspace_root / ".pre-commit-config.yaml"
    if not precommit.exists():
        return False
    text = precommit.read_text(encoding="utf-8")
    return "omo-state-plane-asset-gate" in text and "lint state-plane-assets" in text


def _has_c2g_omo_boundary_gate(workspace_root: Path) -> bool:
    precommit = workspace_root / ".pre-commit-config.yaml"
    if not precommit.exists():
        return False
    text = precommit.read_text(encoding="utf-8")
    return "omo-c2g-omo-boundary-gate" in text and "lint c2g-omo-boundary" in text


def _has_ingress_artifact_gate(workspace_root: Path) -> bool:
    precommit = workspace_root / ".pre-commit-config.yaml"
    if not precommit.exists():
        return False
    text = precommit.read_text(encoding="utf-8")
    return "omo-ingress-artifact-gate" in text and "lint ingress-artifacts" in text


def _has_mutation_ledger_gate(workspace_root: Path) -> bool:
    precommit = workspace_root / ".pre-commit-config.yaml"
    if not precommit.exists():
        return False
    text = precommit.read_text(encoding="utf-8")
    return "omo-mutation-ledger-gate" in text and "lint mutation-ledger" in text


def _candidate_roots(start: Path) -> list[Path]:
    current = start.resolve()
    if current.is_file():
        current = current.parent
    return [current, *current.parents]


def resolve_governance_workspace_root(start: Path | None = None) -> Path:
    starts: list[Path] = []
    if start is not None:
        starts.append(start)
    starts.append(Path.cwd())
    starts.append(Path(__file__).resolve())

    seen: set[Path] = set()
    for origin in starts:
        for candidate in _candidate_roots(origin):
            if candidate in seen:
                continue
            seen.add(candidate)
            if (candidate / ".omo").exists() and (
                (candidate / "projects" / "c2g").exists()
                or (candidate / "projects" / "omo").exists()
            ):
                return candidate
    for origin in starts:
        for candidate in _candidate_roots(origin):
            if (candidate / ".omo").exists():
                return candidate
    raise FileNotFoundError("unable to locate workspace root containing .omo/")

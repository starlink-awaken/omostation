#!/usr/bin/env python3
"""ADR-0456 B5 — `.omo/state/system.yaml` 的创建者 (materializer).

该文件自 #4606 起是**设计上的陈旧快照** (检出里那份 = 最后一次提交的镜像, 现值在 state 根)。
摘库 (git rm --cached) 之后, 干净检出里它根本不存在, 而 `bin/ssot/current-state-coherence.py`
对缺失输入抛 `CoherenceInputError` 并返回 rc 2 —— 所以摘库必须与创建者同批, 否则
摘库这一刀会自己把绿的 CI 砍红。

契约 (spec §3 I1–I4):
  I1  输出的 top-level 键集合 == write-owners.yaml 声明集合 (双向, 少写=ghost / 多写=undeclared)。
  I2  写路径在**调用时刻**经 repo_root.state_root() 解析, 不写模块级常量。
  I3  幂等且不覆盖: 目标已存在 ⇒ skipped + rc 0 (生产机上那份是 8 个写者正在维护的活运行态)。
  I4  原子写入: 临时文件 + os.replace, 读者不会读到半份。

取值口径与在案写者 `projects/omo/src/omo/omo_state.py:sync-tasks` 逐字段一致 (§8: 不改语义),
生成者所有的 13 个键给**空形** (标量 null / 结构 {}), 因为 `null` 才是"没人测过";
写 0 会被健康度类门禁读成"测了, 是零分"。

Usage:
  python3 bin/gac/materialize-system-state.py [--root <checkout>] [--json] [--dry-run] [--force]
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
from repo_root import code_root, state_root  # noqa: E402

SYSTEM_YAML_REL = Path(".omo") / "state" / "system.yaml"
WRITE_OWNERS_REL = Path(".omo") / "_truth" / "registry" / "write-owners.yaml"
TITLE_MAX = 48

# 生成者所有的键 → 空形。物化器不测量这些, 只保证 I1 的键集合相等。
EMPTY_SCALAR_KEYS = (
    "health_score",
    "health_score_source",
    "health_score_generated_at",
    "health_score_evidence",
    "health_score_evidence_source",
    "health_score_evidence_generated_at",
    "governance_anomaly_score",
    "governance_feedback_last_run",
    "service_online_ratio",
)
EMPTY_MAPPING_KEYS = (
    "runtime_health_summary",
    "workflow_mesh_health",
    "harness",
    "self_evolution",
)


class MaterializeError(RuntimeError):
    """缺失/畸形的已提交真源 —— 宁可不写, 也不写一份靠猜测补齐的状态."""


def _merged_yaml(path: Path) -> dict:
    """多文档 YAML 合并 —— 与 current-state-coherence.py:_merged_yaml 同一口径.

    `.omo/goals/current.yaml` 是 frontmatter + body 两个文档, `yaml.safe_load` 会当场
    ComposerError, 所以必须 safe_load_all 后逐文档 update。
    """
    if not path.is_file():
        raise MaterializeError(f"missing input: {path}")
    merged: dict = {}
    try:
        documents = list(yaml.safe_load_all(path.read_text(encoding="utf-8")))
    except (OSError, yaml.YAMLError) as exc:
        raise MaterializeError(f"cannot read YAML: {path}") from exc
    for document in documents:
        if isinstance(document, dict):
            merged.update(document)
    return merged


def _direct_yaml_count(path: Path) -> int:
    return len(list(path.glob("*.yaml"))) if path.is_dir() else 0


def task_counts(root: Path) -> dict[str, int]:
    """tasks/ 真实文件计数, archived/done 计入 completed (同 omo_state.sync-tasks)。"""
    task_dir = root / ".omo" / "tasks"
    done = _direct_yaml_count(task_dir / "done") + _direct_yaml_count(task_dir / "archived" / "done")
    return {
        "active_tasks": _direct_yaml_count(task_dir / "active"),
        "planned_tasks": _direct_yaml_count(task_dir / "planned"),
        "blocked_tasks": _direct_yaml_count(task_dir / "blocked"),
        "completed_tasks": done,
        "total_tasks": _direct_yaml_count(task_dir / "active")
        + _direct_yaml_count(task_dir / "planned")
        + _direct_yaml_count(task_dir / "blocked")
        + done,
    }


def _read_task_title(task_file: Path) -> str:
    """只取头部 title 行 (omo_state.py:194 的省 IO 口径, 含 48 字符截断)。"""
    try:
        for line in task_file.read_text(encoding="utf-8").splitlines():
            if line.startswith("title:"):
                return line.split(":", 1)[1].strip().strip("\"'")[:TITLE_MAX]
            if line.startswith(("status:", "description:")):
                break
    except OSError:
        pass
    return "(no title)"


def task_items(root: Path, sub: str) -> list[str]:
    d = root / ".omo" / "tasks" / sub
    if not d.is_dir():
        return []
    return [f"{f.stem} ({_read_task_title(f)})" for f in sorted(d.glob("*.yaml"))]


def declared_keys(root: Path) -> set[str]:
    """write-owners.yaml 对 `.omo/state/system.yaml` 声明的键集合 (I1 的另一侧)。"""
    owners = _merged_yaml(root / WRITE_OWNERS_REL)
    fields = owners.get("fields")
    if not isinstance(fields, dict):
        raise MaterializeError(f"{WRITE_OWNERS_REL}: no `fields:` mapping")
    declared = fields.get(str(SYSTEM_YAML_REL))
    if not isinstance(declared, dict):
        raise MaterializeError(f"write-owners.yaml declares no fields for {SYSTEM_YAML_REL}")
    return set(declared)


def build_document(root: Path) -> dict[str, object]:
    goals = _merged_yaml(root / ".omo" / "goals" / "current.yaml")
    for key in ("phase", "current_wave"):
        if key not in goals:
            raise MaterializeError(f".omo/goals/current.yaml lacks `{key}` — cannot derive current_{key}")
    doc: dict[str, object] = {
        "current_phase": goals["phase"],
        "current_wave": goals["current_wave"],
        **task_counts(root),
        "next_active_tasks": task_items(root, "active") or ["(No active tasks)"],
        "next_planned_tasks": task_items(root, "planned"),
        "updated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
    }
    for key in EMPTY_SCALAR_KEYS:
        doc[key] = None
    for key in EMPTY_MAPPING_KEYS:
        doc[key] = {}
    return doc


def write_target() -> Path:
    """I2 — 落点在调用时刻的 state 根; 未声明 profile 时 state_root()==code_root()。"""
    return state_root() / SYSTEM_YAML_REL


def omo_target_check(target: Path) -> bool | None:
    """I2 的可指认性: 本工具的落点必须与 omo 内核的写目标逐字节相等。

    相等是 §8「不动 omo 侧写者」成立的唯一依据; omo 不可导入时返回 None (不谎报)。
    """
    try:
        from omo.omo_paths import STATE_SYSTEM_YAML  # type: ignore
    except Exception:
        return None
    return Path(STATE_SYSTEM_YAML).resolve() == target.resolve()


def build_report(root: Path) -> dict[str, object]:
    declared = declared_keys(root)
    doc = build_document(root)
    produced = set(doc)
    return {
        "read_root": str(root),
        "target": str(write_target()),
        "key_count": len(produced),
        "declared_count": len(declared),
        "key_set_equals_declared": produced == declared,
        "undeclared": sorted(produced - declared),
        "ghost": sorted(declared - produced),
        "derived": {
            key: doc[key]
            for key in (
                "current_phase",
                "current_wave",
                "active_tasks",
                "planned_tasks",
                "blocked_tasks",
                "completed_tasks",
                "total_tasks",
            )
        },
        "empty_shape_keys": len(EMPTY_SCALAR_KEYS) + len(EMPTY_MAPPING_KEYS),
        "document": doc,
    }


def emit(report: dict[str, object], as_json: bool) -> None:
    if as_json:
        public = {k: v for k, v in report.items() if k != "document"}
        print(json.dumps(public, ensure_ascii=False, indent=2))
    else:
        for key in ("status", "target", "key_set_equals_declared", "undeclared", "ghost"):
            print(f"{key}: {report.get(key)}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Materialize .omo/state/system.yaml from committed truth")
    parser.add_argument("--root", type=Path, default=None, help="读取已提交真源的检出根 (默认 code_root())")
    parser.add_argument("--json", action="store_true", dest="as_json")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--force", action="store_true", help="目标已存在时仍重写 (默认跳过, I3)")
    args = parser.parse_args(argv)

    root = (args.root or code_root()).resolve()
    try:
        report = build_report(root)
    except MaterializeError as exc:
        print(f"materialize-system-state: {exc}", file=sys.stderr)
        return 1

    report["target_equals_omo_state_yaml"] = omo_target_check(Path(report["target"]))
    target = write_target()

    if not report["key_set_equals_declared"]:
        report["status"] = "failed"
        report["reason"] = "I1: key set != declared set (would造 ghost/undeclared findings)"
        emit(report, args.as_json)
        return 1

    if args.dry_run:
        report["status"] = "dry_run"
        emit(report, args.as_json)
        return 0

    if target.is_file() and not args.force:
        report["status"] = "skipped"
        report["reason"] = "I3: target exists (pass --force to rewrite)"
        emit(report, args.as_json)
        return 0

    target.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(target.parent), prefix=".system.yaml.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            yaml.safe_dump(report["document"], fh, allow_unicode=True, sort_keys=False)
        os.replace(tmp, target)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise
    report["status"] = "materialized"
    report["bytes"] = target.stat().st_size
    emit(report, args.as_json)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

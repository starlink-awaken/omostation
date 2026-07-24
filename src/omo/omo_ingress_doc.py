"""omo_ingress doc 创建 (从 God Module 拆出, SRP · P60+ 第五步).

create_knowledge_doc / create_standard_doc / create_audit_report.
写 .omo/_knowledge/{plane}/*.md + .omo/standards/*.md + .omo/_knowledge/audits/*.md.
依赖 trail (已拆 omo_ingress_trail) + registry (_record_mutation) — 无循环.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from omo.omo_audit import record as record_audit
from omo.omo_ingress_paths import (
    _audit_log_path,
    _delivery_root,
    _lock_path,
    _safe_doc_name,
    _timestamp_slug,
    _utc_now,
    _workspace_relative,
)
from omo.omo_io import fcntl_lock, write_text_atomic, write_yaml_atomic


def create_knowledge_doc(
    omo_dir: Path,
    *,
    plane: str,
    title: str,
    source_ref: str = "",
    content: str,
    actor: str,
    now: str | None = None,
) -> dict[str, Any]:
    from omo.omo_ingress import _record_mutation, _record_trail

    timestamp = now or _utc_now()
    safe_name = _safe_doc_name(title)
    doc_path = omo_dir / "_knowledge" / plane / f"{safe_name}.md"

    with fcntl_lock(_lock_path(omo_dir)):
        if doc_path.exists():
            raise ValueError(f"{doc_path.name} already exists")
        write_text_atomic(doc_path, f"# {title}\n\n{content}\n")
        artifact = {
            "kind": "knowledge_doc_created",
            "plane": plane,
            "title": title,
            "doc_ref": f".omo/_knowledge/{plane}/{safe_name}.md",
            "actor": actor,
            "source_ref": source_ref,
            "created_at": timestamp,
        }
        artifact_path = (
            _delivery_root(omo_dir)
            / "knowledge"
            / f"{plane}-{safe_name}-{_timestamp_slug(timestamp)}.yaml"
        )
        write_yaml_atomic(artifact_path, artifact)
        parent_step_id = f"ingress:knowledge:{plane}:{safe_name}:{timestamp}"
        details = (
            f"plane={plane} title={title} actor={actor} "
            f"source_ref={source_ref or '-'} artifact={_workspace_relative(artifact_path)}"
        )
        record_audit(
            action="ingress_create_knowledge_doc",
            debt_id="",
            actor=actor,
            details=details,
            audit_file=_audit_log_path(omo_dir),
        )
        _record_trail(
            omo_dir,
            actor=f"broker:{actor}",
            action="create_knowledge_doc",
            target=f".omo/_knowledge/{plane}/{safe_name}.md",
            parent_step_id=parent_step_id,
        )
        _record_mutation(
            omo_dir,
            actor=actor,
            action="create_knowledge_doc",
            target=f".omo/_knowledge/{plane}/{safe_name}.md",
            artifact_ref=f"runtime/omo/_delivery/ingress/knowledge/{artifact_path.name}",
            source_ref=source_ref,
            created_at=timestamp,
            extra={"plane": plane, "title": title},
        )
        return artifact


def create_standard_doc(
    omo_dir: Path,
    *,
    title: str,
    content: str,
    actor: str,
    source_ref: str = "",
    now: str | None = None,
) -> dict[str, Any]:
    from omo.omo_ingress import _record_mutation, _record_trail

    timestamp = now or _utc_now()
    safe_name = _safe_doc_name(title)
    doc_path = omo_dir / "standards" / f"{safe_name}.md"

    with fcntl_lock(_lock_path(omo_dir)):
        if doc_path.exists():
            raise ValueError(f"{doc_path.name} already exists")
        write_text_atomic(doc_path, f"# {title}\n\n{content}\n")
        artifact = {
            "kind": "standard_doc_created",
            "title": title,
            "doc_ref": f".omo/standards/{safe_name}.md",
            "actor": actor,
            "source_ref": source_ref,
            "created_at": timestamp,
        }
        artifact_path = (
            _delivery_root(omo_dir)
            / "standards"
            / f"{safe_name}-{_timestamp_slug(timestamp)}.yaml"
        )
        write_yaml_atomic(artifact_path, artifact)
        parent_step_id = f"ingress:standard:{safe_name}:{timestamp}"
        details = (
            f"title={title} actor={actor} source_ref={source_ref or '-'} "
            f"artifact={_workspace_relative(artifact_path)}"
        )
        record_audit(
            action="ingress_create_standard_doc",
            debt_id="",
            actor=actor,
            details=details,
            audit_file=_audit_log_path(omo_dir),
        )
        _record_trail(
            omo_dir,
            actor=f"broker:{actor}",
            action="create_standard_doc",
            target=f".omo/standards/{safe_name}.md",
            parent_step_id=parent_step_id,
        )
        _record_mutation(
            omo_dir,
            actor=actor,
            action="create_standard_doc",
            target=f".omo/standards/{safe_name}.md",
            artifact_ref=f"runtime/omo/_delivery/ingress/standards/{artifact_path.name}",
            source_ref=source_ref,
            created_at=timestamp,
            extra={"title": title},
        )
        return artifact


def create_audit_report(
    omo_dir: Path,
    *,
    filename: str,
    title: str,
    content: str,
    actor: str,
    source_ref: str = "",
    now: str | None = None,
) -> dict[str, Any]:
    from omo.omo_ingress import _record_mutation, _record_trail

    timestamp = now or _utc_now()
    report_path = omo_dir / "_knowledge" / "audits" / f"{filename}.md"

    with fcntl_lock(_lock_path(omo_dir)):
        if report_path.exists():
            raise ValueError(f"{report_path.name} already exists")
        write_text_atomic(report_path, f"# {title}\n\n{content}\n")
        artifact = {
            "kind": "audit_report_created",
            "title": title,
            "report_ref": f".omo/_knowledge/audits/{filename}.md",
            "actor": actor,
            "source_ref": source_ref,
            "created_at": timestamp,
        }
        artifact_path = (
            _delivery_root(omo_dir)
            / "audits"
            / f"{filename}-{_timestamp_slug(timestamp)}.yaml"
        )
        write_yaml_atomic(artifact_path, artifact)
        parent_step_id = f"ingress:audit:{filename}:{timestamp}"
        details = (
            f"filename={filename} actor={actor} source_ref={source_ref or '-'} "
            f"artifact={_workspace_relative(artifact_path)}"
        )
        record_audit(
            action="ingress_create_audit_report",
            debt_id="",
            actor=actor,
            details=details,
            audit_file=_audit_log_path(omo_dir),
        )
        _record_trail(
            omo_dir,
            actor=f"broker:{actor}",
            action="create_audit_report",
            target=f".omo/_knowledge/audits/{filename}.md",
            parent_step_id=parent_step_id,
        )
        _record_mutation(
            omo_dir,
            actor=actor,
            action="create_audit_report",
            target=f".omo/_knowledge/audits/{filename}.md",
            artifact_ref=f"runtime/omo/_delivery/ingress/audits/{artifact_path.name}",
            source_ref=source_ref,
            created_at=timestamp,
            extra={"title": title},
        )
        return artifact

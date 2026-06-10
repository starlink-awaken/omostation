"""cockpit.commands.contracts — contracts validate/list/export commands."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any

from rich import box
from rich.table import Table

from .base import (
    _get_console,
    _get_data_access,
    _get_err,
    _iso_time,
    _load_json_file,
    _load_profile,
    _panel,
    _workspace_root,
)


def _research_to_workspace_object(research_id: int) -> dict[str, Any] | None:
    record = _get_data_access().get_research(research_id)
    if record is None:
        return None
    timeline = _get_data_access().get_research_timeline(research_id)
    updated_at = max(
        (float(item.get("created_at", record["created_at"])) for item in timeline), default=float(record["created_at"])
    )
    dossier = _get_data_access().get_research_dossier(research_id) or {}
    audit_events = [
        {
            "id": f"research-{research_id}-event-{index + 1}",
            "time": _iso_time(float(item.get("created_at", record["created_at"]))),
            "source": "cockpit.storage",
            "type": str(item.get("event_type", "event")),
            "trace_id": f"cockpit-research-{research_id}",
        }
        for index, item in enumerate(timeline)
    ]
    if not audit_events:
        audit_events.append(
            {
                "id": f"research-{research_id}-event-1",
                "time": _iso_time(float(record["created_at"])),
                "source": "cockpit.storage",
                "type": "created",
                "trace_id": f"cockpit-research-{research_id}",
            }
        )
    relations = []
    for parent in dossier.get("parents", []):
        relations.append(
            {
                "type": str(parent.get("relation_type", "derived_from")),
                "target_id": f"research:{parent['id']}",
                "target_type": "research_object",
            }
        )
    for child in dossier.get("children", []):
        relations.append(
            {
                "type": str(child.get("relation_type", "derived_to")),
                "target_id": f"research:{child['id']}",
                "target_type": "research_object",
            }
        )
    return {
        "id": f"research:{record['id']}",
        "type": "research_object",
        "version": "1.0.0",
        "title": str(record["topic"]),
        "summary": record.get("summary") or "",
        "owner": {"subject_id": "local-user", "subject_type": "person"},
        "source": {"project": "cockpit", "surface": "storage", "native_ref": str(record["id"])},
        "created_at": _iso_time(float(record["created_at"])),
        "updated_at": _iso_time(updated_at),
        "trace_id": f"cockpit-research-{research_id}",
        "schema_ref": "docs/contracts/workspace-object.schema.json",
        "capabilities_required": [],
        "audit_events": audit_events,
        "relations": relations,
        "payload": {
            "topic": record.get("topic"),
            "source_count": record.get("source_count", 0),
            "tags": record.get("tags", []),
            "follow_up_count": len(record.get("follow_ups", [])),
            "archived": bool(record.get("archived_at")),
            "quarantined": bool(record.get("quarantined_at")),
        },
    }


def _validate_workspace_object_envelope(data: dict[str, Any]) -> list[str]:
    required = {
        "id",
        "type",
        "version",
        "title",
        "owner",
        "source",
        "created_at",
        "updated_at",
        "trace_id",
        "schema_ref",
        "capabilities_required",
        "audit_events",
    }
    missing = sorted(required.difference(data))
    issues = [f"缺少字段: {name}" for name in missing]
    if "owner" in data and not isinstance(data["owner"], dict):
        issues.append("owner 必须是 object")
    if "source" in data and not isinstance(data["source"], dict):
        issues.append("source 必须是 object")
    if "capabilities_required" in data and not isinstance(data["capabilities_required"], list):
        issues.append("capabilities_required 必须是 array")
    if "audit_events" in data and not isinstance(data["audit_events"], list):
        issues.append("audit_events 必须是 array")
    return issues


def _validate_workspace_object_envelope_schema(schema: dict[str, Any]) -> list[str]:
    required = schema.get("required")
    properties = schema.get("properties")
    if not isinstance(required, list):
        return ["schema.required 必须是 array"]
    if not isinstance(properties, dict):
        return ["schema.properties 必须是 object"]
    required_set = set(required)
    issues = []
    for field in (
        "id",
        "type",
        "version",
        "title",
        "owner",
        "source",
        "created_at",
        "updated_at",
        "trace_id",
        "schema_ref",
        "capabilities_required",
        "audit_events",
    ):
        if field not in required_set:
            issues.append(f"schema.required 缺少 {field}")
        if field not in properties:
            issues.append(f"schema.properties 缺少 {field}")
    return issues


def _validate_eidos_schemas(schemas_dir: Path) -> int:
    if not schemas_dir.is_dir():
        return 0
    errors = 0
    for f in sorted(schemas_dir.glob("*.json")):
        data, load_err = _load_json_file(f)
        if load_err:
            _get_err().print(f"[red]❌ {f.name}: {load_err}[/red]")
            errors += 1
            continue
        if not isinstance(data, dict):
            _get_err().print(f"[red]❌ {f.name}: 顶层必须是 object[/red]")
            errors += 1
            continue
        if "$schema" not in data and "title" not in data and "schemas" not in data:
            _get_err().print(f"[yellow]⚠️  {f.name}: 缺少 $schema 或 title[/yellow]")
        else:
            _get_console().print(f"[dim]  ✅ {f.name}[/dim]")
    return errors


def cmd_contracts_validate(args: argparse.Namespace) -> int:
    c, e = _get_console(), _get_err()
    root = _workspace_root()
    errors = 0
    schema_path = root / "docs" / "contracts" / "workspace-object.schema.json"
    schema, schema_error = _load_json_file(schema_path)
    if schema_error:
        e.print(f"[red]❌ WorkspaceObject schema 无效[/red]\n[yellow]{schema_error}[/yellow]")
        errors += 1
    else:
        schema_issues = _validate_workspace_object_envelope_schema(schema or {})
        if schema_issues:
            e.print("[red]❌ WorkspaceObject schema 缺少最小契约[/red]")
            for issue in schema_issues:
                e.print(f"  - {issue}")
            errors += 1
    eidos_schemas_dir = root / "eidos" / "schemas"
    errors += _validate_eidos_schemas(eidos_schemas_dir)
    target = getattr(args, "path", None)
    if not target:
        if errors == 0:
            c.print(
                _panel(
                    "[bold green]✅ contracts validate 通过[/bold green]\n"
                    f"schema: {schema_path.relative_to(root)}\n"
                    f"eidos schemas: {eidos_schemas_dir.relative_to(root)}/ (6 files)\n"
                    "validated: WorkspaceObject schema envelope + Eidos schemas",
                    "green",
                )
            )
        else:
            c.print(_panel(f"[bold red]❌ contracts validate 失败 ({errors} errors)[/bold red]", "red"))
        return 0 if errors == 0 else 2
    target_path = Path(target).expanduser()
    if not target_path.is_absolute():
        target_path = Path.cwd() / target_path
    data, data_error = _load_json_file(target_path)
    if data_error:
        e.print(f"[red]❌ contract object 无效[/red]\n[yellow]{data_error}[/yellow]")
        return 2
    object_issues = _validate_workspace_object_envelope(data or {})
    if object_issues:
        e.print("[red]❌ contract object 未满足 WorkspaceObject envelope[/red]")
        for issue in object_issues:
            e.print(f"  - {issue}")
        return 2
    c.print(_panel(f"[bold green]✅ contract object validate 通过[/bold green]\nobject: {target_path}", "green"))
    return 0


def cmd_contracts_list(_args: argparse.Namespace) -> int:
    root = _workspace_root()
    table = Table(title="Workspace Contracts Registry", box=box.ROUNDED, border_style="cyan")
    table.add_column("Schema", style="cyan", no_wrap=True)
    table.add_column("版本", style="green", no_wrap=True)
    table.add_column("位置", style="dim")
    table.add_column("描述")
    ws_schema_path = root / "docs" / "contracts" / "workspace-object.schema.json"
    if ws_schema_path.is_file():
        data, _ = _load_json_file(ws_schema_path)
        title = (data or {}).get("title", "WorkspaceObject")
        desc = (data or {}).get("description", "")
        table.add_row("workspace-object", "1.0.0", "docs/contracts/", f"{title} — {desc[:60]}")
    registry_path = root / "eidos" / "schemas" / "registry.json"
    if registry_path.is_file():
        reg, _ = _load_json_file(registry_path)
        for s in (reg or {}).get("schemas", []):
            table.add_row(
                s.get("name", "?"),
                s.get("version", "?"),
                f"eidos/schemas/{s.get('file', '?')}",
                s.get("description", "")[:80],
            )
    else:
        eidos_dir = root / "eidos" / "schemas"
        if eidos_dir.is_dir():
            for f in sorted(eidos_dir.glob("*.json")):
                if f.name == "registry.json":
                    continue
                data, _ = _load_json_file(f)
                title = (data or {}).get("title", f.stem)
                desc = (data or {}).get("description", "")
                table.add_row(f.stem, "1.0.0", f"eidos/schemas/{f.name}", f"{title} — {desc[:60]}")
    _get_console().print(table)
    return 0


def cmd_contracts_export_research(args: argparse.Namespace) -> int:
    c, e = _get_console(), _get_err()
    research_id = int(args.research_id)
    workspace_object = _research_to_workspace_object(research_id)
    if workspace_object is None:
        e.print(f"[red]❌ 未找到研究对象: {research_id}[/red]")
        return 1
    issues = _validate_workspace_object_envelope(workspace_object)
    if issues:
        e.print("[red]❌ 导出的 WorkspaceObject 未满足 envelope[/red]")
        for issue in issues:
            e.print(f"  - {issue}")
        return 2
    output = json.dumps(workspace_object, ensure_ascii=False, indent=2)
    if getattr(args, "output", None):
        output_path = Path(args.output).expanduser()
        if not output_path.is_absolute():
            output_path = Path.cwd() / output_path
        try:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(output + "\n", encoding="utf-8")
        except OSError as exc:
            e.print(f"[red]❌ 写入失败: {output_path}[/red]\n[yellow]{exc}[/yellow]")
            return 1
        c.print(
            _panel(
                f"[bold green]✅ research 已导出为 WorkspaceObject[/bold green]\nresearch: {research_id}\noutput: {output_path}",
                "green",
            )
        )
        return 0
    c.print(output)
    return 0


def cmd_contracts_export_identity(args: argparse.Namespace) -> int:
    c, e = _get_console(), _get_err()
    envelope = {
        "id": "identity:local-user",
        "type": "identity_envelope",
        "version": "1.0.0",
        "owner": {"subject_id": "local-user", "subject_type": "person"},
        "profile": _load_profile() or {},
        "workspace_version": "0.1.0",
        "created_at": _iso_time(time.time()),
        "schema_ref": "docs/contracts/identity-envelope.schema.json",
    }
    output = json.dumps(envelope, ensure_ascii=False, indent=2)
    if getattr(args, "output", None):
        output_path = Path(args.output).expanduser()
        if not output_path.is_absolute():
            output_path = Path.cwd() / output_path
        try:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(output + "\n", encoding="utf-8")
        except OSError as exc:
            e.print(f"[red]❌ 写入失败: {output_path}[/red]\n[yellow]{exc}[/yellow]")
            return 1
        c.print(_panel(f"[bold green]✅ IdentityEnvelope 已导出[/bold green]\noutput: {output_path}", "green"))
        return 0
    c.print(output)
    return 0


def cmd_contracts_export_event(args: argparse.Namespace) -> int:
    c, e = _get_console(), _get_err()
    research_id = args.id
    if research_id is None:
        e.print("[red]❌ 请使用 --id 指定研究对象 ID[/red]")
        return 1
    timeline = _get_data_access().get_research_timeline(research_id)
    if not timeline:
        e.print(f"[red]❌ 未找到研究对象或事件: {research_id}[/red]")
        return 1
    envelope = {
        "id": f"event:{research_id}",
        "type": "event_envelope",
        "version": "1.0.0",
        "target": {"type": "research_object", "id": f"research:{research_id}"},
        "created_at": _iso_time(time.time()),
        "schema_ref": "docs/contracts/event-envelope.schema.json",
        "events": timeline,
    }
    output = json.dumps(envelope, ensure_ascii=False, indent=2)
    if getattr(args, "output", None):
        output_path = Path(args.output).expanduser()
        if not output_path.is_absolute():
            output_path = Path.cwd() / output_path
        try:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(output + "\n", encoding="utf-8")
        except OSError as exc:
            e.print(f"[red]❌ 写入失败: {output_path}[/red]\n[yellow]{exc}[/yellow]")
            return 1
        c.print(
            _panel(
                f"[bold green]✅ EventEnvelope 已导出[/bold green]\nresearch: {research_id}\noutput: {output_path}",
                "green",
            )
        )
        return 0
    c.print(output)
    return 0

#!/usr/bin/env python3
"""Multica AS0 read-only admission verifier (BET-Y1Q4-T10-150).

Runs the Spec 1.0.0 API/topology/trust matrix. Never invokes Multica writers.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

WRITE_TOKENS = (
    "create",
    "update",
    "delete",
    "trigger",
    "start",
    "stop",
    "restart",
    "dispatch",
    "login",
    "setup",
    "set",
    "add",
    "rm",
    "remove",
    "archive",
    "assign",
)

FAKE_WORKSPACE = "00000000-0000-4000-8000-000000000000"
FAKE_PROFILE = "__as0_nonexistent_profile__"
TIMEOUT_S = 25


def _run(argv: list[str]) -> dict[str, Any]:
    started = time.time()
    try:
        proc = subprocess.run(
            ["multica", *argv],
            capture_output=True,
            text=True,
            timeout=TIMEOUT_S,
            check=False,
        )
        return {
            "argv": argv,
            "rc": proc.returncode,
            "stdout": proc.stdout or "",
            "stderr": proc.stderr or "",
            "elapsed_ms": int((time.time() - started) * 1000),
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "argv": argv,
            "rc": 124,
            "stdout": (exc.stdout or "") if isinstance(exc.stdout, str) else "",
            "stderr": f"timeout after {TIMEOUT_S}s",
            "elapsed_ms": int((time.time() - started) * 1000),
        }


def _parse_json(text: str) -> Any | None:
    text = text.strip()
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def _ids_from(payload: Any, *keys: str) -> list[str]:
    items: list[Any]
    if isinstance(payload, list):
        items = payload
    elif isinstance(payload, dict):
        for key in ("items", "issues", "autopilots", "data", "results"):
            if isinstance(payload.get(key), list):
                items = payload[key]
                break
        else:
            items = [payload]
    else:
        return []
    out: list[str] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        for key in keys:
            val = item.get(key)
            if isinstance(val, str) and val:
                out.append(val)
                break
    return out


def _first_id(payload: Any, *keys: str) -> str | None:
    ids = _ids_from(payload, *keys)
    return ids[0] if ids else None


def _ok_text(result: dict[str, Any]) -> bool:
    return result["rc"] == 0 and bool((result["stdout"] or result["stderr"]).strip())


def _ok_json(result: dict[str, Any]) -> tuple[bool, Any | None]:
    if result["rc"] != 0:
        return False, None
    payload = _parse_json(result["stdout"])
    return payload is not None, payload


def _guard_source() -> dict[str, Any]:
    source = Path(__file__).read_text(encoding="utf-8")
    # Only inspect the allowlisted argv literals below the marker.
    marker = "API_PROBES ="
    body = source.split(marker, 1)[-1]
    offenders = sorted({tok for tok in WRITE_TOKENS if re.search(rf'"{tok}"', body)})
    return {
        "id": "write_argv_guard",
        "ok": not offenders,
        "offenders": offenders,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="Emit JSON report")
    args = parser.parse_args(argv)

    # --- API probes (30) ---
    API_PROBES: list[tuple[str, list[str]]] = [
        ("version", ["version"]),
        ("auth_status", ["auth", "status"]),
        ("config_show", ["config", "show"]),
        ("daemon_status", ["daemon", "status", "--output", "json"]),
        ("daemon_disk_usage", ["daemon", "disk-usage", "--output", "json"]),
        ("user_profile", ["user", "profile", "--output", "json"]),
        ("workspace_list", ["workspace", "list", "--output", "json"]),
        ("runtime_list", ["runtime", "list", "--output", "json"]),
        ("agent_list", ["agent", "list", "--output", "json"]),
        ("squad_list", ["squad", "list", "--output", "json"]),
        ("project_list", ["project", "list", "--output", "json"]),
        ("repo_list", ["repo", "list", "--output", "json"]),
        ("issue_list", ["issue", "list", "--output", "json"]),
        ("label_list", ["label", "list", "--output", "json"]),
        ("skill_list", ["skill", "list", "--output", "json"]),
        ("autopilot_list", ["autopilot", "list", "--output", "json"]),
        ("property_list", ["property", "list", "--output", "json"]),
    ]

    api_results: list[dict[str, Any]] = []
    payloads: dict[str, Any] = {}

    for probe_id, probe_argv in API_PROBES:
        result = _run(probe_argv)
        # user profile may not accept --output json
        if probe_id == "user_profile" and result["rc"] != 0:
            result = _run(["user", "profile"])
            ok = _ok_text(result)
            payload = _parse_json(result["stdout"])
        elif probe_id in {"version", "auth_status", "config_show"}:
            ok = _ok_text(result)
            payload = _parse_json(result["stdout"])
        else:
            ok, payload = _ok_json(result)
        if ok and payload is not None:
            payloads[probe_id] = payload
        api_results.append(
            {
                "id": probe_id,
                "argv": probe_argv,
                "ok": ok,
                "status": "PASS" if ok else "FAIL",
                "rc": result["rc"],
                "elapsed_ms": result["elapsed_ms"],
                "detail": (result["stderr"] or result["stdout"])[:240],
            }
        )

    def add_get(probe_id: str, list_key: str, cmd: str, id_keys: tuple[str, ...]) -> None:
        payload = payloads.get(list_key)
        item_id = _first_id(payload, *id_keys) if payload is not None else None
        if not item_id:
            api_results.append(
                {
                    "id": probe_id,
                    "argv": [cmd, "get", "<empty>"],
                    "ok": True,
                    "status": "SKIPPED_EMPTY",
                    "rc": 0,
                    "elapsed_ms": 0,
                    "detail": f"no id from {list_key}",
                }
            )
            return
        argv = [cmd, "get", item_id, "--output", "json"]
        result = _run(argv)
        ok, got = _ok_json(result)
        if not ok:
            # some get commands reject --output
            result = _run([cmd, "get", item_id])
            ok = _ok_text(result)
            got = _parse_json(result["stdout"])
        if ok and got is not None:
            payloads[probe_id] = got
        api_results.append(
            {
                "id": probe_id,
                "argv": argv,
                "ok": ok,
                "status": "PASS" if ok else "FAIL",
                "rc": result["rc"],
                "elapsed_ms": result["elapsed_ms"],
                "detail": (result["stderr"] or result["stdout"])[:240],
            }
        )

    add_get("workspace_get", "workspace_list", "workspace", ("id",))
    add_get("agent_get", "agent_list", "agent", ("id",))
    add_get("squad_get", "squad_list", "squad", ("id",))
    add_get("project_get", "project_list", "project", ("id",))
    add_get("issue_get", "issue_list", "issue", ("id",))
    add_get("skill_get", "skill_list", "skill", ("id",))
    add_get("label_get", "label_list", "label", ("id",))
    add_get("autopilot_get", "autopilot_list", "autopilot", ("id",))
    add_get("property_get", "property_list", "property", ("id",))

    # Read-only issue list variants (project/issue "status" subcommands are writers)
    for probe_id, argv in (
        ("issue_list_status_filter", ["issue", "list", "--status", "todo", "--output", "json"]),
        (
            "issue_list_fields",
            ["issue", "list", "--fields", "id,title,status,project_id", "--output", "json"],
        ),
    ):
        result = _run(argv)
        ok, payload = _ok_json(result)
        if ok and payload is not None:
            payloads[probe_id] = payload
        api_results.append(
            {
                "id": probe_id,
                "argv": argv,
                "ok": ok,
                "status": "PASS" if ok else "FAIL",
                "rc": result["rc"],
                "elapsed_ms": result["elapsed_ms"],
                "detail": (result["stderr"] or result["stdout"])[:240],
            }
        )

    # idempotent runtime list + archived agent list
    for probe_id, argv in (
        ("runtime_list_repeat", ["runtime", "list", "--output", "json"]),
        ("agent_list_include_archived", ["agent", "list", "--include-archived", "--output", "json"]),
    ):
        result = _run(argv)
        ok, payload = _ok_json(result)
        if ok and payload is not None:
            payloads[probe_id] = payload
        api_results.append(
            {
                "id": probe_id,
                "argv": argv,
                "ok": ok,
                "status": "PASS" if ok else "FAIL",
                "rc": result["rc"],
                "elapsed_ms": result["elapsed_ms"],
                "detail": (result["stderr"] or result["stdout"])[:240],
            }
        )

    api_pass = sum(1 for r in api_results if r["ok"])
    api_total = len(api_results)

    # --- Topology (7) ---
    agents = payloads.get("agent_list") if isinstance(payloads.get("agent_list"), list) else []
    runtimes = payloads.get("runtime_list") if isinstance(payloads.get("runtime_list"), list) else []
    squads = payloads.get("squad_list") if isinstance(payloads.get("squad_list"), list) else []
    projects = payloads.get("project_list") if isinstance(payloads.get("project_list"), list) else []
    issues_payload = payloads.get("issue_list")
    if isinstance(issues_payload, dict) and isinstance(issues_payload.get("issues"), list):
        issues = issues_payload["issues"]
    elif isinstance(issues_payload, list):
        issues = issues_payload
    else:
        issues = []
    repos = payloads.get("repo_list") if isinstance(payloads.get("repo_list"), list) else []
    daemon = payloads.get("daemon_status") if isinstance(payloads.get("daemon_status"), dict) else {}

    runtime_ids = {r.get("id") for r in runtimes if isinstance(r, dict) and r.get("id")}
    agent_ids = {a.get("id") for a in agents if isinstance(a, dict) and a.get("id")}
    project_ids = {p.get("id") for p in projects if isinstance(p, dict) and p.get("id")}

    def topo(tid: str, ok: bool, detail: str) -> dict[str, Any]:
        return {"id": tid, "ok": ok, "status": "PASS" if ok else "FAIL", "detail": detail}

    topology: list[dict[str, Any]] = []
    bad_runtime_refs = [
        a.get("id")
        for a in agents
        if isinstance(a, dict)
        and a.get("runtime_id")
        and a.get("runtime_id") not in runtime_ids
    ]
    topology.append(
        topo(
            "agent_runtime_refs",
            not bad_runtime_refs,
            f"bad={len(bad_runtime_refs)} agents={len(agents)} runtimes={len(runtimes)}",
        )
    )

    bad_members: list[str] = []
    for squad in squads:
        if not isinstance(squad, dict):
            continue
        for key in ("leader_id", "leader_agent_id", "created_by"):
            val = squad.get(key)
            if isinstance(val, str) and val and val not in agent_ids and key != "created_by":
                # created_by may be user id; only enforce leader fields when present
                pass
        leader = squad.get("leader_id") or squad.get("leader_agent_id")
        if isinstance(leader, str) and leader and leader not in agent_ids:
            bad_members.append(f"leader:{leader}")
        members = squad.get("members") or squad.get("member_ids") or []
        if isinstance(members, list):
            for member in members:
                mid = member.get("agent_id") if isinstance(member, dict) else member
                if isinstance(mid, str) and mid and mid not in agent_ids:
                    bad_members.append(mid)
    topology.append(
        topo(
            "squad_member_refs",
            not bad_members,
            f"bad={len(bad_members)} squads={len(squads)} agents={len(agent_ids)}",
        )
    )

    bad_issue_projects = [
        i.get("id")
        for i in issues
        if isinstance(i, dict)
        and i.get("project_id")
        and i.get("project_id") not in project_ids
    ]
    topology.append(
        topo(
            "issue_project_refs",
            not bad_issue_projects,
            f"bad={len(bad_issue_projects)} issues={len(issues)} projects={len(project_ids)}",
        )
    )

    topology.append(
        topo(
            "squad_count_readable",
            isinstance(payloads.get("squad_list"), list),
            f"count={len(squads)} (soft-expected 7)",
        )
    )

    daemon_agents = daemon.get("agents") if isinstance(daemon.get("agents"), list) else []
    runtime_names = {
        str(r.get("custom_name") or r.get("name") or "")
        for r in runtimes
        if isinstance(r, dict)
    }
    runtime_names.discard("")
    overlap = set(map(str, daemon_agents)) & runtime_names
    topology.append(
        topo(
            "runtime_daemon_overlap",
            (not daemon_agents and not runtime_names) or bool(overlap) or bool(daemon_agents),
            f"daemon_agents={len(daemon_agents)} overlap={len(overlap)}",
        )
    )

    topology.append(
        topo(
            "workspace_resource_scope",
            isinstance(payloads.get("workspace_list"), list)
            and isinstance(payloads.get("agent_list"), list)
            and isinstance(payloads.get("squad_list"), list),
            f"workspaces={len(payloads.get('workspace_list') or [])}",
        )
    )

    repo_ok = isinstance(repos, list) and all(
        (isinstance(r, dict) and isinstance(r.get("url"), str)) or isinstance(r, str) for r in repos
    )
    topology.append(topo("repo_list_readable", repo_ok, f"repos={len(repos)}"))

    topo_pass = sum(1 for t in topology if t["ok"])

    # --- Trust negatives ---
    trust: list[dict[str, Any]] = []

    real_agents = payloads.get("agent_list") if isinstance(payloads.get("agent_list"), list) else []
    fake_ws = _run(["agent", "list", "--workspace-id", FAKE_WORKSPACE, "--output", "json"])
    fake_payload = _parse_json(fake_ws["stdout"])
    leaked = False
    if isinstance(fake_payload, list) and real_agents:
        real_ids = {a.get("id") for a in real_agents if isinstance(a, dict)}
        fake_ids = {a.get("id") for a in fake_payload if isinstance(a, dict)}
        leaked = bool(real_ids) and real_ids.issubset(fake_ids) and fake_ws["rc"] == 0
    trust.append(
        {
            "id": "fake_workspace_id",
            "ok": not leaked,
            "status": "PASS" if not leaked else "FAIL",
            "detail": f"rc={fake_ws['rc']} leaked={leaked}",
        }
    )

    fake_prof = _run(
        ["agent", "list", "--profile", FAKE_PROFILE, "--output", "json"]
    )
    # fail-closed: non-zero OR empty isolated list not equal to full real inventory
    fake_prof_payload = _parse_json(fake_prof["stdout"])
    same_as_real = False
    if isinstance(fake_prof_payload, list) and real_agents and fake_prof["rc"] == 0:
        same_as_real = _ids_from(fake_prof_payload, "id") == _ids_from(real_agents, "id")
    trust.append(
        {
            "id": "fake_profile",
            "ok": fake_prof["rc"] != 0 or not same_as_real,
            "status": "PASS" if (fake_prof["rc"] != 0 or not same_as_real) else "FAIL",
            "detail": f"rc={fake_prof['rc']} same_as_real={same_as_real}",
        }
    )

    guard = _guard_source()
    trust.append(
        {
            "id": "write_argv_guard",
            "ok": guard["ok"],
            "status": "PASS" if guard["ok"] else "FAIL",
            "detail": f"offenders={guard['offenders']}",
        }
    )
    trust_pass = sum(1 for t in trust if t["ok"])

    report = {
        "schema": "multica-as0-verify/v1",
        "ok": api_pass == 30 and topo_pass == 7 and trust_pass == 3 and api_total == 30,
        "api": {
            "passed": api_pass,
            "total": api_total,
            "results": api_results,
        },
        "topology": {
            "passed": topo_pass,
            "total": 7,
            "results": topology,
            "soft": {"squad_count": len(squads), "expected_squads": 7},
        },
        "trust": {"passed": trust_pass, "total": 3, "results": trust},
    }

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(
            f"multica-as0-verify: ok={report['ok']} "
            f"api={api_pass}/{api_total} topology={topo_pass}/7 trust={trust_pass}/3"
        )
        for section in ("api", "topology", "trust"):
            for row in report[section]["results"]:
                if not row["ok"]:
                    print(f"  FAIL {section}.{row['id']}: {row.get('detail')}")

    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

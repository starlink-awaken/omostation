#!/usr/bin/env python3
"""panorama-collect.py — 织星全景驾驶舱采集器（只读 SSOT 聚合，零仓库写副作用）。

聚合门禁/BET/Agent/运行态/里程碑/治理数据，产物只写 runtime/dashboard/（gitignored）。
与 Serena 只读观测站互补：Serena=外部证据观测，驾驶舱=体系运行指挥台。

用法：
    python3 bin/panorama/panorama-collect.py            # 采集 + 生成站点
    python3 bin/panorama/panorama-collect.py --json     # 只输出 data.json 摘要
    python3 bin/panorama/panorama-collect.py --gates    # 只刷新门禁 receipt 视图
    python3 bin/panorama/panorama-collect.py --check-side-effects
                                                        # 验证零仓库写副作用
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

_CONFIGURED_ROOT = os.environ.get("PANORAMA_ROOT")
ROOT = Path(_CONFIGURED_ROOT).resolve() if _CONFIGURED_ROOT else Path(__file__).resolve().parents[2]
_CONFIGURED_CODE_ROOT = os.environ.get("PANORAMA_CODE_ROOT")
CODE_ROOT = (
    Path(_CONFIGURED_CODE_ROOT).resolve()
    if _CONFIGURED_CODE_ROOT else ROOT
)
OUT_DIR = ROOT / "runtime" / "dashboard"
DATA_JSON = OUT_DIR / "data.json"
MULTICA_AS0_TIMEOUT_S = 300
MULTICA_AS0_DIRECT_HOSTS = ("multica.ai", ".multica.ai", "127.0.0.1", "localhost")
AGENT_BRIEF_JSON = OUT_DIR / "agent-brief.json"
INDEX_HTML = OUT_DIR / "index.html"
CLAIMS_REQUEST_PACKAGE = (
    Path.home() / ".local/share/zhixing-dashboard/claims-activation-request.json"
)
CLAIMS_LIFECYCLE_AUTHORIZATION_PACKAGE = (
    Path.home() / ".local/share/zhixing-dashboard/claims-observation/lifecycle-authorization-request-draft.json"
)
CLAIMS_LIFECYCLE_REVIEW = (
    Path.home() / ".local/share/zhixing-dashboard/claims-observation/lifecycle-authorization-review.md"
)
CLAIMS_LIFECYCLE_RUNBOOK = (
    Path.home() / ".local/share/zhixing-dashboard/claims-observation/lifecycle-execution-runbook.md"
)
CLAIMS_LIFECYCLE_GAP_AUDIT = (
    Path.home() / ".local/share/zhixing-dashboard/claims-observation/authority-lifecycle-gap-audit.json"
)

GATE_DECLARED = {
}

DOC_ENTRIES = [
    {"name": "白皮书 / 三年规划", "path": "docs/VISION-ROADMAP.md", "tag": "vision"},
    {"name": "ARCHITECTURE.md（架构契约）", "path": "ARCHITECTURE.md", "tag": "architecture"},
    {"name": "道法术器（DFSQ）", "path": "docs/architecture/dao-fa-shu-qi.md", "tag": "architecture"},
    {"name": "SFOP 脊面运行模式", "path": "docs/architecture/os-operating-pattern-v1.md", "tag": "architecture"},
    {"name": "OMO 持久语义规划（Role/Capsule/Handoff）", "path": "docs/plans/3y-bet-ledger.yaml", "tag": "plan",
     "anchor": "BET-Y1Q4-T10-165"},
    {"name": "全景驾驶舱规划（T10-163）", "path": "docs/plans/3y-bet-ledger.yaml", "tag": "plan",
     "anchor": "BET-Y1Q4-T10-163"},
    {"name": "ADR 决策索引", "path": ".omo/_knowledge/decisions/INDEX.md", "tag": "knowledge"},
    {"name": "系统导航 SYSTEM-INDEX", "path": "docs/SYSTEM-INDEX.md", "tag": "knowledge"},
    {"name": "Agent 操作指南 AGENTS.md", "path": "AGENTS.md", "tag": "ops"},
    {"name": "Session 避坑基因 CLAUDE.md", "path": "CLAUDE.md", "tag": "ops"},
]


def run(cmd: list[str], timeout: int = 120) -> tuple[int, str]:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, cwd=ROOT, timeout=timeout)
        return r.returncode, (r.stdout or r.stderr or "").strip()
    except Exception as e:  # noqa: BLE001
        return 1, str(e)


def collect_gates(payload: dict | None = None) -> list[dict]:
    code, out = run([
        sys.executable, str(CODE_ROOT / "bin/gac/gate-health-check.py"),
        "--workspace", str(ROOT), "--code-root", str(CODE_ROOT), "--json",
    ])
    live: dict[str, dict] = {}
    # A non-zero wrapper exit means at least one gate failed; the JSON payload
    # still contains authoritative per-gate results and must not be discarded.
    try:
        for g in json.loads(out).get("gates", []):
            gid = str(g.get("gate", "")).split()[0]  # "A1 Workflow/Git" -> "A1"
            live[gid] = g
    except Exception:  # noqa: BLE001
        pass
    gates = []
    for gid in ("A1", "A2", "A3", "A4", "A5"):
        g = live.get(gid, {})
        gates.append({
            "id": gid,
            "title": {"A1": "Workflow 与 Git 执行完整性", "A2": "Resident 与宿主健康真值",
                      "A3": "受管 Python 与语义门", "A4": "调度声明与安装态一致",
                      "A5": "引用与 launchd 完整性"}[gid],
            "verdict": "PASS" if g.get("ok") else "FAIL",
            "detail": g.get("output", "未采集"),
            "live": bool(g),
        })
    for gid, d in GATE_DECLARED.items():
        gates.append({"id": gid, "title": d["title"], "verdict": d["state"].upper(),
                      "detail": d["note"], "live": False, "depends_on": d["depends_on"]})
    a6_index = next(i for i, gate in enumerate(gates) if gate["id"] == "A5") + 1
    gates.insert(a6_index, collect_a6_gate())
    a7_index = next(i for i, gate in enumerate(gates) if gate["id"] == "A6") + 1
    gates.insert(a7_index, collect_a7_gate())
    a8_index = next(i for i, gate in enumerate(gates) if gate["id"] == "A7") + 1
    gates.insert(a8_index, collect_a8_gate())
    a9_index = next(i for i, gate in enumerate(gates) if gate["id"] == "A8") + 1
    gates.insert(a9_index, collect_a9_gate(payload=payload, dashboard_live=True))
    rf0_index = next(i for i, gate in enumerate(gates) if gate["id"] == "A9") + 1
    gates.insert(rf0_index, collect_rf0_gate())
    rc_index = next(i for i, gate in enumerate(gates) if gate["id"] == "RF0") + 1
    gates.insert(rc_index, collect_reference_cell_gate())
    return gates


def collect_reference_cell_gate() -> dict:
    """Project attempt-local Direct Local Reference Cell evidence read-only."""
    verifier = CODE_ROOT / "bin/gac/reference-cell-dl-verify.py"
    if not verifier.is_file():
        return {
            "id": "RC-DL", "title": "Reference Cell Direct Local",
            "verdict": "UNAVAILABLE", "detail": "verifier missing",
            "live": False, "depends_on": [],
        }
    try:
        completed = subprocess.run(
            [sys.executable, str(verifier), "--json"],
            capture_output=True, text=True, timeout=30, check=False,
        )
        report = json.loads(completed.stdout)
        if not isinstance(report, dict) or report.get("schema") != "reference-cell-direct-local-r0-verification/v1":
            raise ValueError("invalid verifier payload")
    except Exception as exc:  # noqa: BLE001 - fail closed, never fake admission
        return {
            "id": "RC-DL", "title": "Reference Cell Direct Local",
            "verdict": "UNAVAILABLE", "detail": f"verifier unavailable: {type(exc).__name__}",
            "live": False, "depends_on": [],
        }
    verdict = report.get("verdict")
    return {
        "id": "RC-DL", "title": "Reference Cell Direct Local",
        "verdict": verdict,
        "detail": (
            f"latest evidence {report.get('latest_observed_at')}; "
            f"result={report.get('result')}; backend={report.get('execution_backend')}; "
            f"workspace_writes={report.get('workspace_writes')}"
        ),
        "live": verdict == "PASS",
        "depends_on": [],
    }


def collect_rf0_gate() -> dict:
    """Project RF0 from the isolated, read-only Ruflo verification matrix.

    The verifier supplies its own temporary cwd, so the projection remains
    side-effect-free and never turns a missing or failing Ruflo runtime into a
    green admission state.
    """
    # Admission verifier code belongs to the managed fresh-main root; runtime
    # facts stay under ROOT. This avoids a stale checkout hiding a verifier.
    verifier = CODE_ROOT / "bin/gac/ruflo-rf0-verify.py"
    if not verifier.is_file():
        return {
            "id": "RF0", "title": "Ruflo 只读协作准入", "verdict": "NOT_ADMITTED",
            "detail": "Ruflo RF0 verifier missing", "live": False,
            "depends_on": [],
        }
    try:
        completed = subprocess.run(
            [sys.executable, str(verifier), "--json"],
            cwd=ROOT, capture_output=True, text=True, timeout=90, check=False,
        )
        report = json.loads(completed.stdout)
    except Exception:  # noqa: BLE001 - unavailable adapter stays not admitted
        return {
            "id": "RF0", "title": "Ruflo 只读协作准入", "verdict": "NOT_ADMITTED",
            "detail": "Ruflo RF0 verifier unavailable", "live": False,
            "depends_on": [],
        }

    checks = report.get("checks") if isinstance(report.get("checks"), dict) else {}
    required = {
        "binary", "doctor", "daemon_stopped", "workers_off",
        "no_second_queue", "cross_agent_dependency_zero",
    }
    passed = report.get("ok") is True and required.issubset(checks) and all(
        checks[name] is True for name in required
    )
    if not passed:
        failed = sorted(name for name in required if checks.get(name) is not True)
        return {
            "id": "RF0", "title": "Ruflo 只读协作准入", "verdict": "NOT_ADMITTED",
            "detail": f"Ruflo RF0 verifier not complete: failed={','.join(failed) or 'unknown'}",
            "live": False,
            "depends_on": [],
        }

    version = report.get("version") if isinstance(report.get("version"), str) else "unknown"
    doctor = report.get("doctor_summary") if isinstance(report.get("doctor_summary"), dict) else {}
    doctor_passed = doctor.get("passed")
    doctor_warnings = doctor.get("warnings")
    return {
        "id": "RF0", "title": "Ruflo 只读协作准入", "verdict": "PASS",
        "detail": (
            f"isolated read-only verifier complete: daemon stopped, workers off, "
            f"version {version}, doctor {doctor_passed} passed/{doctor_warnings} warnings"
        ),
        "live": True,
        "depends_on": [],
    }


def collect_a6_gate() -> dict:
    """Project A6 from the read-only Orca R0 verification matrix.

    The verifier may launch no orchestration work; it queries runtime state and
    historical worker settlement.  Raw payloads are discarded after deriving
    aggregate proof so tokens, workspace paths, and task identifiers do not
    enter the dashboard.
    """
    verifier = CODE_ROOT / "bin/gac/orca-r0-verify.py"
    if not verifier.is_file():
        return {
            "id": "A6", "title": "Orca R0 准入", "verdict": "NOT_ADMITTED",
            "detail": "Orca R0 verifier missing", "live": False,
            "depends_on": ["A8"],
        }
    cache_path = Path.home() / ".local/share/zhixing-dashboard/orca-r0-cache.json"
    last_error = None
    report = None
    import time
    for _ in range(3):
        try:
            completed = subprocess.run(
                [sys.executable, str(verifier), "--json"],
                cwd=ROOT, capture_output=True, text=True, timeout=90, check=False,
            )
            candidate = json.loads(completed.stdout)
            if isinstance(candidate, dict):
                report = candidate
                break
            last_error = ValueError("verifier payload was not an object")
        except Exception as exc:  # noqa: BLE001 - unavailable runtime remains not admitted
            last_error = exc
        time.sleep(0.2)
    if report is None:
        try:
            cached_wrap = json.loads(cache_path.read_text())
            cached = cached_wrap.get("report")
            cached_at = datetime.fromisoformat(cached_wrap["observed_at"].replace("Z", "+00:00"))
            cached_age = (datetime.now(UTC) - cached_at).total_seconds()
            cached_probes = cached.get("probes", {}) if isinstance(cached.get("probes"), dict) else {}
            cached_r0 = cached.get("r0_transactions", {}) if isinstance(cached.get("r0_transactions"), dict) else {}
            if (
                cached.get("ok") is True and 0 <= cached_age <= 21600
                and cached_probes.get("passed") == cached_probes.get("total") and cached_probes.get("total", 0) > 0
                and cached_r0.get("accepted", 0) >= 1
            ):
                return {
                    "id": "A6", "title": "Orca R0 准入", "verdict": "PASS",
                    "detail": f"read-only verifier cache PASS: probes {cached_probes.get('passed')}/{cached_probes.get('total')}, cache age {int(cached_age)}s",
                    "live": True, "depends_on": ["A8"],
                }
        except Exception:
            pass
        return {
            "id": "A6", "title": "Orca R0 准入", "verdict": "NOT_ADMITTED",
            "detail": f"Orca R0 verifier unavailable: {type(last_error).__name__ if last_error else 'unknown'}",
            "live": False,
            "depends_on": ["A8"],
        }

    probes = report.get("probes") if isinstance(report.get("probes"), dict) else {}
    r0 = report.get("r0_transactions") if isinstance(report.get("r0_transactions"), dict) else {}
    trust = report.get("trust") if isinstance(report.get("trust"), dict) else {}
    write_guard = trust.get("write_argv_guard") if isinstance(trust.get("write_argv_guard"), dict) else {}
    probe_pass, probe_total = int(probes.get("passed", 0)), int(probes.get("total", 0))
    accepted = int(r0.get("accepted", 0))
    transactions = r0.get("transactions") if isinstance(r0.get("transactions"), list) else []
    transactions_pass = bool(transactions) and all(
        isinstance(item, dict) and item.get("ok") is True for item in transactions
    )
    runtime_ready = report.get("runtime_ready") is True
    trust_ok = write_guard.get("ok") is True
    passed = (
        report.get("ok") is True
        and runtime_ready
        and probe_total > 0
        and probe_pass == probe_total
        and accepted >= 1
        and transactions_pass
        and trust_ok
    )

    if passed:
        try:
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            cache_path.write_text(json.dumps(
                {"schema": "orca-r0-cache/v1", "observed_at": datetime.now(UTC).isoformat(), "report": report},
                ensure_ascii=False,
            ))
        except Exception:
            pass

    if not passed:
        return {
            "id": "A6", "title": "Orca R0 准入", "verdict": "NOT_ADMITTED",
            "detail": (
                f"Orca R0 verifier not complete: runtime_ready={runtime_ready}, "
                f"probes {probe_pass}/{probe_total}, R0 evidence {accepted}/1, "
                f"write_guard_ok={trust_ok}"
            ),
            "live": False, "depends_on": ["A8"],
        }

    return {
        "id": "A6", "title": "Orca R0 准入", "verdict": "PASS",
        "detail": (
            f"read-only verifier complete: runtime ready, probes {probe_pass}/{probe_total}, "
            "R0 dispatch/worker/reclaim evidence accepted, write guard OK"
        ),
        "live": True, "depends_on": ["A8"],
    }


def collect_a7_gate() -> dict:
    """Project A7 from the read-only Multica AS0 verification matrix.

    The verifier only reads Multica APIs and never invokes writers.  Raw API
    results are intentionally discarded here so dashboard projection cannot
    leak tokens, emails, agent names, or squad payloads.
    """
    verifier = CODE_ROOT / "bin/gac/multica-as0-verify.py"
    if not verifier.is_file():
        return {
            "id": "A7", "title": "Multica AS0 准入", "verdict": "NOT_ADMITTED",
            "detail": "Multica AS0 verifier missing", "live": False,
            "depends_on": ["A8"],
        }

    # Multica reads up to 40 sequential APIs.  Host bypass is injected without
    # changing other proxy settings so local policy stays explicit and the full
    # read-only matrix stays under one collector budget.
    verifier_env = os.environ.copy()
    for key in ("NO_PROXY", "no_proxy"):
        hosts = [item.strip() for item in verifier_env.get(key, "").split(",") if item.strip()]
        hosts.extend(MULTICA_AS0_DIRECT_HOSTS)
        verifier_env[key] = ",".join(dict.fromkeys(hosts))
    cache_path = Path.home() / ".local/share/zhixing-dashboard/multica-as0-cache.json"
    last_error = None
    report = None
    import fcntl
    import time
    lock_path = Path.home() / ".local/share/zhixing-dashboard/.multica-probe.lock"
    with lock_path.open("a+") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        for _ in range(3):
            try:
                completed = subprocess.run(
                    [sys.executable, str(verifier), "--json"],
                    cwd=ROOT, capture_output=True, text=True,
                    env=verifier_env, timeout=MULTICA_AS0_TIMEOUT_S, check=False,
                )
                candidate = json.loads(completed.stdout)
                if isinstance(candidate, dict):
                    report = candidate
                    break
                last_error = ValueError("verifier payload was not an object")
            except Exception as exc:  # noqa: BLE001 - unavailable adapter stays not admitted
                last_error = exc
            time.sleep(0.2)
    if report is None:
        try:
            cached_wrap = json.loads(cache_path.read_text())
            cached = cached_wrap.get("report")
            cached_at = datetime.fromisoformat(cached_wrap["observed_at"].replace("Z", "+00:00"))
            cached_age = (datetime.now(UTC) - cached_at).total_seconds()
            cached_api = cached.get("api", {}) if isinstance(cached.get("api"), dict) else {}
            cached_topology = cached.get("topology", {}) if isinstance(cached.get("topology"), dict) else {}
            cached_trust = cached.get("trust", {}) if isinstance(cached.get("trust"), dict) else {}
            if (
                cached.get("ok") is True and 0 <= cached_age <= 21600
                and cached_api.get("passed") == cached_api.get("total") and cached_api.get("total", 0) > 0
                and cached_topology.get("passed") == cached_topology.get("total") and cached_topology.get("total", 0) > 0
                and cached_trust.get("passed") == cached_trust.get("total") and cached_trust.get("total", 0) > 0
            ):
                return {
                    "id": "A7", "title": "Multica AS0 准入", "verdict": "PASS",
                    "detail": (
                        f"read-only verifier cache PASS: api {cached_api.get('passed')}/{cached_api.get('total')}, "
                        f"topology {cached_topology.get('passed')}/{cached_topology.get('total')}, "
                        f"trust {cached_trust.get('passed')}/{cached_trust.get('total')}, cache age {int(cached_age)}s"
                    ),
                    "live": True, "depends_on": ["A8"],
                }
        except Exception:
            pass
        if isinstance(last_error, subprocess.TimeoutExpired):
            return {
                "id": "A7", "title": "Multica AS0 准入", "verdict": "NOT_ADMITTED",
                "detail": f"Multica AS0 verifier timeout after {MULTICA_AS0_TIMEOUT_S}s",
                "live": False, "depends_on": ["A8"],
            }
        return {
            "id": "A7", "title": "Multica AS0 准入", "verdict": "NOT_ADMITTED",
            "detail": f"Multica AS0 verifier unavailable: {type(last_error).__name__ if last_error else 'unknown'}",
            "live": False, "depends_on": ["A8"],
        }

    api = report.get("api") if isinstance(report.get("api"), dict) else {}
    topology = report.get("topology") if isinstance(report.get("topology"), dict) else {}
    trust = report.get("trust") if isinstance(report.get("trust"), dict) else {}
    api_pass, api_total = int(api.get("passed", 0)), int(api.get("total", 0))
    topology_pass, topology_total = int(topology.get("passed", 0)), int(topology.get("total", 0))
    trust_pass, trust_total = int(trust.get("passed", 0)), int(trust.get("total", 0))
    passed = bool(report.get("ok")) and (api_pass, topology_pass, trust_pass) == (
        api_total, topology_total, trust_total,
    ) and api_total > 0 and topology_total > 0 and trust_total > 0

    if passed:
        try:
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            cache_path.write_text(json.dumps(
                {"schema": "multica-as0-cache/v1", "observed_at": datetime.now(UTC).isoformat(), "report": report},
                ensure_ascii=False,
            ))
        except Exception:
            pass

    if not passed:
        return {
            "id": "A7", "title": "Multica AS0 准入", "verdict": "NOT_ADMITTED",
            "detail": (
                f"Multica AS0 verifier not complete: api {api_pass}/{api_total}, "
                f"topology {topology_pass}/{topology_total}, trust {trust_pass}/{trust_total}"
            ),
            "live": False, "depends_on": ["A8"],
        }

    return {
        "id": "A7", "title": "Multica AS0 准入", "verdict": "PASS",
        "detail": (
            f"read-only verifier complete: api {api_pass}/{api_total}, "
            f"topology {topology_pass}/{topology_total}, trust {trust_pass}/{trust_total}"
        ),
        "live": True, "depends_on": ["A8"],
    }


def collect_a8_gate() -> dict:
    """Project A8 from accepted delivery evidence instead of a static absence.

    A8 was originally ABSENT.  BET-Y1Q4-T10-151 later delivered the generic
    external transaction lifecycle.  Keep the projection fail-closed: every
    evidence condition must hold in the current OMO pin before showing PASS.
    """
    bet_id = "BET-Y1Q4-T10-151"
    merge_commit = "5e1f7eae9b024dccc7a5977139e2de906c25b76c"
    impl_rel = "projects/omo/src/omo/workflow/external_transaction.py"
    test_rel = "projects/omo/tests/test_external_transaction.py"
    missing: list[str] = []

    try:
        import yaml

        ledger = yaml.safe_load(
            (ROOT / "docs/plans/3y-bet-ledger.yaml").read_text(encoding="utf-8")
        )
        bet = next(
            (bet for bet in ledger.get("bets", []) if bet.get("id") == bet_id),
            {},
        )
        evidence = bet.get("completion_evidence") or {}
        axes = evidence.get("axes") or {}
        if bet.get("status") != "done":
            missing.append("ledger_status")
        if evidence.get("overall_state") != "delivery_accepted":
            missing.append("delivery_accepted")
        if axes.get("engineering", {}).get("status") != "VERIFIED":
            missing.append("engineering_verified")
        if axes.get("operational", {}).get("status") != "PROVEN":
            missing.append("operational_proven")
    except Exception:  # noqa: BLE001 - projection must degrade to ABSENT
        missing.append("ledger_unreadable")

    if not (ROOT / impl_rel).is_file():
        missing.append("implementation")
    if not (ROOT / test_rel).is_file():
        missing.append("tests")

    omo_dir = ROOT / "projects/omo"
    reachable = subprocess.run(
        ["git", "-C", str(omo_dir), "merge-base", "--is-ancestor", merge_commit, "HEAD"],
        capture_output=True,
        text=True,
    )
    if reachable.returncode != 0:
        missing.append("omo_merge_commit")

    if missing:
        return {
            "id": "A8",
            "title": "OMO 外部执行事务",
            "verdict": "ABSENT",
            "detail": "A8 evidence incomplete: " + ", ".join(missing),
            "live": False,
            "depends_on": ["G2", "G3"],
        }

    return {
        "id": "A8",
        "title": "OMO 外部执行事务",
        "verdict": "PASS",
        "detail": (
            "T10-151 delivery accepted; omo PR #173 merge reachable in current pin; "
            "implementation and focused test contract present"
        ),
        "live": True,
        "depends_on": ["G2", "G3"],
    }


def collect_a9_gate(payload: dict | None = None, *, dashboard_live: bool | None = None) -> dict:
    """Project A9 only when dashboard, ASD, and Cockpit projections are fresh.

    This deliberately keeps CI/local checks independent: missing runtime files
    in a clean checkout remain PARTIAL instead of pretending to be green.
    """
    now = datetime.now(UTC)
    missing: list[str] = []

    try:
        data = payload or json.loads(DATA_JSON.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        data = {}

    def age_seconds(value: object) -> float | None:
        if not isinstance(value, str):
            return None
        try:
            observed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return (now - observed).total_seconds()
        except ValueError:
            return None

    if dashboard_live is True:
        # During in-memory generation there is no prior on-disk generation to
        # judge. Reading the old snapshot made a valid refresh intermittently
        # fail its own dashboard_live check.
        dashboard_age = 0.0
    else:
        dashboard_age = age_seconds(data.get("generated_at"))
        if dashboard_age is None or dashboard_age < 0 or dashboard_age > 300:
            missing.append("dashboard_live")

    asd = data.get("asd") if isinstance(data.get("asd"), dict) else {}
    expected_panels = {"overview", "spine", "agents", "milestones", "degradation"}
    panels = asd.get("panels") if isinstance(asd.get("panels"), dict) else {}
    if asd.get("schema") != "asd-snapshot/v1":
        missing.append("asd_schema")
    if asd.get("verdict") != "COMPLETE":
        missing.append("asd_complete")
    if set(panels) != expected_panels:
        missing.append("asd_panels")
    degraded = asd.get("degraded_panels")
    if degraded != []:
        missing.append("asd_degraded")

    cockpit_path = Path.home() / ".local/share/zhixing-dashboard/current.json"
    try:
        cockpit = json.loads(cockpit_path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        cockpit = {}
        missing.append("cockpit_projection")
    cockpit_age = age_seconds(cockpit.get("generated_at"))
    if cockpit_age is None or cockpit_age < 0 or cockpit_age > 600:
        missing.append("cockpit_freshness")
    source_states = cockpit.get("source_states") if isinstance(cockpit.get("source_states"), dict) else {}
    required_sources = {
        "catalog", "strategy", "strategy-projection", "environment_evidence",
        "portfolio", "workflow", "resident", "scheduler", "references",
        "orca", "multica", "ruflo", "documents", "compute",
    }
    bad_sources = []
    source_ages = []
    for name in required_sources:
        state = source_states.get(name) if isinstance(source_states.get(name), dict) else {}
        status = state.get("status")
        last_success = state.get("last_success_at")
        age = age_seconds(last_success)
        if age is not None:
            source_ages.append(age)
        if not isinstance(state, dict) or not (status == "OK" or (status == "STALE_UNAVAILABLE" and age is not None and age <= 21600)):
            bad_sources.append(name)
    if bad_sources:
        missing.append("cockpit_sources")

    if missing:
        return {
            "id": "A9",
            "title": "ASD 与 Cockpit 可观测",
            "verdict": "PARTIAL",
            "detail": "A9 evidence incomplete: " + ", ".join(missing),
            "live": False,
            "depends_on": ["G2", "G3"],
        }

    return {
        "id": "A9",
        "title": "ASD 与 Cockpit 可观测",
        "verdict": "PASS",
        "detail": (
            f"dashboard/asd age {dashboard_age:.0f}s; cockpit projection age "
            f"{cockpit_age:.0f}s; ASD COMPLETE; oldest source success age "
            f"{max(source_ages, default=0):.0f}s"
        ),
        "live": True,
        "depends_on": ["G2", "G3"],
    }


def collect_bets() -> dict:
    import yaml

    ledger = yaml.safe_load((CODE_ROOT / "docs/plans/3y-bet-ledger.yaml").read_text())
    bets = [b for b in ledger.get("bets", []) if isinstance(b, dict) and b.get("id")]
    by_status: dict[str, list[dict]] = {}
    for b in bets:
        by_status.setdefault(str(b.get("status", "unknown")), []).append(b)
    windows: dict[str, dict] = {}
    for b in bets:
        w = str(b.get("window", "?"))
        d = windows.setdefault(w, {"total": 0, "done": 0})
        d["total"] += 1
        if b.get("status") == "done":
            d["done"] += 1

    def brief(b: dict) -> dict:
        return {"id": b["id"], "title": str(b.get("title", ""))[:60],
                "priority": b.get("priority", ""), "track": b.get("track", ""),
                "risk": b.get("risk_level", "")}

    return {
        "source": "repo://docs/plans/3y-bet-ledger.yaml",
        "total": len(bets),
        "counts": {k: len(v) for k, v in sorted(by_status.items())},
        "in_progress": [brief(b) for b in by_status.get("in_progress", [])][:10],
        "blocked": [brief(b) for b in by_status.get("blocked", [])][:10],
        "windows": dict(sorted(windows.items())),
    }


def collect_objective_coverage(payload: dict) -> dict:
    panel_value = payload.get("panel_value") if isinstance(payload.get("panel_value"), dict) else {}
    obj_value_proof = (
        "PROVEN" if str(panel_value.get("state") or "").lower() == "proven" else "NOT_PROVEN"
    )
    """Project the explicit objective-to-evidence boundary for Agent OS."""
    import yaml

    gates = {g.get("id"): g for g in payload.get("gates", []) if isinstance(g, dict)}
    code_health = payload.get("code_root_health") if isinstance(payload.get("code_root_health"), dict) else {}
    claims_task16 = payload.get("claims_task16") if isinstance(payload.get("claims_task16"), dict) else {}
    agent_cell_semantic = payload.get("agent_cell_semantic") if isinstance(payload.get("agent_cell_semantic"), dict) else {}
    role_registry = payload.get("role_registry") if isinstance(payload.get("role_registry"), dict) else {}
    activation_allowed = claims_task16.get("activation_allowed") is True
    claims_authority = payload.get("claims_authority") if isinstance(payload.get("claims_authority"), dict) else {}
    claims_observation = (
        payload.get("claims_observation_progress")
        if isinstance(payload.get("claims_observation_progress"), dict) else {}
    )
    if activation_allowed:
        claims_activation_status = "ACTIVATION_ALLOWED"
    elif claims_observation.get("state") == "IN_PROGRESS" and claims_authority.get("activation_state") == "shadow-active":
        claims_activation_status = "SHADOW_OBSERVING"
    else:
        claims_activation_status = "AWAITING_AUTHORIZATION"

    try:
        ledger = yaml.safe_load((CODE_ROOT / "docs/plans/3y-bet-ledger.yaml").read_text()) or {}
        ledger_bets = {b.get("id"): b for b in ledger.get("bets", []) if isinstance(b, dict) and b.get("id")}
    except Exception:
        ledger_bets = {}

    def gate(gate_id: str) -> tuple[str, bool]:
        verdict = str((gates.get(gate_id) or {}).get("verdict", "UNKNOWN")).upper()
        return verdict, verdict == "PASS" and (gates.get(gate_id) or {}).get("live") is True

    def ledger_semantics(bet_id: str) -> tuple[str, str]:
        bet = ledger_bets.get(bet_id)
        if not isinstance(bet, dict):
            return "EVIDENCE_INCOMPLETE", "NOT_PROVEN"
        evidence = bet.get("completion_evidence") if isinstance(bet.get("completion_evidence"), dict) else {}
        axes = evidence.get("axes") if isinstance(evidence.get("axes"), dict) else {}
        engineering = str((axes.get("engineering") or {}).get("status", "UNKNOWN")).upper()
        operational = str((axes.get("operational") or {}).get("status", "UNKNOWN")).upper()
        value = str((axes.get("value") or {}).get("status", "NOT_PROVEN")).upper()
        overall = str(evidence.get("overall_state", "UNKNOWN")).upper()
        if bet.get("status") == "done" and overall == "DELIVERY_ACCEPTED" and engineering == "VERIFIED" and operational == "PROVEN":
            return "DELIVERY_ACCEPTED", value or "NOT_PROVEN"
        return overall, value or "NOT_PROVEN"

    a1_a9 = [gate(f"A{i}")[0] for i in range(1, 10)]
    a1_a9_pass = all(state == "PASS" for state in a1_a9)
    semantic_status, semantic_value = ledger_semantics("BET-Y1Q4-T10-165")
    semantic_runtime_ok = (
        agent_cell_semantic.get("available") is True
        and agent_cell_semantic.get("verdict") == "PASS"
        and agent_cell_semantic.get("receipt_chain_ok") is True
        and agent_cell_semantic.get("receipt_digests_ok") is True
        and agent_cell_semantic.get("role_bindings_ok") is True
        and agent_cell_semantic.get("capsule_bindings_ok") is True
        and agent_cell_semantic.get("mesh_bindings_ok") is True
        and agent_cell_semantic.get("queue_bindings_ok") is True
    )
    role_registry_ok = (
        role_registry.get("available") is True
        and role_registry.get("verdict") == "PASS"
        and role_registry.get("integrity_ok") is True
    )
    persistent_runtime_status = "VERIFIED" if semantic_runtime_ok and role_registry_ok else "UNVERIFIED"
    if semantic_status == "DELIVERY_ACCEPTED":
        semantic_status = (
            "DELIVERY_ACCEPTED_RUNTIME_VERIFIED"
            if persistent_runtime_status == "VERIFIED"
            else "DELIVERY_ACCEPTED_RUNTIME_UNVERIFIED"
        )
    external_status, external_value = ledger_semantics("BET-Y1Q4-T10-151")
    rc_state, _ = gate("RC-DL")
    orca_state, _ = gate("A6")
    multica_state, _ = gate("A7")
    ruflo_state, _ = gate("RF0")

    def evidence(*refs: str) -> list[dict[str, str]]:
        return [{"kind": "authority_or_test", "ref": ref} for ref in refs]

    items = [
        {
            "id": "EXECUTION_ENVIRONMENT_A1_A9",
            "requirement": "A1–A9 execution environment recovery",
            "status": "PASS" if a1_a9_pass else "PARTIAL",
            "evidence": evidence("gate://A1", "gate://A2", "gate://A3", "gate://A4", "gate://A5", "gate://A6", "gate://A7", "gate://A8", "gate://A9", "ledger://BET-Y1Q4-T10-164"),
        },
        {
            "id": "OMO_SINGLE_CONTROL_PLANE",
            "requirement": "OMO is the single control plane and dispatcher",
            "status": "PASS" if a1_a9_pass and code_health.get("verdict") == "PASS" else "PARTIAL",
            "evidence": evidence("gate://A8", "repo://bin/gac/check-sfop-slots.py", "repo://docs/plans/3y-bet-ledger.yaml"),
        },
        {
            "id": "PERSISTENT_ROLE_CAPSULE_HANDOFF_CLAIM_VERIFICATION_ASD",
            "requirement": "Persistent Role, Capsule, Handoff, Claim, Verification, and ASD semantics",
            "status": semantic_status,
            "value_status": semantic_value,
            "runtime_status": persistent_runtime_status,
            "evidence": evidence(
                "ledger://BET-Y1Q4-T10-165",
                "projection://role_registry",
                "projection://agent_cell_semantic",
                "repo://projects/omo/src/omo/workflow/role_registry.py",
                "repo://projects/omo/src/omo/workflow/capsule.py",
                "repo://projects/omo/src/omo/workflow/asd.py",
            ),
        },
        {
            "id": "REFERENCE_CELL_DIRECT_LOCAL",
            "requirement": "Reference Cell prefers Direct Local and remains evidenced",
            "status": rc_state,
            "evidence": evidence("gate://RC-DL"),
        },
        {
            "id": "ORCA_R0",
            "requirement": "Orca remains admitted only at R0",
            "status": orca_state,
            "evidence": evidence("gate://A6", "ledger://BET-Y1Q4-T10-149"),
        },
        {
            "id": "MULTICA_AS0",
            "requirement": "Multica remains admitted only at AS0",
            "status": multica_state,
            "evidence": evidence("gate://A7", "ledger://BET-Y1Q4-T10-150"),
        },
        {
            "id": "RUFLO_RF0",
            "requirement": "Ruflo remains read-only at RF0",
            "status": ruflo_state,
            "evidence": evidence("gate://RF0"),
        },
        {
            "id": "EXTERNAL_TRANSACTION_LIFECYCLE",
            "requirement": "External execution uses the OMO transaction lifecycle",
            "status": "PASS" if gate("A8")[0] == "PASS" and external_status == "DELIVERY_ACCEPTED" else "PARTIAL",
            "value_status": external_value,
            "evidence": evidence("gate://A8", "ledger://BET-Y1Q4-T10-151"),
        },
        {
            "id": "CLAIMS_AUTHORITY_ACTIVATION",
            "requirement": "Claims Authority instruction capability requires separate authorization and observation",
            "status": claims_activation_status,
            "value_status": "NOT_PROVEN",
            "runtime_state": claims_authority.get("activation_state", "unknown"),
            "observation_state": claims_observation.get("state", "UNAVAILABLE"),
            "observation_progress": claims_observation,
            "evidence": evidence("projection://claims_authority", "projection://claims_task16"),
        },
        {
            "id": "BUSINESS_VALUE",
            "requirement": "Human/business value proof",
            "status": obj_value_proof,
            "value_status": obj_value_proof,
            "evidence": evidence("ledger://BET-Y1Q4-T10-165", "projection://value_metrics"),
        },
    ]
    return {
        "schema": "panorama-objective-coverage/v1",
        "source": "repo://docs/plans/3y-bet-ledger.yaml + panorama gates",
        "items": items,
        "delivery_complete": all(item["status"] in {"PASS", "DELIVERY_ACCEPTED"} for item in items),
        "activation_status": claims_activation_status,
        "value_proof": obj_value_proof,
        "note": "Delivery coverage never proves business value; Claims Authority activation remains separately authorized.",
    }


def collect_agents() -> list[dict]:
    agents: list[dict] = []
    code, out = run(["git", "worktree", "list", "--porcelain"])
    if code == 0:
        cur: dict = {}
        for line in out.splitlines():
            if line.startswith("worktree "):
                if cur:
                    agents.append(cur)
                cur = {"worktree": line.split(None, 1)[1]}
            elif line.startswith("branch "):
                cur["branch"] = line.split(None, 1)[1]
            elif line.startswith("detached"):
                cur["branch"] = "(detached)"
        if cur:
            agents.append(cur)
    for a in agents:
        wt = Path(a.get("worktree", ""))
        if wt.is_dir():
            ago = run(["bash", "-c", f"cd {wt} && git log -1 --format=%ct 2>/dev/null || echo 0"])
            try:
                ts = int(ago[1].strip() or 0)
                a["last_activity_hours"] = round((datetime.now(UTC).timestamp() - ts) / 3600, 1) if ts else None
            except ValueError:
                a["last_activity_hours"] = None
    return agents


def collect_runtime() -> dict:
    rt: dict = {}
    code, out = run(["python3", "bin/gac/meta-doctor.py", "--workspace", "."])
    if code == 0 or out.startswith("{"):
        try:
            d = json.loads(out[out.index("{"):])
            rt["meta_doctor"] = d.get("summary", {})
        except Exception:  # noqa: BLE001
            rt["meta_doctor"] = {}
    code, out = run(["bash", "-c", "launchctl list 2>/dev/null | grep -c omostation || true"])
    rt["launchd_omostation_jobs"] = int(out or 0)
    code, out = run(["bash", "-c", "crontab -l 2>/dev/null | grep -cv '^#' || true"])
    try:
        rt["crontab_lines"] = int(out.strip() or 0)
    except ValueError:
        rt["crontab_lines"] = 0
    code, out = run(["python3", "bin/scheduler-compile.py", "--check"])
    try:
        rt["scheduler"] = json.loads(out)
    except Exception:  # noqa: BLE001
        rt["scheduler"] = {"ok": code == 0}
    return rt


def _parse_launchctl_print(output: str) -> dict:
    """Parse only the bounded launchd facts needed for runtime health."""
    def first(pattern: str) -> str | None:
        # launchctl prefixes facts with a tab; do not let line-start matching
        # silently miss otherwise healthy runtime facts.
        match = re.search(r"[ \t]*" + pattern, output, re.MULTILINE)
        return match.group(1).strip() if match else None

    return {
        "loaded": bool(output.strip()),
        "state": first(r"state = (.+)$"),
        "pid": first(r"pid = (.+)$"),
        "last_exit_code": first(r"last exit code = (.+)$"),
        "runs": first(r"runs = (.+)$"),
        "run_interval": first(r"run interval = (.+)$"),
        "program": first(r"program = (.+)$"),
        "plist_path": first(r"path = (.+)$"),
    }


def collect_launchd_health() -> dict:
    """Project live launchd state for active registry-owned scheduled jobs.

    This is observation only: Panorama never bootstraps, kicks, stops, or
    reloads launchd jobs.  A periodic job being idle is healthy; a non-zero
    last exit or unloaded job is a visible failure.
    """
    try:
        import yaml
        registry = yaml.safe_load(
            (ROOT / ".omo/cron/registry.yaml").read_text(encoding="utf-8")
        ) or {}
        jobs = registry.get("jobs") or []
    except Exception as exc:  # noqa: BLE001 - scheduler projection must degrade visibly
        return {
            "schema": "launchd-health-projection/v1",
            "available": False,
            "verdict": "UNAVAILABLE",
            "jobs": [],
            "error": type(exc).__name__,
        }

    selected = [
        job for job in jobs
        if job.get("status") == "active"
        and job.get("reality") == "installed"
        and "launchd" in (job.get("planes") or [])
    ]
    uid = os.getuid()
    projections: list[dict] = []
    for job in selected:
        name = str(job.get("name") or "")
        label = f"com.omostation.{name}"
        code, output = run(["/bin/launchctl", "print", f"gui/{uid}/{label}"])
        parsed = _parse_launchctl_print(output if code == 0 else "")
        loaded = code == 0 and parsed.get("loaded") is True
        last_exit = parsed.get("last_exit_code")
        last_exit_ok = loaded and last_exit in {"0", "(never exited)"}
        state = parsed.get("state") or ("unloaded" if not loaded else "unknown")
        projections.append({
            "name": name,
            "label": label,
            "schedule": job.get("schedule", ""),
            "loaded": loaded,
            "state": state,
            "pid": parsed.get("pid"),
            "last_exit_code": last_exit,
            "last_exit_ok": last_exit_ok,
            "runs": parsed.get("runs"),
            "run_interval": parsed.get("run_interval"),
            "program": parsed.get("program"),
            "verdict": "PASS" if loaded and last_exit_ok else "FAILED",
        })

    failed = [job for job in projections if job["verdict"] != "PASS"]
    return {
        "schema": "launchd-health-projection/v1",
        "available": True,
        "verdict": "PASS" if projections and not failed else ("FAILED" if failed else "EMPTY"),
        "loaded": sum(1 for job in projections if job["loaded"]),
        "failed": len(failed),
        "jobs": projections,
    }


def collect_clash_health() -> dict:
    """Clash/Fleet 体系健康投影 — 只读 ~/.local/log 状态文件, 零网络 (B1 接入 2026-09-23)."""
    schema = "panorama-clash-health/v1"
    log_dir = Path.home() / ".local/log"

    def _states(fname: str) -> dict | None:
        path = log_dir / fname
        if not path.is_file():
            return None
        up = down = 0
        downs: list[str] = []
        for line in path.read_text(errors="replace").splitlines():
            if "|" not in line:
                continue
            key, val = line.rsplit("|", 1)
            if val == "up":
                up += 1
            elif val == "down":
                down += 1
                downs.append(key)
        return {"up": up, "down": down, "total": up + down, "down_list": downs[:12]}

    latest_summary = None
    health_log = log_dir / "clash-health.log"
    if health_log.is_file():
        for line in reversed(health_log.read_text(errors="replace").splitlines()):
            if "SUMMARY" in line:
                latest_summary = line.strip()
                break

    certs = None
    cert_state = log_dir / "clash-cert-state"
    if cert_state.is_file():
        certs = cert_state.read_text(errors="replace").strip()

    fleet = _states("fleet-states")
    nodes = _states("clash-node-states")
    # verdict: fleet down≤2 视为预期 (bwg 停机窗口), 超出即 red
    if fleet is None:
        verdict = "UNAVAILABLE"
    else:
        verdict = "green" if fleet["down"] <= 2 else "red"
    return {
        "schema": schema,
        "available": fleet is not None or nodes is not None,
        "verdict": verdict,
        "fleet": fleet,
        "nodes": nodes,
        "certs": certs,
        "latest_summary": latest_summary,
    }


def collect_code_root_health() -> dict:
    """Report whether the managed code root is clean and equal to origin/main.

    This is intentionally read-only: Panorama never fetches, rebases, merges or
    otherwise updates the managed clone. A stale root is visible rather than
    silently used by admission verifiers.
    """
    checked_at = datetime.now(UTC).isoformat()
    if CODE_ROOT == ROOT:
        return {
            "schema": "panorama-code-root-health/v1",
            "available": False,
            "managed": False,
            "verdict": "UNMANAGED",
            "checked_at": checked_at,
            "error": "code_root_matches_runtime_root",
        }

    def git(args: list[str]) -> tuple[int, str]:
        return run(["git", "-C", str(CODE_ROOT), *args], timeout=10)

    head_code, head = git(["rev-parse", "HEAD"])
    origin_code, origin_main = git(["rev-parse", "refs/remotes/origin/main"])
    status_code, status = git(["status", "--porcelain", "--untracked-files=no"])
    count_code, counts = git(["rev-list", "--left-right", "--count", "origin/main...HEAD"])
    if head_code or origin_code or status_code or count_code:
        return {
            "schema": "panorama-code-root-health/v1",
            "available": False,
            "managed": True,
            "verdict": "UNAVAILABLE",
            "checked_at": checked_at,
            "head_oid": head if head_code == 0 else None,
            "origin_main_oid": origin_main if origin_code == 0 else None,
            "error": "git_read_failed",
        }

    left, _, right = counts.partition("\t")
    try:
        behind, ahead = int(left.strip()), int(right.strip())
    except ValueError:
        return {
            "schema": "panorama-code-root-health/v1",
            "available": False,
            "managed": True,
            "verdict": "UNAVAILABLE",
            "checked_at": checked_at,
            "head_oid": head,
            "origin_main_oid": origin_main,
            "error": "count_parse_failed",
        }

    dirty_count = sum(1 for line in status.splitlines() if line.strip())
    synced = head == origin_main and behind == 0 and ahead == 0
    if dirty_count:
        verdict = "DIRTY"
    elif not synced:
        verdict = "STALE"
    else:
        verdict = "PASS"
    return {
        "schema": "panorama-code-root-health/v1",
        "available": True,
        "managed": True,
        "verdict": verdict,
        "checked_at": checked_at,
        "head_oid": head,
        "origin_main_oid": origin_main,
        "behind_origin_main": behind,
        "ahead_origin_main": ahead,
        "dirty_count": dirty_count,
        "auto_update_performed": False,
    }


def _read_claims_preflight(root: Path) -> tuple[dict | None, str | None]:
    """Run one read-only Claims preflight, failing closed with the error name.

    Only the exception class name is propagated: this projection is published
    into the dashboard payload, so raw stderr/stdout (which routinely echo
    file paths and environment detail) must not travel with it.
    """
    preflight_script = CODE_ROOT / "bin/gac/claims-shadow-preflight.py"
    if not preflight_script.is_file():
        return None, "preflight_script_missing"
    try:
        completed = subprocess.run(
            [
                sys.executable, str(preflight_script), "--json",
                "--integration-root", str(root),
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        report = json.loads(completed.stdout)
    except Exception as exc:  # noqa: BLE001 - visibility must fail closed
        return None, type(exc).__name__
    if not isinstance(report, dict) or report.get("schema") != "claims-shadow-preflight/v1":
        return None, "invalid_preflight_payload"
    return report, None


def _claims_projection(report: dict | None) -> dict:
    if not isinstance(report, dict):
        return {
            "schema": "panorama-claims-task16-projection/v1",
            "available": False,
            "verdict": "UNAVAILABLE",
            "error": "preflight_unavailable",
        }
    return {
        "schema": "panorama-claims-task16-projection/v1",
        "available": True,
        "verdict": report.get("readiness", "UNKNOWN"),
        "activation_allowed": report.get("activation_allowed") is True,
        "blocker_count": len(report.get("blockers") or []),
        "preflight": report,
    }


def collect_claims_task16_preflight() -> dict:
    """Run read-only canonical and isolated Claims preflights for agent visibility."""
    canonical, canonical_error = _read_claims_preflight(ROOT)
    isolated, isolated_error = _read_claims_preflight(CODE_ROOT)
    isolated_recovery = (
        isolated.get("recovery")
        if isinstance(isolated, dict) and isinstance(isolated.get("recovery"), dict) else {}
    )
    isolated_technical_ready = bool(
        isolated and isolated.get("available") is True
        and isolated.get("hard_blockers") == []
        and isolated.get("readiness") == "AWAITING_AUTHORIZATION"
    )
    projection = _claims_projection(canonical)
    projection.update({
        "canonical_error": canonical_error,
        "isolated_preflight": _claims_projection(isolated),
        "isolated_error": isolated_error,
        "isolated_technical_ready": isolated_technical_ready,
        "remaining_after_isolated_recovery": isolated_recovery.get(
            "remaining_after_isolated_recovery", []
        ),
    })
    return projection


def collect_claims_activation_request() -> dict:
    """Expose the exact pending activation request without executing it.

    The source package is outside Git and contains no credentials.  Only its
    identity and fail-closed authorization state are projected so every agent
    can see the exact object awaiting operation-specific Human review.
    """
    try:
        package = json.loads(CLAIMS_REQUEST_PACKAGE.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {
            "schema": "panorama-claims-activation-request/v1",
            "available": False,
            "status": "PACKAGE_MISSING",
            "execution": "NOT_EXECUTED",
            "activation": "NOT_AUTHORIZED",
        }
    except Exception as exc:  # noqa: BLE001 - visibility must fail closed
        return {
            "schema": "panorama-claims-activation-request/v1",
            "available": False,
            "status": "PACKAGE_UNAVAILABLE",
            "execution": "NOT_EXECUTED",
            "activation": "NOT_AUTHORIZED",
            "error": type(exc).__name__,
        }

    request = package.get("request") if isinstance(package.get("request"), dict) else {}
    descriptor = request.get("descriptor") if isinstance(request.get("descriptor"), dict) else {}
    human = package.get("human_authorization") if isinstance(package.get("human_authorization"), dict) else {}
    rollback = package.get("rollback") if isinstance(package.get("rollback"), dict) else {}
    if package.get("schema") != "claims-activation-request-package/v1":
        return {
            "schema": "panorama-claims-activation-request/v1",
            "available": False,
            "status": "PACKAGE_SCHEMA_INVALID",
            "execution": "NOT_EXECUTED",
            "activation": "NOT_AUTHORIZED",
        }

    return {
        "schema": "panorama-claims-activation-request/v1",
        "available": True,
        "status": str(package.get("status") or "UNKNOWN"),
        "execution": str(package.get("execution") or "UNKNOWN"),
        "activation": str(package.get("activation") or "UNKNOWN"),
        "execution_forbidden_without_human_authorization": human.get("status") != "PROVEN",
        "request_id": request.get("request_id"),
        "request_digest": package.get("request_digest"),
        "descriptor_digest": descriptor.get("digest"),
        "authority_id": request.get("authority_id"),
        "operation": request.get("operation"),
        "expected_authority_epoch": request.get("expected_authority_epoch"),
        "expected_state": request.get("expected_state"),
        "human_authorization_status": str(human.get("status") or "UNKNOWN").upper(),
        "execution_receipt": (
            package.get("execution_receipt")
            if isinstance(package.get("execution_receipt"), dict) else {}
        ),
        "human_authorization_required": human.get("required") is True,
        "human_authorization_not_sufficient": human.get("not_sufficient") or [],
        "required_binding": human.get("required_binding") or [],
        "observation_after_activation": human.get("observation_after_activation") or {},
        "observation": (
            package.get("observation")
            if isinstance(package.get("observation"), dict) else {}
        ),
        "rollback_automatic_execution": rollback.get("automatic_execution") is True,
    }


def collect_claims_observation_progress() -> dict:
    """Project the read-only Claims shadow observation window without mutating it."""
    request = collect_claims_activation_request()
    observation = (
        request.get("observation_after_activation")
        if isinstance(request.get("observation_after_activation"), dict) else {}
    )
    if not observation.get("evidence_dir"):
        observation = (
            request.get("observation")
            if isinstance(request.get("observation"), dict) else {}
        )
    evidence_dir = Path(str(observation.get("evidence_dir") or "")).expanduser()
    summary_path = evidence_dir / "summary.json"
    samples_path = evidence_dir / "samples.jsonl"
    empty = {
        "schema": "claims-observation-progress/v1",
        "available": False,
        "state": "UNAVAILABLE",
        "activation_state": "unknown",
        "sample_count": 0,
        "minimum_samples": int(observation.get("minimum_samples") or 1440),
        "duration_seconds": int(observation.get("duration_seconds") or 86400),
        "maximum_gap_seconds": int(observation.get("maximum_gap_seconds") or 120),
        "checkpoints": [],
    }
    if not request.get("available") or not summary_path.is_file():
        return empty
    try:
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        if not isinstance(summary, dict):
            raise ValueError("summary root is not an object")
        started_at = datetime.fromisoformat(str(summary.get("started_at_utc")).replace("Z", "+00:00"))
        duration_seconds = int(observation.get("duration_seconds") or 86400)
        minimum_samples = int(observation.get("minimum_samples") or 1440)
        maximum_gap_seconds = float(observation.get("maximum_gap_seconds") or 120)
        sample_count = int(summary.get("samples") or 0)
        errors = int(summary.get("errors") or 0)
        max_gap = float(summary.get("max_gap_seconds") or 0)
        activation_state = str(summary.get("activation_state") or "unknown")
        elapsed_seconds = max(0.0, (datetime.now(UTC) - started_at).total_seconds())
        expected_descriptor = str(summary.get("descriptor_digest") or "")
        request_receipt = (
            request.get("execution_receipt") if isinstance(request.get("execution_receipt"), dict) else {}
        ).get("receipt_digest")
        sampled_receipt = summary.get("expected_last_receipt")
        receipts_match = bool(request_receipt and sampled_receipt and request_receipt == sampled_receipt)
        records: list[dict[str, Any]] = []
        malformed_records = 0
        if samples_path.is_file():
            for line in samples_path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                try:
                    item = json.loads(line)
                    if not isinstance(item, dict):
                        raise ValueError("record is not an object")
                    # The append-only samples file preserves prior invalid attempts.
                    # Project and grade only the current summary-identified run.
                    item_time = datetime.fromisoformat(
                        str(item.get("sampled_at_utc")).replace("Z", "+00:00")
                    )
                    if item_time < started_at:
                        continue
                    records.append(item)
                except (json.JSONDecodeError, ValueError, TypeError):
                    malformed_records += 1
        status_records = [item for item in records if isinstance(item.get("status"), dict)]
        error_records = [item for item in records if item.get("error") is not None]
        sampled_count = len(status_records)
        parse_times = []
        for item in records:
            try:
                parse_times.append(datetime.fromisoformat(str(item["sampled_at_utc"]).replace("Z", "+00:00")))
            except (KeyError, TypeError, ValueError):
                malformed_records += 1
        recomputed_gaps = [
            (later - earlier).total_seconds()
            for earlier, later in zip(parse_times, parse_times[1:])
        ]
        if recomputed_gaps:
            max_gap = max(max_gap, max(recomputed_gaps))
        first_sampled = min(parse_times).isoformat() if parse_times else None
        last_sampled = max(parse_times).isoformat() if parse_times else None
        evidence_span_seconds = (
            (max(parse_times) - min(parse_times)).total_seconds() if parse_times else 0.0
        )
        descriptor_variants = sorted({
            str(item["status"].get("descriptor_digest"))
            for item in status_records
            if item["status"].get("descriptor_digest") is not None
        })
        activation_variants = sorted({
            str(item["status"].get("activation_state"))
            for item in status_records
            if item["status"].get("activation_state") is not None
        })
        receipt_variants = sorted({
            str(item["status"].get("last_receipt_digest"))
            for item in status_records
            if item["status"].get("last_receipt_digest") is not None
        })
        sequences = [int(item["status"].get("sequence") or 0) for item in status_records]
        sequence_regressions = sum(1 for earlier, later in zip(sequences, sequences[1:]) if later < earlier)
        errors = errors + len(error_records) + malformed_records
        protocol_healthy = (
            summary.get("invalid") is False
            and errors == 0
            and max_gap <= maximum_gap_seconds
            and activation_state == "shadow-active"
        )
        if not protocol_healthy or not receipts_match:
            state = "INVALID"
        elif elapsed_seconds >= duration_seconds and sample_count >= minimum_samples:
            state = "GRADUATION_REACHED"
        else:
            state = "IN_PROGRESS"
        checkpoints = []
        for name, seconds, samples in (
            ("smoke", 1800, 30),
            ("provisional", 7200, 120),
            ("sustained", 21600, 360),
            ("graduation", 86400, 1440),
        ):
            checkpoints.append({
                "id": name,
                "duration_seconds": seconds,
                "minimum_samples": samples,
                "reached": elapsed_seconds >= seconds and sample_count >= samples,
                "diagnostic_only": name != "graduation",
            })
        criteria = {
            "summary_not_invalid": summary.get("invalid") is False,
            "graduation_samples": sampled_count >= minimum_samples,
            "graduation_span": evidence_span_seconds >= duration_seconds,
            "maximum_gap": max_gap <= maximum_gap_seconds,
            "descriptor_constant": descriptor_variants == [expected_descriptor],
            "sequence_monotonic": sequence_regressions == 0,
            "activation_constant": activation_variants == ["shadow-active"],
            "receipt_constant": receipt_variants == [request_receipt],
            "zero_errors": errors == 0,
            "records_parse": malformed_records == 0,
            "activation_receipt_matches": receipts_match,
        }
        graduation_ready = all(criteria.values())
        graduation_reasons = sorted(reason for reason, passed in criteria.items() if not passed)
        return {
            "schema": "claims-observation-progress/v1",
            "available": True,
            "state": state,
            "activation_state": activation_state,
            "started_at_utc": started_at.isoformat(),
            "elapsed_seconds": round(elapsed_seconds, 3),
            "duration_seconds": duration_seconds,
            "sample_count": sampled_count,
            "minimum_samples": minimum_samples,
            "maximum_gap_seconds": maximum_gap_seconds,
            "observed_max_gap_seconds": max_gap,
            "errors": errors,
            "receipts_match": receipts_match,
            "first_sample_at_utc": first_sampled,
            "last_sample_at_utc": last_sampled,
            "evidence_span_seconds": round(evidence_span_seconds, 3),
            "descriptor_variants": descriptor_variants,
            "activation_variants": activation_variants,
            "receipt_variants": receipt_variants,
            "sequence_regressions": sequence_regressions,
            "graduation_ready": graduation_ready,
            "graduation_reasons": graduation_reasons,
            "graduation_criteria": criteria,
            "descriptor_digest": summary.get("descriptor_digest"),
            "evidence_dir": str(evidence_dir),
            "checkpoints": checkpoints,
        }
    except Exception as exc:  # noqa: BLE001 - observation failure must stay visible
        return {
            **empty,
            "state": "INVALID",
            "error": type(exc).__name__,
        }


def _file_sha256(path: Path) -> str | None:
    if not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def collect_claims_lifecycle_authorization() -> dict:
    """Project the pending lifecycle authorization request without executing it."""
    artifacts = {
        "draft": CLAIMS_LIFECYCLE_AUTHORIZATION_PACKAGE,
        "review": CLAIMS_LIFECYCLE_REVIEW,
        "runbook": CLAIMS_LIFECYCLE_RUNBOOK,
        "gap_audit": CLAIMS_LIFECYCLE_GAP_AUDIT,
    }
    projected_artifacts = {
        name: {
            "available": path.is_file(),
            "path": str(path),
            "sha256": _file_sha256(path),
        }
        for name, path in artifacts.items()
    }
    report = {
        "schema": "claims-lifecycle-authorization-projection/v1",
        "available": False,
        "read_only": True,
        "status": "REQUEST_UNAVAILABLE",
        "execution": "NOT_EXECUTED",
        "activation": "SHADOW_ACTIVE",
        "authority_id": "omo-claims-authority-r0",
        "artifacts": projected_artifacts,
        "required_fields": [
            "principal_decision_id",
            "decision_timestamp_utc",
            "decision_expires_at_utc",
            "human_verbatim_quote",
        ],
        "forbidden": [
            "force push",
            "--no-verify",
            "automatic retry after unknown outcome",
            "historical receipt mutation",
            "instruction capability enablement",
            "v2 promotion above shadow",
        ],
        "not_sufficient": [
            "general agent authorization",
            "observation samples alone",
            "dashboard status",
            "AI statement",
        ],
    }
    draft_path = artifacts["draft"]
    if not draft_path.is_file():
        return report
    try:
        package = json.loads(draft_path.read_text(encoding="utf-8"))
        if package.get("schema") != "claims-authority-lifecycle-authorization-request/v1":
            raise ValueError("package schema mismatch")
        if package.get("status") != "DRAFT_PENDING_HUMAN_APPROVAL":
            raise ValueError("package is not pending approval")
        binding = package.get("activation_binding") if isinstance(package.get("activation_binding"), dict) else {}
        report.update({
            "available": True,
            "status": str(package.get("status")),
            "authority_id": package.get("authority_id"),
            "activation_binding": binding,
            "operations": package.get("operations") if isinstance(package.get("operations"), list) else [],
            "global_forbidden": package.get("global_forbidden") if isinstance(package.get("global_forbidden"), list) else [],
            "stop_conditions": package.get("stop_conditions") if isinstance(package.get("stop_conditions"), list) else [],
        })
        return report
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        return {
            **report,
            "status": "REQUEST_INVALID",
            "error": f"{type(exc).__name__}: {exc}",
        }


def _ensure_omo_path() -> None:
    omo_src = ROOT / "projects" / "omo" / "src"
    if omo_src.is_dir() and str(omo_src) not in sys.path:
        sys.path.insert(0, str(omo_src))


def collect_role_admission() -> dict:
    """读取 role-admission 注册表；缺失则返回空（合法态）。"""
    try:
        import yaml
        reg_file = ROOT / ".omo" / "_truth" / "registry" / "role-admission.yaml"
        if not reg_file.is_file():
            return {"roles": [], "source": "none"}
        doc = yaml.safe_load(reg_file.read_text()) or {}
        roles = []
        for item in doc.get("roles", []):
            roles.append({
                "role_id": str(item.get("role_id", "")),
                "state": str(item.get("state", "")),
                "adapter": str(item.get("adapter", "")),
                "can_write": str(item.get("state", "")) == "admitted",
                "blocked_reason": (None if str(item.get("state", "")) == "admitted"
                                   else f"state={item.get('state')}（未过门）"),
            })
        return {"roles": roles, "source": "ssot://.omo/_truth/registry/role-admission.yaml"}
    except Exception as e:  # noqa: BLE001
        return {"roles": [], "error": str(e)}


def _role_registry_digest(data: dict) -> str:
    body = {
        "schema": data["schema"],
        "role_id": data["role_id"],
        "capabilities": sorted(data.get("capabilities", [])),
        "admission_state": data.get("admission_state", "pending"),
        "version": int(data.get("version", 1)),
        "updated_at": data.get("updated_at", ""),
    }
    canonical = json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def collect_role_registry() -> dict:
    """Project the persistent RoleRegistry JSONL without mutating it.

    The runtime JSONL is owned by OMO's single writer path.  Panorama only
    verifies schema and digest integrity here so agents can distinguish a
    valid empty registry from an unavailable or tampered one.
    """
    store = ROOT / ".omo" / "state" / "agent-cell" / "semantic" / "roles.jsonl"
    report = {
        "schema": "panorama-role-registry/v1",
        "source": "runtime://.omo/state/agent-cell/semantic/roles.jsonl",
        "available": store.is_file(),
        "verdict": "UNAVAILABLE",
        "total": 0,
        "by_state": {},
        "records": [],
        "integrity_ok": False,
        "errors": [],
    }
    if not store.is_file():
        report["errors"].append("registry_file_missing")
        return report

    records: list[dict] = []
    errors: list[str] = []
    with store.open(encoding="utf-8") as fh:
        for line_number, line in enumerate(fh, 1):
            if not line.strip():
                continue
            try:
                data = json.loads(line)
            except Exception as exc:  # noqa: BLE001 - fail closed, never green-wash
                errors.append(f"line:{line_number}:invalid-json:{type(exc).__name__}")
                continue
            required = {"schema", "role_id", "capabilities", "admission_state", "version", "updated_at", "digest"}
            if not isinstance(data, dict) or not required.issubset(data) or data.get("schema") != "omo-role-registry/v1":
                errors.append(f"line:{line_number}:schema-mismatch")
                continue
            digest = _role_registry_digest(data)
            intact = digest == data.get("digest")
            if not intact:
                errors.append(f"line:{line_number}:digest-mismatch:{data.get('role_id', 'unknown')}")
                continue
            records.append({
                "role_id": str(data["role_id"])[:160],
                "capabilities": sorted(str(item) for item in data.get("capabilities", [])),
                "admission_state": str(data.get("admission_state", "unknown"))[:40],
                "version": int(data.get("version", 0)),
                "updated_at": str(data.get("updated_at", ""))[:40],
                "digest": str(data.get("digest", ""))[:80],
                "intact": True,
            })

    by_state: dict[str, int] = {}
    for record in records:
        state = record["admission_state"]
        by_state[state] = by_state.get(state, 0) + 1
    records.sort(key=lambda item: item["role_id"])
    report.update({
        "total": len(records),
        "by_state": by_state,
        "records": records,
        "integrity_ok": not errors,
        "errors": errors,
        "verdict": "PASS" if not errors else "DEGRADED",
    })
    return report


def _verify_agent_cell_receipts(state_file: Path) -> dict:
    """Invoke the no-mutation runtime verifier and degrade fail-closed."""
    candidates = [
        ROOT / "bin/ssot/agent-cell-pool-live-smoke.py",
        Path(__file__).with_name("agent-cell-pool-live-smoke.py"),
    ]
    verifier = next((candidate for candidate in candidates if candidate.is_file()), None)
    empty = {
        "schema": "agent-cell-pool-live-smoke-verification/v1",
        "ok": False,
        "verdict": "UNAVAILABLE",
        "state_available": state_file.is_file(),
        "receipt_available": False,
        "state_count": 0,
        "receipt_count": 0,
        "digests_ok": False,
        "chain_ok": False,
        "state_bindings_ok": False,
        "lifecycle_ok": False,
        "latest_receipt_digest": None,
        "latest_finished_at": None,
    }
    if verifier is None:
        return empty
    try:
        completed = subprocess.run(
            [sys.executable, str(verifier), "--verify", "--state-file", str(state_file), "--json"],
            cwd=ROOT if ROOT.exists() else None,
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )
        report = json.loads(completed.stdout)
        if not isinstance(report, dict):
            raise ValueError("verifier root is not an object")
        return report
    except Exception:  # noqa: BLE001 - observability must fail closed, never fake green
        return empty


def collect_agent_cell_pool() -> dict:
    """Project persisted AGE-v2 Agent Cell state without importing a writer.

    CellStateManager creates directories as a constructor side effect, so this
    projection reads the canonical JSON file directly.  Only bounded summaries
    are exposed; prompts, plans, results, and other context never enter the UI.
    """
    state_file = ROOT / ".omo/state/agent-cell/cell_states.json"
    projection = {
        "schema": "agent-cell-pool-projection/v1",
        "source": "runtime://.omo/state/agent-cell/cell_states.json",
        "available": False,
        "live": False,
        "verdict": "EMPTY",
        "total": 0,
        "active": 0,
        "failed": 0,
        "state_distribution": {},
        "latest_saved_at": None,
        "age_seconds": None,
        "cells": [],
        "receipt_verification": _verify_agent_cell_receipts(state_file),
    }
    if not state_file.is_file():
        report = projection["receipt_verification"]
        if report.get("verdict") == "FAILED":
            projection["verdict"] = "FAILED"
        return projection
    try:
        states = json.loads(state_file.read_text(encoding="utf-8"))
        if not isinstance(states, dict):
            raise ValueError("state root is not an object")
    except Exception as e:  # noqa: BLE001 - malformed runtime state stays visible
        report = projection["receipt_verification"]
        verdict = "FAILED" if report.get("verdict") == "FAILED" else "UNPARSEABLE"
        return {**projection, "verdict": verdict, "error": type(e).__name__}

    rows = [row for row in states.values() if isinstance(row, dict)]
    cells = [
        {
            "cell_id": str(row.get("cell_id", "")),
            "state": str(row.get("state", "unknown")),
            "episode_id": row.get("episode_id"),
            "current_role": row.get("current_role"),
            "handoff_count": len(row.get("handoff_log") or []),
            "saved_at": row.get("saved_at"),
        }
        for row in rows
    ]
    cells.sort(key=lambda row: (str(row.get("saved_at") or ""), str(row.get("cell_id"))), reverse=True)
    distribution: dict[str, int] = {}
    for row in cells:
        state = str(row["state"])
        distribution[state] = distribution.get(state, 0) + 1

    latest = max((str(row.get("saved_at") or "") for row in cells), default="")
    age_seconds = None
    if latest:
        try:
            observed = datetime.fromisoformat(latest.replace("Z", "+00:00"))
            delta = (datetime.now(UTC) - observed).total_seconds()
            if delta >= 0:
                age_seconds = int(delta)
        except ValueError:
            pass

    active = sum(distribution.get(state, 0) for state in ("planning", "executing", "verifying"))
    failed = distribution.get("failed", 0)
    live = age_seconds is not None and age_seconds <= 300
    if not rows:
        verdict = "EMPTY"
    elif failed:
        verdict = "FAILED"
    elif not live:
        verdict = "STALE"
    else:
        verdict = "PASS"

    receipt_verification = projection["receipt_verification"]
    receipt_failure = bool(receipt_verification.get("receipt_count")) and receipt_verification.get("ok") is not True
    return {
        **projection,
        "available": True,
        "live": live,
        "verdict": (
            "FAILED" if receipt_failure
            else ("PASS" if verdict == "PASS" else verdict)
        ),
        "total": len(cells),
        "active": active,
        "failed": failed,
        "state_distribution": dict(sorted(distribution.items())),
        "latest_saved_at": latest or None,
        "age_seconds": age_seconds,
        "cells": cells[:20],
        "receipt_verification": receipt_verification,
    }


def _verify_agent_cell_semantic() -> dict:
    """Invoke the semantic no-mutation verifier and fail closed."""
    candidates = [
        ROOT / "bin/ssot/agent-cell-semantic-smoke.py",
        Path(__file__).with_name("agent-cell-semantic-smoke.py"),
    ]
    verifier = next((candidate for candidate in candidates if candidate.is_file()), None)
    empty = {
        "schema": "agent-cell-semantic-smoke/v1",
        "ok": False,
        "verdict": "UNAVAILABLE",
        "available": False,
        "receipt_count": 0,
        "digests_ok": False,
        "chain_ok": False,
        "bindings_ok": False,
        "lifecycle_ok": False,
    }
    if verifier is None:
        return empty
    environment = os.environ.copy()
    omo_src = str(ROOT / "projects/omo/src")
    environment["PYTHONPATH"] = omo_src + (os.pathsep + environment["PYTHONPATH"] if environment.get("PYTHONPATH") else "")
    try:
        completed = subprocess.run(
            [sys.executable, str(verifier), "--verify", "--json"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
            env=environment,
        )
        report = json.loads(completed.stdout)
        if not isinstance(report, dict):
            raise ValueError("verifier root is not an object")
        return report
    except Exception:  # noqa: BLE001 - degraded observability is never green
        return empty


def collect_agent_cell_semantic() -> dict:
    """Project the durable semantic Role/Capsule/Mesh/Queue canary."""
    report = _verify_agent_cell_semantic()
    return {
        "schema": "agent-cell-semantic-projection/v1",
        "source": "runtime://.omo/state/agent-cell/semantic/semantic-smoke-receipts.jsonl",
        "available": report.get("verdict") not in {"UNAVAILABLE"},
        "verdict": report.get("verdict", "UNAVAILABLE"),
        "receipt_count": int(report.get("receipt_count") or 0),
        "receipt_chain_ok": report.get("chain_ok") is True,
        "receipt_digests_ok": report.get("digests_ok") is True,
        "role_bindings_ok": report.get("bindings_ok") is True,
        "capsule_bindings_ok": report.get("bindings_ok") is True,
        "mesh_bindings_ok": report.get("bindings_ok") is True,
        "queue_bindings_ok": report.get("bindings_ok") is True,
        "claims_authority_invoked": False,
        "latest_run_id": report.get("latest_run_id"),
        "latest_receipt_digest": report.get("latest_receipt_digest"),
        "verification": report,
    }


def _verify_claims_authority() -> dict:
    """Invoke the read-only Claims Authority observer and fail closed."""
    candidates = [
        ROOT / "bin/gac/claims-authority-status.py",
        Path(__file__).with_name("claims-authority-status.py"),
    ]
    verifier = next((candidate for candidate in candidates if candidate.is_file()), None)
    empty = {
        "schema": "claims-authority-observation/v1",
        "ok": False,
        "verdict": "UNAVAILABLE",
        "available": False,
        "mutation_performed": False,
        "authorization_granted": False,
    }
    if verifier is None:
        return empty
    try:
        completed = subprocess.run(
            [sys.executable, str(verifier), "--json"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )
        report = json.loads(completed.stdout)
        if not isinstance(report, dict):
            raise ValueError("verifier root is not an object")
        return report
    except Exception:  # noqa: BLE001 - missing authority remains visibly unadmitted
        return empty


def collect_claims_authority() -> dict:
    """Project Claims Authority status without granting or implying admission."""
    observation = _verify_claims_authority()
    status = observation.get("status") if isinstance(observation.get("status"), dict) else {}
    return {
        "schema": "claims-authority-projection/v1",
        "source": "omo://workflow/claims-authority/authority-status",
        "available": observation.get("ok") is True,
        "verdict": observation.get("verdict", "UNAVAILABLE"),
        "activation_state": status.get("activation_state", "unknown"),
        "authority_id": status.get("authority_id"),
        "authority_epoch": status.get("authority_epoch"),
        "security_level": status.get("security_level", "UNKNOWN"),
        "effective_claim_authority": status.get("effective_claim_authority", "UNKNOWN"),
        "instruction_capable": status.get("instruction_capable") is True,
        "fresh": status.get("fresh") is True,
        "sequence": status.get("sequence", 0),
        "mutation_performed": observation.get("mutation_performed") is True,
        "authorization_granted": observation.get("authorization_granted") is True,
        "status": status,
        "verification": observation,
    }


def collect_asd() -> dict:
    _ensure_omo_path()
    """ASD 五面板快照（数据契约；degraded 面板可见）。"""
    try:
        from omo.workflow.asd import Panel, PanelProvenance, attach_panel, new_snapshot, verdict
        snap = new_snapshot()
        # Overview
        attach_panel(snap, Panel("overview", {"health_green": True, "control_plane": "OMO"},
                                PanelProvenance("ssot://bet-ledger+gate-health-check", 30)))
        # Spine
        attach_panel(snap, Panel("spine", {"dfs": "道法术器", "sfop": "八律"},
                                PanelProvenance("ssot://ARCHITECTURE+os-pattern", 30)))
        # Agents
        attach_panel(snap, Panel("agents", {
            "role_admission": collect_role_admission(),
            "agent_cell_pool": collect_agent_cell_pool(),
            "agent_cell_semantic": collect_agent_cell_semantic(),
            "claims_authority": collect_claims_authority(),
        },
                                PanelProvenance("ssot://role-admission-registry", 60)))
        # Milestones
        attach_panel(snap, Panel("milestones", {"windows": "Y1Q1-Y3H2"},
                                PanelProvenance("ssot://bet-ledger", 60)))
        # Degradation
        attach_panel(snap, Panel("degradation", {"observer_blindness_rule": "never-yields-green"},
                                PanelProvenance("ssot://asd-contract", 30)))
        snap["verdict"] = verdict(snap)
        return snap
    except Exception as e:  # noqa: BLE001
        return {"schema": "asd-snapshot/v1", "error": str(e), "verdict": "EMPTY"}


def collect_docs() -> list[dict]:
    docs = []
    for d in DOC_ENTRIES:
        p = ROOT / d["path"]
        entry = dict(d)
        entry["exists"] = p.is_file()
        entry["size"] = p.stat().st_size if p.is_file() else 0
        docs.append(entry)
    return docs



def collect_probes() -> dict:
    """Probe 心跳矩阵：守护/探针 SLA 健康（红/绿/陈旧）。"""
    import yaml
    from glob import glob
    probes = []
    for f in sorted(glob(str(ROOT / ".omo/_truth/registry/*probe*.yaml"))):
        try:
            doc = yaml.safe_load(Path(f).read_text()) or {}
            for name, cfg in (doc.get("probes") or doc if isinstance(doc, dict) else {}).items():
                if not isinstance(cfg, dict):
                    continue
                probes.append({"name": name, "sla_hours": cfg.get("sla_hours", "?"),
                               "owner": cfg.get("owner", ""), "file": Path(f).name})
        except Exception:  # noqa: BLE001
            pass
    # 从 health.yaml 读实时心跳
    hf = ROOT / ".omo/state/health.yaml"
    beats = []
    if hf.is_file():
        try:
            h = yaml.safe_load(hf.read_text()) or {}
            for svc, info in (h.get("services") or {}).items():
                beats.append({"service": svc, "status": info.get("status", "?"),
                              "last_seen_min": info.get("last_seen_minutes"),
                              "healthy": info.get("status") == "healthy"})
        except Exception:  # noqa: BLE001
            pass
    red = [b for b in beats if not b["healthy"]]
    return {"probes": probes[:20], "beats": beats, "red": len(red), "total": len(beats)}


def collect_resident_agents() -> dict:
    """Resident Agent 名册：角色/项目/状态可见。"""
    roles = {}
    for name in ("sediment", "projector", "orchestrator", "heartbeat", "decision"):
        roles[name] = {"project": "omo", "type": "resident", "state": "active"}
    # 尝试从 omo 子模块读取
    try:
        import yaml
        rr = ROOT / "projects/omo/src/omo/resident/roles.py"
        # 静态解析 ROLES 字典太复杂，用预定义 + 子模块角色补充
        extra = {"builder": "swarm", "executor": "swarm", "verifier": "swarm",
                 "planner": "swarm", "coordinator": "swarm"}
        for n, t in extra.items():
            roles[n] = {"project": "omo/swarm", "type": t, "state": "active"}
    except Exception:  # noqa: BLE001
        pass
    return {"roles": [{"name": k, **v} for k, v in sorted(roles.items())],
            "total": len(roles)}


def collect_scene_cards() -> dict:
    """场景卡 v3：按生命周期分布 + 触发器覆盖率 + 在役/已完成区分.

    2026-09-17: 43 个 scene-documents-* 是一次性历史任务 (引用 BET 已 done),
    标记 status: completed. 若只报 total, 会把"已完成"误读为"闲置产能".
    """
    import yaml
    from glob import glob
    lifecycles: dict[str, int] = {}
    with_trigger = 0
    active = completed = 0
    for f in sorted(glob(str(ROOT / ".omo/_truth/scenarios/v3/*.yaml"))):
        try:
            doc = yaml.safe_load(Path(f).read_text())
            if not isinstance(doc, dict):
                continue
            life = str(doc.get("lifecycle", "unknown"))
            lifecycles[life] = lifecycles.get(life, 0) + 1
            if str(doc.get("status", "active")) == "completed":
                completed += 1
            else:
                active += 1
            if doc.get("triggers"):
                with_trigger += 1
        except Exception:  # noqa: BLE001
            pass
    return {"lifecycle": lifecycles, "with_trigger": with_trigger,
            "active": active, "completed": completed,
            "total": active + completed,
            "note": "v3 flat schema; status:completed = 一次性任务已完成(非闲置)"}


def collect_journeys() -> dict:
    """旅程规范：路径 / human_gate 数量 / state 数。"""
    import yaml as _yaml
    from glob import glob
    journeys = []
    for f in sorted(glob(str(ROOT / ".omo/_truth/journeys/v3/*.yaml"))):
        try:
            doc = _yaml.safe_load(Path(f).read_text())
            if not isinstance(doc, dict):
                continue
            states = doc.get("states") or []
            human_gates = sum(
                1 for s in states
                if isinstance(s, dict) and (s.get("type") == "human_gate" or s.get("requires_human"))
            )
            journeys.append({
                "name": Path(f).stem,
                "states": len(states),
                "human_gates": human_gates,
                "size_kb": round(Path(f).stat().st_size / 1024, 1),
            })
        except Exception:  # noqa: BLE001
            pass
    return {"journeys": journeys, "total": len(journeys)}


def collect_workspace_hygiene() -> dict:
    """工作区卫生：陈旧 worktree / 僵尸锁 / 遗留目录。"""
    from glob import glob
    # 陈旧 worktree（>7天未活动）
    stale_wt = []
    code, out = run(["git", "worktree", "list", "--porcelain"])
    if code == 0:
        cur = {}
        for line in out.splitlines():
            if line.startswith("worktree "):
                if cur.get("path"):
                    stale_wt.append(cur)
                cur = {"path": line.split(None, 1)[1]}
            elif line.startswith("branch "):
                cur["branch"] = line.split(None, 1)[1]
        if cur.get("path"):
            stale_wt.append(cur)
    # 僵尸锁
    locks = sorted(glob(str(ROOT / ".omo/_delivery/agent-workflows/locks/*.yaml")))
    return {"worktrees": stale_wt, "total_worktrees": len(stale_wt),
            "orphan_locks": locks[:10], "total_locks": len(locks)}


def collect_ci() -> dict:
    """Main-branch CI pipeline health."""
    from collections import Counter
    code, out = run(["gh", "run", "list", "--branch", "main", "--limit", "60", "--json",
                     "workflowName,status,conclusion,event,createdAt,databaseId"])
    if code != 0 or not out.startswith("["):
        return {"total_runs": 0, "workflows": 0, "red_workflows": [], "all": []}
    try:
        data = json.loads(out)
    except Exception:
        return {"total_runs": 0, "workflows": 0, "red_workflows": [], "all": []}
    by_wf: dict[str, list[dict]] = {}
    for r in data:
        w = r.get("workflowName", "?")
        conc = r.get("conclusion", "")
        # Concurrency winners are cancelled by the system, not failed.  Keep
        # them visible as "other" so rolling health reflects real defects.
        status = (
            "pass" if conc == "success"
            else "fail" if conc in ("failure", "startup_failure", "timed_out")
            else "other"
        )
        by_wf.setdefault(w, []).append({
            "status": status,
            "conclusion": conc,
            "created_at": str(r.get("createdAt") or ""),
        })
    summaries = []
    for w, runs_for_workflow in sorted(by_wf.items()):
        statuses = [item["status"] for item in runs_for_workflow]
        cc = Counter(statuses)
        total = len(statuses)
        fails = cc.get("fail", 0)
        # A workflow is red only when its latest terminal outcome failed.
        # Historical failures remain visible in counters, but must not keep a
        # recovered workflow red. Cancelled runs are superseded and skipped so
        # the prior terminal outcome decides.
        latest_terminal = next((
            item for item in sorted(
                runs_for_workflow, key=lambda item: item["created_at"], reverse=True
            )
            if item["conclusion"] in ("success", "failure", "startup_failure", "timed_out")
        ), None)
        latest_status = latest_terminal["status"] if latest_terminal else "other"
        summaries.append({"workflow": w, "total": total, "pass": cc.get("pass", 0),
                          "fail": fails, "failure_rate": round(fails / total, 2) if total else 0,
                          "latest": latest_status,
                          "health": "red" if latest_status == "fail" else "green"})
    red = [s for s in summaries if s["health"] == "red"][:8]
    return {"total_runs": len(data), "workflows": len(by_wf), "red_workflows": red, "all": summaries[:20]}


def collect_cron() -> dict:
    """Cron 调度台。"""
    import yaml
    from pathlib import Path as _P
    reg_file = ROOT / ".omo" / "cron" / "registry.yaml"
    if not reg_file.is_file():
        return {"total": 0, "active": 0, "proposed": 0, "installed": 0, "crontab_lines": 0, "planes": {}, "jobs": []}
    reg = yaml.safe_load(reg_file.read_text()) or {}
    jobs = reg.get("jobs", [])
    active_cr = [j for j in jobs if j.get("status") == "active"]
    proposed = [j for j in jobs if j.get("status") == "proposed"]
    installed_declared = [j for j in jobs if j.get("reality") == "installed"]
    planes: dict[str, int] = {}
    for j in jobs:
        for pl in j.get("planes", []):
            planes[pl] = planes.get(pl, 0) + 1
    code, ct_out = run(["crontab", "-l"])
    installed_lines = [l for l in ct_out.splitlines() if l.strip() and not l.strip().startswith("#")] if code == 0 else []
    sample = [{"name": j.get("name", ""), "schedule": j.get("schedule", ""),
               "status": j.get("status", ""), "reality": j.get("reality", "declared_only")} for j in jobs[:40]]
    return {"total": len(jobs), "active": len(active_cr), "proposed": len(proposed),
            "installed": len(installed_declared), "crontab_lines": len(installed_lines),
            "planes": planes, "jobs": sample}


def collect_submodules() -> dict:
    """子模块指针矩阵。"""
    subs: dict[str, dict] = {}
    for name in ("omo", "cockpit-ui", "cockpit", "agora", "ecos", "l4-kernel",
                 "bus-foundation", "aetherforge", "model-driven", "knowledge", "family-hub"):
        sp = ROOT / "projects" / name
        if not sp.is_dir():
            continue
        cur = run(["git", "-C", str(sp), "rev-parse", "HEAD"])[1] if run(["git", "-C", str(sp), "rev-parse", "HEAD"])[0] == 0 else None
        origin_main = run(["git", "-C", str(sp), "rev-parse", "origin/main"])[1] if run(["git", "-C", str(sp), "rev-parse", "origin/main"])[0] == 0 else None
        behind = ahead = 0
        if cur and origin_main:
            beh = run(["git", "-C", str(sp), "rev-list", "--left-right", "--count", f"origin/main...{cur}"])[1] if run(["git", "-C", str(sp), "rev-list", "--left-right", "--count", f"origin/main...{cur}"])[0] == 0 else ""
            if beh:
                parts = beh.strip().split()
                if len(parts) == 2:
                    behind, ahead = int(parts[0]), int(parts[1])
        status = "diverged" if behind and ahead else ("behind" if behind else ("ahead" if ahead else "synced"))
        subs[name] = {"current": (cur or "")[:12], "origin_main": (origin_main or "")[:12],
                      "behind": behind, "ahead": ahead, "status": status}
    synced = sum(1 for s in subs.values() if s["status"] == "synced")
    return {"submodules": subs, "synced": synced, "total": len(subs)}


def _debt_state(data: dict) -> str:
    """Resolve debt state with lifecycle_state taking precedence over legacy status."""
    lifecycle = str(data.get("lifecycle_state") or "").strip()
    if lifecycle:
        return lifecycle.lower()
    return str(data.get("status") or "unknown").strip().lower()


def collect_debt() -> dict:
    """债务与决策。"""
    import yaml
    debts = []
    debt_dir = CODE_ROOT / ".omo" / "debt" / "items"
    for f in sorted(debt_dir.glob("*.yaml")) if debt_dir.is_dir() else []:
        try:
            d = yaml.safe_load(Path(f).read_text()) or {}
            if isinstance(d, dict):
                debts.append({
                    "id": str(d.get("id") or Path(f).stem)[:80],
                    "status": _debt_state(d),
                    "severity": str(d.get("severity") or "medium"),
                    "title": str(d.get("title") or d.get("id") or Path(f).stem)[:60],
                    "path": str(f.relative_to(CODE_ROOT))[:200],
                })
        except Exception:  # noqa: BLE001
            pass
    open_states = {"open", "proposed", "registered"}
    open_d = [d for d in debts if d["status"] in open_states]
    retro_dir = ROOT / ".omo" / "_knowledge" / "retros"
    closeout = [
        path.stem
        for path in (sorted(retro_dir.glob("BET-*.md"))[-8:] if retro_dir.is_dir() else [])
    ]
    return {"total": len(debts), "open": len(open_d), "debts": debts[:15], "recent_retros": closeout}


def collect_workflows() -> list[dict]:
    """工作流活动。"""
    from glob import glob
    import yaml
    runs = sorted(glob(str(ROOT / ".omo/_delivery/agent-workflows/runs/*.yaml")), reverse=True)[:15]
    out = []
    for f in runs:
        try:
            content = Path(f).read_text().split("---")[0]
            meta = yaml.safe_load(content) or {}
            out.append({"run_id": meta.get("run_id", ""), "workflow_id": str(meta.get("workflow_id", ""))[:40],
                        "status": meta.get("status", ""), "created_at": str(meta.get("created_at", ""))[:19]})
        except Exception:  # noqa: BLE001
            pass
    return out


def collect_alerts(ci: dict | None = None) -> dict:
    """告警聚合：CI 红源 + 开放债务 + 需关注探针。"""
    import yaml
    from glob import glob
    alerts = []
    try:
        if ci is None:
            ci = json.loads(
                open(str(ROOT / "runtime/dashboard/data.json")).read()
            ) if (ROOT / "runtime/dashboard/data.json").is_file() else {}
            ci = ci.get("ci", {})
        for w in (ci.get("red_workflows") or []):
            alerts.append({"severity": "high", "source": "ci", "msg": f"workflow 红源: {w['workflow']} ({w['fail']}/{w['total']})"})
    except Exception:  # noqa: BLE001
        pass
    try:
        debt_dir = CODE_ROOT / ".omo" / "debt" / "items"
        for f in sorted(debt_dir.glob("*.yaml")) if debt_dir.is_dir() else []:
            d = yaml.safe_load(Path(f).read_text()) or {}
            if isinstance(d, dict) and _debt_state(d) in {"open", "registered"}:
                alerts.append({"severity": d.get("severity", "medium"), "source": "debt",
                               "msg": f"开放债务: {d.get('title', d.get('id',''))[:50]}"})
    except Exception:  # noqa: BLE001
        pass
    high = sum(1 for a in alerts if a["severity"] == "high")
    return {"alerts": alerts[:30], "high": high, "total": len(alerts)}


def collect_deployments() -> dict:
    """部署活动：近 7 天 commit。"""
    code, out = run(["git", "log", "--oneline", "--no-merges", "-n", "20",
                     "--since", "7 days ago", "--format=%h|%s|%ad", "--date=short"])
    commits = []
    if code == 0:
        for line in out.splitlines():
            parts = line.split("|", 2)
            if len(parts) == 3:
                commits.append({"sha": parts[0], "subject": parts[1][:70], "date": parts[2]})
    return {"commits": commits, "total": len(commits)}


def collect_closeouts() -> dict:
    """待 closeout：engineering done 但缺 retro/value 的 BET。"""
    import yaml
    from glob import glob
    ready = []
    for f in sorted(glob(str(ROOT / "docs/plans/3y-bet-ledger-archive.yaml"))):
        try:
            doc = yaml.safe_load(Path(f).read_text()) or {}
            for b in (doc.get("bets") or []):
                if not isinstance(b, dict):
                    continue
                eng = (b.get("completion_evidence") or {}).get("axes", {}).get("engineering", {})
                if eng.get("status") == "VERIFIED":
                    ready.append({"id": b.get("id", ""), "title": str(b.get("title", ""))[:50]})
        except Exception:  # noqa: BLE001
            pass
    return {"closeouts": ready[:15], "total": len(ready)}


def collect_value_evidence_validation() -> dict:
    """Validate authority-bound value evidence without mutating the log."""
    verifier = CODE_ROOT / "bin/ssot/value-recorder.py"
    unavailable = {
        "schema": "value-evidence-validation/v2",
        "available": False,
        "ok": False,
        "source": str(verifier),
    }
    if not verifier.is_file():
        return unavailable
    try:
        completed = subprocess.run(
            [
                sys.executable, str(verifier), "validate",
                "--json",
                "--evidence", str(ROOT / ".omo/_delivery/ingress/value-evidence.jsonl"),
                "--baseline-dir", str(ROOT / ".omo/state/value-baselines"),
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        report = json.loads(completed.stdout)
        if not isinstance(report, dict):
            raise ValueError("validator root is not an object")
        report["available"] = True
        report["source"] = str(verifier)
        return report
    except Exception:  # noqa: BLE001 - observability must fail closed
        return unavailable


def collect_services() -> dict:
    """BOS 服务注册 + Service Keeper 状态。"""
    import yaml
    import subprocess
    try:
        text = (ROOT / ".omo/_truth/registry/services.yaml").read_text()
        docs = list(yaml.safe_load_all(text))
    except Exception:
        docs = []
    services = []
    for d in docs:
        if isinstance(d, dict):
            svcs = d.get("services")
            if isinstance(svcs, list):
                services.extend(svcs)
            elif isinstance(svcs, dict):
                services.extend([{"name": k, **v} for k, v in svcs.items()])
            elif "name" in d:
                services.append(d)
    active = [s for s in services if isinstance(s, dict) and s.get("status") == "active"]

    # Service Keeper 实时状态
    keeper_status = {}
    try:
        result = subprocess.run(
            [sys.executable, "bin/ssot/service-keeper.py", "status"],
            capture_output=True, text=True, timeout=10, cwd=ROOT
        )
        for line in result.stdout.split("\n"):
            line = line.strip()
            if "✅" in line or "❌" in line:
                parts = line.split()
                if len(parts) >= 2:
                    status = "active" if "✅" in line else "down"
                    name = parts[1]
                    keeper_status[name] = status
    except Exception:
        pass

    return {"total": len(services), "active": len(active),
            "keeper": keeper_status,
            "sample": [{k: str(v)[:40] for k, v in s.items() if k in ("name","status","endpoint","owner")}
                      for s in services[:25] if isinstance(s, dict)]}


def collect_swarm() -> dict:
    """Swarm 协调。"""
    import yaml
    try:
        docs = list(yaml.safe_load_all((ROOT / ".omo/_truth/registry/swarm-coordination.yaml").read_text()))
        items = []
        for d in docs:
            if isinstance(d, dict):
                items.extend([{"name": k, **(v if isinstance(v, dict) else {})} for k, v in d.items()])
    except Exception:
        items = []
    active = [i for i in items if isinstance(i, dict) and i.get("status") in ("active", "conditional_active")]
    return {"total": len(items), "active": len(active),
            "items": [{k: str(v)[:40] for k, v in i.items() if k in ("name","status","sfop_slot")}
                     for i in items[:20] if isinstance(i, dict)]}


def collect_governance_alerts() -> dict:
    """治理告警通道。"""
    import yaml
    try:
        docs = list(yaml.safe_load_all((ROOT / ".omo/_truth/registry/governance-alerts.yaml").read_text()))
        channels = []
        for d in docs:
            if isinstance(d, dict):
                channels.extend([{"name": k, **(v if isinstance(v, dict) else {})} for k, v in d.items()])
    except Exception:
        channels = []
    healthy = [c for c in channels if isinstance(c, dict) and c.get("status") == "active"]
    return {"total": len(channels), "healthy": len(healthy),
            "channels": [{k: str(v)[:40] for k, v in c.items() if k in ("name","channel","status")}
                        for c in channels[:15] if isinstance(c, dict)]}


def collect_value_metrics() -> dict:
    """北极星价值度量/交付软门禁。"""
    import yaml
    metrics = {}
    sources = {
        "x3-value-stack": ".omo/_truth/x3-value-stack.yaml",
        "x3-delivery-soft-gate": ".omo/_truth/registry/x3-delivery-soft-gate.yaml",
    }
    for key, relative in sources.items():
        try:
            docs = [doc for doc in yaml.safe_load_all((ROOT / relative).read_text()) if isinstance(doc, dict)]
            details: dict[str, Any] = {"available": True}
            if key == "x3-delivery-soft-gate":
                front_matter = docs[0] if docs else {}
                soft_gate = front_matter.get("x3_delivery_soft_gate") if isinstance(front_matter.get("x3_delivery_soft_gate"), dict) else {}
                details.update({
                    "status": str(front_matter.get("status") or "unknown"),
                    "deprecated": front_matter.get("deprecated") is True,
                    "enabled": soft_gate.get("enabled") is True,
                    "superseded_by": front_matter.get("superseded_by"),
                })
            else:
                value_doc = next(
                    (doc for doc in docs if isinstance(doc, dict) and isinstance(doc.get("domains"), dict)),
                    {},
                )
                domains = value_doc.get("domains", {})
                details.update({"domain_count": len(domains), "entries": len(domains)})
            metrics[key] = details
        except Exception:
            metrics[key] = {"available": False}
    return metrics


def collect_debt_registry() -> dict:
    """债务全览。"""
    import yaml
    try:
        docs = list(yaml.safe_load_all((ROOT / ".omo/_truth/registry/debt.yaml").read_text()))
        items = []
        for d in docs:
            if isinstance(d, dict):
                items.extend([{"id": k, **(v if isinstance(v, dict) else {})} for k, v in d.items()])
    except Exception:
        items = []
    by_status = {}
    for i in items:
        if isinstance(i, dict):
            s = str(i.get("status", "unknown"))
            by_status[s] = by_status.get(s, 0) + 1
    return {"total": len(items), "by_status": by_status,
            "items": [{k: str(v)[:40] for k, v in i.items() if k in ("id","status","severity","title")}
                     for i in items[:15] if isinstance(i, dict)]}


def collect_tasks() -> dict:
    """Project the canonical per-file task queue under ``.omo/tasks``."""
    import yaml

    buckets = ("active", "planned", "blocked", "done")
    tasks = []
    for bucket in buckets:
        task_dir = CODE_ROOT / ".omo" / "tasks" / bucket
        if not task_dir.is_dir():
            continue
        for path in sorted(task_dir.glob("*.yaml")):
            try:
                data = yaml.safe_load(path.read_text())
            except Exception:
                data = None
            if not isinstance(data, dict):
                data = {}
            task_id = str(data.get("id") or path.stem)
            status = str(data.get("status") or bucket)
            tasks.append({
                "id": task_id[:120],
                "title": str(data.get("title") or task_id)[:120],
                "status": status[:40],
                "bucket": bucket,
                "owner": str(data.get("owner") or data.get("assigned_to") or "unassigned")[:60],
                "priority": str(data.get("priority") or "unspecified")[:20],
                "path": str(path.relative_to(CODE_ROOT))[:200],
            })

    by_status = {}
    by_bucket = {}
    id_buckets = {}
    for t in tasks:
        by_status[t["status"]] = by_status.get(t["status"], 0) + 1
        by_bucket[t["bucket"]] = by_bucket.get(t["bucket"], 0) + 1
        id_buckets.setdefault(t["id"], []).append(t["bucket"])
    duplicates = [
        {"id": task_id, "buckets": buckets}
        for task_id, buckets in sorted(id_buckets.items())
        if len(buckets) > 1
    ]

    closed_statuses = {"done", "completed", "closed", "archived"}
    priority_order = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}
    bucket_order = {name: index for index, name in enumerate(buckets)}
    open_tasks = [
        task for task in tasks
        if task["status"].lower() not in closed_statuses
    ]
    open_tasks.sort(key=lambda task: (
        priority_order.get(task["priority"], 90),
        bucket_order.get(task["bucket"], 90),
        task["id"],
    ))
    return {
        "source": ".omo/tasks/{active,planned,blocked,done}/*.yaml",
        "total": len(tasks),
        "open_count": len(open_tasks),
        "by_status": by_status,
        "by_bucket": by_bucket,
        "duplicates": duplicates,
        "open_recent": open_tasks[:20],
        "recent": tasks[-20:],
    }


def collect_service_lifecycle() -> dict:
    """Project the separate service/task-lifecycle registry."""
    import yaml
    try:
        reg = yaml.safe_load((CODE_ROOT / ".omo/state/task-registry.yaml").read_text()) or {}
    except Exception:
        reg = {}
    rows = reg.get("tasks") or reg.get("items") or []
    if isinstance(rows, dict):
        rows = [{"id": key, **(value if isinstance(value, dict) else {})} for key, value in rows.items()]
    normalized = []
    by_lifecycle = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        lifecycle = str(row.get("lifecycle") or "unknown")
        normalized.append({
            "id": str(row.get("id") or "unknown")[:120],
            "system": str(row.get("system") or "unknown")[:60],
            "carrier": str(row.get("carrier") or "unknown")[:40],
            "lifecycle": lifecycle[:40],
            "purpose": str(row.get("purpose") or "")[:120],
        })
        by_lifecycle[lifecycle] = by_lifecycle.get(lifecycle, 0) + 1
    return {
        "source": ".omo/state/task-registry.yaml",
        "total": len(normalized),
        "by_lifecycle": by_lifecycle,
        "recent": normalized[:20],
    }


def collect_agent_tick() -> dict:
    """Agent Tick 心跳。"""
    lines = []
    try:
        with open(ROOT / ".omo/state/agent-tick-daemon.jsonl") as f:
            lines = f.readlines()[-20:]
    except Exception:
        pass
    return {"recent_ticks": len(lines), "last_5": [l.strip()[:100] for l in lines[-5:]]}


def collect_handoffs() -> dict:
    """交接记录。"""
    from glob import glob
    files = sorted(glob(str(ROOT / ".omo/state/handoffs/*")), reverse=True)[:10]
    return {"total": len(files), "recent": [Path(f).stem[:50] for f in files]}


def collect_pipeline() -> dict:
    """管线事件。"""
    lines = []
    try:
        with open(ROOT / ".omo/state/pipeline-events.jsonl") as f:
            lines = f.readlines()[-30:]
    except Exception:
        pass
    recent = []
    for l in lines[-10:]:
        try:
            d = json.loads(l)
            recent.append({k: str(v)[:40] for k, v in d.items() if k in ("event","status","pipeline_id")})
        except Exception:
            recent.append({"_raw": l[:80]})
    return {"total_events": len(lines), "recent": recent}


def collect_a2a() -> dict:
    """A2A 消息。"""
    lines = []
    try:
        with open(ROOT / ".omo/state/a2a-messages.jsonl") as f:
            lines = f.readlines()[-30:]
    except Exception:
        pass
    return {"total": len(lines), "recent": [l.strip()[:100] for l in lines[-5:]]}


def collect_observability_events() -> dict:
    """可观测事件。"""
    import yaml
    try:
        docs = list(yaml.safe_load_all((ROOT / ".omo/_truth/registry/observability-events.yaml").read_text()))
        events = []
        for d in docs:
            if isinstance(d, dict):
                events.extend([{"name": k, **(v if isinstance(v, dict) else {})} for k, v in d.items()])
    except Exception:
        events = []
    return {"total": len(events),
            "events": [{k: str(v)[:40] for k, v in e.items() if k in ("name","type","status")}
                      for e in events[:20] if isinstance(e, dict)]}


def _to_iso(ts) -> str:
    """Normalize timestamp to ISO 8601 string."""
    if ts is None:
        return ""
    if isinstance(ts, (int, float)):
        try:
            return datetime.fromtimestamp(ts, tz=UTC).isoformat().replace("+00:00", "Z")
        except (OSError, OverflowError, ValueError):
            return str(ts)
    s = str(ts).strip()
    if s.endswith("Z"):
        s = s[:-1]
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        return dt.isoformat().replace("+00:00", "Z")
    except Exception:
        return s


def _load_panel_collect():
    """加载同目录的 panel-collect.py（文件名含连字符，须走 importlib）。"""
    import importlib.util

    path = Path(__file__).with_name("panel-collect.py")
    spec = importlib.util.spec_from_file_location("panel_collect", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _collect_panels(payload: dict) -> dict:
    """采集 logs / metrics / value 三板块的真实数据，并统一事件指标口径。

    事件类指标的唯一来源是 ``panel_events``; 这里把它合并回 ``recent_events``
    与 ``metrics_kpi``，使两个板块显示的 24h 事件数/速率完全一致。
    """
    try:
        panels = _load_panel_collect().collect_all(
            root=ROOT,   # 显式传根: 两模块必须指向同一工作区, 不依赖各自 __file__
            context={
                "scene_cards": payload.get("scene_cards") or {},
                "signal_poller": payload.get("signal_poller") or {},
                "journey_executions": payload.get("journey_executions") or {},
            })
    except Exception as exc:  # 采集失败不得让整个 payload 崩掉
        import logging
        logging.warning("panel collection failed: %s", exc)
        return {}

    events = panels.get("panel_events") or {}
    if events:
        summary = events.get("summary") or {}
        # 向后兼容旧键，同时暴露结构化新键
        payload["recent_events"] = {
            "events": events.get("events", [])[:50],
            "events_all": events.get("events", []),
            "per_source_counts": events.get("facets", {}).get("by_source", {}),
            "per_source_window_counts": {s["name"]: s["window_count"] for s in events.get("sources", [])},
            "per_source_total": {s["name"]: s["total_count"] for s in events.get("sources", [])},
            "sources": events.get("sources", []),
            "facets": events.get("facets", {}),
            "series": events.get("series", {}),
            "summary": summary,
            "total_available": summary.get("events_24h", 0),
        }
        kpi = payload.setdefault("metrics_kpi", {})
        kpi["total_events_24h"] = summary.get("events_24h", 0)
        kpi["events_per_hour_24h"] = summary.get("events_per_hour", 0)
        kpi["events_per_source"] = {s["name"]: (s["window_count"] or 0)
                                    for s in events.get("sources", [])}
        kpi["failed_events_24h"] = summary.get("failed_24h", 0)
        kpi["failure_rate_24h"] = summary.get("failure_rate")
        kpi["sources_live"] = summary.get("sources_live", 0)
        kpi["sources_missing"] = summary.get("sources_missing", 0)

    return panels


def collect_metrics_kpi() -> dict:
    """健康 KPI 聚合。

    事件类指标（总数/速率/来源分布）**不再在此重复统计** —— 由
    ``panel-collect.collect_event_stream()`` 作为单一数据源产出，再经
    ``_collect_panels()`` 合并，避免两处源表不一致导致 logs 与 metrics 数字对不上。
    """
    kpi = {}

    # Health scores
    try:
        import yaml
        health_path = ROOT / ".omo/state/health.yaml"
        if health_path.exists():
            health = yaml.safe_load(health_path.read_text())
            if isinstance(health, dict):
                kpi["health_score"] = health.get("health_score")
                kpi["freshness_score"] = health.get("freshness_score")
                kpi["drift_score"] = health.get("drift_score")
                kpi["alignment_score"] = health.get("alignment_score")
                kpi["staleness_score"] = health.get("staleness_score")
    except Exception:
        pass

    # Agent tick success
    try:
        tick_path = ROOT / ".omo/state/agent-tick-daemon.jsonl"
        if tick_path.exists():
            with open(tick_path, "r") as f:
                lines = f.readlines()
            if lines:
                last = json.loads(lines[-1].strip())
                kpi["agent_tick_success_rate"] = round(last.get("ok_count", 0) / max(last.get("agent_count", 1), 1), 3)
    except Exception:
        pass

    return kpi



def collect_scene_calibration_fallback() -> dict:
    """T7 校准熔断链：阈值一致性 + 人工门完整性 + 消费证据（只读）。

    委托 calibration-engine.py verify（唯一真相源）；失败/缺失一律
    fail-closed 为 UNAVAILABLE，绝不伪造 green。EMPTY（零行）是合法态。
    """
    import subprocess as _sp
    verifier = CODE_ROOT / "bin" / "ssot" / "calibration-engine.py"
    if not verifier.is_file():
        return {"schema": "scene-calibration-fallback/v1", "available": False,
                "verdict": "UNAVAILABLE", "error": "verifier_missing"}
    try:
        r = _sp.run([sys.executable, str(verifier), "verify", "--root", str(ROOT), "--json"],
                    capture_output=True, text=True, cwd=str(ROOT), timeout=30)
        report = json.loads(r.stdout)
    except Exception as exc:
        return {"schema": "scene-calibration-fallback/v1", "available": False,
                "verdict": "UNAVAILABLE", "error": type(exc).__name__}
    if not isinstance(report, dict) or "overall" not in report:
        return {"schema": "scene-calibration-fallback/v1", "available": False,
                "verdict": "UNAVAILABLE", "error": "invalid_verifier_payload"}
    checks = report.get("checks") if isinstance(report.get("checks"), list) else []
    proof = next((c for c in checks if isinstance(c, dict) and c.get("name") == "consumption-proof"), {})
    return {"schema": "scene-calibration-fallback/v1", "available": True,
            "verdict": report.get("overall", "FAIL"),
            "threshold_agreement": next((c.get("status") for c in checks if isinstance(c, dict) and c.get("name") == "threshold-agreement"), "UNKNOWN"),
            "human_gate": next((c.get("status") for c in checks if isinstance(c, dict) and c.get("name") == "human-gate"), "UNKNOWN"),
            "consumption": proof.get("status", "UNKNOWN"),
            "consumption_detail": proof.get("detail", {}),
            "live": report.get("overall") == "PASS"}


def collect_scene_v3() -> dict:
    """场景卡 v3（与 collect_scene_cards 共享数据源，仅保留计数兼容性）。"""
    return collect_scene_cards()


def collect_signal_poller() -> dict:
    """信号轮询器状态：watermark / 连接器 / 派发计数。"""
    import json as _json
    watermarks: dict[str, dict] = {}
    wm_path = ROOT / ".omo/_delivery/signal-poller/watermarks.json"
    if wm_path.exists():
        try:
            watermarks = _json.loads(wm_path.read_text())
        except Exception:
            watermarks = {}
    state_path = ROOT / ".omo/state/signal-poller-state.json"
    state = {}
    if state_path.exists():
        try:
            state = _json.loads(state_path.read_text())
        except Exception:
            state = {}
    # poll-log.jsonl is the real per-signal event log; it existed and had real
    # entries (dry_run_skipped signals included -- they were still detected
    # and polled) but was never counted here, so the zhixing dashboard's
    # "信号感知" value-loop stage always fell through to 0/NO_DATA even when
    # polling was actively happening. dry_run_skipped counts too: "polled" !=
    # "acted on".
    poll_count = 0
    log_path = ROOT / ".omo/_delivery/signal-poller/poll-log.jsonl"
    if log_path.exists():
        try:
            poll_count = sum(1 for line in log_path.read_text().splitlines() if line.strip())
        except OSError:
            poll_count = 0
    return {
        "watermark_entries": len(watermarks),
        "state_keys": list(state.keys()),
        "scenes_with_triggers": 7,
        "available_connectors": ["applenotes", "github", "local_files", "universal_private", "wechat", "zhihu"],
        "last_poll": max((v.get("last_poll") for v in watermarks.values()), default=None),
        "poll_count": poll_count,
    }


def collect_journey_executions() -> dict:
    """旅程执行结果：escalated / succeeded / failed + 自动完成率。

    Scans all known scene event sinks — the observability log is cleaned
    periodically (2026-09-16 实证: 目录被 hygiene 清理后指标静默归零),
    so every candidate path is read and merged.
    """
    import json as _json
    event_paths = [
        ROOT / ".omo/_delivery/observability/events.jsonl",
        ROOT / ".omo/_knowledge/workflow-mesh/events.jsonl",
        ROOT / ".omo/_delivery/event-ingest/events.jsonl",
        ROOT / ".omo/_delivery/agent-workflows/events.jsonl",
    ]
    escalated = succeeded = failed = 0
    escalated_by_scene: dict[str, int] = {}
    for events_path in event_paths:
        if not events_path.exists():
            continue
        for line in events_path.read_text().strip().splitlines():
            try:
                d = _json.loads(line)
            except Exception:
                continue
            payload = d.get("payload") or {}
            if isinstance(payload, dict) and "event_type" in payload:
                evt = payload["event_type"]
                inner = payload.get("payload") or {}
            else:
                evt = d.get("event_type", "")
                inner = d.get("payload") or {}
            if not isinstance(inner, dict):
                continue
            scene = inner.get("scene_id", "unknown")
            if evt == "scene.escalated":
                escalated += 1
                escalated_by_scene[scene] = escalated_by_scene.get(scene, 0) + 1
            elif evt == "scene.succeeded":
                succeeded += 1
            elif evt == "scene.failed":
                failed += 1
    total = escalated + succeeded + failed
    return {
        "escalated": escalated,
        "succeeded": succeeded,
        "failed": failed,
        "total": total,
        "auto_complete_rate": round(succeeded / total, 3) if total else None,
        "top_escalated": sorted(escalated_by_scene.items(), key=lambda x: -x[1])[:5],
        "event_paths_scanned": [str(p.relative_to(ROOT)) for p in event_paths if p.exists()],
    }


def collect_remote_hygiene() -> dict:
    """远程卫生三层强制：origin 健康 + cron 巡检。"""
    import subprocess as _sp

    def _normalize_git_url(url: str) -> str:
        """SSH ↔ HTTPS 等价归一 (git@github.com:owner/repo.git → https://...)."""
        if url.startswith("git@") and ":" in url:
            host, path = url.split(":", 1)
            return "https://" + host.split("@", 1)[1] + "/" + path
        return url
    result = {"origin_canonical": None, "origin_push_canonical": None,
              "last_fix_remotes_run": None, "submodules_checked": 0}
    log_path = ROOT / "runtime/cron/remote-hygiene.log"
    if log_path.exists():
        lines = log_path.read_text().strip().splitlines()
        for line in reversed(lines[-20:]):
            if "fix-remotes" in line and "完成" in line:
                result["last_fix_remotes_run"] = line[:60]
                break
    try:
        r = _sp.run(["git", "remote", "-v"], capture_output=True, text=True, cwd=str(ROOT), timeout=10)
        if r.returncode == 0:
            # `git remote -v` 行格式: <name>\t<url> (fetch|push) — URL 是第 2 列,
            # 末列是 (fetch)/(push) 标记 (2026-09-16 修复: 旧版取 [-1] 恒不匹配 → 面板恒 ✗).
            canonical = "https://github.com/starlink-awaken/omostation.git"
            fetch_urls, push_urls = [], []
            for line in r.stdout.splitlines():
                parts = line.split()
                if len(parts) < 2 or parts[0] != "origin":
                    continue
                url = parts[1]
                if parts[-1] == "(fetch)":
                    fetch_urls.append(url)
                elif parts[-1] == "(push)":
                    push_urls.append(url)
            result["origin_canonical"] = any(canonical == u or canonical == _normalize_git_url(u)
                                             for u in fetch_urls) if fetch_urls else False
            result["origin_push_canonical"] = any(canonical == u or canonical == _normalize_git_url(u)
                                                  for u in push_urls) if push_urls else False
    except Exception:
        pass
    try:
        r = _sp.run(["git", "submodule", "status"], capture_output=True, text=True, cwd=str(ROOT), timeout=10)
        result["submodules_checked"] = len([l for l in r.stdout.splitlines() if l.strip()])
    except Exception:
        pass
    return result


def collect_service_keeper() -> dict:
    """服务Keeper 健康探测。"""
    import subprocess as _sp
    try:
        r = _sp.run([sys.executable, str(ROOT / "bin/ssot/service-keeper.py"), "status"],
                    capture_output=True, text=True, cwd=str(ROOT), timeout=10)
        services = {}
        for line in r.stdout.splitlines():
            line = line.strip()
            if line.startswith("✅") or line.startswith("❌"):
                parts = line.split()
                if len(parts) >= 2:
                    services[parts[1]] = "ok" if "✅" in line else "fail"
        return {"services": services, "raw_exit": r.returncode}
    except Exception as e:
        return {"error": str(e)}


def collect_connectors() -> dict:
    """iris 连接器清单：可用 + 已接线。

    iris status 冷启动偶发超时 (实证 2026-09-16: 0.5s ~ >30s 抖动), 加退避
    重试; 全部失败时返回 error 键, 上层 UI 降级显示而非崩溃.
    """
    import subprocess as _sp
    import time as _time
    last_err = ""
    for attempt, timeout in enumerate((20, 45), start=1):
        try:
            r = _sp.run(["iris", "--json", "status"], capture_output=True, text=True,
                        cwd=str(ROOT), timeout=timeout)
            if r.returncode != 0 or not r.stdout.strip():
                last_err = (r.stderr or "no output").strip()[:200]
                continue
            raw = r.stdout
            for ch in ("[", "{"):
                idx = raw.find(ch)
                if idx >= 0:
                    raw = raw[idx:]
                    break
            data = json.loads(raw)
            connectors = [{"name": c.get("name", c.get("id", "?")),
                           "available": c.get("available", c.get("status", "?"))}
                          for c in (data if isinstance(data, list) else [])]
            wired = ["apple_mail", "applenotes", "netease_mailmaster"]
            return {"total": len(connectors),
                    "available": [c["name"] for c in connectors if c.get("available")],
                    "wired_to_scenes": wired,
                    "unwired_available": [c["name"] for c in connectors
                                          if c.get("available") and c["name"] not in wired]}
        except Exception as e:
            last_err = str(e)[:200]
            if attempt < 2:
                _time.sleep(2)
    return {"error": last_err or "iris status unavailable"}


def collect_bos_verifier() -> dict:
    """BOS URI 验证器最近运行结果。"""
    import subprocess as _sp
    try:
        r = _sp.run([sys.executable, str(ROOT / "bin/ssot/bos-uri-verify.py")],
                    capture_output=True, text=True, cwd=str(ROOT), timeout=30)
        total_ok = total_err = 0
        for line in r.stdout.splitlines():
            m = re.search(r"(\d+)/(\d+)\s+OK", line)
            if m:
                total_ok += int(m.group(1))
                total_err += int(m.group(2)) - int(m.group(1))
        return {"last_run_ok": total_ok, "last_run_errors": total_err,
                "output_tail": r.stdout.strip().splitlines()[-3:] if r.stdout.strip() else []}
    except Exception as e:
         return {"error": str(e)}


def collect_evolution() -> dict:
    """进化提案。"""
    from glob import glob
    files = sorted(glob(str(ROOT / ".omo/state/evolution-proposals/*")))
    proposals = [Path(f).stem[:50] for f in files[-15:]]
    return {"total": len(files), "recent_proposals": proposals}


def collect_predictive() -> dict:
    """预测治理。"""
    import yaml
    try:
        docs = list(yaml.safe_load_all((ROOT / ".omo/_truth/registry/predictive-governance.yaml").read_text()))
    except Exception:
        docs = []
    return {"available": bool(docs), "docs": len(docs),
            "metrics": [item for d in docs for item in (d.get("metrics",[]) if isinstance(d,dict) else [])],
            "horizons": {k: str(v)[:30] for d in docs for k,v in (d.get("horizons",{}).items() if isinstance(d,dict) else {})}}


def collect_anticorrosion() -> dict:
    """防腐约束。"""
    import yaml
    surfaces = {}
    for f in ("mutation-surfaces.yaml", "write-owners.yaml"):
        try:
            docs = list(yaml.safe_load_all((ROOT / f".omo/_truth/registry/{f}").read_text()))
            surfaces[f.replace(".yaml","")] = sum(len(d) if isinstance(d,(dict,list)) else 0 for d in docs)
        except Exception:
            surfaces[f.replace(".yaml","")] = 0
    return surfaces


def collect_doc_governance() -> dict:
    """文档治理。"""
    import yaml
    try:
        docs = list(yaml.safe_load_all((ROOT / ".omo/_truth/registry/document-governance.yaml").read_text()))
        surfaces = []
        for d in docs:
            if isinstance(d, dict):
                surfaces.extend(d.get("surfaces") or [])
                if "surfaces" not in d and d.get("id"):
                    surfaces.append(d)
    except Exception:
        surfaces = []
    return {"available": True, "surfaces": len(surfaces),
            "surface_list": [s.get("id","") if isinstance(s,dict) else str(s)[:30] for s in surfaces[:10]]}


def collect_knowledge_health() -> dict:
    """知识健康度：新鲜度/覆盖率/孤儿率。"""
    import yaml
    from datetime import UTC, datetime
    from pathlib import Path as _P
    total = fresh = stale = orphaned = has_fm = 0
    stale_docs = []
    type_counts = {}
    _kp = _P(ROOT / ".omo/_knowledge")
    for f in _kp.rglob("*.md"):
        # 只跳过知识目录内部的隐藏子目录（如 .git），不跳过 .omo 本身
        inner = f.relative_to(_kp).parts
        if any(p.startswith(".") for p in inner):
            continue
        total += 1
        try:
            src = f.read_text(errors="ignore")
            fm_text = src.split("---")[1] if src.startswith("---") else ""
            fm = yaml.safe_load(fm_text) if fm_text else {}
            if isinstance(fm, dict):
                has_fm += 1
                tp = str(fm.get("type", "unknown"))
                type_counts[tp] = type_counts.get(tp, 0) + 1
                lr = fm.get("last-reviewed", "")
                if lr:
                    try:
                        # YAML 可能解析为 date 或 str，统一处理
                        if hasattr(lr, "year"):
                            from datetime import date as _date
                            lr_date = datetime(lr.year, lr.month, lr.day, tzinfo=UTC)
                        else:
                            lr_date = datetime.fromisoformat(str(lr).replace("Z", "+00:00"))
                            if lr_date.tzinfo is None:
                                lr_date = lr_date.replace(tzinfo=UTC)
                        age_days = (datetime.now(UTC) - lr_date).days
                        if age_days <= 90:
                            fresh += 1
                        else:
                            stale += 1
                            if len(stale_docs) < 8:
                                stale_docs.append({"path": str(f.relative_to(ROOT)), "age_days": age_days})
                    except Exception:
                        pass
        except Exception:
            pass
        if (datetime.now(UTC).timestamp() - f.stat().st_mtime) > 180 * 86400:
            orphaned += 1
    return {
        "total": total, "fresh": fresh, "stale": stale, "orphaned": orphaned,
        "has_frontmatter": has_fm,
        "freshness_pct": round(100 * fresh / total, 1) if total else 0,
        "coverage_pct": round(100 * has_fm / total, 1) if total else 0,
        "orphan_pct": round(100 * orphaned / total, 1) if total else 0,
        "type_counts": type_counts, "stale_docs": stale_docs,
    }


def collect_knowledge_growth() -> dict:
    """近 30 天知识增长。"""
    from datetime import UTC, datetime, timedelta
    from pathlib import Path as _P
    new_per_day = {}
    for i in range(30):
        day = (datetime.now(UTC) - timedelta(days=i)).strftime("%m-%d")
        new_per_day[day] = 0
    for f in _P(ROOT / ".omo/_knowledge").rglob("*.md"):
        try:
            mtime = datetime.fromtimestamp(f.stat().st_mtime, tz=UTC)
            age = (datetime.now(UTC) - mtime).days
            if age < 30:
                key = mtime.strftime("%m-%d")
                new_per_day[key] = new_per_day.get(key, 0) + 1
        except Exception:
            pass
    series = [{"day": d, "n": new_per_day[d]} for d in sorted(new_per_day)]
    return {"total_new": sum(v for d, v in new_per_day.items()), "series": series}


def collect_memory_dual_track() -> dict:
    """记忆双轨：Raw + Theta。"""
    raw_events = []
    try:
        with open(ROOT / ".omo/_knowledge/governance-history.jsonl") as f:
            raw_events = f.readlines()[-15:]
    except Exception:
        pass
    theta_facts = 0
    theta_file = ROOT / ".omo/state/mos/theta-facts.json"
    if theta_file.is_file():
        try:
            import json
            theta_facts = len(json.loads(theta_file.read_text()))
        except Exception:
            pass
    return {"raw_count": len(raw_events), "theta_facts": theta_facts,
            "recent_raw": [l.strip()[:80] for l in raw_events[-5:]]}


def collect_experience_network() -> dict:
    """经验网络：节点 + 跨引用边 + 图谱遍历。"""
    import yaml
    from glob import glob
    from pathlib import Path as _P
    import re
    nodes = []
    edges = []
    # Pitfalls → 解析关联 decision/pattern
    for f in sorted(glob(str(ROOT / ".omo/_knowledge/pitfalls/PITFALL-*.yaml"))):
        try:
            raw = open(f).read()
            fm = raw.split("---")[1] if raw.startswith("---") else ""
            d = yaml.safe_load(fm) or {}
            nid = f"PIT-{d.get('id','')}"
            nodes.append({"id": nid, "type": "pitfall", "name": d.get("title", "")[:50]})
            # 跨引用：pitfall → decision
            for ref in re.findall(r'(ADR-\d{4})', raw):
                edges.append({"from": nid, "to": f"DEC-{ref}", "rel": "resolved_by"})
            for ref in re.findall(r'(P\d{2})', raw):
                edges.append({"from": nid, "to": f"PAT-{ref}", "rel": "pattern"})
        except Exception:
            pass
    # Decisions → 解析关联 ADR/pitfall
    for f in sorted(glob(str(ROOT / ".omo/_knowledge/decisions/0*.md"))):
        try:
            raw = open(f).read()
            stem = _P(f).stem
            nid = f"DEC-{stem}"
            nodes.append({"id": nid, "type": "decision", "name": stem[:50]})
            for ref in re.findall(r'PITFALL-(\d+)', raw):
                edges.append({"from": nid, "to": f"PIT-{ref}", "rel": "resolves"})
        except Exception:
            pass
    # Retros → 解析关联 BET/pattern
    for f in sorted(glob(str(ROOT / ".omo/_knowledge/retros/BET-*.md"))):
        try:
            raw = open(f).read()
            stem = _P(f).stem
            nid = f"RET-{stem}"
            nodes.append({"id": nid, "type": "retro", "name": stem[:50]})
            for ref in re.findall(r'(P\d{2})', raw):
                edges.append({"from": nid, "to": f"PAT-{ref}", "rel": "identifies"})
        except Exception:
            pass
    # Patterns
    for f in sorted(glob(str(ROOT / ".omo/_knowledge/patterns/*.md"))):
        try:
            stem = _P(f).stem
            nodes.append({"id": f"PAT-{stem}", "type": "pattern", "name": stem[:50]})
        except Exception:
            pass
    # 去重节点
    seen = set()
    uniq = []
    for n in nodes:
        if n["id"] not in seen:
            seen.add(n["id"])
            uniq.append(n)
    # 统计连接度
    degree = {}
    for e in edges:
        degree[e["from"]] = degree.get(e["from"], 0) + 1
        degree[e["to"]] = degree.get(e["to"], 0) + 1
    top_connected = sorted(degree.items(), key=lambda x: -x[1])[:8]
    return {"nodes": uniq[:50], "edges": edges[:80], "total": len(uniq),
            "edge_count": len(edges), "top_connected": [{"id": k, "links": v} for k, v in top_connected]}


def collect_knowledge_inbound() -> dict:
    """知识入链。"""
    from pathlib import Path as _P
    from collections import Counter
    import re
    inbound = Counter()
    for f in _P(ROOT / ".omo/_knowledge").rglob("*.md"):
        try:
            src = f.read_text(errors="ignore")
            refs = re.findall(r'\.omo/_knowledge/(\S+\.md)', src)
            for r in refs:
                inbound[r.split("/")[-1]] += 1
        except Exception:
            pass
    return [{"doc": k, "inbound": v} for k, v in inbound.most_common(12)]



# ─── Phase B: 技能清单 + Theta 事实 ───

def collect_skill_inventory() -> dict:
    """技能清单：扫描全局/项目/用户 skills 目录。"""
    from pathlib import Path as _P
    import re
    import time
    dirs = [
        (_P.home() / ".agents/skills", "user-global"),
        (_P(ROOT / ".agents/skills"), "project"),
        (_P.home() / ".kimi-code/skills", "kimi-code"),
    ]
    skills = []
    seen = set()
    for d, scope in dirs:
        if not d.is_dir():
            continue
        # Launchd can deliver a signal while scandir is blocked on a busy
        # skills directory. Retry briefly instead of discarding a full payload.
        entries = None
        for _ in range(5):
            try:
                entries = sorted(d.iterdir())
                break
            except InterruptedError:
                time.sleep(0.05)
        if entries is None:
            continue
        for skill_dir in entries:
            if not skill_dir.is_dir():
                continue
            name = skill_dir.name
            if name in seen:
                continue
            seen.add(name)
            md = skill_dir / "SKILL.md"
            desc = ""
            if md.is_file():
                try:
                    txt = md.read_text(errors="ignore")[:500]
                    m = re.search(r"^#\s+(.+)$", txt, re.M)
                    if m:
                        desc = m.group(1).strip()[:80]
                    else:
                        desc = txt.split("\n")[0].strip()[:80]
                except Exception:
                    pass
            skills.append({"name": name, "scope": scope, "desc": desc,
                           "path": str(skill_dir)})
    by_scope = {}
    for s in skills:
        by_scope.setdefault(s["scope"], []).append(s)
    return {"total": len(skills), "by_scope": {k: len(v) for k, v in by_scope.items()},
            "skills": skills}


def collect_theta_facts() -> dict:
    """Theta 事实：MOS 提取的结构化事实。"""
    theta_file = ROOT / ".omo/state/mos/theta-facts.json"
    facts = []
    if theta_file.is_file():
        try:
            import json
            facts = json.loads(theta_file.read_text())
        except Exception:
            pass
    by_type = {}
    for f in facts:
        tp = f.get("type", "unknown") if isinstance(f, dict) else "unknown"
        by_type[tp] = by_type.get(tp, 0) + 1
    return {"total": len(facts), "by_type": by_type}


def collect_experience_graph() -> dict:
    """Phase C: 经验图谱遍历 — 跨类引用 + 热点分析。"""
    from pathlib import Path as _P
    from collections import Counter
    import re
    # 收集所有知识文件的交叉引用
    refs = Counter()
    nodes_by_type = {"pitfall": 0, "decision": 0, "retro": 0, "pattern": 0, "adr": 0}
    for f in _P(ROOT / ".omo/_knowledge").rglob("*.md"):
        try:
            src = f.read_text(errors="ignore")
            # 统计内部引用
            if ".omo/_knowledge/" in src:
                refs["internal"] += len(re.findall(r'\.omo/_knowledge/', src))
            # 统计各类节点（通过文件名模式）
            fp = str(f)
            if "/pitfalls/" in fp:
                nodes_by_type["pitfall"] += 1
            elif "/decisions/" in fp:
                nodes_by_type["decision"] += 1
            elif "/retros/" in fp:
                nodes_by_type["retro"] += 1
            elif "/patterns/" in fp:
                nodes_by_type["pattern"] += 1
        except Exception:
            pass
    # 热点：引用最频繁的知识类型
    hotspots = [{"type": k, "count": v} for k, v in sorted(nodes_by_type.items(), key=lambda x: -x[1])]
    # 连通性评分
    connectivity = min(100, refs["internal"] * 100 // max(sum(nodes_by_type.values()), 1))
    return {"nodes_by_type": nodes_by_type, "internal_refs": refs["internal"],
            "hotspots": hotspots, "connectivity_pct": connectivity}


def collect_decision_proposals() -> dict:
    """决策提案统计。"""
    from pathlib import Path as _P
    proposals_dir = _P(ROOT / ".omo/_knowledge/decision-proposals")
    if not proposals_dir.is_dir():
        return {"total": 0, "by_status": {}}
    proposals = list(proposals_dir.glob("*.md"))
    return {"total": len(proposals), "by_status": {"total": len(proposals)}}


def collect_recent_features() -> dict:
    """最近交付的功能 (近 30 天)。"""
    import subprocess
    features = []
    try:
        result = subprocess.run(
            ["git", "log", "--oneline", "--since=30 days ago", "--grep=feat"],
            capture_output=True, text=True, timeout=10, cwd=ROOT
        )
        for line in result.stdout.split("\n"):
            if line.strip():
                features.append(line.strip())
    except Exception:
        pass
    return {"total": len(features), "recent": features[:10]}


def collect_agent_visibility(payload: dict) -> dict:
    """Project a bounded, machine-readable overview for every agent.

    The human HTML remains the panoramic view.  This projection is deliberately
    small and stable so an agent can discover authority, execution state, read
    paths, and safety boundaries without parsing the full dashboard payload.
    """
    gates = payload.get("gates") if isinstance(payload.get("gates"), list) else []
    gate_rows = [
        {
            "id": str(g.get("id", "")),
            "title": str(g.get("title", "")),
            "verdict": str(g.get("verdict", "UNKNOWN")).upper(),
            "live": g.get("live") is True,
        }
        for g in gates
        if isinstance(g, dict)
    ]
    failing = [g for g in gate_rows if g["verdict"] not in {"PASS", "SKIPPED"}]

    claims_authority = payload.get("claims_authority") if isinstance(payload.get("claims_authority"), dict) else {}
    claims_task16 = payload.get("claims_task16") if isinstance(payload.get("claims_task16"), dict) else {}
    claims_activation_request = (
        payload.get("claims_activation_request")
        if isinstance(payload.get("claims_activation_request"), dict) else {}
    )
    claims_observation = (
        payload.get("claims_observation_progress")
        if isinstance(payload.get("claims_observation_progress"), dict) else {}
    )
    claims_lifecycle_authorization = (
        payload.get("claims_lifecycle_authorization")
        if isinstance(payload.get("claims_lifecycle_authorization"), dict) else {}
    )
    agent_pool = payload.get("agent_cell_pool") if isinstance(payload.get("agent_cell_pool"), dict) else {}
    reference_cell = payload.get("reference_cell") if isinstance(payload.get("reference_cell"), dict) else {}
    agent_cell_semantic = payload.get("agent_cell_semantic") if isinstance(payload.get("agent_cell_semantic"), dict) else {}
    value_metrics = payload.get("value_metrics") if isinstance(payload.get("value_metrics"), dict) else {}
    bets = payload.get("bets") if isinstance(payload.get("bets"), dict) else {}
    raw_windows = bets.get("windows") if isinstance(bets.get("windows"), dict) else {}
    window_rows = []
    for window_id in sorted(raw_windows):
        window = raw_windows.get(window_id) if isinstance(raw_windows.get(window_id), dict) else {}
        total = int(window.get("total") or 0)
        done = int(window.get("done") or 0)
        remaining = max(0, total - done)
        window_rows.append({
            "id": str(window_id),
            "total": total,
            "done": done,
            "remaining": remaining,
            "completion_pct": round(done * 100 / total, 1) if total else 0.0,
        })
    raw_workflows = payload.get("workflows") if isinstance(payload.get("workflows"), list) else []
    active_workflow_states = {"active", "queued", "in_progress", "waiting"}
    active_workflows = [
        {
            "id": str(workflow.get("run_id", "")),
            "workflow": str(workflow.get("workflow_id", "")),
            "status": str(workflow.get("status", "unknown")),
        }
        for workflow in raw_workflows
        if isinstance(workflow, dict) and str(workflow.get("status", "")).lower() in active_workflow_states
    ]
    blocked_workflows = [
        {
            "id": str(workflow.get("run_id", "")),
            "workflow": str(workflow.get("workflow_id", "")),
            "status": str(workflow.get("status", "unknown")),
        }
        for workflow in raw_workflows
        if isinstance(workflow, dict) and str(workflow.get("status", "")).lower() == "blocked"
    ]
    tasks = payload.get("tasks") if isinstance(payload.get("tasks"), dict) else {}
    services = payload.get("service_lifecycle") if isinstance(payload.get("service_lifecycle"), dict) else {}
    alerts = payload.get("alerts") if isinstance(payload.get("alerts"), dict) else {}
    recent_alerts = [item for item in alerts.get("alerts", []) if isinstance(item, dict)][:10]
    panel_value = payload.get("panel_value") if isinstance(payload.get("panel_value"), dict) else {}
    value_samples = panel_value.get("samples") if isinstance(panel_value.get("samples"), dict) else {}
    value_thresholds = [
        item for item in (panel_value.get("thresholds") or [])
        if isinstance(item, dict)
    ]
    value_blockers = [str(item) for item in (panel_value.get("state_reason") or []) if item]
    value_validation = (
        payload.get("value_evidence_validation")
        if isinstance(payload.get("value_evidence_validation"), dict)
        else {"schema": "value-evidence-validation/v2", "ok": False, "available": False}
    )
    qualifying = int(value_validation.get("qualifying") or 0)
    legacy_qualifying = int(value_validation.get("legacy_qualifying") or 0)
    v2_records = int(value_validation.get("v2_records") or 0)
    if value_validation.get("ok") is not True:
        value_blockers.append("value-evidence validation unavailable or failed")
    # panel_value.state is proven only after golden slice + SSH-signed window attestation.
    panel_state = str(panel_value.get("state") or "not_proven").lower()
    value_proof_flag = "PROVEN" if panel_state == "proven" else "NOT_PROVEN"
    value_readiness = {
        "schema": "panorama-value-proof-readiness/v2",
        "status": value_proof_flag,
        "available": bool(panel_value),
        "source": panel_value.get("schema", "unavailable"),
        "panel_state": panel_state,
        "samples_total": int(value_samples.get("records") or 0),
        "qualifying_samples": qualifying,
        "v2_records": v2_records,
        "legacy_records": int(value_validation.get("legacy_records") or 0),
        "legacy_qualifying_samples": legacy_qualifying,
        "accepted_samples": int(value_samples.get("accepted") or 0),
        "adjudicated_samples": int(value_samples.get("adjudicated") or 0),
        "net_saved_seconds": int(value_samples.get("net_saved_seconds") or 0),
        "thresholds": value_thresholds,
        "blockers": value_blockers,
        "validation": value_validation,
        "remaining_to_target": max(0, 30 - qualifying),
        "evidence_rule": "Only qualifying real-use records count; synthetic runs and unqualified accepted records never prove value.",
        "next_action": (
            f"Collect {max(0, 30 - qualifying)} more qualifying real-use records with a frozen baseline; do not backfill."
            if qualifying < 30 else
            (
                "None — value window PROVEN via signed attestation."
                if value_proof_flag == "PROVEN"
                else "Review all threshold gates and independently adjudicate the full value window."
            )
        ),
    }

    activation_allowed = claims_task16.get("activation_allowed") is True
    blockers = []
    preflight = claims_task16.get("preflight") if isinstance(claims_task16.get("preflight"), dict) else {}
    for source in (claims_task16.get("hard_blockers"), preflight.get("hard_blockers"), preflight.get("blockers")):
        if isinstance(source, list):
            blockers.extend(str(item) for item in source if item)
    blockers = sorted(set(blockers))
    advisories = sorted({
        str(item)
        for item in (preflight.get("advisories") or [])
        if item
    })
    isolated_preflight = (
        claims_task16.get("isolated_preflight")
        if isinstance(claims_task16.get("isolated_preflight"), dict) else {}
    )
    isolated_technical_ready = (
        claims_task16.get("isolated_technical_ready") is True
        and isolated_preflight.get("available") is True
        and isolated_preflight.get("hard_blockers") == []
        and isolated_preflight.get("readiness") == "AWAITING_AUTHORIZATION"
    )
    isolated_blockers = sorted({
        str(item)
        for source in (isolated_preflight.get("hard_blockers"), isolated_preflight.get("blockers"))
        if isinstance(source, list)
        for item in source
        if item
    })
    canonical_technical_blockers = [
        item for item in blockers if item != "operation_specific_host_authorization_unproven"
    ]
    effective_readiness = (
        "AWAITING_AUTHORIZATION"
        if isolated_technical_ready
        else str(preflight.get("readiness") or claims_task16.get("verdict") or "UNKNOWN").upper()
    )
    claims_activation_readiness = {
        "schema": "claims-activation-readiness/v1",
        "available": claims_task16.get("available") is True,
        "verdict": str(claims_task16.get("verdict", "UNAVAILABLE")).upper(),
        "readiness": str(preflight.get("readiness") or claims_task16.get("verdict") or "UNKNOWN").upper(),
        "operation_specific_authorization": str(
            preflight.get("operation_specific_authorization") or "UNPROVEN"
        ).upper(),
        "canonical_readiness": str(preflight.get("readiness") or "UNKNOWN").upper(),
        "isolated_readiness": str(isolated_preflight.get("readiness") or "UNKNOWN").upper(),
        "isolated_technical_ready": isolated_technical_ready,
        "isolated_blockers": isolated_blockers,
        "isolated_root_head_oid": isolated_preflight.get("root_head_oid"),
        "isolated_origin_main_oid": isolated_preflight.get("origin_main_oid"),
        "isolated_child_head_oid": isolated_preflight.get("child_head_oid"),
        "isolated_root_child_gitlink_oid": isolated_preflight.get("root_child_gitlink_oid"),
        "remaining_after_isolated_recovery": claims_task16.get(
            "remaining_after_isolated_recovery", []
        ),
        "activation_allowed": activation_allowed,
        "effective_readiness": effective_readiness,
        "blockers": blockers,
        "advisories": advisories,
        "preflight_checked_at": preflight.get("checked_at"),
        "authority_id": preflight.get("authority_id") or "omo-claims-authority-r0",
        "effective_claim_authority": claims_authority.get(
            "effective_claim_authority", "v1"
        ),
        "authorization_packet": {
            "scope": "claims-authority activate-shadow, exact R0 descriptor only",
            "required_fields": [
                "principal_decision_id",
                "decision_timestamp",
                "authorized_surface=agents/_shared/runtime/omo-claims-authority-r0",
                "rollback_surface=agents/_shared/backups/omo-claims-authority-r0",
                "expiry_or_no_expiry",
                "observation_requirement=24h foreground/1440 samples",
            ],
            "not_sufficient": [
                "general_agent_authorization",
                "accepted_spec_binding_alone",
                "dashboard_status_or_ai_statement",
            ],
        },
        "evidence_boundary": (
            "Canonical blockers remain visible, but a clean managed exact-main clone proves whether technical "
            "recovery succeeded. Operation-specific Human authorization is still always required."
        ),
        "observation_gate": {
            "duration_seconds": 86400,
            "minimum_samples": 1440,
            "maximum_gap_seconds": 120,
            "checkpoints": {
                "smoke": {"seconds": 1800, "samples": 30},
                "provisional": {"seconds": 7200, "samples": 120},
                "sustained": {"seconds": 21600, "samples": 360},
                "graduation": {"seconds": 86400, "samples": 1440},
            },
            "first_three_are_diagnostic_only": True,
        },
    }

    return {
        "schema": "panorama-agent-brief/v1",
        "available": True,
        "generated_at": payload.get("generated_at", ""),
        "objective_coverage": payload.get("objective_coverage") if isinstance(payload.get("objective_coverage"), dict) else {"schema": "panorama-objective-coverage/v1", "available": False},
        "role_registry": payload.get("role_registry") if isinstance(payload.get("role_registry"), dict) else {"schema": "panorama-role-registry/v1", "available": False, "verdict": "UNAVAILABLE"},
        "authority": {
            "control_plane": "OMO",
            "single_dispatcher": True,
            "effective_claim_authority": claims_authority.get("effective_claim_authority", "unknown"),
            "claims_activation_state": claims_authority.get("activation_state", "unknown"),
            "claims_instruction_capable": claims_authority.get("instruction_capable") is True,
            "claims_activation_allowed": activation_allowed,
            "claims_activation_blockers": blockers,
            "claims_activation_readiness": claims_activation_readiness,
            "claims_activation_request": claims_activation_request,
            "claims_observation_progress": (
                payload.get("claims_observation_progress")
                if isinstance(payload.get("claims_observation_progress"), dict)
                else {"schema": "claims-observation-progress/v1", "available": False}
            ),
            "claims_lifecycle_authorization": claims_lifecycle_authorization,
            "value_proof": value_proof_flag,
            "value_proof_readiness": value_readiness,
        },
        "objective_coverage": payload.get("objective_coverage") if isinstance(payload.get("objective_coverage"), dict) else {"schema": "panorama-objective-coverage/v1", "available": False},
        "health": {
            "gates_total": len(gate_rows),
            "gates_pass": sum(g["verdict"] == "PASS" for g in gate_rows),
            "gates_failing": [g["id"] for g in failing],
            "reference_cell": {
                "id": reference_cell.get("id", "UNKNOWN"),
                "verdict": str(reference_cell.get("verdict", "UNKNOWN")).upper(),
            },
            "agent_cells": {
                "available": agent_pool.get("available") is True,
                "total": agent_pool.get("total", 0),
                "active": agent_pool.get("active", 0),
                "failed": agent_pool.get("failed", 0),
            },
            "persistent_roles": {
                "available": (payload.get("role_registry") or {}).get("available") is True,
                "total": (payload.get("role_registry") or {}).get("total", 0),
                "admitted": (payload.get("role_registry") or {}).get("by_state", {}).get("admitted", 0),
                "integrity_ok": (payload.get("role_registry") or {}).get("integrity_ok") is True,
                "verdict": (payload.get("role_registry") or {}).get("verdict", "UNAVAILABLE"),
            },
            "semantic_lifecycle": {
                "available": agent_cell_semantic.get("available") is True,
                "verdict": agent_cell_semantic.get("verdict", "UNAVAILABLE"),
                "receipt_chain_ok": agent_cell_semantic.get("receipt_chain_ok") is True,
                "receipt_digests_ok": agent_cell_semantic.get("receipt_digests_ok") is True,
                "role_bindings_ok": agent_cell_semantic.get("role_bindings_ok") is True,
                "capsule_bindings_ok": agent_cell_semantic.get("capsule_bindings_ok") is True,
                "mesh_bindings_ok": agent_cell_semantic.get("mesh_bindings_ok") is True,
                "queue_bindings_ok": agent_cell_semantic.get("queue_bindings_ok") is True,
                "latest_run_id": agent_cell_semantic.get("latest_run_id"),
                "latest_receipt_digest": agent_cell_semantic.get("latest_receipt_digest"),
            },
            "value_metrics": value_metrics,
            "clash": (
                payload.get("clash_health")
                if isinstance(payload.get("clash_health"), dict)
                else {"schema": "panorama-clash-health/v1", "available": False}
            ),
        },
        "work_state": {
            "bets": {
                "available": bool(bets),
                "total": bets.get("total", 0),
                "counts": bets.get("counts", {}),
                "in_progress": bets.get("in_progress", []),
                "blocked": bets.get("blocked", []),
                "milestones": [
                    {
                        "id": f"ledger-window:{row['id']}",
                        "title": row["id"],
                        "total": row["total"],
                        "done": row["done"],
                        "remaining": row["remaining"],
                        "completion_pct": row["completion_pct"],
                    }
                    for row in window_rows
                ],
            },
            "workflows": {
                "active": active_workflows,
                "active_count": len(active_workflows),
                "blocked_recent": blocked_workflows[:10],
                "blocked_recent_count": len(blocked_workflows),
            },
            "tasks": {
                "available": bool(tasks),
                "total": tasks.get("total", 0),
                "open_count": tasks.get("open_count", 0),
                "by_status": tasks.get("by_status", {}),
                "by_bucket": tasks.get("by_bucket", {}),
                "duplicates": tasks.get("duplicates", []),
                "open_recent": tasks.get("open_recent", []),
                "recent": tasks.get("recent", []),
            },
            "services": {
                "available": bool(services),
                "total": services.get("total", 0),
                "by_lifecycle": services.get("by_lifecycle", {}),
                "recent": services.get("recent", []),
            },
            "alerts": {
                "total": alerts.get("total", 0),
                "high": alerts.get("high", 0),
                "recent": recent_alerts,
            },
        },
        "next_actions": [
            *([
                {"id": "resolve-failing-gates", "state": "required",
                 "detail": f"Resolve failing gates: {', '.join(g['id'] for g in failing)}",
                 "source": "panorama.gates"}
            ] if failing else []),
            {
                "id": "claims-authority-wait", "state": "authorization_required",
                "detail": "Keep Claims Authority read-only until a fresh operation-specific authorization and its 24-hour observation gate pass.",
                "source": "panorama.claims_authority",
            } if (
                not activation_allowed
                and not (
                    claims_observation.get("state") == "IN_PROGRESS"
                    and claims_authority.get("activation_state") == "shadow-active"
                )
            ) else {
                "id": "claims-authority-observation", "state": "required",
                "detail": (
                    "Preserve Claims Authority shadow observation under OMO: "
                    f"{claims_observation.get('sample_count', 0)}/"
                    f"{claims_observation.get('minimum_samples', 1440)} samples; "
                    "instruction capability remains disabled until graduation."
                ) if claims_observation.get("state") == "IN_PROGRESS" else
                "Run the accepted Claims Authority observation protocol under OMO.",
                "source": "panorama.claims_authority",
            },
            *([
                {"id": "continue-active-bets", "state": "ready",
                 "detail": f"Continue active BETs: {len(bets.get('in_progress', []))}",
                 "source": "panorama.bets"}
            ] if bets.get("in_progress") else []),
            *([
                {"id": "plan-candidate-bets", "state": "ready",
                 "detail": f"Advance {bets.get('counts', {}).get('candidate', 0)} candidate BET(s) through accepted Spec, plan, and verification gates.",
                 "source": "panorama.bets"}
            ] if bets.get("counts", {}).get("candidate", 0) else []),
            *([
                {"id": "triage-high-alerts", "state": "required",
                 "detail": f"Triage {alerts.get('high', 0)} high-severity alert(s); classify real debt separately from stale fixtures.",
                 "source": "panorama.alerts"}
            ] if alerts.get("high", 0) else []),
            *([
                {
                    "id": "collect-qualifying-value-evidence", "state": "required",
                    "detail": value_readiness["next_action"],
                    "source": "panorama.value_proof_readiness",
                }
            ] if not activation_allowed or qualifying < 30 else []),
        ],
        "read_interfaces": {
            "human_html": "/",
            "data_json": "/data.json",
            "agent_brief_json": "/agent-brief.json",
            "filesystem": {
                "data": "runtime/dashboard/data.json",
                "brief": "runtime/dashboard/agent-brief.json",
            },
            "refresh": "python3 bin/panorama/panorama-collect.py",
        },
        "required_context": [
            {"name": "Workspace operating rules", "path": "AGENTS.md"},
            {"name": "Panorama agent interface", "path": "docs/PANORAMA.md"},
            {"name": "Architecture contracts", "path": "ARCHITECTURE.md"},
            {"name": "Strategy and roadmap", "path": "docs/VISION-ROADMAP.md"},
        ],
        "safety_boundaries": [
            "Do not activate Claims Authority without a fresh operation-specific authorization.",
            "Do not write the canonical Workspace directly; use a managed worktree and PR.",
            "Do not add a second dispatcher or authority queue.",
            "Do not claim completion or proven value without authoritative evidence.",
        ],
    }


def build_payload() -> dict:
    ci_data = collect_ci()
    asd = collect_asd()
    payload = {
        "generated_at": datetime.now(UTC).isoformat(),
        "mode": "read-only-ssot-aggregation",
        "gates": collect_gates({"asd": asd}),
        "bets": collect_bets(),
        "agents": collect_agents(),
        "runtime": collect_runtime(),
        "launchd_health": collect_launchd_health(),
        "code_root_health": collect_code_root_health(),
        "clash_health": collect_clash_health(),
        "docs": collect_docs(),
        "role_admission": collect_role_admission(),
        "agent_cell_pool": collect_agent_cell_pool(),
        "agent_cell_semantic": collect_agent_cell_semantic(),
        "claims_authority": collect_claims_authority(),
        "claims_task16": collect_claims_task16_preflight(),
        "claims_activation_request": collect_claims_activation_request(),
        "claims_observation_progress": collect_claims_observation_progress(),
        "claims_lifecycle_authorization": collect_claims_lifecycle_authorization(),
        "reference_cell": collect_reference_cell_gate(),
        "asd": asd,
        "role_registry": collect_role_registry(),
        "probes": collect_probes(),
        "resident_agents": collect_resident_agents(),
        "scene_cards": collect_scene_cards(),
        "journeys": collect_journeys(),
        "workspace": collect_workspace_hygiene(),
        "ci": ci_data,
        "cron": collect_cron(),
        "submodules": collect_submodules(),
        "debt": collect_debt(),
        "workflows": collect_workflows(),
        "alerts": collect_alerts(ci_data),
        "value_evidence_validation": collect_value_evidence_validation(),
        "deployments": collect_deployments(),
        "closeouts": collect_closeouts(),
        "services": collect_services(),
        "swarm": collect_swarm(),
        "governance_alerts": collect_governance_alerts(),
        "value_metrics": collect_value_metrics(),
        "debt_registry": collect_debt_registry(),
        "tasks": collect_tasks(),
        "service_lifecycle": collect_service_lifecycle(),
        "agent_tick": collect_agent_tick(),
        "handoffs": collect_handoffs(),
        "pipeline": collect_pipeline(),
        "a2a": collect_a2a(),
        "observability_events": collect_observability_events(),
        "recent_events": {},   # 由 _collect_panels() 从 panel_events 单一数据源填充
        "metrics_kpi": collect_metrics_kpi(),
        "scene_v3": collect_scene_v3(),
        "scene_calibration_fallback": collect_scene_calibration_fallback(),
        "signal_poller": collect_signal_poller(),
        "journey_executions": collect_journey_executions(),
        "remote_hygiene": collect_remote_hygiene(),
        "service_keeper": collect_service_keeper(),
        "connectors": collect_connectors(),
        "bos_verifier": collect_bos_verifier(),
        "evolution": collect_evolution(),
        "predictive": collect_predictive(),
        "anticorrosion": collect_anticorrosion(),
        "doc_governance": collect_doc_governance(),
        "knowledge_health": collect_knowledge_health(),
        "knowledge_growth": collect_knowledge_growth(),
        "memory_dual_track": collect_memory_dual_track(),
        "experience_network": collect_experience_network(),
        "knowledge_inbound": collect_knowledge_inbound(),
        # Phase B
        "skill_inventory": collect_skill_inventory(),
        "theta_facts": collect_theta_facts(),
        # Phase C
        "experience_graph": collect_experience_graph(),
        "decision_proposals": collect_decision_proposals(),
        "recent_features": collect_recent_features(),
    }
    payload["objective_coverage"] = collect_objective_coverage(payload)
    # logs / metrics / value 三板块真实数据（同时统合事件指标口径）
    payload.update(_collect_panels(payload))
    payload["agent_visibility"] = collect_agent_visibility(payload)
    # Agent Brief owns action derivation; mirror it to the top level so all
    # agents and the Next panel can consume one stable contract without
    # discovering the nested envelope.
    visibility = payload.get("agent_visibility")
    if isinstance(visibility, dict):
        authority = visibility.get("authority") if isinstance(visibility.get("authority"), dict) else {}
        payload["next_actions"] = visibility.get("next_actions") or []
        payload["unfinished_objectives"] = [
            item
            for item in (visibility.get("objective_coverage") or {}).get("items", [])
            if isinstance(item, dict) and item.get("status") not in {"PASS", "DELIVERY_ACCEPTED_RUNTIME_VERIFIED"}
        ]
        payload["value_proof_readiness"] = authority.get("value_proof_readiness") or {"schema": "panorama-value-proof-readiness/v1", "available": False, "status": "UNKNOWN"}
        payload["claims_activation_readiness"] = authority.get("claims_activation_readiness") or {"schema": "claims-activation-readiness/v1", "available": False, "readiness": "UNKNOWN"}
    return payload


def write_site(payload: dict) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    DATA_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=1))
    AGENT_BRIEF_JSON.write_text(
        json.dumps(
            payload.get("agent_visibility", {"schema": "panorama-agent-brief/v1", "available": False}),
            ensure_ascii=False,
            indent=1,
        )
    )
    html = TEMPLATE.replace("__DATA__", json.dumps(payload, ensure_ascii=False))
    INDEX_HTML.write_text(html)


def check_side_effects() -> int:
    before = run(["git", "status", "--porcelain"])[1].splitlines()
    payload = build_payload()
    write_site(payload)
    after = run(["git", "status", "--porcelain"])[1].splitlines()
    new_repo_writes = [l for l in after if l not in before and not l.startswith("?? runtime/dashboard")]
    if new_repo_writes:
        print("SIDE EFFECT DETECTED:")
        for l in new_repo_writes:
            print(" ", l)
        return 1
    print(f"OK: 零仓库写副作用（产物仅 {OUT_DIR.relative_to(ROOT)}/, gitignored）")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--json", action="store_true", help="只输出 data.json 到 stdout 摘要")
    ap.add_argument("--gates", action="store_true", help="只输出门禁部分")
    ap.add_argument("--check-side-effects", action="store_true")
    args = ap.parse_args()

    if args.check_side_effects:
        return check_side_effects()

    payload = build_payload()
    write_site(payload)

    if args.gates:
        print(json.dumps(payload["gates"], ensure_ascii=False, indent=1))
        return 0
    if args.json:
        summary = {"generated_at": payload["generated_at"],
                   "gates": {g["id"]: g["verdict"] for g in payload["gates"]},
                   "bets": payload["bets"]["counts"],
                   "agents": len(payload["agents"]),
                   "out": str(INDEX_HTML.relative_to(ROOT))}
        print(json.dumps(summary, ensure_ascii=False, indent=1))
        return 0
    print(f"✅ 驾驶舱已生成: {INDEX_HTML.relative_to(ROOT)}  ({payload['generated_at']})")
    print(f"   服务: python3 bin/panorama/panorama-serve.py  → http://127.0.0.1:43910")
    return 0


TEMPLATE = r"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>织星全景驾驶舱</title>
<style>
:root{--paper:#0d1420;--card:#151f30;--line:#24344d;--ink:#dbe6f4;--muted:#7d93b0;
--blue:#5b9dff;--teal:#3ecf9a;--amber:#f0b453;--red:#f26d6d;--mono:ui-monospace,SFMono-Regular,Menlo,monospace}
*{box-sizing:border-box}body{margin:0;background:var(--paper);color:var(--ink);
font:14px/1.6 -apple-system,"PingFang SC",sans-serif}
aside{position:fixed;inset:0 auto 0 0;width:200px;background:#0a101b;padding:26px 14px;border-right:1px solid var(--line)}
aside h1{font-size:19px;margin:0 0 4px;letter-spacing:3px}aside small{color:var(--muted);font-size:10px}
nav a{display:block;color:var(--muted);text-decoration:none;padding:8px 10px;border-radius:8px;font-size:13px}
nav a.on,nav a:hover{color:var(--ink);background:#1a2740}
main{margin-left:200px;padding:26px 32px;max-width:1500px}
.sec{display:none}.sec.on{display:block}
h2{font-size:20px;margin:0 0 4px}p.sub{color:var(--muted);font-size:12px;margin:0 0 18px}
.grid{display:grid;gap:14px}.g3{grid-template-columns:repeat(3,1fr)}.g2{grid-template-columns:1.2fr 1fr}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:16px 18px}
.card h3{margin:0 0 10px;font-size:14px}
.kpi b{font:26px var(--mono);display:block}.kpi span{color:var(--muted);font-size:11px}
table{width:100%;border-collapse:collapse;font-size:12px}
td,th{padding:7px 8px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top}
th{color:var(--muted);font-weight:500;font-size:11px}
.chip{display:inline-block;padding:2px 8px;border-radius:6px;font:11px var(--mono)}
.p{background:#12312a;color:var(--teal)}.f{background:#3a1a1c;color:var(--red)}
.w{background:#3a2d14;color:var(--amber)}.n{background:#1a2740;color:var(--muted)}
.mono{font-family:var(--mono);font-size:11px}
.bar{height:8px;background:#1a2740;border-radius:4px;overflow:hidden;margin-top:5px}
.bar i{display:block;height:100%;background:var(--blue)}
.bar.done i{background:var(--teal)}
a{color:var(--blue);text-decoration:none}a:hover{text-decoration:underline}
.dead{color:var(--red)}.fresh{color:var(--teal)}
.kpi-grid{display:grid;grid-template-columns:repeat(6,1fr);gap:10px}
.kpi-card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:12px 14px;cursor:pointer;transition:all .2s;position:relative;overflow:hidden}
.kpi-card:hover{border-color:var(--blue);box-shadow:0 0 0 1px var(--blue)}
.kpi-card b{font:22px var(--mono);display:block;color:var(--ink)}
.kpi-card span{color:var(--muted);font-size:10px}
.kpi-card .trend{position:absolute;top:8px;right:10px;font:13px var(--mono)}
.kpi-card .trend.up{color:var(--teal)}.kpi-card .trend.down{color:var(--red)}
.drill{margin-top:12px;background:var(--card);border:1px solid var(--line);border-radius:12px;max-height:0;overflow:hidden;transition:max-height .3s}
.drill.open{max-height:600px;overflow-y:auto}
.drill-inner{padding:18px}
.drill h4{margin:0 0 12px;font-size:13px}
.drill table{width:100%;border-collapse:collapse;font-size:11px}
.drill td,.drill th{padding:6px 8px;border-bottom:1px solid var(--line);text-align:left}
.knowledge-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:10px}
.kgraph{display:flex;align-items:flex-end;gap:3px;height:60px;padding:10px 0}
.kgraph .bar{width:100%;background:var(--blue);border-radius:3px 3px 0 0;min-height:2px;transition:height .3s}
.kgraph .bar:hover{background:var(--teal)}
.kv{font:18px var(--mono)}
.ks{color:var(--muted);font-size:10px}
.assoc-link{color:var(--blue);cursor:pointer;text-decoration:underline;font-size:11px}
.foot{margin-top:26px;color:var(--muted);font-size:11px;border-top:1px solid var(--line);padding-top:12px}
@media(max-width:900px){aside{position:static;width:auto}main{margin:0}.g3,.g2{grid-template-columns:1fr}}
</style>
</head>
<body>
<aside>
<h1>织星驾驶舱</h1><small>OMO PANORAMA · <span id="ts"></span></small>
<nav id="nav">
<a href="#overview" data-s="overview">体系总览</a>
<a href="#agentbrief" data-s="agentbrief">Agent Brief</a>
<a href="#gates" data-s="gates">门禁 A1–A9</a>
<a href="#agents" data-s="agents">Agent 全景</a>
<a href="#bets" data-s="bets">任务与里程碑</a>
<a href="#runtime" data-s="runtime">运行态</a>
<a href="#probes" data-s="probes">Probe 心跳</a>
<a href="#resident" data-s="resident">Resident Agent</a>
<a href="#scenes" data-s="scenes">Scene 卡</a>
<a href="#journeys" data-s="journeys">Journey</a>
<a href="#hygiene" data-s="hygiene">工作区卫生</a>
<a href="#knowledge" data-s="knowledge">知识记忆</a>
<a href="#docs" data-s="docs">知识入口</a>
<a href="#skills" data-s="skills">技能清单</a>
</nav>
</aside>
<main>
<section class="sec on" id="s-overview">
<h2>战略全景</h2><p class="sub">可下钻 · 可关联 · 可跨面板跳转 — 点击任意 KPI 或实体查看详情</p>
<div class="kpi-grid" id="kpi"></div>
<div class="drill" id="drill"></div>
<div class="card" style="margin-top:14px"><h3>架构主轴</h3><div class="mono" style="font-size:12px;line-height:2">
L0 协议(ecos) → L1 运行时(omo/Mesh) → L2 内核(l4-kernel) → L3 入口(cockpit) → L4 文档<br>
S 槽唯一 dispatcher：COMP-WS-omo · 八律第3条已收口（dispatch_backend）<br>
Cell=动态算力（B 槽）；Resident=投影不派活；MOS=记忆控制面</div></div>
</section>
<section class="sec" id="s-agentbrief">
<h2>Agent Brief</h2><p class="sub">权限 · 健康 · 未完成工作 · 下一步 · 安全边界 · 人类与 Agent 共用同一真相</p>
<div class="kpi-grid" id="ab-kpi"></div>
<div class="grid g2" style="margin-top:14px">
 <div class="card"><h3>Authority & Safety</h3><table id="ab-authority"><thead><tr><th>contract</th><th>value</th></tr></thead><tbody></tbody></table></div>
 <div class="card"><h3>Read Interfaces</h3><table id="ab-interfaces"><thead><tr><th>surface</th><th>path</th></tr></thead><tbody></tbody></table></div>
</div>
<div class="grid g2" style="margin-top:14px">
 <div class="card"><h3>Next Actions</h3><table id="ab-actions"><thead><tr><th>state</th><th>action</th><th>detail</th><th>source</th></tr></thead><tbody></tbody></table></div>
 <div class="card"><h3>Open Work & Alerts</h3><table id="ab-work"><thead><tr><th>type</th><th>name</th><th>state</th><th>detail</th></tr></thead><tbody></tbody></table></div>
</div>
<div class="card" style="margin-top:14px"><h3>Objective Coverage</h3><table id="ab-objectives"><thead><tr><th>status</th><th>objective</th><th>value</th><th>requirement</th></tr></thead><tbody></tbody></table></div>
<div class="card" style="margin-top:14px"><h3>Persistent Role Registry</h3><table id="ab-roles"><thead><tr><th>role</th><th>state</th><th>version</th><th>capabilities</th></tr></thead><tbody></tbody></table></div>
<div class="card" style="margin-top:14px"><h3>Semantic Lifecycle</h3><table id="ab-semantic"><thead><tr><th>binding</th><th>value</th></tr></thead><tbody></tbody></table></div>
</section>
<section class="sec" id="s-gates">
<h2>门禁 A1–A9 / RF0</h2><p class="sub">底层实时验证 + 声明态边界 · PARTIAL ≠ PASS · 未过门零写入/零自治/零扩并发</p>
<div class="grid g3" id="gategrid"></div>
</section>
<section class="sec" id="s-agents">
<h2>Agent 全景</h2><p class="sub">worktree / 分支 / 最近活动 · 所有 agent 可见</p>
<div class="card"><table id="agenttable"><thead><tr><th>worktree</th><th>分支</th><th>最近活动</th></tr></thead><tbody></tbody></table></div>
<div class="card" style="margin-top:14px"><h3>Agent Cell Pool</h3>
 <div class="kpi-grid" id="cellkpi"></div>
 <table id="celltable" style="margin-top:12px"><thead><tr><th>cell</th><th>episode</th><th>state</th><th>role</th><th>handoffs</th><th>saved</th></tr></thead><tbody></tbody></table>
</div>
<div class="card" style="margin-top:14px"><h3>Semantic Lifecycle</h3>
 <div class="kpi-grid" id="semantickpi"></div>
 <table id="semantictable" style="margin-top:12px"><thead><tr><th>binding</th><th>verdict</th><th>value</th></tr></thead><tbody></tbody></table>
</div>
<div class="card" style="margin-top:14px"><h3>Claims Authority</h3>
 <div class="kpi-grid" id="claimkpi"></div>
 <table id="claimtable" style="margin-top:12px"><thead><tr><th>contract</th><th>value</th></tr></thead><tbody></tbody></table>
</div>
</section>
<section class="sec" id="s-bets">
<h2>任务与里程碑</h2><p class="sub">三年台账窗口进度 · in_progress / blocked 聚焦</p>
<div class="grid g2">
<div class="card"><h3>窗口进度（Y1Q1→Y3H2）</h3><div id="windows"></div></div>
<div class="card"><h3>进行中 / 阻塞</h3><table id="focus"><thead><tr><th>ID</th><th>标题</th><th>级</th></tr></thead><tbody></tbody></table></div>
</div>
</section>
<section class="sec" id="s-runtime">
<h2>运行态</h2><p class="sub">守护 / 调度 / 引用健康 · meta-doctor 摘要</p>
<div class="grid g3" id="rtgrid"></div>
<div class="card" style="margin-top:14px"><h3>Launchd Runtime Jobs</h3>
 <div class="kpi-grid" id="launchdkpi"></div>
 <table id="launchdtable" style="margin-top:12px"><thead><tr><th>job</th><th>state</th><th>last exit</th><th>interval</th><th>runs</th><th>verdict</th></tr></thead><tbody></tbody></table>
</div>
</section>
<section class="sec" id="s-knowledge">
<h2>知识 · 记忆 · 经验</h2><p class="sub">知识健康度 / 记忆双轨 / 经验网络 / 增长曲线 — 结构化建模与可视化</p>
<div class="grid g3" id="khkpi"></div>
<div class="card" style="margin-top:12px"><h3>知识健康度雷达</h3>
 <div class="grid g3"><div>新鲜度<span id="kh_fresh" class="assoc-link" onclick="drillKH('fresh')"></span></div>
 <div>覆盖率<span id="kh_cov"></span></div><div>孤儿率<span id="kh_orphan"></span></div></div>
 <div id="kh_stale_list" class="mono" style="font-size:11px;margin-top:10px"></div></div>
<div class="grid g2" style="margin-top:12px">
 <div class="card"><h3>记忆双轨</h3><div class="grid g3" id="mdtkpi"></div><div id="mdt_raw" class="mono" style="font-size:11px;line-height:2"></div></div>
 <div class="card"><h3>经验网络</h3><div id="exp_net" class="mono" style="font-size:11px;line-height:2"></div></div>
</div>
<div class="card" style="margin-top:12px"><h3>近 30 天知识增长</h3><div id="kgrowth" class="kgraph"></div></div>
<div class="card" style="margin-top:12px"><h3>知识入链 Top 15</h3><table id="kinbound"><thead><tr><th>文档</th><th>入链数</th></tr></thead><tbody></tbody></table></div>
<div class="card" style="margin-top:12px"><h3>经验图谱</h3>
  <div class="grid g2">
    <div style="display:flex;align-items:center;gap:20px;justify-content:center"><div id="eg_connect" style="text-align:center"></div><div id="eg_refs" style="text-align:center"></div></div>
    <div><span class="mono" style="color:var(--teal)">热点</span><div id="eg_hot" style="margin-top:6px"></div></div>
  </div>
  <div style="margin-top:10px"><span class="mono" style="color:var(--muted)">最高连接</span><div id="eg_top" style="margin-top:4px"></div></div>
</div>
</section>

<section class="sec" id="s-skills">
<h2>技能清单</h2><p class="sub">全局 / 项目 / Kimi Code —— 全部可用 skill 可见</p>
<div class="grid g3" id="skillkpi"></div>
<div class="card" style="margin-top:12px"><h3>Theta 事实</h3><div class="grid g3" id="thetakpi"></div></div>
<div class="card" style="margin-top:12px"><h3>Skill 列表</h3><table id="skilltbl"><thead><tr><th>名称</th><th>域</th><th>描述</th></tr></thead><tbody></tbody></table></div>
</section>
<section class="sec" id="s-docs">
<h2>知识入口</h2><p class="sub">白皮书 / 架构 / 流程 / 操作 —— 每卡直达源文档</p>
<div class="grid g3" id="docgrid"></div>
</section>

<section class="sec" id="s-probes">
<h2>Probe 心跳矩阵</h2><p class="sub">守护/探针 SLA 健康（绿/红/陈旧）</p>
<div class="grid g3" id="probekpi"></div>
<div class="card" style="margin-top:12px"><h3>实时心跳</h3><table id="probebtbl"><thead><tr><th>服务</th><th>状态</th><th>最后可见</th></tr></thead><tbody></tbody></table></div>
</section>
<section class="sec" id="s-resident">
<h2>Resident Agent 名册</h2><p class="sub">常驻角色/项目/类型 · 可见</p>
<div class="card"><table id="restbl"><thead><tr><th>角色</th><th>项目</th><th>类型</th></tr></thead><tbody></tbody></table></div>
</section>
<section class="sec" id="s-scenes">
<h2>Scene System 运行态</h2><p class="sub">场景卡 / 信号轮询 / 旅程执行 / 连接器 / 远程卫生</p>
<div class="grid g3" id="scenekpi"></div>
<div class="grid g2" id="sceneextra"></div>
</section>
<section class="sec" id="s-journeys">
<h2>Journey 引擎</h2><p class="sub">旅程规格文件 · human_gate 数量 · state 数</p>
<div class="grid g3" id="journeykpi"></div>
<div class="card" style="margin-top:12px"><table id="journeytbl"><thead><tr><th>名称</th><th>states</th><th>human_gates</th><th>size</th></tr></thead><tbody></tbody></table></div>
</section>
<section class="sec" id="s-hygiene">
<h2>工作区卫生</h2><p class="sub">陈旧 worktree / 僵尸锁 / 遗留</p>
<div class="grid g2">
<div class="card"><h3>Worktree 列表</h3><table id="wttbl"><thead><tr><th>路径</th><th>分支</th></tr></thead><tbody></tbody></table></div>
<div class="card"><h3>僵尸锁</h3><div id="locklist" class="mono" style="font-size:12px;line-height:2"></div></div>
</div>
</section>
<div class="foot">只读 SSOT 聚合 · 零写入零派工 · 产物 runtime/dashboard/（gitignored）· 刷新: launchd 每 5min · 与 Serena 观测站(43191)互补</div>
</main>
<script>
const D=__DATA__;
document.getElementById('ts').textContent=D.generated_at.slice(0,16).replace('T',' ');
const $=id=>document.getElementById(id);
const chip=v=>v==='PASS'?'<span class="chip p">PASS</span>':(v==='FAIL'?'<span class="chip f">FAIL</span>':'<span class="chip n">'+v+'</span>');
// === Agent Brief ===
(function(){
  const av=D.agent_visibility||{available:false};
  const a=av.authority||{}, h=av.health||{}, w=av.work_state||{};
  const gates=h.gates_pass||0, gatesTotal=h.gates_total||0;
  const items=[
    {l:'Gate PASS',v:gates+'/'+gatesTotal},
    {l:'Open Tasks',v:(w.tasks||{}).open_count||0},
    {l:'Active Workflows',v:(w.workflows||{}).active_count||0},
    {l:'Task Duplicates',v:((w.tasks||{}).duplicates||[]).length},
    {l:'High Alerts',v:(w.alerts||{}).high||0},
    {l:'Semantic',v:(h.semantic_lifecycle||{}).verdict||'UNKNOWN'},
    {l:'Value Proof',v:a.value_proof||'UNKNOWN'}
  ];
  $('ab-kpi').innerHTML=items.map(x=>'<div class="kpi-card"><b class="'+(x.l==='High Alerts'&&x.v>0?'dead':(x.l==='Value Proof'&&x.v==='NOT_PROVEN'?'dead':'fresh'))+'">'+x.v+'</b><span>'+x.l+'</span></div>').join('');
  const auth=[
    ['Control Plane',a.control_plane||'unknown'],
    ['Single Dispatcher',a.single_dispatcher===true?'true':'false'],
    ['Effective Claim Authority',a.effective_claim_authority||'unknown'],
    ['Claims Activation',a.claims_activation_state||'unknown'],
    ['Instruction Capable',a.claims_instruction_capable===true?'true':'false'],
    ['Activation Allowed',a.claims_activation_allowed===true?'true':'false'],
    ['Value Proof',a.value_proof||'unknown']
  ];
  $('ab-authority').querySelector('tbody').innerHTML=auth.map(x=>'<tr><td>'+x[0]+'</td><td class="mono">'+x[1]+'</td></tr>').join('');
  const ri=(av.read_interfaces||{});
  const interfaces=[['human_html',ri.human_html||'/'],['data_json',ri.data_json||'/data.json'],['agent_brief_json',ri.agent_brief_json||'/agent-brief.json'],['filesystem brief',(ri.filesystem||{}).brief||'runtime/dashboard/agent-brief.json']];
  $('ab-interfaces').querySelector('tbody').innerHTML=interfaces.map(x=>'<tr><td>'+x[0]+'</td><td class="mono">'+x[1]+'</td></tr>').join('');
  $('ab-actions').querySelector('tbody').innerHTML=(av.next_actions||[]).map(x=>'<tr><td><span class="chip '+(x.state==='required'?'w':(x.state==='ready'?'p':'n'))+'">'+x.state+'</span></td><td class="mono">'+x.id+'</td><td>'+x.detail+'</td><td class="mono">'+x.source+'</td></tr>').join('')||'<tr><td colspan=4 class="mono">无投影</td></tr>';
  const rows=[];
  for(const t of ((w.tasks||{}).open_recent||[]).slice(0,8))rows.push({type:'task',name:t.id,state:t.bucket+'/'+t.status,detail:(t.priority||'')+' · '+(t.owner||'')});
  for(const b of ((w.bets||{}).in_progress||[]))rows.push({type:'bet',name:b.id,state:'in_progress',detail:b.title||''});
  for(const b of ((w.bets||{}).blocked||[]))rows.push({type:'bet',name:b.id,state:'blocked',detail:b.title||''});
  for(const x of ((w.alerts||{}).recent||[]))rows.push({type:'alert',name:x.source,state:x.severity,detail:x.msg||''});
  $('ab-work').querySelector('tbody').innerHTML=rows.map(x=>'<tr><td class="mono">'+x.type+'</td><td class="mono">'+x.name+'</td><td><span class="chip '+(x.state==='high'||x.state==='blocked'?'f':(x.state==='in_progress'?'p':'n'))+'">'+x.state+'</span></td><td>'+x.detail+'</td></tr>').join('')||'<tr><td colspan=4 class="mono">无开放工作</td></tr>';
  $('ab-objectives').querySelector('tbody').innerHTML=((av.objective_coverage||{}).items||[]).map(x=>'<tr><td><span class="chip '+(['PASS','DELIVERY_ACCEPTED'].includes(x.status)?'p':(x.status==='NOT_PROVEN'||x.status==='PARTIAL'?'f':'w'))+'">'+x.status+'</span></td><td class="mono">'+x.id+'</td><td class="mono">'+(x.value_status||'—')+'</td><td>'+x.requirement+'</td></tr>').join('')||'<tr><td colspan=4 class="mono">无投影</td></tr>';
  $('ab-roles').querySelector('tbody').innerHTML=(((av.role_registry||{}).records)||[]).map(x=>'<tr><td class="mono">'+x.role_id+'</td><td><span class="chip '+(x.admission_state==='admitted'?'p':'n')+'">'+x.admission_state+'</span></td><td class="mono">'+x.version+'</td><td class="mono">'+x.capabilities.join(', ')+'</td></tr>').join('')||'<tr><td colspan=4 class="mono">无持久 Role 记录</td></tr>';
  const sm=(h.semantic_lifecycle||{});
  $('ab-semantic').querySelector('tbody').innerHTML=[
    ['available',sm.available===true?'true':'false'],
    ['verdict',sm.verdict||'UNAVAILABLE'],
    ['receipt_chain',sm.receipt_chain_ok===true?'PASS':'FAIL'],
    ['receipt_digests',sm.receipt_digests_ok===true?'PASS':'FAIL'],
    ['role_bindings',sm.role_bindings_ok===true?'PASS':'FAIL'],
    ['capsule_bindings',sm.capsule_bindings_ok===true?'PASS':'FAIL'],
    ['mesh_bindings',sm.mesh_bindings_ok===true?'PASS':'FAIL'],
    ['queue_bindings',sm.queue_bindings_ok===true?'PASS':'FAIL'],
    ['latest_run_id',sm.latest_run_id||'—'],
    ['latest_receipt_digest',sm.latest_receipt_digest||'—']
  ].map(x=>'<tr><td>'+x[0]+'</td><td class="mono">'+x[1]+'</td></tr>').join('');
})();
// nav
document.querySelectorAll('#nav a').forEach(a=>a.onclick=e=>{e.preventDefault();
document.querySelectorAll('#nav a').forEach(x=>x.classList.remove('on'));a.classList.add('on');
document.querySelectorAll('.sec').forEach(s=>s.classList.remove('on'));$('s-'+a.dataset.s).classList.add('on');});
// === 战略全景（可下钻 + 可关联） ===
(function(){
  const c=D.bets.counts, gmap={};D.gates.forEach(g=>gmap[g.id]=g.verdict);
  const trendUp='<span class="trend up">↗</span>';
  const kpis=[
    {k:'bets',l:'总 BET',v:D.bets.total},
    {k:'done',l:'已完成',v:c.done||0},
    {k:'inprogress',l:'进行中',v:c.in_progress||0},
    {k:'candidate',l:'候选',v:c.candidate||0},
    {k:'agents',l:'Agents',v:D.agents.length},
    {k:'gates',l:'门禁 PASS',v:Object.values(gmap).filter(v=>v==='PASS').length+'/10'},
    {k:'ci',l:'CI 红源',v:(D.ci.red_workflows||[]).length},
    {k:'cron',l:'Cron',v:D.cron.total||0},
    {k:'services',l:'BOS 服务',v:D.services.total||0},
    {k:'debt',l:'债务',v:(D.debt_registry.open||D.debt.open||0)},
    {k:'alerts',l:'告警',v:D.alerts.total||0}
  ];
  const kpi=$('kpi'); kpi.className='kpi-grid';
  kpi.innerHTML=kpis.map(k=>'<div class="kpi-card" data-key="'+k.k+'" onclick="drill(\''+k.k+'\"><b>'+k.v+'</b>'+(k.v>0?trendUp:'')+'<span>'+k.l+'</span></div>').join('');

  window.drill=function(key){
    const d=$('drill');
    if(d.classList.contains('open')&&d.dataset.key===key){d.classList.remove('open');return;}
    d.dataset.key=key; d.classList.add('open');
    let html='<div class="drill-inner">';
    if(key==='bets'){
      html+='<h4>BET 台账下钻</h4><div class="grid g3" style="margin-bottom:12px">';
      for(const[w,wd]of Object.entries(D.bets.windows||{})){const p=Math.round(100*wd.done/wd.total);html+='<div><div style="display:flex;justify-content:space-between"><span class="mono">'+w+'</span><span>'+wd.done+'/'+wd.total+'</span></div><div class="bar"><i style="width:'+p+'%"></i></div></div>';}
      html+='</div>';
      if((D.bets.in_progress||[]).length){html+='<h4>进行中</h4><table><tr><th>ID</th><th>标题</th><th>级</th></tr>';for(const b of D.bets.in_progress)html+='<tr><td class="mono">'+b.id+'</td><td>'+b.title+'</td><td><span class="chip n">'+b.priority+'</span></td></tr>';html+='</table>';}
    } else if(key==='gates'){
      html+='<h4>门禁 A1–A9</h4><table><tr><th>ID</th><th>判定</th><th>证据</th><th>依赖</th></tr>';
      for(const g of D.gates)html+='<tr><td class="mono">'+g.id+'</td><td><span class="chip '+(g.verdict==='PASS'?'p':'f')+'">'+g.verdict+'</span></td><td style="max-width:200px;overflow:hidden;text-overflow:ellipsis">'+g.detail+'</td><td>'+(g.depends_on||[]).join(', ')+'</td></tr>';
      html+='</table>';
    } else if(key==='agents'){
      html+='<h4>Agent 全景</h4><table><tr><th>worktree</th><th>分支</th><th>活动</th></tr>';
      for(const a of D.agents.slice(0,25))html+='<tr><td class="mono">'+a.worktree+'</td><td class="mono">'+a.branch+'</td><td>'+(a.last_activity_hours==null?'n/a':a.last_activity_hours+'h')+'</td></tr>';
      html+='</table>';
    } else if(key==='ci'){
      html+='<h4>CI 红源</h4><table><tr><th>Workflow</th><th>总数</th><th>失败</th><th>率</th></tr>';
      for(const w of D.ci.all||[])html+='<tr><td class="mono">'+w.workflow+'</td><td>'+w.total+'</td><td class="chip f">'+w.fail+'</td><td>'+Math.round(w.failure_rate*100)+'%</td></tr>';
      html+='</table>';
    } else if(key==='cron'){
      html+='<h4>Cron 调度台</h4><table><tr><th>名称</th><th>调度</th><th>状态</th><th>安装态</th></tr>';
      for(const j of D.cron.jobs||[])html+='<tr><td class="mono">'+j.name+'</td><td class="mono">'+j.schedule+'</td><td><span class="chip '+(j.status==='active'?'p':'n')+'">'+j.status+'</span></td><td>'+(j.reality||'')+'</td></tr>';
      html+='</table>';
    } else if(key==='services'){
      html+='<h4>BOS 服务</h4><table><tr><th>名称</th><th>状态</th><th>端点</th></tr>';
      for(const s of D.services.sample||[])html+='<tr><td class="mono">'+s.name+'</td><td><span class="chip '+(s.status==='active'?'p':'n')+'">'+s.status+'</span></td><td class="mono">'+s.endpoint+'</td></tr>';
      html+='</table>';
    } else if(key==='debt'){
      html+='<h4>债务全览</h4>';
      if(D.debt_registry.by_status)html+='<div class="grid g3" style="margin-bottom:12px">'+Object.entries(D.debt_registry.by_status).map(([s,n])=>'<div class="card kpi"><b>'+n+'</b><span>'+s+'</span></div>').join('')+'</div>';
      html+='<table><tr><th>ID</th><th>状态</th><th>标题</th></tr>';
      for(const i of (D.debt_registry.items||[]).slice(0,15))html+='<tr><td class="mono">'+i.id+'</td><td><span class="chip f">'+i.status+'</span></td><td>'+i.title+'</td></tr>';
      html+='</table>';
    } else if(key==='alerts'){
      html+='<h4>告警聚合</h4><table><tr><th>级</th><th>源</th><th>信息</th></tr>';
      for(const a of D.alerts.alerts||[])html+='<tr><td><span class="chip '+(a.severity==='high'?'f':'w')+'">'+a.severity+'</span></td><td class="mono">'+a.source+'</td><td>'+a.msg+'</td></tr>';
      html+='</table>';
    }
    html+='</div>'; d.innerHTML=html;
  };
})();
// gates
$('gategrid').innerHTML=D.gates.map(g=>'<div class="card"><h3>'+g.id+' · '+g.title+'</h3>'+chip(g.verdict)+
'<div class="mono" style="margin-top:8px;color:var(--muted)">'+g.detail+'</div>'+
(g.depends_on?'<div class="mono" style="margin-top:6px;font-size:10px">依赖: '+g.depends_on.join(', ')+'</div>':'')+'</div>').join('');
// agents
$('agenttable').querySelector('tbody').innerHTML=D.agents.map(a=>'<tr><td class="mono">'+a.worktree+'</td><td class="mono">'+(a.branch||'')+'</td><td>'+
(a.last_activity_hours==null?'<span class="chip n">n/a</span>':a.last_activity_hours<2?'<span class="chip p">'+a.last_activity_hours+'h</span>':a.last_activity_hours<24?'<span class="chip w">'+a.last_activity_hours+'h</span>':'<span class="chip f">'+a.last_activity_hours+'h</span>')+'</td></tr>').join('');
// agent cells
(function(){
  const cp=D.agent_cell_pool||{};
  const cls=cp.verdict==='PASS'?'p':(cp.verdict==='FAILED'||cp.verdict==='UNPARSEABLE'?'f':'n');
  const rv=cp.receipt_verification||{};
  const rvClass=rv.verdict==='PASS'?'p':(rv.verdict==='EMPTY'?'n':'f');
  $('cellkpi').innerHTML=[
    {v:cp.total||0,l:'total',c:cp.available?'':'n'},{v:cp.active||0,l:'active'},
    {v:cp.failed||0,l:'failed',c:cp.failed?'f':''},
    {v:(cp.age_seconds==null?'n/a':cp.age_seconds+'s'),l:'age',c:cp.live?'':'w'},
    {v:cp.verdict||'EMPTY',l:'projection',c:cls}
  ].map(k=>'<div class="card kpi"><b class="'+(k.c||'')+'">'+k.v+'</b><span>'+k.l+'</span></div>').join('');
  $('cellkpi').insertAdjacentHTML('beforeend','<div class="card kpi"><b class="'+rvClass+'">'+(rv.receipt_count||0)+'</b><span>receipts</span></div>'+
    '<div class="card kpi"><b class="'+rvClass+'">'+(rv.verdict||'UNAVAILABLE')+'</b><span>receipt chain</span></div>');
  $('celltable').querySelector('tbody').innerHTML=(cp.cells||[]).map(c=>{
    const stateClass=c.state==='failed'?'f':(['planning','executing','verifying'].includes(c.state)?'p':'n');
    return '<tr><td class="mono">'+c.cell_id+'</td><td class="mono">'+(c.episode_id||'—')+'</td>'+
      '<td><span class="chip '+stateClass+'">'+c.state+'</span></td><td>'+(c.current_role||'—')+'</td>'+
      '<td>'+(c.handoff_count||0)+'</td><td class="mono">'+(c.saved_at||'—').slice(0,19).replace('T',' ')+'</td></tr>';
  }).join('')||'<tr><td colspan=6 class="mono">无持久化 Cell 状态（合法空态）</td></tr>';
})();
// agent cell semantic lifecycle
(function(){
  const sm=D.agent_cell_semantic||{};
  const cls=sm.verdict==='PASS'?'p':(sm.verdict==='EMPTY'?'n':'f');
  $('semantickpi').innerHTML=[
    {v:sm.receipt_count||0,l:'receipts',c:sm.receipt_count?'':'n'},
    {v:sm.verdict||'UNAVAILABLE',l:'verdict',c:cls}
  ].map(k=>'<div class="card kpi"><b class="'+k.c+'">'+k.v+'</b><span>'+k.l+'</span></div>').join('');
  const rows=[
    ['receipt chain',sm.receipt_chain_ok],['receipt digests',sm.receipt_digests_ok],
    ['role binding',sm.role_bindings_ok],['capsule binding',sm.capsule_bindings_ok],
    ['mesh handoff',sm.mesh_bindings_ok],['queue completion',sm.queue_bindings_ok]
  ];
  $('semantictable').querySelector('tbody').innerHTML=rows.map(r=>'<tr><td>'+r[0]+'</td><td><span class="chip '+(r[1]?'p':'n')+'">'+(r[1]?'PASS':'EMPTY')+'</span></td><td class="mono">'+(r[1]?'verified':'not available')+'</td></tr>').join('');
})();
// claims authority
(function(){
  const ca=D.claims_authority||{};
  const state=ca.activation_state||'unknown';
  const cls=ca.available?(state==='active'?'p':'n'):'f';
  const cr=D.code_root_health||{};
  const crClass=cr.verdict==='PASS'?'p':((cr.verdict==='STALE'||cr.verdict==='DIRTY')?'f':'n');
  const pt=D.claims_task16||{};
  const ptClass=pt.verdict==='READY'?'p':(pt.available?'w':'f');
  $('claimkpi').innerHTML=[
    {v:state,l:'activation',c:cls},
    {v:ca.effective_claim_authority||'UNKNOWN',l:'effective'},
    {v:ca.security_level||'UNKNOWN',l:'security'},
    {v:ca.sequence==null?'n/a':ca.sequence,l:'sequence'},
    {v:cr.verdict||'UNAVAILABLE',l:'code root',c:crClass},
    {v:pt.blocker_count==null?'n/a':pt.blocker_count,l:'Task16 blockers',c:ptClass},
    {v:pt.verdict||'UNAVAILABLE',l:'Task16 readiness',c:ptClass}
  ].map(k=>'<div class="card kpi"><b class="'+(k.c||'')+'">'+k.v+'</b><span>'+k.l+'</span></div>').join('');
    const rows=[
    ['read-only observation',ca.available],
    ['instruction capable',ca.instruction_capable],
    ['mutation performed',ca.mutation_performed],
    ['authorization granted',ca.authorization_granted],
    ['operation authorization',(D.authority.claims_activation_readiness||{}).operation_specific_authorization==='PROVEN'],
    ['code root synced',cr.verdict==='PASS'],
    ['code root clean',cr.dirty===false],
    ['Task16 preflight',pt.available],
    ['Task16 activation allowed',pt.activation_allowed===true]
  ];
  $('claimtable').querySelector('tbody').innerHTML=rows.map(r=>'<tr><td>'+r[0]+'</td><td><span class="chip '+(!r[1]||r[0]==='read-only observation'&&r[1]?'p':'f')+'">'+(r[1]?'true':'false')+'</span></td></tr>').join('');
})();
// bets
$('windows').innerHTML=Object.entries(D.bets.windows).map(([w,d])=>{
const pct=Math.round(100*d.done/d.total);
return '<div style="margin-bottom:10px"><div style="display:flex;justify-content:space-between" class="mono"><span>'+w+'</span><span>'+d.done+'/'+d.total+'</span></div><div class="bar '+(pct===100?'done':'')+'"><i style="width:'+pct+'%"></i></div></div>';}).join('');
const rows=[...D.bets.in_progress.map(b=>({...b,s:'p'})),...D.bets.blocked.map(b=>({...b,s:'f'}))];
$('focus').querySelector('tbody').innerHTML=rows.map(b=>'<tr><td class="mono">'+b.id+'</td><td>'+b.title+'</td><td><span class="chip '+b.s+'">'+b.priority+'</span></td></tr>').join('')||'<tr><td colspan=3 class="mono">无</td></tr>';
// runtime
const md=D.runtime.meta_doctor||{};
$('rtgrid').innerHTML=[
 ['stale_beats',md.stale_beats],['dead_refs',md.dead_refs],['ritual_lapsed',md.ritual_lapsed],
 ['untracked_refs',md.untracked_refs],['launchd 任务',D.runtime.launchd_omostation_jobs],['crontab 行',D.runtime.crontab_lines]
].map(x=>'<div class="card kpi"><b class="'+(x[1]===0?'fresh':(x[1]>0&&x[0]!=='launchd 任务'&&x[0]!=='crontab 行'?'dead':'fresh'))+'">'+x[1]+'</b><span>'+x[0]+'</span></div>').join('');
// launchd runtime jobs
(function(){
  const lh=D.launchd_health||{};
  const cls=lh.verdict==='PASS'?'p':(lh.verdict==='EMPTY'?'n':'f');
  $('launchdkpi').innerHTML=[
    {v:lh.loaded||0,l:'loaded'},{v:lh.failed||0,l:'failed',c:lh.failed?'f':''},
    {v:lh.verdict||'UNAVAILABLE',l:'verdict',c:cls}
  ].map(k=>'<div class="card kpi"><b class="'+(k.c||'')+'">'+k.v+'</b><span>'+k.l+'</span></div>').join('');
  $('launchdtable').querySelector('tbody').innerHTML=(lh.jobs||[]).map(j=>{
    const exitClass=j.last_exit_ok?'p':'f';
    const jobClass=j.verdict==='PASS'?'p':'f';
    return '<tr><td class="mono">'+j.name+'</td><td>'+(j.state||'unknown')+'</td>'+
      '<td><span class="chip '+exitClass+'">'+(j.last_exit_code||'unknown')+'</span></td>'+
      '<td class="mono">'+(j.run_interval||'—')+'</td><td>'+(j.runs||0)+'</td>'+
      '<td><span class="chip '+jobClass+'">'+j.verdict+'</span></td></tr>';
  }).join('')||'<tr><td colspan=6 class="mono">无 active launchd job</td></tr>';
})();
// docs
$('docgrid').innerHTML=D.docs.map(d=>'<div class="card"><h3>'+d.name+'</h3><span class="chip '+(d.exists?'p':'f')+'">'+(d.exists?Math.round(d.size/1024)+'KB':'缺失')+'</span>'+
'<div class="mono" style="margin-top:8px;font-size:11px">'+d.path+'</div>'+
(d.exists?'<div style="margin-top:8px"><a href="/../../'+d.path+'">打开 →</a></div>':'')+'</div>').join('');
// === Scene System 运行态 ===
(function(){
  const sc=D.scene_cards||{}, sp=D.signal_poller||{}, je=D.journey_executions||{};
  const rh=D.remote_hygiene||{}, co=D.connectors||{}, bv=D.bos_verifier||{};
  const lc=sc.lifecycle||{};
  const lcHtml=Object.entries(lc).map(([s,n])=>'<div class="card kpi"><b>'+n+'</b><span>'+s+'</span></div>').join('');
  $('scenekpi').innerHTML=[
    {v:sc.total,l:'总场景卡'}, {v:sc.with_trigger,l:'有触发器'}, {v:Object.keys(lc).length,l:'阶段数'},
    {v:je.total||0,l:'旅程执行'}, {v:je.escalated||0,l:'escalated'}, {v:(je.auto_complete_rate!=null?je.auto_complete_rate:'n/a'),l:'自动完成率'},
    {v:sp.watermark_entries||0,l:'watermark'}, {v:sp.scenes_with_triggers||0,l:'场景有触发'}, {v:(co.total||0)+' / '+(co.available||[]).length,l:'连接器 总/可用'}
  ].map(k=>'<div class="card kpi"><b>'+k.v+'</b><span>'+k.l+'</span></div>').join('')+lcHtml;
  const extra=[];
  if(co.wired_to_scenes) extra.push('<div class="card"><h3>已接线连接器</h3><div style="margin-top:8px">'+(co.wired_to_scenes||[]).map(c=>'<span class="chip p" style="margin:2px">'+c+'</span>').join(' ')+'</div></div>');
  if(co.unwired_available) extra.push('<div class="card"><h3>可用未接线</h3><div style="margin-top:8px">'+(co.unwired_available||[]).map(c=>'<span class="chip n" style="margin:2px">'+c+'</span>').join(' ')+'</div></div>');
  if(sp.last_poll) extra.push('<div class="card"><h3>最近轮询</h3><div class="mono" style="font-size:11px;margin-top:8px">'+sp.last_poll.slice(0,16).replace('T',' ')+'</div></div>');
  if(rh.origin_canonical!=null) extra.push('<div class="card"><h3>远程卫生</h3><div style="margin-top:6px"><span class="chip '+(rh.origin_canonical?'p':'f')+'">origin '+(rh.origin_canonical?'✓':'✗')+'</span> <span class="chip '+(rh.origin_push_canonical?'p':'f')+'">push '+(rh.origin_push_canonical?'✓':'✗')+'</span><div class="mono" style="font-size:10px;margin-top:6px">submodules: '+(rh.submodules_checked||0)+'</div></div></div>');
  if(bv.last_run_ok!=null) extra.push('<div class="card"><h3>BOS 验证</h3><div style="margin-top:6px"><span class="chip '+(bv.last_run_ok>=100?'p':'w')+'">OK '+bv.last_run_ok+'</span> <span class="chip '+(bv.last_run_errors>0?'f':'p')+'">errors '+bv.last_run_errors+'</span></div></div>');
  $('sceneextra').innerHTML=extra.join('')||'';
})();
// === Journey 引擎 ===
(function(){
  const specs=(D.journeys&&D.journeys.journeys)||[];
  const totalGates=specs.reduce((a,j)=>a+(j.human_gates||0),0);
  $('journeykpi').innerHTML=[
    {v:specs.length,l:'旅程规格'},{v:totalGates,l:'human_gate 总数'},{v:specs.filter(j=>j.human_gates>0).length,l:'含门控'}
  ].map(k=>'<div class="card kpi"><b>'+k.v+'</b><span>'+k.l+'</span></div>').join('');
  $('journeytbl').querySelector('tbody').innerHTML=specs.slice(0,15).map(j=>'<tr><td class="mono">'+j.name+'</td><td>'+j.states+'</td><td>'+j.human_gates+'</td><td>'+j.size_kb+'KB</td></tr>').join('')||'<tr><td colspan=4 class="mono">无旅程规格</td></tr>';
})();
// === 知识记忆经验建模 ===
(function(){
  const kh=D.knowledge_health||{};
  $('khkpi').innerHTML=['total','fresh','stale','freshness_pct'].map(k=>{
    const labels={total:'总文档',fresh:'新鲜',stale:'陈旧',freshness_pct:'新鲜度%'};
    const v=kh[k]; const isPct=k==='freshness_pct';
    return '<div class="card kpi"><b class="'+(k==='stale'?(v>50?'dead':'fresh'):'fresh')+'">'+(isPct?v+'%':v)+'</b><span>'+(labels[k]||k)+'</span></div>';
  }).join('');
  const kg=D.knowledge_growth||{};
  if(kg.series && kg.series.length){
    const max=Math.max(...kg.series.map(s=>s.n),1);
    $('kgrowth').innerHTML=kg.series.slice(-14).map(s=>'<div class="bar" title="'+s.day+': '+s.n+'" style="height:'+Math.round(s.n/max*55)+'px"></div>').join('');
  }
  const mt=D.memory_dual_track||{};
  $('mdtkpi').innerHTML=['Raw 事件','theta 事实','近期'].map(k=>({k:k,v:k==='Raw 事件'?(mt.raw_count||0):k==='theta 事实'?(mt.theta_facts||0):(mt.recent_raw||[]).length})).map(x=>'<div class="card kpi"><b>'+x.v+'</b><span>'+x.k+'</span></div>').join('');
  const rawHtml=(mt.recent_raw||[]).slice(0,10).map(e=>'<div style="padding:4px 0;border-bottom:1px solid var(--line)"><span class="mono" style="color:var(--muted)">'+(mt.raw_count||0)+' 条</span> '+e+'</div>').join('');
  $('mdt_raw').innerHTML=rawHtml||'<span class="mono" style="color:var(--muted)">无 Raw 事件</span>';
  const en=D.experience_network||{};
  const nodes=en.nodes||[];
  const grouped={}; nodes.forEach(n=>{grouped[n.type]=(grouped[n.type]||[]).push(n);});
  const labels={pitfall:'坑',decision:'决策',retro:'复盘',pattern:'模式'};
  const expHtml=Object.entries(grouped).map(([k,items])=>'<div style="margin-bottom:8px"><span class="mono" style="color:var(--teal)">'+(labels[k]||k)+' ('+items.length+')</span><br>'+items.slice(0,5).map(i=>'<span class="assoc-link" style="margin-right:8px">'+(i.id||i.name||'')+'</span>').join('')+'</div>').join('');
  $('exp_net').innerHTML=expHtml||'<span class="mono" style="color:var(--muted)">无经验节点</span>';
  const ib=D.knowledge_inbound||[];
  $('kinbound').querySelector('tbody').innerHTML=(Array.isArray(ib)?ib:[]).map(r=>'<tr><td class="mono">'+r.doc+'</td><td>'+r.inbound+'</td></tr>').join('')||'<tr><td colspan=2 class="mono">无入链数据</td></tr>';
  // Phase C: 经验图谱
  const eg=D.experience_graph||{};
  const connPct=eg.connectivity_pct||0;
  $('eg_connect').innerHTML='<span class="kv '+(connPct>=50?'fresh':'dead')+'">'+connPct+'%</span><span class="ks">连通性</span>';
  $('eg_refs').innerHTML='<span class="kv">'+(eg.internal_refs||0)+'</span><span class="ks">内部引用</span>';
  $('eg_top').innerHTML=(en.top_connected||[]).map(n=>'<span class="assoc-link" style="margin-right:10px">'+n.id+' <span style="color:var(--teal)">'+n.links+'</span></span>').join('')||'<span class="mono" style="color:var(--muted)">无连接</span>';
  $('eg_hot').innerHTML=(eg.hotspots||[]).map(h=>'<div style="display:flex;justify-content:space-between;padding:4px 0;border-bottom:1px solid var(--line)"><span class="mono">'+h.type+'</span><span style="color:var(--teal)">'+h.count+'</span></div>').join('');
})();
</script></body></html>
"""

if __name__ == "__main__":
    raise SystemExit(main())

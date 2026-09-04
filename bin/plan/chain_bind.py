#!/usr/bin/env python3
"""Plan → BET → workflow → closeout → retro bind predicate.

Pure functions over run/ledger/retro/north-star so tests need no live swarm.
No fourth tracker: reuses Plan §0.3, 3y-bet-ledger, agent-workflow runs, retros.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

NORTH_STAR_REF = "docs/STRATEGY-3YEAR-PLAN-2026H2-2029.md"
NORTH_STAR_SENTENCE = (
    "织星是夏明星一个人的业务操作系统。"
    "它的唯一职责是：把外部进来的信号，变成他愿意署名发出去的东西，并且记住他每次改了什么。"
)
EXEMPT_WORKFLOWS = frozenset({"observer-audit"})
# G8 (T10-08): 治理演进类 workflow — 自进化改进治理机制本身, 由治理 bet (T10-MATURITY)
# 承载 vision→run→retro 闭环, closeout 无需业务 bet 绑定.
GOVERNANCE_EVOLVE_WORKFLOWS = frozenset(
    {
        "governance-audit",
        "governance-state-mutation",
        "governance-phase-closeout",
        # ADR-0441 原语 3 周期执行面: Documents 执行面巡检由治理线承载,
        # per-run 无业务 bet 语义 (forbidden=0 硬门监控, 非 delivery).
        # (原 #2736 二段提交因 PR 合并后同名分支重建而丢失, 本提交一并恢复)
        "documents-consumer-audit-weekly",
        # ADR-0443 收敛脉搏: 产出/收敛平衡的周期执行面, 同为治理巡检非 delivery.
        "convergence-pulse-weekly",
    }
)
GATE_ENV = "AGCP_REQUIREMENT_ITERATION_GATE"
RETRO_REL = ".omo/_knowledge/retros"
RUNS_REL = ".omo/_delivery/agent-workflows/runs"
LEDGER_REL = "docs/plans/3y-bet-ledger.yaml"


@dataclass(frozen=True)
class BindVerdict:
    ok: bool
    reasons: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {"ok": self.ok, "reasons": list(self.reasons)}


def gate_disabled(env: dict[str, str] | None = None) -> bool:
    import os

    source = env if env is not None else os.environ
    return source.get(GATE_ENV, "1") == "0"


def start_requires_bet(
    workflow_id: str,
    bet_id: str,
    *,
    env: dict[str, str] | None = None,
) -> BindVerdict:
    """Reject requirement-iteration start unless a ledger bet id is supplied."""
    wf = (workflow_id or "").strip()
    if wf in EXEMPT_WORKFLOWS or gate_disabled(env):
        return BindVerdict(True, [])
    if not (bet_id or "").strip():
        return BindVerdict(False, ["missing_bet_id"])
    return BindVerdict(True, [])


def evaluate_bind(
    *,
    bet_id: str | None,
    run_bet_id: str | None,
    north_star_present: bool,
    retro_required: bool,
    retro_present: bool,
    exempt: bool = False,
) -> BindVerdict:
    """Halt unless run↔bet binding, Plan north-star pointer, and retro (when required)."""
    if exempt:
        return BindVerdict(True, [])
    reasons: list[str] = []
    bound = (run_bet_id or "").strip()
    expected = (bet_id or "").strip()
    if not bound:
        reasons.append("missing_bet_binding")
    elif expected and bound != expected:
        reasons.append("bet_id_mismatch")
    if not north_star_present:
        reasons.append("missing_north_star_pointer")
    if retro_required and not retro_present:
        reasons.append("missing_retro")
    return BindVerdict(ok=not reasons, reasons=reasons)


def north_star_present(workspace: Path) -> bool:
    path = workspace / NORTH_STAR_REF
    if not path.is_file():
        return False
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return False
    return NORTH_STAR_SENTENCE[:12] in text


def retro_path_for(workspace: Path, bet_id: str) -> Path:
    return workspace / RETRO_REL / f"{bet_id}.md"


def load_yaml(path: Path) -> Any:
    import yaml

    return yaml.safe_load(path.read_text(encoding="utf-8"))


def load_ledger(workspace: Path) -> dict[str, Any]:
    path = workspace / LEDGER_REL
    if not path.is_file():
        return {"bets": []}
    data: dict[str, Any] = {}
    import yaml

    for doc in yaml.safe_load_all(path.read_text(encoding="utf-8")):
        if isinstance(doc, dict):
            data.update(doc)
    data.setdefault("bets", [])
    return data


def bet_by_id(ledger: dict[str, Any], bet_id: str) -> dict[str, Any] | None:
    for item in ledger.get("bets") or []:
        if isinstance(item, dict) and item.get("id") == bet_id:
            return item
    return None


def persist_bind_on_run(record: dict[str, Any], bet_id: str) -> dict[str, Any]:
    """Write bet_id + north_star_ref onto the run record itself."""
    if bet_id:
        record["bet_id"] = bet_id
        record["north_star_ref"] = NORTH_STAR_REF
    return record


def write_run_file(path: Path, record: dict[str, Any]) -> None:
    import yaml

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(record, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )


def iter_run_records(workspace: Path) -> list[dict[str, Any]]:
    import yaml

    runs_dir = workspace / RUNS_REL
    if not runs_dir.is_dir():
        return []
    out: list[dict[str, Any]] = []
    for path in sorted(runs_dir.glob("*.yaml")):
        try:
            payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except OSError:
            continue
        if isinstance(payload, dict) and payload.get("run_id"):
            payload["_path"] = str(path)
            out.append(payload)
    return out


def bound_runs_for_bet(workspace: Path, bet_id: str) -> list[dict[str, Any]]:
    return [r for r in iter_run_records(workspace) if r.get("bet_id") == bet_id]


def evaluate_closeout(
    run: dict[str, Any],
    workspace: Path,
    *,
    env: dict[str, str] | None = None,
    status: str = "ok",
) -> BindVerdict:
    if status != "ok":
        return BindVerdict(True, [])
    wf = str(run.get("workflow_id") or "")
    if wf in EXEMPT_WORKFLOWS:
        return BindVerdict(True, [])
    bet_id = str(run.get("bet_id") or "").strip()
    if not bet_id:
        # G8 (T10-08): 治理演进 workflow 无业务 bet 不 halt — 治理自进化闭环由
        # 治理 bet (T10-MATURITY) 承载, 不强制绑定业务 bet.
        if wf in GOVERNANCE_EVOLVE_WORKFLOWS and _has_governance_bet(workspace):
            return BindVerdict(True, [])
        if gate_disabled(env):
            return BindVerdict(True, [])
        return BindVerdict(False, ["missing_bet_binding"])
    ledger = load_ledger(workspace)
    bet = bet_by_id(ledger, bet_id) or {"id": bet_id, "retro": "required"}
    retro_req = bet.get("retro") in ("required", "light")
    return evaluate_bind(
        bet_id=bet_id,
        run_bet_id=bet_id,
        north_star_present=north_star_present(workspace),
        retro_required=bool(retro_req),
        retro_present=retro_path_for(workspace, bet_id).is_file(),
    )


def _has_governance_bet(workspace: Path) -> bool:
    """Ledger 存在治理演进 bet (track=T10-MATURITY 或 BET-Y1Q*-T10-*)."""
    ledger = load_ledger(workspace)
    for item in ledger.get("bets") or []:
        if not isinstance(item, dict):
            continue
        bid = str(item.get("id") or "")
        track = str(item.get("track") or "")
        if track == "T10-MATURITY" or "-T10-" in bid:
            return True
    return False


def evaluate_complete(
    bet: dict[str, Any],
    workspace: Path,
    *,
    env: dict[str, str] | None = None,
    force: bool = False,
) -> BindVerdict:
    if force:
        return BindVerdict(True, [])
    # Plan: only retro-required bets must close the vision→run→retro chain.
    if bet.get("retro") not in ("required", "light"):
        return BindVerdict(True, [])
    bet_id = str(bet.get("id") or "")
    bound = bound_runs_for_bet(workspace, bet_id)
    run_bet = bet_id if bound else ""
    return evaluate_bind(
        bet_id=bet_id,
        run_bet_id=run_bet,
        north_star_present=north_star_present(workspace),
        retro_required=True,
        retro_present=retro_path_for(workspace, bet_id).is_file(),
    )


def overdue_retros(workspace: Path) -> list[str]:
    ledger = load_ledger(workspace)
    due: list[str] = []
    for bet in ledger.get("bets") or []:
        if not isinstance(bet, dict):
            continue
        if bet.get("status") not in {"review", "done", "in_progress"}:
            continue
        if bet.get("retro") not in ("required", "light"):
            continue
        bet_id = str(bet.get("id") or "")
        if bet_id and not retro_path_for(workspace, bet_id).is_file():
            due.append(bet_id)
    return due


CLOSED_RUN_STATUSES = frozenset({"ok", "blocked", "failed"})


def run_recency_key(run: dict[str, Any]) -> str:
    """ISO timestamps and run_id sort lexicographically; latest wins."""
    return str(run.get("updated_at") or run.get("closed_at") or run.get("created_at") or run.get("run_id") or "")


def _bet_id_of(run: dict[str, Any]) -> str:
    return str(run.get("bet_id") or "").strip()


def perception_fields(workspace: Path) -> dict[str, Any]:
    """Active bound bets win; else latest closed bound run; never a false missing-bet."""
    active_runs: list[dict[str, Any]] = []
    closed_runs: list[dict[str, Any]] = []
    for run in iter_run_records(workspace):
        if not _bet_id_of(run):
            continue
        status = str(run.get("status") or "")
        if status == "active":
            active_runs.append(run)
        elif status in CLOSED_RUN_STATUSES:
            closed_runs.append(run)
    active_bets = [_bet_id_of(r) for r in active_runs]
    closed_bets = [_bet_id_of(r) for r in sorted(closed_runs, key=run_recency_key, reverse=True)]
    if active_runs:
        bound = _bet_id_of(max(active_runs, key=run_recency_key))
        bound_state = "active"
    elif closed_runs:
        bound = f"{_bet_id_of(max(closed_runs, key=run_recency_key))} (closed)"
        bound_state = "closed"
    else:
        bound = "unbound"
        bound_state = "unbound"
    due = overdue_retros(workspace)
    return {
        "north_star": NORTH_STAR_SENTENCE,
        "north_star_ref": NORTH_STAR_REF,
        "north_star_present": north_star_present(workspace),
        "bound_bet": bound,
        "bound_state": bound_state,
        "bound_bets": active_bets,
        "closed_bets": closed_bets,
        "overdue_retros": due,
        "overdue_retros_display": ",".join(due) if due else "none",
    }


def print_perception(fields: dict[str, Any]) -> None:
    print(f"chain: north_star={fields.get('north_star', '')}")
    print(f"chain: bet={fields.get('bound_bet', 'unbound')}")
    print(f"chain: overdue_retros={fields.get('overdue_retros_display', 'none')}")


def inject_perception(report: dict[str, Any], workspace: Path) -> dict[str, Any]:
    report["chain"] = perception_fields(workspace)
    return report


@dataclass(frozen=True)
class PortfolioVerdict:
    """Read-only higher-level completion predicate (T1-06). Never mutates state."""

    ok: bool
    code: str
    reasons: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {"ok": self.ok, "code": self.code, "reasons": list(self.reasons)}


def _bet_index(ledger: dict[str, Any]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for bet in ledger.get("bets") or []:
        if isinstance(bet, dict) and isinstance(bet.get("id"), str):
            out[bet["id"]] = bet
    return out


def _kr_status(ledger: dict[str, Any], kr_id: str) -> str | None:
    for objective in ledger.get("objectives") or []:
        if not isinstance(objective, dict):
            continue
        for kr in objective.get("key_results") or []:
            if isinstance(kr, dict) and kr.get("id") == kr_id:
                status = kr.get("status")
                return status if isinstance(status, str) else None
    return None


def _replacement_covers_failed(bet: dict[str, Any], index: dict[str, dict[str, Any]]) -> bool:
    """A failed BET may be conserved when a completed replacement references it."""
    if bet.get("status") != "failed":
        return False
    bet_id = str(bet.get("id") or "")
    for other in index.values():
        if other.get("status") != "done":
            continue
        if other.get("replacement_of") == bet_id or bet_id in (other.get("replaces") or []):
            return True
        # also accept explicit replaced_by on the failed leaf
    replaced_by = bet.get("replaced_by")
    if isinstance(replaced_by, str) and replaced_by in index and index[replaced_by].get("status") == "done":
        return True
    return False


def evaluate_milestone(
    milestone: dict[str, Any],
    ledger: dict[str, Any],
    evidence: dict[str, Any] | None = None,
) -> PortfolioVerdict:
    """Derived Milestone close predicate. Read-only; never writes status."""
    evidence = evidence or {}
    reasons: list[str] = []
    index = _bet_index(ledger)

    for bid in milestone.get("required_bets") or []:
        if not isinstance(bid, str):
            reasons.append("MILESTONE_FALSE_CLOSE: required_bets entry invalid")
            continue
        bet = index.get(bid)
        if bet is None:
            reasons.append(f"MILESTONE_FALSE_CLOSE: missing required bet {bid}")
            continue
        status = bet.get("status")
        if status == "done":
            continue
        if status == "failed" and _replacement_covers_failed(bet, index):
            continue
        reasons.append(f"MILESTONE_FALSE_CLOSE: required bet {bid} not terminal/replaced (status={status!r})")

    for kr_id in milestone.get("required_krs") or []:
        if not isinstance(kr_id, str):
            reasons.append("MILESTONE_FALSE_CLOSE: required_krs entry invalid")
            continue
        status = _kr_status(ledger, kr_id)
        if status != "proven":
            reasons.append(f"MILESTONE_FALSE_CLOSE: required KR {kr_id} not proven (status={status!r})")

    if evidence.get("unresolved_blocker"):
        reasons.append("MILESTONE_FALSE_CLOSE: unresolved blocker present")
    if int(evidence.get("p0_guardrail_breaches") or 0) > 0:
        reasons.append("MILESTONE_FALSE_CLOSE: p0 guardrail breach")

    # Campaign / Objective parents must also be met when declared on evidence envelope
    for cid in evidence.get("required_campaigns_unmet") or []:
        reasons.append(f"MILESTONE_FALSE_CLOSE: required campaign unmet {cid}")
    for oid in evidence.get("required_objectives_unmet") or []:
        reasons.append(f"MILESTONE_FALSE_CLOSE: required objective unmet {oid}")

    if reasons:
        return PortfolioVerdict(False, "MILESTONE_FALSE_CLOSE", reasons)
    return PortfolioVerdict(True, "MILESTONE_MET", [])


def _is_proxy_or_synthetic(sample: dict[str, Any]) -> bool:
    partition = str(sample.get("partition") or sample.get("evidence_partition") or "").lower()
    if partition in {"test", "synthetic", "proxy"}:
        return True
    if sample.get("proxy") is True:
        return True
    if sample.get("synthetic") is True:
        return True
    return False


def _is_principal_bound(sample: dict[str, Any]) -> bool:
    if sample.get("principal_bound") is True:
        return True
    if sample.get("human_verdict_bound") is True:
        return True
    att = sample.get("attestation")
    return isinstance(att, dict) and bool(att.get("ref"))


def evaluate_vision(
    vision: dict[str, Any],
    objectives: list[PortfolioVerdict] | list[dict[str, Any]],
    window: list[dict[str, Any]],
    *,
    evidence: dict[str, Any] | None = None,
) -> PortfolioVerdict:
    """Derived Vision close predicate. Read-only; never writes status."""
    evidence = evidence or {}
    reasons: list[str] = []

    # Required objectives must all be met
    for obj in objectives:
        if isinstance(obj, PortfolioVerdict):
            ok, code = obj.ok, obj.code
        elif isinstance(obj, dict):
            ok, code = bool(obj.get("ok")), str(obj.get("code") or "")
        else:
            reasons.append("MILESTONE_FALSE_CLOSE: objective verdict invalid")
            continue
        if not ok:
            reasons.append(f"MILESTONE_FALSE_CLOSE: required objective unmet ({code})")

    for cid in evidence.get("required_campaigns_unmet") or []:
        reasons.append(f"MILESTONE_FALSE_CLOSE: required campaign unmet {cid}")

    if len(window) < 12:
        reasons.append(f"VISION_WINDOW_INCOMPLETE: weeks={len(window)} need>=12")

    for sample in window:
        if not isinstance(sample, dict):
            reasons.append("VALUE_PROXY_REJECTED: window sample not a mapping")
            continue
        if _is_proxy_or_synthetic(sample):
            reasons.append("VALUE_PROXY_REJECTED: synthetic/proxy evidence partition")
        if not _is_principal_bound(sample):
            reasons.append("VALUE_PROXY_REJECTED: human evidence not principal-bound")

    # Weekly thresholds (optional keys on evidence)
    min_accepted = evidence.get("min_accepted_outputs_per_week")
    if isinstance(min_accepted, (int, float)):
        for sample in window:
            if isinstance(sample, dict) and sample.get("accepted_outputs") is not None:
                if float(sample["accepted_outputs"]) < float(min_accepted):
                    reasons.append("VISION_WINDOW_INCOMPLETE: accepted_outputs below threshold")
                    break
    min_rate = evidence.get("min_acceptance_rate")
    if isinstance(min_rate, (int, float)):
        for sample in window:
            if isinstance(sample, dict) and sample.get("acceptance_rate") is not None:
                if float(sample["acceptance_rate"]) < float(min_rate):
                    reasons.append("VISION_WINDOW_INCOMPLETE: acceptance_rate below threshold")
                    break
    if evidence.get("edit_burden_improved") is False:
        reasons.append("VISION_WINDOW_INCOMPLETE: edit-burden did not improve")

    if not evidence.get("human_final_verdict"):
        reasons.append("VISION_WINDOW_INCOMPLETE: missing human final verdict")

    # Value-exempt delivery cannot advance value KRs
    if evidence.get("value_exempt_attempted_value_kr"):
        reasons.append("VALUE_PROXY_REJECTED: value_indicator_policy=false delivery cannot advance value KR")

    # Deduplicate while preserving order
    dedup: list[str] = []
    seen: set[str] = set()
    for r in reasons:
        if r not in seen:
            seen.add(r)
            dedup.append(r)

    if any(r.startswith("VALUE_PROXY_REJECTED") for r in dedup):
        code = "VALUE_PROXY_REJECTED"
    elif any(r.startswith("VISION_WINDOW_INCOMPLETE") for r in dedup):
        code = "VISION_WINDOW_INCOMPLETE"
    elif dedup:
        code = "MILESTONE_FALSE_CLOSE"
    else:
        return PortfolioVerdict(True, "VISION_MET", [])
    return PortfolioVerdict(False, code, dedup)

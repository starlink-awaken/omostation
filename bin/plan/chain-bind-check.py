#!/usr/bin/env python3
"""Redline executor for the Plan→BET→workflow→closeout→retro chain.

Exit 1 on missing --bet (requirement-iteration start), missing binding,
missing north-star pointer, or missing retro. Used as redlines.yaml executor
and as the shared CLI for closeout / bet-ledger complete.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

import chain_bind


def _workspace() -> Path:
    return Path(__file__).resolve().parents[2]


def _load_json_or_yaml(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    if path.suffix == ".json":
        data = json.loads(text)
    else:
        import yaml

        data = yaml.safe_load(text)
    if not isinstance(data, dict):
        raise SystemExit(f"not an object: {path}")
    return data


def cmd_start(args: argparse.Namespace) -> int:
    verdict = chain_bind.start_requires_bet(args.workflow, args.bet or "")
    _emit(verdict, args.json)
    return 0 if verdict.ok else 1


def cmd_closeout(args: argparse.Namespace) -> int:
    run = _load_json_or_yaml(Path(args.run))
    ws = Path(args.workspace) if args.workspace else _workspace()
    verdict = chain_bind.evaluate_closeout(run, ws, status=args.status)
    _emit(verdict, args.json)
    return 0 if verdict.ok else 1


def cmd_complete(args: argparse.Namespace) -> int:
    ws = Path(args.workspace) if args.workspace else _workspace()
    if args.bet_json:
        bet = _load_json_or_yaml(Path(args.bet_json))
    else:
        ledger = chain_bind.load_ledger(ws)
        bet = chain_bind.bet_by_id(ledger, args.bet_id) or {}
        if not bet:
            print(f"chain-bind-check: unknown bet {args.bet_id}", file=sys.stderr)
            return 1
        bet = dict(bet)
        bet.setdefault("id", args.bet_id)
    if args.retro_path:
        # fixture override: evaluate_bind directly
        retro_present = Path(args.retro_path).is_file()
        run_bet = args.run_bet_id if args.run_bet_id is not None else bet.get("id")
        if args.missing_run_bind:
            run_bet = ""
        verdict = chain_bind.evaluate_bind(
            bet_id=str(bet.get("id") or ""),
            run_bet_id=str(run_bet or ""),
            north_star_present=(
                True
                if args.north_star == "yes"
                else False
                if args.north_star == "no"
                else chain_bind.north_star_present(ws)
            ),
            retro_required=bet.get("retro") in ("required", "light"),
            retro_present=retro_present,
        )
    else:
        verdict = chain_bind.evaluate_complete(bet, ws, force=args.force)
    _emit(verdict, args.json)
    return 0 if verdict.ok else 1



def cmd_portfolio(args: argparse.Namespace) -> int:
    """Read-only Milestone/Vision predicates (T1-06). Never mutates Ledger/OMO."""
    ws = Path(args.workspace) if args.workspace else _workspace()
    ledger = chain_bind.load_ledger(ws) if not args.ledger_json else _load_json_or_yaml(Path(args.ledger_json))
    evidence = {}
    if args.evidence_json:
        evidence = _load_json_or_yaml(Path(args.evidence_json))

    if args.milestone_id:
        milestones = ledger.get("milestones") or []
        milestone = next((m for m in milestones if isinstance(m, dict) and m.get("id") == args.milestone_id), None)
        if milestone is None and args.milestone_json:
            milestone = _load_json_or_yaml(Path(args.milestone_json))
        if milestone is None:
            print(f"chain-bind-check: unknown milestone {args.milestone_id}", file=sys.stderr)
            return 1
        verdict = chain_bind.evaluate_milestone(milestone, ledger, evidence)
    elif args.vision:
        vision = ledger.get("vision") if isinstance(ledger.get("vision"), dict) else {"id": "VISION"}
        objectives = []
        if args.objectives_json:
            objectives = _load_json_or_yaml(Path(args.objectives_json))
            if isinstance(objectives, dict):
                objectives = objectives.get("objectives") or []
        window = []
        if args.window_json:
            window = _load_json_or_yaml(Path(args.window_json))
            if isinstance(window, dict):
                window = window.get("window") or []
        verdict = chain_bind.evaluate_vision(vision, objectives, window, evidence=evidence)
    else:
        print("chain-bind-check portfolio: require --milestone-id or --vision", file=sys.stderr)
        return 2

    payload = verdict.as_dict()
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    else:
        print(f"{'OK' if verdict.ok else 'FAIL'} -- {verdict.code}")
        for reason in verdict.reasons:
            print(f"  {reason}")
    return 0 if verdict.ok else 1



def cmd_self_check(_args: argparse.Namespace) -> int:
    """Deterministic fixture cases — used by T6-02 verify (not file-exists theater)."""
    cases = [
        (
            "start-missing-bet",
            chain_bind.start_requires_bet("governance-state-mutation", ""),
            False,
        ),
        (
            "start-with-bet",
            chain_bind.start_requires_bet("governance-state-mutation", "BET-Y1Q1-T6-02"),
            True,
        ),
        (
            "start-observer-exempt",
            chain_bind.start_requires_bet("observer-audit", ""),
            True,
        ),
        (
            "closeout-missing-retro",
            chain_bind.evaluate_bind(
                bet_id="BET-Y1Q1-T6-02",
                run_bet_id="BET-Y1Q1-T6-02",
                north_star_present=True,
                retro_required=True,
                retro_present=False,
            ),
            False,
        ),
        (
            "closeout-complete",
            chain_bind.evaluate_bind(
                bet_id="BET-Y1Q1-T6-02",
                run_bet_id="BET-Y1Q1-T6-02",
                north_star_present=True,
                retro_required=True,
                retro_present=True,
            ),
            True,
        ),
        (
            "closeout-missing-bind",
            chain_bind.evaluate_bind(
                bet_id="BET-Y1Q1-T6-02",
                run_bet_id="",
                north_star_present=True,
                retro_required=True,
                retro_present=True,
            ),
            False,
        ),
        (
            "closeout-missing-north-star",
            chain_bind.evaluate_bind(
                bet_id="BET-Y1Q1-T6-02",
                run_bet_id="BET-Y1Q1-T6-02",
                north_star_present=False,
                retro_required=True,
                retro_present=True,
            ),
            False,
        ),
        # G8: 治理演进 workflow 无业务 bet, ledger 有治理 bet → 豁免
        (
            "closeout-governance-evolve-no-bet",
            chain_bind.evaluate_closeout(
                {"workflow_id": "governance-audit", "bet_id": ""},
                _workspace(),
                status="ok",
            ),
            True,
        ),
        (
            "closeout-governance-evolve-no-bet-no-ldg",
            chain_bind.evaluate_closeout(
                {"workflow_id": "governance-audit", "bet_id": ""},
                Path("/nonexistent-workspace"),
                status="ok",
            ),
            False,
        ),
        (
            "closeout-business-no-bet-still-halts",
            chain_bind.evaluate_closeout(
                {"workflow_id": "project-code-change", "bet_id": ""},
                _workspace(),
                status="ok",
            ),
            False,
        ),
    ]
    failed: list[str] = []
    for name, verdict, expect_ok in cases:
        if verdict.ok != expect_ok:
            failed.append(f"{name}: ok={verdict.ok} expected={expect_ok} {verdict.reasons}")
    if failed:
        print("chain-bind-check self-check FAIL")
        for row in failed:
            print(f"  {row}")
        return 1
    print("chain-bind-check self-check PASS")
    print(f"  {len(cases)} fixture cases")
    return 0


def cmd_perception(args: argparse.Namespace) -> int:
    ws = Path(args.workspace) if args.workspace else _workspace()
    fields = chain_bind.perception_fields(ws)
    if args.json:
        print(json.dumps(fields, ensure_ascii=False, indent=2))
    else:
        chain_bind.print_perception(fields)
    return 0


def _emit(verdict: chain_bind.BindVerdict, as_json: bool) -> None:
    if as_json:
        print(json.dumps(verdict.as_dict(), ensure_ascii=False))
        return
    status = "PASS" if verdict.ok else "FAIL"
    print(f"chain-bind-check: {status}")
    for reason in verdict.reasons:
        print(f"  - {reason}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--json", action="store_true")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_start = sub.add_parser("start", help="gate a requirement-iteration start")
    p_start.add_argument("--workflow", required=True)
    p_start.add_argument("--bet", default="")

    p_co = sub.add_parser("closeout", help="gate an ok closeout")
    p_co.add_argument("--run", required=True, help="run record yaml/json")
    p_co.add_argument("--status", default="ok")
    p_co.add_argument("--workspace", default="")

    p_cp = sub.add_parser("complete", help="gate bet-ledger complete")
    p_cp.add_argument("--bet-id", default="")
    p_cp.add_argument("--bet-json", default="")
    p_cp.add_argument("--workspace", default="")
    p_cp.add_argument("--retro-path", default="")
    p_cp.add_argument("--run-bet-id", default=None)
    p_cp.add_argument("--missing-run-bind", action="store_true")
    p_cp.add_argument("--north-star", choices=["yes", "no", "detect"], default="detect")
    p_cp.add_argument("--force", action="store_true")

    portfolio_p = sub.add_parser("portfolio", help="T1-06 Milestone/Vision derived predicates (read-only)")
    portfolio_p.add_argument("--workspace", default="")
    portfolio_p.add_argument("--ledger-json", default="")
    portfolio_p.add_argument("--evidence-json", default="")
    portfolio_p.add_argument("--milestone-id", default="")
    portfolio_p.add_argument("--milestone-json", default="")
    portfolio_p.add_argument("--vision", action="store_true")
    portfolio_p.add_argument("--objectives-json", default="")
    portfolio_p.add_argument("--window-json", default="")
    portfolio_p.add_argument("--json", action="store_true")
    portfolio_p.set_defaults(func=cmd_portfolio)

    sub.add_parser("self-check", help="run fixture halt/pass cases")
    p_pe = sub.add_parser("perception", help="print north-star / bet / overdue retros")
    p_pe.add_argument("--workspace", default="")

    args = parser.parse_args(argv)
    return {
        "start": cmd_start,
        "closeout": cmd_closeout,
        "complete": cmd_complete,
        "self-check": cmd_self_check,
        "perception": cmd_perception,
    }[args.cmd](args)


if __name__ == "__main__":
    raise SystemExit(main())

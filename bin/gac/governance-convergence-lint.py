#!/usr/bin/env python3
"""Governance Convergence Linter (ADR-0121 GCSI).

Validates that governance declarations are registered, executed, and verified
—the "convergence layer" that closes the declaration→registration→execution
→verification→feedback loop.

Rules:
  R-GOV-1 ERROR  ADR-referenced CR-* rules must be registered in governance-checks.yaml
  R-GOV-2 WARN   health_score vs health_score_evidence divergence < 5
  R-GOV-3 WARN   governance feedback loop alive (last run < 6h, ERROR if > 24h)
  R-GOV-4 WARN   matrix.yaml port ↔ port-registry.yaml consistency (delegates to matrix-consistency-lint)
  R-GOV-5 WARN   AGENTS.md gac.rules_count matches actual governance-checks.yaml count
  R-GOV-6 ERROR  daemon services have launchd_label or docker_container (delegates to matrix-consistency-lint)

Usage:
  python3 bin/gac/governance-convergence-lint.py [--rule <name>] [--json]
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[2]
DECISIONS_DIR = WORKSPACE / ".omo/_knowledge/decisions"
GOV_CHECKS_YAML = WORKSPACE / ".omo/_truth/registry/governance-checks.yaml"
SYSTEM_YAML = WORKSPACE / ".omo/state/system.yaml"
AGENTS_MD = WORKSPACE / "AGENTS.md"


def _extract_cr_ids_from_adrs() -> set[str]:
    """Extract all CR-* rule IDs referenced in ADR files."""
    cr_ids: set[str] = set()
    pattern = re.compile(r"\b(CR-[A-Z0-9][-A-Z0-9]*)\b")
    for adr_file in DECISIONS_DIR.glob("*.md"):
        try:
            text = adr_file.read_text(encoding="utf-8")
            cr_ids.update(pattern.findall(text))
        except Exception:
            continue
    return cr_ids


def _extract_registered_cr_ids() -> set[str]:
    """Extract registered CR-* rule IDs from governance-checks.yaml."""
    registered: set[str] = set()
    pattern = re.compile(r"^\s+-\s+id:\s+(CR-[A-Z0-9][-A-Z0-9]*)", re.MULTILINE)
    try:
        text = GOV_CHECKS_YAML.read_text(encoding="utf-8")
        registered.update(pattern.findall(text))
    except Exception:
        pass
    return registered


def _read_system_yaml() -> dict:
    try:
        import yaml
        return yaml.safe_load(SYSTEM_YAML.read_text(encoding="utf-8")) or {}
    except Exception:
        return {}


def check_rule_registration() -> tuple[list[str], list[str]]:
    """R-GOV-1: ADR-referenced CR-* rules must be registered."""
    errors, warnings = [], []
    adr_cr_ids = _extract_cr_ids_from_adrs()
    registered_ids = _extract_registered_cr_ids()
    unregistered = adr_cr_ids - registered_ids
    if unregistered:
        for cr_id in sorted(unregistered):
            errors.append(
                f"R-GOV-1 ERROR: Rule '{cr_id}' referenced in ADR but not registered in governance-checks.yaml"
            )
    return errors, warnings


def check_score_convergence() -> tuple[list[str], list[str]]:
    """R-GOV-2: health_score vs evidence score divergence < 5."""
    errors, warnings = [], []
    data = _read_system_yaml()
    health_score = data.get("health_score")
    evidence_score = data.get("health_score_evidence")
    if health_score is not None and evidence_score is not None:
        diff = abs(float(health_score) - float(evidence_score))
        if diff > 5:
            warnings.append(
                f"R-GOV-2 WARN: health_score ({health_score}) vs health_score_evidence ({evidence_score}) "
                f"divergence {diff:.1f} > 5"
            )
    elif health_score is not None and evidence_score is None:
        warnings.append(
            "R-GOV-2 WARN: health_score_evidence field missing from system.yaml "
            "(run evidence-smoke.py to populate)"
        )
    return errors, warnings


def _git_last_commit_age_hours() -> float | None:
    """git 最近 commit 年龄 (CI fallback: tracked system.yaml stale 时验回路活性).

    system.yaml 的 governance_feedback_last_run 是 tracked 运行快照, CI checkout 拿到
    上次 commit 的值 (可能 stale). 用 git 最近 commit 作为回路活性的第二源 (多源 OR),
    避免 CI 上因运行时服务不存在而误判 stalled. 见 feedback-loop-recovery-generator-trap.
    """
    try:
        import subprocess
        from datetime import datetime, timezone
        r = subprocess.run(
            ["git", "log", "-1", "--format=%ct"],
            capture_output=True, text=True, timeout=10, cwd=WORKSPACE,
        )
        if r.returncode == 0 and r.stdout.strip():
            ts = int(r.stdout.strip())
            now = datetime.now(timezone.utc).timestamp()
            return max(0.0, (now - ts) / 3600)
    except Exception:
        pass
    return None


def check_feedback_loop() -> tuple[list[str], list[str]]:
    """R-GOV-3: governance feedback loop alive (last run < 6h)."""
    errors, warnings = [], []
    data = _read_system_yaml()
    last_run = data.get("governance_feedback_last_run")
    if last_run is None:
        # Fallback: use updated_at as proxy
        last_run = data.get("updated_at")
    if last_run:
        try:
            from datetime import datetime, timezone
            # Parse ISO format with timezone
            dt = datetime.fromisoformat(last_run.replace("Z", "+00:00"))
            now = datetime.now(timezone.utc)
            age_hours = (now - dt).total_seconds() / 3600
            if age_hours > 24:
                # CI fallback: tracked system.yaml 的 last_run 是 commit 快照 (可能 stale),
                # 用 git 最近 commit 验回路活性 (有开发活动 = 回路活着). 多源 OR.
                git_age = _git_last_commit_age_hours()
                if git_age is not None and git_age < 24:
                    warnings.append(
                        f"R-GOV-3 WARN: system.yaml last_run {age_hours:.1f}h stale "
                        f"(tracked 快照), but git active {git_age:.1f}h ago — 回路活着, 降级 WARN"
                    )
                else:
                    errors.append(
                        f"R-GOV-3 ERROR: Governance feedback loop stalled for {age_hours:.1f}h (> 24h)"
                    )
            elif age_hours > 6:
                warnings.append(
                    f"R-GOV-3 WARN: Governance feedback loop last run {age_hours:.1f}h ago (> 6h)"
                )
        except Exception as e:
            warnings.append(f"R-GOV-3 WARN: Cannot parse governance_feedback_last_run '{last_run}': {e}")
    else:
        warnings.append("R-GOV-3 WARN: governance_feedback_last_run not found in system.yaml")
    return errors, warnings


def check_rules_count() -> tuple[list[str], list[str]]:
    """R-GOV-5: AGENTS.md gac.rules_count matches actual count."""
    errors, warnings = [], []
    # Count actual rules in governance-checks.yaml
    registered = _extract_registered_cr_ids()
    actual_count = len(registered)
    # Find gac.rules_count in AGENTS.md or generated docs
    try:
        gen_path = WORKSPACE / "docs/generated/agent-gac-rules.md"
        if gen_path.exists():
            text = gen_path.read_text(encoding="utf-8")
            match = re.search(r"(\d+)\s+条规则", text)
            if match:
                doc_count = int(match.group(1))
                if doc_count != actual_count:
                    warnings.append(
                        f"R-GOV-5 WARN: docs/generated/agent-gac-rules.md says {doc_count} rules, "
                        f"actual governance-checks.yaml has {actual_count}"
                    )
    except Exception:
        pass
    return errors, warnings


def check_matrix_consistency() -> tuple[list[str], list[str]]:
    """R-GOV-4/6: Delegate to matrix-consistency-lint for port/launchd checks."""
    errors, warnings = [], []
    lint_script = WORKSPACE / "bin/ssot/matrix-consistency-lint.py"
    if not lint_script.exists():
        warnings.append("R-GOV-4/6 WARN: bin/ssot/matrix-consistency-lint.py not found")
        return errors, warnings
    try:
        r = subprocess.run(
            [sys.executable, str(lint_script), "--skip-launchd", "--json"],
            capture_output=True, text=True, timeout=30, cwd=WORKSPACE,
        )
        if r.returncode == 0:
            result = json.loads(r.stdout)
            for e in result.get("errors", []):
                errors.append(f"R-GOV-6 ERROR: {e}")
            for w in result.get("warnings", []):
                warnings.append(f"R-GOV-4 WARN: {w}")
        else:
            # matrix-consistency-lint exited non-zero (has errors)
            try:
                result = json.loads(r.stdout)
                for e in result.get("errors", []):
                    errors.append(f"R-GOV-6 ERROR: {e}")
                for w in result.get("warnings", []):
                    warnings.append(f"R-GOV-4 WARN: {w}")
            except Exception:
                errors.append(f"R-GOV-6 ERROR: matrix-consistency-lint failed: {r.stderr.strip()[:200]}")
    except Exception as e:
        warnings.append(f"R-GOV-4/6 WARN: matrix-consistency-lint execution error: {e}")
    return errors, warnings


def lint(rule_filter: str | None = None) -> tuple[list[str], list[str]]:
    """Run all convergence checks. Returns (errors, warnings)."""
    checks = {
        "registration": check_rule_registration,
        "score": check_score_convergence,
        "loop": check_feedback_loop,
        "rules-count": check_rules_count,
        "matrix": check_matrix_consistency,
    }
    all_errors: list[str] = []
    all_warnings: list[str] = []
    for name, check_fn in checks.items():
        if rule_filter and rule_filter != name:
            continue
        errs, warns = check_fn()
        all_errors.extend(errs)
        all_warnings.extend(warns)
    return all_errors, all_warnings


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Governance convergence linter (ADR-0121 GCSI)")
    parser.add_argument("--rule", help="Run specific rule only (registration/score/loop/rules-count/matrix)")
    parser.add_argument("--json", action="store_true", help="Output JSON")
    args = parser.parse_args()

    errors, warnings = lint(rule_filter=args.rule)

    if args.json:
        print(json.dumps({"errors": errors, "warnings": warnings, "ok": len(errors) == 0}))
    else:
        for w in warnings:
            print(w)
        for e in errors:
            print(e, file=sys.stderr)
        if errors:
            print(f"\n{len(errors)} ERROR(s), {len(warnings)} WARN(s)", file=sys.stderr)
        elif warnings:
            print(f"\n{len(warnings)} WARN(s), 0 ERRORs")

    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()

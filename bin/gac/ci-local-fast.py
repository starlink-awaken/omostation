"""Run the local pre-push checks without losing producer exit codes.

The former Make recipe piped every producer through ``sed`` under ``/bin/sh``.
POSIX pipelines report the final command's status, so a failing producer looked
green whenever ``sed`` succeeded.  This runner owns prefixing and failure
aggregation directly and keeps the broad Ruff inventory as explicit debt while
blocking diagnostics beyond the reviewed baseline.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import subprocess
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, TextIO

WORKSPACE = Path(__file__).resolve().parents[2]
BASELINE_PATH = WORKSPACE / ".omo/_truth/registry/ruff-diagnostics-baseline.yaml"
RuffKey = tuple[str, str, str]
RUFF_BASELINE_MAXIMA: dict[RuffKey, int] = {
    # 2026-08-27: cockpit 子仓 33cc02ba 更新带入 (PR #2313), 原 omo 6 条已全部修复
    (
        "projects/cockpit/src/cockpit/web/api_workflow_mesh_operations.py",
        "F811",
        "Redefinition of unused `_build_draft_from_snapshot`",
    ): 1,
    (
        "projects/cockpit/src/cockpit/web/api_workflow_mesh_operations.py",
        "F811",
        "Redefinition of unused `_normalize_resp_input`",
    ): 1,
    (
        "projects/cockpit/src/cockpit/web/api_workflow_mesh_operations.py",
        "F811",
        "Redefinition of unused `_optional_burden`",
    ): 1,
    (
        "projects/cockpit/src/cockpit/web/api_workflow_mesh_operations.py",
        "F811",
        "Redefinition of unused `_personal_draft_evidence_ref`",
    ): 1,
    (
        "projects/cockpit/src/cockpit/web/api_workflow_mesh_operations.py",
        "F811",
        "Redefinition of unused `_personal_error`",
    ): 1,
    (
        "projects/cockpit/src/cockpit/web/api_workflow_mesh_operations.py",
        "F811",
        "Redefinition of unused `_projection_fields`",
    ): 1,
    (
        "projects/cockpit/src/cockpit/web/api_workflow_mesh_operations.py",
        "F811",
        "Redefinition of unused `_projection_value_is_private`",
    ): 1,
    (
        "projects/cockpit/src/cockpit/web/api_workflow_mesh_operations.py",
        "F811",
        "Redefinition of unused `_required_text`",
    ): 1,
    (
        "projects/cockpit/src/cockpit/web/api_external_resources.py",
        "F811",
        "Redefinition of unused `_latest_catalog`",
    ): 1,
    (
        "projects/cockpit/src/cockpit/web/api_external_resources.py",
        "F811",
        "Redefinition of unused `_latest_observation`",
    ): 1,
    (
        "projects/cockpit/src/cockpit/web/api_external_resources.py",
        "F811",
        "Redefinition of unused `_resolve_catalog_projection`",
    ): 1,
}
RUFF_BASELINE_CAP = sum(RUFF_BASELINE_MAXIMA.values())


@dataclass(frozen=True)
class Check:
    key: str
    title: str
    command: tuple[str, ...]
    blocking: bool = True


@dataclass(frozen=True)
class RuffComparison:
    known: dict[RuffKey, int]
    new: dict[RuffKey, int]
    resolved: dict[RuffKey, int]


def run_check(check: Check, *, cwd: Path, output: TextIO) -> int:
    """Run one producer, prefix combined output, and preserve its return code."""

    output.write(f"── {check.title} {'─' * max(1, 52 - len(check.title))}\n")
    try:
        proc = subprocess.Popen(
            check.command,
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except OSError as exc:
        output.write(f"[{check.key}] unable to start: {exc}\n")
        return 127

    assert proc.stdout is not None
    output.writelines(f"[{check.key}] {line}" for line in proc.stdout)
    return proc.wait()


UNINIT_MARKERS = (
    "submodule not initialized",
    "子模块未初始化",
    "git submodule update --init",
    "partial worktree",
)
INNER_BASELINE_KEYS = frozenset({"ruff"})

# ADR-0443 v6: 定向失败行提取——v5 人审退回草案的直接根因是头部 240 截断
# 只装得下 banner+PASS 段，失败核心丢失。改为优先抓失败行及其后 2 行
# （gate 的修复指引通常紧跟），无失败标记才回退头部截断（旧行为）。
FAILURE_MARKERS = ("\u274c", "FAIL", "Error", "error:", "\u9519\u8bef")


def failure_excerpt(text: str, limit: int = 240) -> str:
    lines = [ln.strip() for ln in (text or "").splitlines() if ln.strip()]
    for i, ln in enumerate(lines):
        if any(m in ln for m in FAILURE_MARKERS):
            joined = " | ".join(lines[i : i + 3])
            return " ".join(joined.split())[:limit]
    return " ".join(" ".join(lines).split())[:limit]


def classify_preflight_failure(check_key: str, output: str) -> dict[str, Any]:
    """Map a ci-local-fast producer failure to a skip-layer fingerprint."""
    text = output or ""
    lowered = text.lower()
    producer = check_key
    if producer in INNER_BASELINE_KEYS:
        kind = "inner-baseline"
        check_id = producer
    elif any(marker.lower() in lowered for marker in UNINIT_MARKERS):
        kind = "uninitialized-submodule"
        check_id = f"uninitialized-submodule:{producer}"
    else:
        kind = "preflight"
        check_id = producer
    excerpt = failure_excerpt(text)
    signature = hashlib.sha256(f"{producer}\n{excerpt}".encode()).hexdigest()[:16]
    return {
        "surface": "ci-local-fast",
        "check_id": check_id,
        "signature": signature,
        "kind": kind,
        "producer": producer,
        "output_excerpt": excerpt,
    }


def run_suite(
    checks: tuple[Check, ...],
    *,
    cwd: Path,
    output: TextIO,
    failure_sink: list[dict[str, Any]] | None = None,
) -> int:
    """Run all checks so one failure cannot hide evidence from later checks."""

    failures: list[tuple[str, int]] = []
    for check in checks:
        buf = io.StringIO()
        returncode = run_check(check, cwd=cwd, output=buf)
        text = buf.getvalue()
        output.write(text)
        output.write("\n")
        if returncode == 0:
            continue
        if check.blocking:
            failures.append((check.key, returncode))
            output.write(f"❌ {check.key}: exit {returncode}\n\n")
            if failure_sink is not None:
                failure_sink.append(classify_preflight_failure(check.key, text))
        else:
            output.write(f"⚠️ {check.key}: DEBT/ADVISORY exit {returncode}; 不计为通过，也不阻断本地提交\n\n")

    if failures:
        summary = ", ".join(f"{key}={returncode}" for key, returncode in failures)
        output.write(f"❌ ci-local-fast: blocking check 失败 ({summary})\n")
        return 1
    output.write("✅ ci-local-fast: 全部 blocking checks 通过\n")
    return 0


def _load_ruff_baseline(
    path: Path = BASELINE_PATH,
) -> tuple[dict[str, Any], Counter[RuffKey]]:
    try:
        import yaml
    except ImportError as exc:  # pragma: no cover - Make supplies pyyaml
        raise RuntimeError("pyyaml is required for the Ruff baseline") from exc

    if not path.is_file():
        raise RuntimeError(f"Ruff baseline not found: {path}")
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if payload.get("version") != 1 or not isinstance(payload.get("policy"), dict):
        raise RuntimeError(f"invalid Ruff baseline schema: {path}")

    baseline: Counter[RuffKey] = Counter()
    for item in payload.get("diagnostics") or []:
        if not isinstance(item, dict):
            raise TypeError("Ruff baseline diagnostics must be mappings")
        key = (
            str(item.get("path") or ""),
            str(item.get("code") or ""),
            _normalize_ruff_message(str(item.get("message") or "")),
        )
        count = item.get("count")
        if not all(key) or not isinstance(count, int) or count < 1:
            raise RuntimeError(f"invalid Ruff baseline diagnostic: {item!r}")
        baseline[key] += count
    policy = payload["policy"]
    if policy.get("growth_policy") != "forbidden":
        raise RuntimeError("Ruff baseline growth_policy must be forbidden")
    if policy.get("hard_cap") != RUFF_BASELINE_CAP:
        raise RuntimeError(f"Ruff baseline hard_cap must remain {RUFF_BASELINE_CAP}")
    if policy.get("captured_diagnostic_count") != sum(baseline.values()):
        raise RuntimeError("Ruff baseline captured_diagnostic_count does not match diagnostics")
    if sum(baseline.values()) > RUFF_BASELINE_CAP:
        raise RuntimeError(f"Ruff baseline exceeds hard cap {RUFF_BASELINE_CAP}: {sum(baseline.values())}")
    for key, count in baseline.items():
        maximum = RUFF_BASELINE_MAXIMA.get(key)
        if maximum is None:
            raise RuntimeError(f"Ruff baseline contains unapproved bucket: {key!r}")
        if count > maximum:
            raise RuntimeError(f"Ruff baseline bucket exceeds approved maximum {maximum}: {key!r}={count}")
    return policy, baseline


def _normalize_ruff_message(message: str) -> str:
    """剥 ruff 消息中的行号 (F811 'from line N: ...'), 使 baseline 对代码位移鲁棒."""
    # F811: "Redefinition of unused `xxx` from line 27: `xxx` redefined here"
    # → "Redefinition of unused `xxx`"
    import re

    m = re.match(r"(.+?)\s+from line \d+:.*", message)
    if m:
        return m.group(1)
    return message


def _diagnostic_counts(diagnostics: list[dict[str, Any]], *, root: Path) -> Counter[RuffKey]:
    counts: Counter[RuffKey] = Counter()
    resolved_root = root.resolve()
    for item in diagnostics:
        filename = Path(str(item.get("filename") or ""))
        absolute = filename if filename.is_absolute() else resolved_root / filename
        try:
            relpath = absolute.resolve().relative_to(resolved_root).as_posix()
        except ValueError as exc:
            raise RuntimeError(f"Ruff diagnostic outside workspace: {filename}") from exc
        raw_message = str(item.get("message") or "")
        message = _normalize_ruff_message(raw_message)
        key = (relpath, str(item.get("code") or ""), message)
        if not key[1] or not key[2]:
            raise RuntimeError(f"malformed Ruff diagnostic: {item!r}")
        counts[key] += 1
    return counts


def compare_ruff_diagnostics(
    diagnostics: list[dict[str, Any]], baseline: dict[RuffKey, int], *, root: Path
) -> RuffComparison:
    current = _diagnostic_counts(diagnostics, root=root)
    expected = Counter(baseline)
    keys = set(current) | set(expected)
    known = {key: min(current[key], expected[key]) for key in keys if min(current[key], expected[key])}
    new = {key: current[key] - expected[key] for key in keys if current[key] > expected[key]}
    resolved = {key: expected[key] - current[key] for key in keys if expected[key] > current[key]}
    return RuffComparison(known=known, new=new, resolved=resolved)


def _ruff_json(policy: dict[str, Any], *, root: Path, debt: bool) -> list[dict[str, Any]]:
    scope_key = "debt_scope" if debt else "blocking_scope"
    ignore_key = "debt_ignore" if debt else "ignore"
    scopes = [str(item) for item in policy.get(scope_key) or []]
    if not scopes:
        raise RuntimeError(f"Ruff policy has no {scope_key}")
    missing = [scope for scope in scopes if not (root / scope).exists()]
    if missing:
        # BET-Y1Q3-T10-09: worktree 环境感知 — 未 init 子模块时降级 skip 非 fail.
        # 判据: .git 指向 worktrees/ 子目录 = fresh worktree, 非主仓遗漏.
        git_dir = root / ".git"
        is_worktree = git_dir.is_file() and "worktrees" in git_dir.read_text()
        if is_worktree:
            print(
                f"SKIP: ruff (worktree scope dirs not initialized: {', '.join(missing)}). "
                f"Run: bash bin/gac/worktree-init.sh --minimal"
            )
            return []  # 空 diagnostics → compare_ruff_diagnostics 得 new=0, 降级 skip 非 fail (T10-09)
        raise RuntimeError(f"Ruff scope is not initialized: {', '.join(missing)}")

    command = ["ruff", "check", *scopes]
    selected = [str(item) for item in policy.get("select") or []]
    ignored = [str(item) for item in policy.get(ignore_key) or []]
    if not debt and selected:
        command.extend(("--select", ",".join(selected)))
    if ignored:
        command.extend(("--ignore", ",".join(ignored)))
    command.extend(("--output-format", "json"))
    try:
        proc = subprocess.run(command, cwd=root, capture_output=True, text=True, check=False)
    except OSError as exc:
        raise RuntimeError(f"unable to run Ruff: {exc}") from exc
    if proc.returncode not in {0, 1}:
        raise RuntimeError(f"Ruff execution failed (exit {proc.returncode}): {proc.stderr.strip()}")
    try:
        diagnostics = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Ruff returned invalid JSON: {proc.stdout[:200]!r}") from exc
    if not isinstance(diagnostics, list) or not all(isinstance(item, dict) for item in diagnostics):
        raise RuntimeError("Ruff JSON must be a list of diagnostics")
    return diagnostics


def run_ruff_gate(*, root: Path = WORKSPACE, output: TextIO = sys.stdout) -> int:
    try:
        policy, baseline = _load_ruff_baseline()
        diagnostics = _ruff_json(policy, root=root, debt=False)
        comparison = compare_ruff_diagnostics(diagnostics, baseline, root=root)
    except (RuntimeError, TypeError) as exc:
        output.write(f"ERROR: {exc}\n")
        return 2

    known_count = sum(comparison.known.values())
    resolved_count = sum(comparison.resolved.values())
    new_count = sum(comparison.new.values())
    output.write(f"Ruff regression gate: known_debt={known_count} resolved={resolved_count} new={new_count}\n")
    output.writelines(
        f"NEW {path} {code} x{count}: {message}\n" for (path, code, message), count in sorted(comparison.new.items())
    )
    if resolved_count:
        output.write("INFO: baseline 中已有诊断已消除；后续可收缩 baseline，禁止扩容。\n")
    return 1 if new_count else 0


def run_ruff_debt_report(*, root: Path = WORKSPACE, output: TextIO = sys.stdout) -> int:
    try:
        policy, _ = _load_ruff_baseline()
        diagnostics = _ruff_json(policy, root=root, debt=True)
    except (RuntimeError, TypeError) as exc:
        output.write(f"ERROR: {exc}\n")
        return 2
    counts = Counter(str(item.get("code") or "UNKNOWN") for item in diagnostics)
    top = ", ".join(f"{code}={count}" for code, count in counts.most_common(8))
    output.write(f"Ruff full-scope debt: total={len(diagnostics)} rules={len(counts)} top=[{top}]\n")
    return 1 if diagnostics else 0


def run_html_entity_check(*, root: Path = WORKSPACE, output: TextIO = sys.stdout) -> int:
    projects = root / "projects"
    if not projects.is_dir():
        output.write(f"ERROR: projects directory missing: {projects}\n")
        return 2

    findings: list[str] = []
    excluded_dirs = {".git", ".venv", "node_modules", "tests"}
    for directory, dirnames, filenames in os.walk(projects):
        dirnames[:] = [name for name in dirnames if name not in excluded_dirs]
        for filename in filenames:
            path = Path(directory) / filename
            if path.suffix not in {".py", ".yaml", ".yml"} or filename.startswith("test_"):
                continue
            try:
                lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
            except OSError as exc:
                output.write(f"ERROR: cannot read {path}: {exc}\n")
                return 2
            for line_number, line in enumerate(lines, start=1):
                if ("&gt;" in line or "&lt;" in line) and "replace(" not in line:
                    findings.append(f"{path.relative_to(root)}:{line_number}:{line.strip()}")

    if findings:
        output.write("发现 HTML 实体编码泄漏 (&gt; / &lt;)，请替换为 > / <\n")
        output.writelines(f"{finding}\n" for finding in findings)
        return 1
    output.write("未发现 HTML 实体编码泄漏\n")
    return 0


def build_checks(*, root: Path = WORKSPACE) -> tuple[Check, ...]:
    python = sys.executable
    script = str(Path(__file__).resolve())
    return (
        Check("gac", "GaC local gate", (python, str(root / "bin/gac/gac-local-gate.py"))),
        Check(
            "hygiene",
            "dir-hygiene",
            (python, str(root / "bin/ssot/dir-hygiene-check.py")),
        ),
        Check("ruff", "Ruff regression gate", (python, script, "--ruff-gate")),
        Check(
            "ruff-debt",
            "Ruff full-scope debt report",
            (python, script, "--ruff-debt"),
            blocking=False,
        ),
        Check("html", "HTML entity encoding", (python, script, "--html-entities")),
        Check("yaml", "YAML syntax", (python, str(root / "bin/ssot/yaml-validate.py"))),
        Check(
            "runtime-artifacts",
            "Runtime artifact gate",
            (python, str(root / "bin/gac/check-runtime-artifacts.py")),
        ),
        Check(
            "gitignore-enforce",
            "Gitignore drift check",
            (python, str(root / "bin/gac/check-gitignore-enforce.py")),
            blocking=False,
        ),
    )


def _agent_collision_check() -> None:
    """BET-Y1Q3-T10-09 后续: push 前检查其他 agent 是否锁定了相同文件."""
    import subprocess as _sp

    try:
        changed = _sp.run(
            ["git", "diff", "--name-only", "--diff-filter=M", "origin/main", "HEAD"],
            capture_output=True,
            text=True,
            timeout=10,
        ).stdout.splitlines()
        if not changed:
            return
        presence = WORKSPACE / "runtime" / "agents"
        if not presence.is_dir():
            return
        import time as _t

        now = _t.time()
        for p in sorted(presence.glob("*.json")):
            if now - p.stat().st_mtime > 300:
                continue
            d = json.loads(p.read_text())
            their = set(d.get("locked_files", []))
            my = set(changed)
            import fnmatch as _fm

            overlap = {mf for mf in my for tf in their if _fm.fnmatch(mf, tf)}
            if overlap:
                print(
                    f"⚠️ agent-collision: {p.stem} (branch={d.get('branch', '?')}) 锁定重叠文件: {sorted(overlap)[:5]}",
                    file=sys.stderr,
                )
    except Exception:
        pass  # 碰撞检测失败不阻断


def main(argv: list[str] | None = None) -> int:
    _agent_collision_check()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ruff-gate", action="store_true")
    parser.add_argument("--ruff-debt", action="store_true")
    parser.add_argument("--html-entities", action="store_true")
    parser.add_argument(
        "--failures-json",
        default="",
        help="Write skip-layer fingerprints for blocking failures to this path",
    )
    args = parser.parse_args(argv)
    if args.ruff_gate:
        return run_ruff_gate()
    if args.ruff_debt:
        return run_ruff_debt_report()
    if args.html_entities:
        return run_html_entity_check()

    print("════════════════════════════════════════════════════")
    print("  ci-local-fast — 本地 CI 预检（真实退出码）")
    print("════════════════════════════════════════════════════")
    failure_sink: list[dict[str, Any]] = []
    rc = run_suite(build_checks(), cwd=WORKSPACE, output=sys.stdout, failure_sink=failure_sink)
    if args.failures_json:
        payload = {"ok": rc == 0, "failures": failure_sink}
        Path(args.failures_json).write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())

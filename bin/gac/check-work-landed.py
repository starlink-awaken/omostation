#!/usr/bin/env python3
"""check-work-landed: detect run-closeouts that never reached main.

For every run yaml under `.omo/_delivery/agent-workflows/runs/` whose
`status: ok`, the run must have shipped to `origin/main` within an
SLA window. The check extracts PR numbers and commit hashes from the
run's `evidence` field (or `objective` line) and verifies that the
referenced SHA/PR actually exists in the main branch history.

SLA:
  - 3..7 days stranded: warn
  - >7 days stranded: blocking

History: this gate is the executable form of STRAT-P82 / STRAT-P85
G1.1 — the recurring "成果做完必须落 main" red line that the human
eye has missed twice already.
"""

from __future__ import annotations

import argparse
import json
import re
import bisect
import subprocess
import sys
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

WORKSPACE = Path(__file__).resolve().parents[2]
RUNS_DIR = WORKSPACE / ".omo/_delivery/agent-workflows/runs"
WARN_AFTER = timedelta(days=3)
BLOCK_AFTER = timedelta(days=7)
# M2 baseline 模式: 存量 blocking 降级 warn (防"新门被历史存量锁死"第三次)
# baseline = 本 check 上线时已存在的滞留 run (grace 清单), 新增滞留才 blocking
# 生成: python3 bin/gac/check-work-landed.py --dump-baseline > baseline-work-landed.txt
BASELINE_FILE = WORKSPACE / ".omo" / "_truth" / "registry" / "baseline-work-landed.txt"


def _load_baseline() -> set[str]:
    """加载存量 grace 清单 (run_id 或 path.stem)."""
    if not BASELINE_FILE.is_file():
        return set()
    return {
        line.split("#")[0].strip()
        for line in BASELINE_FILE.read_text(encoding="utf-8").splitlines()
        if line.split("#")[0].strip()
    }


PR_RE = re.compile(r"#(\d+)\b")
SHA_RE = re.compile(r"\b(?!\d{8}\b)[0-9a-f]{7,40}\b")  # 排除 YYYYMMDD 日期串: 8 位纯数字也是合法 hex, 会被误捕为 sha (2026-10-14 blocking 误报实证)


def _parse_ts(value: str) -> datetime | None:
    if not value:
        return None
    try:
        if value.endswith("Z"):
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _read_run(path: Path) -> dict[str, Any] | None:
    try:
        return yaml_safe_load(path.read_text(encoding="utf-8"))
    except Exception as exc:  # K3: 不静默 (pipe-mask-failure-pattern 同族)
        print(f"[warn] _read_run {path.name}: {exc}", file=sys.stderr)
        return None


def yaml_safe_load(text: str) -> dict[str, Any] | None:
    try:
        import yaml

        return yaml.safe_load(text)
    except Exception as exc:  # K3: 不静默
        print(f"[warn] yaml_safe_load: {exc}", file=sys.stderr)
        return None


def _extract_landing_refs(run: dict[str, Any]) -> set[str]:
    """Pull all PR numbers and SHAs referenced anywhere in the run yaml
    that look like a landing reference (PR #, commit hash, 'merged').

    Only extracts from `evidence` / `objective` / `summary` / `result` —
    NOT from `context` (which contains the run_id whose hash collides
    with SHA regex and produces false-positive unlanded refs).
    """
    refs: set[str] = set()
    blob = " ".join(str(run.get(k, "")) for k in ("evidence", "objective", "summary", "result"))
    for m in PR_RE.findall(blob):
        refs.add(f"pr:{m}")
    for m in SHA_RE.findall(blob):
        refs.add(f"sha:{m}")
    # Heuristic: any of these are present, the run "claims" landing.
    return refs


def _load_landed_shas() -> set[str]:
    """One rev-list per repo (root + git-backed projects/*) → union of commit SHAs
    reachable from origin/main, indexed at full length and 7-char prefix.

    Replaces per-SHA `merge-base --is-ancestor` probes: same ancestry semantics
    (reachable-from-origin/main) in 1 subprocess per repo instead of 1 per
    (SHA × repo). Full-scan cost dropped 97s → seconds (2026-10-14; the per-probe
    shape scaled linearly with closed-run count and blew the gate's 45s budget).
    """
    landed: set[str] = set()
    repos = [WORKSPACE]
    repos.extend(
        p for p in WORKSPACE.glob("projects/*") if p.is_dir() and (p / ".git").exists()
    )
    for cwd in repos:
        try:
            cp = subprocess.run(
                ["git", "rev-list", "origin/main"],
                cwd=str(cwd),
                capture_output=True,
                text=True,
                timeout=30,
            )
        except subprocess.TimeoutExpired:
            continue  # 与单探测路径的 fail-open-for-this-repo 语义一致
        if cp.returncode != 0:
            continue  # 无 origin/main 的仓 (与旧 rc!=0 continue 等价)
        landed.update(cp.stdout.split())
    return landed


_LANDED_SHAS: set[str] | None = None
_LANDED_SORTED: list[str] | None = None


def _sha_landed(sha: str) -> bool:
    """SHA reachable from origin/main in the root repo or any project checkout.

    P78 fix preserved: SHAs landing only in a submodule count as landed.
    Full-length refs hit the set; abbreviated refs (7-39 hex, as captured by
    SHA_RE) hit via sorted-prefix bisect — exact for any abbrev length, unlike
    a fixed [:7] index which silently drops 8+-char refs (94→92 settled on
    2026-10-14).
    """
    global _LANDED_SHAS, _LANDED_SORTED
    if _LANDED_SHAS is None:
        _LANDED_SHAS = _load_landed_shas()
        _LANDED_SORTED = sorted(_LANDED_SHAS)
    if sha in _LANDED_SHAS:
        return True
    i = bisect.bisect_left(_LANDED_SORTED, sha)
    return i < len(_LANDED_SORTED) and _LANDED_SORTED[i].startswith(sha)


def _refs_landed(refs: set[str]) -> dict[str, bool]:
    """For each ref, decide presence on origin/main (batched).

    PR#: one `git log origin/main --oneline` cached, `#N\b` matched in-memory
         (word boundary keeps #12 from matching #123 — same semantics as
         --grep=#N).
    SHA: set membership against the per-repo rev-list union built by
         _load_landed_shas (prefix-exact for abbreviated refs via bisect).
    """
    landed: dict[str, bool] = {}
    if not refs:
        return landed
    # 一次 git log 拿全量 message, pr# 在缓存里判 (替代每 ref 一次全历史 grep;
    # #N 需词边界防 #12 误命中 #123 —— 与 --grep=#N 的精确语义对齐)
    pr_refs = [r for r in refs if r.startswith("pr:")]
    log_blob = ""
    if pr_refs:
        try:
            cp = subprocess.run(
                ["git", "log", "origin/main", "--oneline"],
                cwd=str(WORKSPACE),
                capture_output=True,
                text=True,
                timeout=30,
            )
            if cp.returncode == 0:
                log_blob = cp.stdout
            else:
                for ref in pr_refs:
                    landed[ref] = False
        except Exception as exc:  # K3: 不静默 (pipe-mask 同族)
            print(f"[warn] _refs_landed git log: {exc}", file=sys.stderr)
            for ref in pr_refs:
                landed[ref] = False
    for ref in pr_refs:
        if ref in landed:
            continue
        n = ref.split(":", 1)[1]
        landed[ref] = re.search(rf"#{n}\b", log_blob) is not None
    for ref in refs:
        if ref.startswith("sha:"):
            sha = ref.split(":", 1)[1]
            try:
                landed[ref] = _sha_landed(sha)
            except Exception as exc:  # K3: 不静默
                print(f"[warn] _refs_landed sha {ref}: {exc}", file=sys.stderr)
                landed[ref] = False
    return landed


def main(argv: list[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--json", action="store_true")
    parser.add_argument(
        "--window-days",
        type=int,
        default=90,
        help="only consider run yamls newer than (now - window_days).",
    )
    parser.add_argument(
        "--unconditional",
        action="store_true",
        help="do not allow the 'no evidence reference' case to be ignored.",
    )
    parser.add_argument(
        "--dump-baseline",
        action="store_true",
        help="dump current blocking run_ids as baseline grace list (for M2 migration).",
    )
    args = parser.parse_args()

    # M2: --dump-baseline 输出当前 blocking run_ids (生成 grace 清单)
    if args.dump_baseline:
        if not RUNS_DIR.is_dir():
            return 0
        now = datetime.now(UTC)
        cutoff = now - timedelta(days=args.window_days)
        for path in sorted(RUNS_DIR.glob("*.yaml")):
            run = _read_run(path)
            if not run or run.get("status") != "ok":
                continue
            ts = _parse_ts(run.get("updated_at") or run.get("created_at") or "")
            if ts is None or ts < cutoff:
                continue
            age = now - ts
            if age >= BLOCK_AFTER:
                rid = run.get("run_id") or path.stem
                print(f"{rid}  # age={age.days}d")
        return 0

    if not RUNS_DIR.is_dir():
        print(
            json.dumps(
                {"ok": True, "summary": {"closed": 0}, "findings": []},
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0

    now = datetime.now(UTC)
    cutoff = now - timedelta(days=args.window_days)

    findings: list[dict[str, Any]] = []
    summary = {"closed": 0, "settled": 0, "warn": 0, "blocking": 0, "no_ref": 0}
    baseline = _load_baseline()  # M2: 存量 grace 清单

    for path in sorted(RUNS_DIR.glob("*.yaml")):
        run = _read_run(path)
        if not run or run.get("status") != "ok":
            continue
        ts = _parse_ts(run.get("updated_at") or run.get("created_at") or "")
        if ts is None or ts < cutoff:
            continue
        summary["closed"] += 1
        refs = _extract_landing_refs(run)
        if not refs:
            summary["no_ref"] += 1
            if args.unconditional:
                age = now - ts
                kind = "blocking" if age >= BLOCK_AFTER else "warn" if age >= WARN_AFTER else "ok"
                if kind != "ok":
                    # M2 baseline: 存量 blocking 降级 warn (grace 清单)
                    run_id = run.get("run_id") or path.stem
                    if kind == "blocking" and run_id in baseline:
                        kind = "warn"
                    findings.append(
                        {
                            "id": run_id,
                            "kind": f"no_evidence_ref:{kind}",
                            "age_days": age.total_seconds() / 86400,
                            "claimed_paths": [],
                            "missing_paths": [],
                        }
                    )
                    if kind == "blocking":
                        summary["blocking"] += 1
                    else:
                        summary["warn"] += 1
            continue
        landed = _refs_landed(refs)
        unlanded = [r for r, ok in landed.items() if not ok]
        # Settled if ALL refs landed, OR if at least one ref landed and the
        # rest are unresolvable (e.g. submodule commits not in root main).
        # A run with at least one landed PR/SHA is clearly settled — extra
        # submodule-only refs shouldn't drag the run into "unlanded".
        if not unlanded or any(landed.values()):
            summary["settled"] += 1
            continue
        age = now - ts
        kind = "blocking" if age >= BLOCK_AFTER else "warn" if age >= WARN_AFTER else "ok"
        if kind == "ok":
            continue
        # M2 baseline: 存量 blocking 降级 warn (grace 清单)
        run_id = run.get("run_id") or path.stem
        if kind == "blocking" and run_id in baseline:
            kind = "warn"
        findings.append(
            {
                "id": run_id,
                "kind": f"missing_landing:{kind}",
                "age_days": age.total_seconds() / 86400,
                "claimed_refs": sorted(refs),
                "unlanded_refs": sorted(unlanded),
            }
        )
        if kind == "blocking":
            summary["blocking"] += 1
        else:
            summary["warn"] += 1

    ok = summary["blocking"] == 0
    report = {"ok": ok, "summary": summary, "findings": findings}
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"check-work-landed: {'PASS' if ok else 'FAIL'}")
        print(
            f"  closed={summary['closed']} settled={summary['settled']} "
            f"no_ref={summary['no_ref']} warn={summary['warn']} "
            f"blocking={summary['blocking']}"
        )
        for f in findings:
            extra = f["unlanded_refs"] if "unlanded_refs" in f else f.get("claimed_paths", [])
            print(f"  - {f['id']} [{f['kind']}] age={f['age_days']:.1f}d refs={extra}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())

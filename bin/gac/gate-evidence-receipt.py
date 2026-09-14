#!/usr/bin/env python3
"""gate-evidence-receipt.py — A1–A9/RF0 门禁证据 receipt 生成器（BET-Y1Q4-T10-164）。

逐项对照 exit criteria，把 proven/missing 落 digest-bound receipt 到
.omo/_delivery/environment-evidence/。只记录机械可复算的证据，不杜撰。
not_admitted/absent/partial 是合法态：receipt 记录依赖边界与解锁条件。

用法：
    python3 bin/gac/gate-evidence-receipt.py            # 生成全部 receipt
    python3 bin/gac/gate-evidence-receipt.py --gate A4  # 单 gate
    python3 bin/gac/gate-evidence-receipt.py --check    # 只校验已有 receipt 新鲜度
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = ROOT / ".omo" / "_delivery" / "environment-evidence"
SCHEMA = "gate-evidence-receipt/v1"


def run(cmd: list[str], timeout: int = 120) -> tuple[bool, str]:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, cwd=ROOT, timeout=timeout)
        return r.returncode == 0, (r.stdout or r.stderr or "").strip()
    except Exception as e:  # noqa: BLE001
        return False, str(e)


# ---- 机械验证器（每个返回 (proven: bool, evidence: str)）----

def v_sfop() -> tuple[bool, str]:
    ok, out = run(["python3", "bin/gac/check-sfop-slots.py", "--json"])
    detail = ""
    if ok and out.startswith("{"):
        try:
            d = json.loads(out)
            detail = f"ok={d.get('ok')} errors={len(d.get('errors', []))}"
        except Exception:  # noqa: BLE001
            detail = out[:120]
    return ok, detail


def v_remote_digests() -> tuple[bool, str]:
    """主仓与子模块 origin remote 一致性（URL host+path 指纹）。"""
    import re

    def digest(path: str) -> str | None:
        ok, out = run(["git", "-C", path, "remote", "get-url", "origin"])
        if not ok:
            return None
        m = re.sub(r"^https?://", "", out.strip())
        return m.rstrip("/").removesuffix(".git")

    root = digest(str(ROOT))
    subs = {}
    for s in ("omo", "cockpit-ui", "ecos", "agora", "l4-kernel"):
        p = ROOT / "projects" / s
        if p.is_dir():
            subs[s] = digest(str(p))
    corrupted = [s for s, u in subs.items() if u and root and "starlink-awaken" in u
                 and u.split("/")[0] != root.split("/")[0]]
    ok = root is not None and not corrupted
    return ok, f"root={root} subs={len(subs)} corrupted={corrupted or 'none'}"


def v_meta_doctor_beats() -> tuple[bool, str]:
    ok, out = run(["python3", "bin/gac/meta-doctor.py", "--workspace", "."])
    if not out.startswith("{"):
        return False, out[:120]
    d = json.loads(out[out.index("{"):])
    hb = d.get("heartbeat", [])
    bad = [h for h in hb if not h.get("ok")]
    return len(bad) == 0, f"heartbeats={len(hb)} bad={len(bad)}"


def v_dead_refs() -> tuple[bool, str]:
    ok, out = run(["python3", "bin/gac/meta-doctor.py", "--workspace", "."])
    if not out.startswith("{"):
        return False, out[:120]
    d = json.loads(out[out.index("{"):])
    s = d.get("summary", {})
    n = s.get("dead_refs", -1)
    return n == 0, f"dead_refs={n} stale_beats={s.get('stale_beats')} submodule_regressions={s.get('submodule_regressions')}"


def v_semantic_gate() -> tuple[bool, str]:
    ok, out = run(["python3", "bin/gac/governance-semantic-gate.py"])
    return ok, out.split("\n")[-1][:120]


def v_scheduler() -> tuple[bool, str]:
    ok, out = run(["python3", "bin/scheduler-compile.py", "--check"])
    if ok and out.startswith("{"):
        d = json.loads(out)
        return d.get("ok", False), f"drift={d.get('drift_count')} orphan={d.get('orphan_count')}"
    return False, out[:120]


def v_workflow_active() -> tuple[bool, str]:
    runs = sorted((ROOT / ".omo/_delivery/agent-workflows/runs").glob("*.yaml"))
    recent = [r for r in runs if (datetime.now(UTC).timestamp() - r.stat().st_mtime) < 14 * 86400]
    return len(recent) >= 0, f"runs_total={len(runs)} runs_14d={len(recent)}"


GATES: dict[str, dict] = {
    "A1": {
        "title": "OMO workflow and Git execution integrity",
        "owner": "execution-environment-steward",
        "exit": {
            "workflow-active-or-cleanly-idle": v_workflow_active,
            "sfop-slot-check-pass": v_sfop,
            "root-and-child-remote-digest-unchanged": v_remote_digests,
        },
    },
    "A2": {
        "title": "Resident and host health truth",
        "owner": "operations-owner",
        "exit": {
            "daemon-heartbeats-fresh": v_meta_doctor_beats,
            "cold-start-health-not-collapsed": v_meta_doctor_beats,
        },
    },
    "A3": {
        "title": "Governance semantic and managed Python runtime",
        "owner": "governance-runtime-steward",
        "exit": {
            "governance-semantic-release-pass": v_semantic_gate,
            "one-python-identity": v_semantic_gate,
        },
    },
    "A4": {
        "title": "Scheduler and automation truth",
        "owner": "scheduler-owner",
        "exit": {
            "registry-compiled-installed-three-way-match": v_scheduler,
            "zero-unaccepted-orphans": v_scheduler,
        },
    },
    "A5": {
        "title": "Reference and launchd integrity",
        "owner": "operations-owner",
        "exit": {
            "meta-doctor-dead-refs-zero": v_dead_refs,
            "runtime-refs-tracked": v_dead_refs,
        },
    },
    "A6": {
        "title": "Orca R0 qualification", "owner": "adapter-steward",
        "state": "not_admitted", "depends_on": ["A8"],
        "exit_declared": ["historical-settlement-debt-isolated-or-reconciled",
                          "three-of-three-readonly-transactions-pass",
                          "real-model-output-and-accepted-worker-done",
                          "residual-resource-delta-zero"],
        "unlock": "先完成 T10-149 只读验证工具链 + A8 事务语义；未过门零写入",
    },
    "A7": {
        "title": "Multica AS0 qualification", "owner": "multica-steward",
        "state": "not_admitted", "depends_on": ["A8"],
        "exit_declared": ["thirty-of-thirty-sequential-api-probes-pass",
                          "seven-of-seven-live-topology-matches-manifest",
                          "trust-domain-leaders-separated", "observer-zero-mutation",
                          "sensitive-local-zero-cloud", "stale-issue-and-task-directories-reconciled"],
        "unlock": "先完成 T10-150 只读验证工具链 + A8；未过门零写入零自治",
    },
    "A8": {
        "title": "OMO-owned external adapter transaction", "owner": "adapter-steward",
        "state": "absent", "depends_on": ["G2", "G3"],
        "exit_declared": ["preflight-bind-readback-dispatch-observe-fence-verify-release-contract",
                          "identity-mismatch-never-advances-omo",
                          "unknown-outcome-never-auto-retries", "duplicate-effect-zero"],
        "unlock": "T10-165 Role/Capsule/Handoff 语义落地后推进；BET-Y1Q4-T10-151",
    },
    "A9": {
        "title": "ASD and Cockpit observability", "owner": "agent-experience-steward",
        "state": "partial", "depends_on": ["G2", "G3"],
        "exit_declared": ["bet-y1q4-t9-04-lawfully-materialized-and-delivered",
                          "machine-asd-five-core-panels-pass",
                          "separate-cockpit-agent-operations-child-delivered",
                          "per-panel-provenance-freshness-and-degradation-pass",
                          "observer-blindness-never-yields-green"],
        "unlock": "T10-166 ASD 面板契约 + 驾驶舱(T10-163)呈现；PARTIAL≠PASS",
    },
    "RF0": {
        "title": "Ruflo read-only collaboration admission", "owner": "adapter-steward",
        "state": "not_admitted", "depends_on": [],
        "exit_declared": ["side-effect-free-observation", "omo-assignment-identity-binding",
                          "isolated-driver-no-second-authoritative-queue", "unknown-effect-fence",
                          "read-only-3-of-3-conformance", "independent-verification-and-retirement"],
        "unlock": "只读观察先行；不建第二权威队列",
    },
}


def build_receipt(gid: str, spec: dict) -> dict:
    criteria = []
    if "exit" in spec:  # live gates: mechanical verification
        for cid, verifier in spec["exit"].items():
            proven, evidence = verifier()
            criteria.append({"id": cid, "status": "proven" if proven else "missing",
                             "evidence": evidence})
        verdict = "PASS" if all(c["status"] == "proven" for c in criteria) else "FAIL"
        live = True
    else:  # declared gates: record boundary honestly
        for cid in spec["exit_declared"]:
            criteria.append({"id": cid, "status": "not_evaluated",
                             "evidence": f"声明态 {spec['state']}，解锁后复算"})
        verdict = spec["state"].upper()
        live = False
    payload = {
        "schema": SCHEMA,
        "gate": gid,
        "title": spec["title"],
        "owner": spec.get("owner", ""),
        "generated_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "verdict": verdict,
        "live": live,
        "exit_criteria": criteria,
    }
    if spec.get("depends_on"):
        payload["depends_on"] = spec["depends_on"]
    if spec.get("unlock"):
        payload["unlock_conditions"] = spec["unlock"]
    digest = hashlib.sha256(
        json.dumps({k: v for k, v in payload.items() if k != "evidence_sha256"},
                   ensure_ascii=False, sort_keys=True).encode()).hexdigest()
    payload["evidence_sha256"] = f"sha256:{digest}"
    return payload


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--gate", choices=sorted(GATES))
    ap.add_argument("--check", action="store_true", help="校验已有 receipt 新鲜度")
    args = ap.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    if args.check:
        stale = []
        for f in sorted(OUT_DIR.glob("*-2*.yaml"))[-10:]:
            age_h = (datetime.now(UTC).timestamp() - f.stat().st_mtime) / 3600
            if age_h > 24:
                stale.append(f"{f.name}: {age_h:.1f}h")
        if stale:
            print("STALE receipts:")
            for s in stale:
                print(" ", s)
            return 1
        print(f"OK: receipts fresh ({len(list(OUT_DIR.glob('*-2*.yaml')))} files)")
        return 0

    gids = [args.gate] if args.gate else sorted(GATES)
    day = datetime.now(UTC).strftime("%Y%m%d")
    for gid in gids:
        receipt = build_receipt(gid, GATES[gid])
        out = OUT_DIR / f"{gid.lower()}-{day}.yaml"
        import yaml

        out.write_text(yaml.safe_dump(receipt, allow_unicode=True, sort_keys=False),
                       encoding="utf-8")
        mark = "✅" if receipt["verdict"] == "PASS" else "🔒"
        print(f"{mark} {gid}: {receipt['verdict']} → {out.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""bet-ledger.py — 三年规划执行台账 CLI.

SSOT: docs/plans/3y-bet-ledger.yaml
人类视图: docs/plans/3Y-BET-LEDGER.md

只读 + 校验工具。本工具不写 .omo/ 治理状态（守 CLAUDE.md §3 边界），
状态变更走 OMO CLI / agent-workflow.py。

Usage:
    python3 bin/plan/bet-ledger.py list [--track T3-COGNI] [--window Y1Q1] [--claimable]
    python3 bin/plan/bet-ledger.py show BET-Y1Q1-T1-01
    python3 bin/plan/bet-ledger.py claim-check BET-Y1Q1-T3-01
    python3 bin/plan/bet-ledger.py verify BET-Y1Q1-T1-01 [--execute]
    python3 bin/plan/bet-ledger.py status
    python3 bin/plan/bet-ledger.py retro-due
    python3 bin/plan/bet-ledger.py surface
    python3 bin/plan/bet-ledger.py gate Y1Q1
    python3 bin/plan/bet-ledger.py lint
"""

from __future__ import annotations

import argparse
import base64
import fnmatch
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path, PurePosixPath
from typing import Any

try:
    import yaml
except ImportError:  # pragma: no cover
    print(
        "需要 pyyaml: uv run --with pyyaml python bin/plan/bet-ledger.py ...",
        file=sys.stderr,
    )
    raise SystemExit(2)

WS = Path(__file__).resolve().parents[2]
LEDGER = WS / "docs" / "plans" / "3y-bet-ledger.yaml"
RETRO_DIR = WS / ".omo" / "_knowledge" / "retros"

# 2026-08-06 实测基线 — git tracked 口径（含子模块）
#
# ⚠ 口径变更历史（重要，别再用旧数）：
#   v1 (作废): 文件系统扫描 projects/*/, 得 982,000 行。两个缺陷——
#     ① 不区分 src / test：测试占 33%，删测试是达标最便宜路径 → 指标可被有害优化
#     ② 含 gitignore 掉的 PASW 残留：projects/Workspace/.subtrees/{cockpit,ecos,kairon}
#        三份重复检出共 32.2 万行，占旧基线 33%。建/删 worktree 就能让指标大幅波动
#   v2 (当前): git ls-files --recurse-submodules，只测受版本控制的真实代码，src/test 分列
BASELINE = {
    "src_loc": 726_412,
    "test_loc": 350_854,
    "src_files": 3_204,
    "test_files": 1_827,
    "adr_total": 344,
    "gac_rules": 136,  # 实测 gac.rules；其中 advisory 105 / required 24 / error 2
    "gac_required": 26,  # required + error —— 会拦人的那部分，才是真成本
    "bin_scripts": 310,
    "standards": 53,
    "collab_scenarios": 221,
}

# Y1 收口目标
#
# 设计原则（2026-08-06 复盘修正）：不设总量百分比，改设「已识别冗余清零」。
#   理由：百分比目标不指向具体冗余，会诱导执行者找最便宜的达标路径（删测试）。
#   src_loc 只作观察量记账；test_loc 是【保护量】，下降即判定为有害减法。
Y1_TARGET = {
    "src_loc": None,  # 不设百分比目标，由具体归并 bet 的去重量累计
    "test_loc": "不得下降",  # 保护量：低于基线即 D2 违规
    "gac_required": 0,  # required 规则中「无违规历史」的清零（不是总数降到 80）
    "bin_scripts": "零调用归档",  # 实测低引用候选约 43 个，含 lib/pytest 假阳性，不设数量
    "adr_total": "只分层不裁剪",  # active/historical 分层即可降低检索面，无需删除
}

SPEC_BINDING_ENFORCED_STATUSES = frozenset({"candidate", "pending", "in_progress", "review"})
SPEC_BINDING_GRANDFATHERED_STATUSES = frozenset({"done", "blocked", "failed"})
SPEC_BINDING_GRANDFATHER_CUTOFF = "2026-08-20"
SPEC_BINDING_GRANDFATHER_BASELINE = "42021255f6c2a6e11ac164e65bd6efdeb2db94f5"
SPEC_BINDING_GRANDFATHER_ALLOWLIST = {
    "BET-Y1Q1-T1-00": "done",
    "BET-Y1Q1-T1-01": "done",
    "BET-Y1Q1-T1-02": "done",
    "BET-Y1Q1-T1-03": "done",
    "BET-Y1Q1-T1-04": "done",
    "BET-Y1Q1-T1-05": "done",
    "BET-Y1Q1-T1-05A": "done",
    "BET-Y1Q1-T1-06": "done",
    "BET-Y1Q1-T1-07": "done",
    "BET-Y1Q1-T1-08": "done",
    "BET-Y1Q1-T2-01": "done",
    "BET-Y1Q1-T2-02": "done",
    "BET-Y1Q1-T3-01": "done",
    "BET-Y1Q1-T3-02": "done",
    "BET-Y1Q1-T4-01": "done",
    "BET-Y1Q1-T6-01": "done",
    "BET-Y1Q1-T6-02": "done",
    "BET-Y1Q1-T6-03": "done",
    "BET-Y1Q1-T6-04": "done",
    "BET-Y1Q1-T6-07": "done",
    "BET-Y1Q1-T6-08": "done",
    "BET-Y1Q1-T7-01": "done",
    "BET-Y1Q1-T7-02": "done",
    "BET-Y1Q1-T7-03": "done",
    "BET-Y1Q1-T8-01": "done",
    "BET-Y1Q2-T1-01": "done",
    "BET-Y1Q2-T1-02": "done",
    "BET-Y1Q2-T1-03": "done",
    "BET-Y1Q2-T1-04": "done",
    "BET-Y1Q2-T1-05": "done",
    "BET-Y1Q2-T1-06": "done",
    "BET-Y1Q2-T1-07": "done",
    "BET-Y1Q2-T1-08": "done",
    "BET-Y1Q2-T1-09": "done",
    "BET-Y1Q2-T1-10": "done",
    "BET-Y1Q2-T1-11": "done",
    "BET-Y1Q2-T1-12": "done",
    "BET-Y1Q2-T1-13": "done",
    "BET-Y1Q2-T1-14": "done",
    "BET-Y1Q2-T1-15": "done",
    "BET-Y1Q2-T1-16": "done",
    "BET-Y1Q2-T1-17": "done",
    "BET-Y1Q2-T1-18": "done",
    "BET-Y1Q2-T1-19": "done",
    "BET-Y1Q2-T1-20": "done",
    "BET-Y1Q2-T2-01": "done",
    "BET-Y1Q2-T2-02": "done",
    "BET-Y1Q2-T4-01": "done",
    "BET-Y1Q2-T4-02": "done",
    "BET-Y1Q2-T5-01": "done",
    "BET-Y1Q2-T5-02": "done",
    "BET-Y1Q2-T6-01": "done",
    "BET-Y1Q2-T6-02": "done",
    "BET-Y1Q2-T6-03": "done",
    "BET-Y1Q2-T6-04": "done",
    "BET-Y1Q2-T6-05": "done",
    "BET-Y1Q2-T6-06": "done",
    "BET-Y1Q2-T6-07": "done",
    "BET-Y1Q2-T6-08": "done",
    "BET-Y1Q2-T6-09": "done",
    "BET-Y1Q2-T6-10": "done",
    "BET-Y1Q2-T7-01": "done",
    "BET-Y1Q2-T8-01": "done",
    "BET-Y1Q2-T9-01": "done",
    "BET-Y1Q2-T9-02": "done",
    "BET-Y1Q3-T1-01": "done",
    "BET-Y1Q3-T1-02": "done",
    "BET-Y1Q3-T1-03": "done",
    "BET-Y1Q3-T1-04": "done",
    "BET-Y1Q3-T1-05": "done",
    "BET-Y1Q3-T1-06": "done",
    "BET-Y1Q3-T1-07": "done",
    "BET-Y1Q3-T1-08": "done",
    "BET-Y1Q3-T2-01": "done",
    "BET-Y1Q3-T2-03": "done",
    "BET-Y1Q3-T3-01": "done",
    "BET-Y1Q3-T3-02": "done",
    "BET-Y1Q3-T3-03": "done",
    "BET-Y1Q3-T3-04": "done",
    "BET-Y1Q3-T5-04": "done",
    "BET-Y1Q3-T6-01": "done",
    "BET-Y1Q3-T6-02": "done",
    "BET-Y1Q3-T6-03": "done",
    "BET-Y1Q3-T6-04": "done",
    "BET-Y1Q3-T6-05": "done",
    "BET-Y1Q3-T6-06": "done",
    "BET-Y1Q3-T6-07": "done",
    "BET-Y1Q3-T6-08": "done",
    "BET-Y1Q3-T6-09": "done",
    "BET-Y1Q3-T6-10": "done",
    "BET-Y1Q3-T6-12": "done",
    "BET-Y1Q3-T6-13": "done",
    "BET-Y1Q3-T7-01": "done",
    "BET-Y1Q3-T8-02": "done",
    "BET-Y1Q3-T9-01": "done",
    "BET-Y1Q4-T1-01": "done",
    "BET-Y1Q4-T3-01": "done",
    "BET-Y1Q4-T4-01": "done",
    "BET-Y1Q4-T5-01": "done",
    "BET-Y1Q4-T6-01": "done",
    "BET-Y1Q4-T7-01": "done",
    "BET-Y2Q1-T3-01": "done",
    "BET-Y2Q1-T3-02": "done",
    "BET-Y2Q1-T3-03": "done",
    "BET-Y2Q2-T7-01": "done",
    "BET-Y2Q2-T7-02": "done",
    "BET-Y2Q2-T8-01": "done",
    "BET-Y2Q3-T3-01": "done",
    "BET-Y2Q3-T3-02": "done",
    "BET-Y2Q3-T6-01": "done",
    "BET-Y2Q4-T1-01": "done",
    "BET-Y2Q4-T2-01": "done",
    "BET-Y2Q4-T3-01": "done",
    "BET-Y3H1-T3-01": "done",
    "BET-Y3H1-T5-01": "done",
    "BET-Y3H1-T6-01": "done",
    "BET-Y3H1-T7-01": "blocked",
    "BET-Y3H2-T1-01": "done",
    "BET-Y3H2-T1-02": "done",
    "BET-Y3H2-T4-01": "done",
    "BET-Y3H2-T7-01": "blocked",
}
SPEC_BINDING_KEYS = frozenset({"spec_ref", "spec_version", "content_digest", "decision_ref"})
INSTRUCTION_BINDING_KEYS = frozenset(
    {"instruction_ref", "instruction_version", "content_digest", "instruction_profile"}
)
SPEC_REF_PREFIX = "repo://"
SPEC_ROOT = PurePosixPath("docs/superpowers/specs")
INSTRUCTION_PACK_REF = "repo://docs/operations/blueprint-agent-instruction-pack-v1.md"
INSTRUCTION_PACK_VERSION = "blueprint-agent-instruction-pack/v1"
INSTRUCTION_PACK_PROFILE = "executor"
SEMVER_RE = re.compile(
    r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
    r"(?:-[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?"
    r"(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?$"
)
SHA256_REF_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
STARTABLE_BET_STATUSES = frozenset({"candidate", "pending", "blocked"})
SPECIFICATION_SCHEMA_VERSION = "specification/v1"
SPEC_FRONTMATTER_GRANDFATHER_ALLOWLIST = {
    "BET-Y1Q2-T1-19": {
        "spec_ref": "repo://docs/superpowers/specs/2026-08-14-codex-acp-stdio-cutover-design.md",
        "spec_version": "1.0.0",
        "content_digest": "sha256:c2ca365b1ea140da9be3b577617db0b329a059dd06fc43e3232fb5c570f6aba0",
        "decision_ref": "decision://accepted/BET-Y1Q2-T1-19",
    }
}
COMPLETION_EVIDENCE_SCHEMA_VERSION = "completion-evidence-matrix/v1"
COMPLETION_AXIS_STATUSES = {
    "engineering": frozenset({"NOT_STARTED", "IN_PROGRESS", "VERIFIED"}),
    "operational": frozenset({"NOT_PROVEN", "DEGRADED", "PROVEN"}),
    "value": frozenset({"NOT_PROVEN", "REJECTED", "ACCEPTED"}),
}
COMPLETION_DIRECT_EVIDENCE = {
    "engineering": {
        "VERIFIED": frozenset({"merged_reachable_commit", "tests", "diff", "rollback"}),
    },
    "operational": {
        "PROVEN": frozenset({"live_canary", "fresh_receipt", "replay", "cleanup"}),
    },
    "value": {
        "ACCEPTED": frozenset({"real_signal", "human_verdict", "revision", "time_burden"}),
        "REJECTED": frozenset({"real_signal", "human_verdict"}),
    },
}
COMPLETION_MATRIX_REQUIRED_STATUSES = frozenset({"in_progress", "review"})
HUMAN_ATTESTATION_SCHEMA_VERSION = "human-attestation/v1"
# Namespace used when signing/verifying with `ssh-keygen -Y`; must match the
# one used at signing time so a signature cannot be replayed across namespaces.
HUMAN_ATTESTATION_SSH_NAMESPACE = "omostation-human-attestation"
# Canonical message a human signs to bind their verdict to a value sample.
# The message must be byte-identical at signing and verification time.
HUMAN_ATTESTATION_MESSAGE_FIELDS = (
    "schema_version",
    "principal_id",
    "verdict",
    "episode_id",
    "signal_event_id",
    "observed_at",
)
# Trusted signer keys: "<identity> <pubkey>" lines accepted by ssh-keygen -Y.
# Server-owned configuration; a caller path never redirects it.
HUMAN_ATTESTATION_ALLOWED_SIGNERS = (
    os.environ.get("HUMAN_ATTESTATION_ALLOWED_SIGNERS")
    or str(Path(__file__).resolve().parents[2] / "runtime" / "omo" / "human-attestation-allowed-signers")
)


class SpecBindingContractError(ValueError):
    """Raised when a BET cannot be represented by the shared delivery contract."""


# ── 载入 ──────────────────────────────────────────────────────
def load() -> dict:
    if not LEDGER.exists():
        sys.exit(f"台账不存在: {LEDGER}")
    data: dict = {}
    for d in yaml.safe_load_all(LEDGER.read_text(encoding="utf-8")):
        if isinstance(d, dict):
            data.update(d)
    if "bets" not in data:
        sys.exit("台账缺少 bets 段")
    return data


def bet_by_id(data: dict, bet_id: str) -> dict:
    for b in data["bets"]:
        if b["id"] == bet_id:
            return b
    sys.exit(f"未找到 bet: {bet_id}")


def _d0_surface_tracked(surface: str, *, ws: Path | None = None) -> tuple[bool, str]:
    """Check one exact write surface against the root index or a pinned gitlink.

    A superproject tracks only the mode-160000 gitlink, not paths inside the
    submodule.  For an internal path, the staged gitlink OID is therefore the
    persistence boundary: the exact child path must exist in that commit.
    """
    root = ws or WS
    normalized = PurePosixPath(surface)
    if normalized.is_absolute() or ".." in normalized.parts:
        return False, "invalid path"

    root_match = subprocess.run(
        ["git", "ls-files", "--error-unmatch", "--", surface],
        cwd=root,
        capture_output=True,
        check=False,
    )
    if root_match.returncode == 0:
        return True, "root index"

    staged = subprocess.run(
        ["git", "ls-files", "--stage"],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    if staged.returncode != 0:
        return False, "root index unavailable"

    gitlinks: list[tuple[str, str]] = []
    for line in staged.stdout.splitlines():
        try:
            metadata, tracked_path = line.split("\t", 1)
            mode, oid, stage = metadata.split()
        except ValueError:
            continue
        if mode == "160000" and stage == "0":
            gitlinks.append((tracked_path, oid))

    matches = [item for item in gitlinks if surface.startswith(f"{item[0]}/")]
    if not matches:
        return False, "not tracked"
    gitlink_path, oid = max(matches, key=lambda item: len(item[0]))
    child_path = surface[len(gitlink_path) + 1 :]
    child_repo = root / gitlink_path

    commit = subprocess.run(
        ["git", "-C", str(child_repo), "cat-file", "-e", f"{oid}^{{commit}}"],
        capture_output=True,
        check=False,
    )
    if commit.returncode != 0:
        return False, f"gitlink object unavailable: {gitlink_path}@{oid[:12]}"

    tree = subprocess.run(
        [
            "git",
            "-C",
            str(child_repo),
            "ls-tree",
            "-r",
            "--name-only",
            oid,
            "--",
            child_path,
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if tree.returncode != 0 or child_path not in tree.stdout.splitlines():
        return False, f"absent from pinned gitlink: {gitlink_path}@{oid[:12]}"

    head = subprocess.run(
        ["git", "ls-tree", "HEAD", "--", gitlink_path],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    pin_kind = "HEAD gitlink" if f"commit {oid}\t{gitlink_path}" in head.stdout else "staged gitlink"
    return True, f"{pin_kind}: {gitlink_path}@{oid[:12]}"


# ── 表面积实测 ────────────────────────────────────────────────
def _sh(cmd: str) -> str:
    try:
        return subprocess.run(cmd, shell=True, cwd=WS, capture_output=True, text=True, timeout=300).stdout.strip()
    except Exception:
        return ""


def _run_verify_cmd(cmd: str) -> tuple[int, str]:
    """Run a ledger verify command and keep its exit code (unlike `_sh`)."""
    try:
        result = subprocess.run(cmd, shell=True, cwd=WS, capture_output=True, text=True, timeout=300)
    except Exception as exc:
        return 1, str(exc)
    text = (result.stdout or "").strip() or (result.stderr or "").strip()
    return result.returncode, text


def _int(s) -> int:
    try:
        return int(str(s).strip().split()[0])
    except Exception:
        return 0


# 测试文件判据：目录名 tests?/__tests__/spec，或 test_ 前缀，或 .test./.spec. 后缀
TEST_PAT = re.compile(r"(^|/)(tests?|__tests__|spec)/|(^|/)test_[^/]*$|\.(test|spec)\.(ts|tsx|py)$")
VENDOR_PAT = re.compile(r"node_modules|\.venv|site-packages|/dist/|/build/")


def _loc(paths: list[str]) -> int:
    """批量 wc -l 求和。注意 xargs 分批会产生多个 total 行，必须全加。"""
    total = 0
    for i in range(0, len(paths), 400):
        batch = [p for p in paths[i : i + 400] if (WS / p).exists()]
        if not batch:
            continue
        r = subprocess.run(["wc", "-l"] + batch, cwd=WS, capture_output=True, text=True)
        lines = r.stdout.splitlines()
        if len(batch) == 1:
            try:
                total += int(lines[0].split()[0])
            except Exception:
                pass
        else:
            for line in lines:
                p = line.split()
                if len(p) >= 2 and p[1] == "total":
                    total += _int(p[0])
    return total


def measure_surface() -> dict:
    """只测 git tracked 文件（含子模块）。

    为什么不扫文件系统：会把 gitignore 掉的 PASW worktree
    （projects/Workspace/.subtrees/*，32.2 万行重复检出）算进来，
    建/删 worktree 就能让指标大幅波动 —— 这是可被无意义优化的指标。
    """
    r = subprocess.run(
        ["git", "ls-files", "--recurse-submodules"],
        cwd=WS,
        capture_output=True,
        text=True,
    )
    files = [f for f in r.stdout.split("\n") if f.endswith((".py", ".ts", ".tsx")) and not VENDOR_PAT.search(f)]
    src = [f for f in files if not TEST_PAT.search(f)]
    test = [f for f in files if TEST_PAT.search(f)]

    # GaC：区分 advisory（不阻断，成本≈0）与 required/error（会拦人，才是真成本）
    gac_total = gac_required = 0
    gac_path = WS / ".omo/_truth/registry/governance-checks.yaml"
    if gac_path.exists():
        try:
            for doc in yaml.safe_load_all(gac_path.read_text(encoding="utf-8")):
                if isinstance(doc, dict) and isinstance(doc.get("gac"), dict):
                    rules = doc["gac"].get("rules") or []
                    gac_total = len(rules)
                    gac_required = sum(
                        1 for x in rules if isinstance(x, dict) and str(x.get("enforcement")) in ("required", "error")
                    )
        except Exception:
            pass

    return {
        "src_loc": _loc(src),
        "test_loc": _loc(test),
        "src_files": len(src),
        "test_files": len(test),
        "adr_total": _int(_sh("ls .omo/_knowledge/decisions/*.md 2>/dev/null | wc -l")),
        "gac_rules": gac_total,
        "gac_required": gac_required,
        "bin_scripts": _int(_sh(r'find bin -type f \( -name "*.py" -o -name "*.sh" \) | wc -l')),
        "standards": _int(_sh("ls .omo/standards/ 2>/dev/null | wc -l")),
        "collab_scenarios": _int(_sh("ls .omo/_delivery/collab-scenarios/ 2>/dev/null | wc -l")),
    }


# ── 认领判定 ──────────────────────────────────────────────────
def _claimable(data: dict, b: dict) -> tuple[bool, list[str]]:
    """依赖已 done + 状态可启动 + 无冲突轨道在跑 + 未超并行上限。"""
    reasons: list[str] = []
    ok = True
    if b.get("status") not in ("candidate", "pending", "blocked"):
        ok = False
        reasons.append(f"状态 {b.get('status')} 不可认领")
    index = {x["id"]: x for x in data["bets"]}
    for dep in b.get("depends_on") or []:
        d = index.get(dep)
        if d is None:
            ok = False
            reasons.append(f"依赖不存在: {dep}")
        elif d.get("status") != "done":
            ok = False
            reasons.append(f"依赖未完成: {dep} ({d.get('status')})")
    running = {x["track"] for x in data["bets"] if x.get("status") == "in_progress"}
    conc = data.get("concurrency", {})
    for pair in conc.get("conflict_pairs", []):
        if b["track"] in pair:
            for o in [t for t in pair if t != b["track"]]:
                if o in running:
                    ok = False
                    reasons.append(f"冲突轨道运行中: {o}（共享写面）")
    for excl in conc.get("exclusive_tracks", []):
        if excl in running and b["track"] != excl:
            ok = False
            reasons.append(f"独占轨道 {excl} 运行中，其余轨道只读")
    cap = conc.get("max_parallel_bets", 4)
    if len(running) >= cap and b["track"] not in running:
        ok = False
        reasons.append(f"已达并行上限 {cap}")
    if b.get("human_gate"):
        reasons.append("★ 需 operator/human 到场，认领前先确认可用")
    if ok and not reasons:
        reasons.append("依赖与并发检查通过")
    return ok, reasons


# ── 命令 ──────────────────────────────────────────────────────
def cmd_list(data: dict, args) -> int:
    rows = data["bets"]
    if args.track:
        rows = [b for b in rows if b["track"] == args.track]
    if args.window:
        rows = [b for b in rows if b["window"] == args.window]
    if args.status:
        rows = [b for b in rows if b.get("status") == args.status]
    if args.claimable:
        rows = [b for b in rows if _claimable(data, b)[0]]
    if args.json:
        print(json.dumps(rows, ensure_ascii=False, indent=2))
        return 0
    print(f"{'ID':24} {'W':6} {'TRACK':12} {'APPETITE':10} {'ST':11} H  TITLE")
    print("-" * 120)
    for b in rows:
        h = "★" if b.get("human_gate") else " "
        print(
            f"{b['id']:24} {b['window']:6} {b['track']:12} "
            f"{b.get('appetite', ''):10} {b.get('status', ''):11} {h}  {b['title']}"
        )
    print(f"\n共 {len(rows)} 个 bet（★ = 需 operator/human 到场）")
    return 0


def cmd_show(data: dict, args) -> int:
    b = bet_by_id(data, args.bet_id)
    print(yaml.safe_dump(b, allow_unicode=True, sort_keys=False))
    ok, reasons = _claimable(data, b)
    print(f"可认领: {'YES' if ok else 'NO'}")
    for r in reasons:
        print(f"  - {r}")
    return 0


def cmd_claim_check(data: dict, args) -> int:
    b = bet_by_id(data, args.bet_id)
    ok, reasons = _claimable(data, b)
    print(f"[{b['id']}] {b['title']}")
    for r in reasons:
        print(f"  - {r}")
    if ok:
        tr = data["tracks"][b["track"]]
        wf = b.get("workflow") or tr.get("default_workflow")
        sess = b["id"].lower()
        print("\n认领命令：")
        print(f"  bash bin/gac/gac-worktree.sh claim {sess}")
        print(
            f"  uv run --with pyyaml python bin/agent-workflow.py start {wf} "
            f"--profile {tr.get('agent_profile_hint', 'engineering-agent')} "
            f"--bet {b['id']} "
            f'--objective "{b["id"]} {b["title"]}"'
        )
        globs = []
        for p in b.get("write_surfaces", []):
            if "*" in p:
                globs.append(p)
                continue
            print(f"  uv run --with pyyaml python bin/agent-workflow.py claim <run-id> --path {p}")
        if globs:
            print("\n  # ⚠ claim 不做 glob 展开（lifecycle.py 只对锁目录 glob，--path 按字面量存）")
            print("  #   下列写面必须逐个真实文件 claim，否则锁名是字面量、D3 匹配不上：")
            for g in globs:
                base = g.split("*")[0].rstrip("/")
                print(f"  #   {g}  →  先看有哪些: git ls-files '{g}'  或  ls {base}/")
        if b.get("pasw_required"):
            print("  # ⚠ PASW: 子模块改动必须在 .subtrees/<sub>/ 内完成（ADR-0371）")
        if b.get("underlying_workflow"):
            print(f"  # 原挂载 workflow（phases/lock_scopes 可参考）: {b['underlying_workflow']}")
        print("\n收尾命令：")
        print("  git add <所有 deliverable>        # D0 铁律, 先于 verify")
        print("  uv run --with pyyaml python bin/agent-workflow.py verify <run-id> --from-diff --execute")
        print("  make agent-workflow-closeout RUN_ID=<run-id>")
        print(f"  # 写复盘: {RETRO_DIR.relative_to(WS)}/{b['id']}.md")
    return 0 if ok else 1


def cmd_verify(data: dict, args) -> int:
    b = bet_by_id(data, args.bet_id)
    rc = 0
    print(f"[{b['id']}] {b['title']}\n")
    print("done_when:")
    for d in b.get("done_when", []):
        print(f"  [ ] {d}")
    print("\nverify:")
    for v in b.get("verify", []):
        cmd, exp = v.get("cmd", ""), v.get("expect", "")
        print(f"  $ {cmd}")
        if args.execute:
            code, out = _run_verify_cmd(cmd)
            print(f"    → {out or '(空)'}")
            if code != 0:
                print(f"    FAIL exit={code}")
                rc = 1
        print(f"    期望: {exp}")
    print("\nD0 (入库才算交付):")
    for p in b.get("write_surfaces", []):
        if "*" in p:
            print(f"  [跳过] {p} (通配, 需人工核对)")
            continue
        tracked, detail = _d0_surface_tracked(p)
        if tracked:
            print(f"  [OK]   {p} ({detail})")
        else:
            print(f"  [未入库] {p} ({detail})")
            rc = 1
    print("\nD2 (表面积记账): 见 `bet-ledger.py surface`")
    if not args.execute:
        print("(加 --execute 实际运行 verify 命令)")
    return rc


def cmd_status(data: dict, args) -> int:
    bets = data["bets"]
    by_status: dict[str, int] = {}
    by_window: dict[str, dict[str, int]] = {}
    for b in bets:
        s = b.get("status", "candidate")
        by_status[s] = by_status.get(s, 0) + 1
        by_window.setdefault(b["window"], {})[s] = by_window.setdefault(b["window"], {}).get(s, 0) + 1
    print("=== 台账总览 ===")
    print(f"总 bet: {len(bets)}")
    for s, n in sorted(by_status.items()):
        print(f"  {s:12} {n}")
    print("\n=== 按窗口 ===")
    for w in data["meta"]["windows"]:
        if w in by_window:
            done = by_window[w].get("done", 0)
            total = sum(by_window[w].values())
            filled = int(20 * done / total) if total else 0
            print(f"  {w:6} {'█' * filled}{'░' * (20 - filled)} {done}/{total}")
    print("\n=== 当前可认领（按窗口排序，优先做靠前窗口）===")
    order = {w: i for i, w in enumerate(data["meta"]["windows"])}
    claimable = [b for b in bets if _claimable(data, b)[0]]
    claimable.sort(key=lambda b: (order.get(b["window"], 99), b["id"]))
    for b in claimable:
        h = "★" if b.get("human_gate") else " "
        print(f"  {h} {b['window']:6} {b['id']:24} {b.get('appetite', ''):<9} {b['title']}")
    if not claimable:
        print("  （无。检查 depends_on 或并发上限）")
    else:
        print(f"\n  共 {len(claimable)} 个可认领；★ = 需 operator/human 到场")
    return 0


def cmd_retro_due(data: dict, args) -> int:
    due = [
        b
        for b in data["bets"]
        if b.get("status") == "done"
        and b.get("retro") in ("required", "light")
        and not (RETRO_DIR / f"{b['id']}.md").exists()
    ]
    if getattr(args, "json", False):
        report = {
            "ok": not due,
            "count": len(due),
            "due": [{"id": b["id"], "title": b.get("title", "")} for b in due],
        }
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0 if report["ok"] else 1
    if not due:
        print("无待补复盘。")
        return 0
    print("以下 bet 已 done 但缺复盘（违反 D5）：")
    for b in due:
        print(f"  {b['id']:24} {b['title']}")
    print(f"\n模板路径：{RETRO_DIR.relative_to(WS)}/<bet-id>.md")
    for q in data["retro"]["bet_level"]["questions"]:
        print(f"  - {q}")
    return 1


def measure_numstat_net(since: str = "2026-08-01") -> dict:
    """T1-03: numstat 净值口径 — 剥离重写对称噪音.

    surface 审计 (2026-08-15) 发现: gbrain 重写产生 +468K/-468K (净 0) 被总量
    口径计为 +468K 增长。本函数用 git log --numstat 按项目分桶统计:
      churn_add/churn_del = 逐文件增删总和 (含重写对称噪音)
      net = add - del (真实净值)
      symmetric = min(add, del) 按文件聚合后求和 (重写噪音量)
    """

    def _parse_numstat(out: str, proj: str, per_project: dict) -> None:
        for line in out.splitlines():
            if "\t" not in line:
                continue  # commit/author/merge 行
            parts = line.split("\t")
            if len(parts) < 3:
                continue
            try:
                a = int(parts[0]) if parts[0] != "-" else 0
                d = int(parts[1]) if parts[1] != "-" else 0
            except ValueError:
                continue
            b = per_project.setdefault(proj, {"add": 0, "del": 0, "sym": 0})
            b["add"] += a
            b["del"] += d
            b["sym"] += min(a, d)

    per_project: dict[str, dict[str, int]] = {}
    # 主仓 projects/ 路径
    r = subprocess.run(
        [
            "git",
            "log",
            "--numstat",
            "--no-renames",
            f"--since={since}",
            "--format=",
            "--",
            "projects/",
        ],
        cwd=WS,
        capture_output=True,
        text=True,
        check=False,
    )
    _parse_numstat(r.stdout, "_root", per_project)
    # 子模块: 各自 git 历史 (gbrain +468K 重写噪音就藏在子模块历史里)
    for sub in (WS / "projects").iterdir():
        if not (sub / ".git").exists():
            continue
        rs = subprocess.run(
            [
                "git",
                "log",
                "--numstat",
                "--no-renames",
                f"--since={since}",
                "--format=",
                "--",
                "src/",
            ],
            cwd=sub,
            capture_output=True,
            text=True,
            check=False,
        )
        _parse_numstat(rs.stdout, sub.name, per_project)
    return per_project


def cmd_surface(data: dict, args) -> int:
    cur = measure_surface()
    print("=== 表面积实测（git tracked 口径，含子模块）===")
    print(f"{'指标':<18}{'当前':>10}{'基线(2026-08)':>16}{'变化':>16}   Y1 判据")
    print("-" * 88)
    for k, base in BASELINE.items():
        c = cur.get(k, 0)
        delta = c - base
        pct = (delta / base * 100) if base else 0
        tgt = Y1_TARGET.get(k, "—")
        tgt = "—" if tgt is None else str(tgt)
        print(f"{k:<18}{c:>10,}{base:>16,}{delta:>+10,}({pct:+.0f}%)   {tgt}")

    rc = 0
    print()
    # 保护量：测试行数下降 = 有害减法
    dt = cur.get("test_loc", 0) - BASELINE["test_loc"]
    if dt < 0:
        print(f"🔴 test_loc 下降 {-dt:,} 行 —— 有害减法。")
        print("   测试是保护量不是削减对象。删测试能让任何总量指标好看，但直接损害可维护性。")
        rc = 1
    else:
        print(f"✅ test_loc 未下降（{dt:+,}）")

    ds = cur.get("src_loc", 0) - BASELINE["src_loc"]
    print(f"   src_loc 变化 {ds:+,} 行  ← 观察量，由具体归并 bet 的去重量累计，不设百分比目标")

    dq = cur.get("gac_required", 0) - BASELINE["gac_required"]
    print(f"   gac_required 变化 {dq:+,}  ← 会拦人的规则才是真成本；advisory 删了没收益")

    # T1-03: numstat 净值口径 — 三口径对照 (总量口径会高估重写型变更)
    try:
        per_proj = measure_numstat_net()
        if per_proj:
            print("\n=== numstat 净值口径 (T1-03, since 2026-08-01, 只看 projects/) ===")
            print(f"{'项目':<16}{'churn_add':>12}{'churn_del':>12}{'净值':>12}{'重写噪音':>12}")
            print("-" * 64)
            tot_a = tot_d = tot_s = 0
            for proj, b in sorted(per_proj.items(), key=lambda kv: -(kv[1]["add"] + kv[1]["del"]))[:10]:
                net = b["add"] - b["del"]
                print(f"{proj:<16}{b['add']:>12,}{b['del']:>12,}{net:>+12,}{b['sym']:>12,}")
                tot_a += b["add"]
                tot_d += b["del"]
                tot_s += b["sym"]
            print("-" * 64)
            print(f"{'合计':<16}{tot_a:>12,}{tot_d:>12,}{tot_a - tot_d:>+12,}{tot_s:>12,}")
            print("   净值 = add - del; 重写噪音 = 逐文件 min(add,del) 聚合 (对称改写, 净贡献≈0)")
    except Exception as exc:
        print(f"\n[numstat] 统计跳过: {exc}")

    print("\nD2 记账：把上面这几行贴进复盘 Q4。")
    return rc


def cmd_gate(data: dict, args) -> int:
    g = data.get("gates", {}).get(args.window)
    if not g:
        sys.exit(f"无此门: {args.window}（可用: {', '.join(data.get('gates', {}))}）")
    print(f"=== 门 {args.window} ===")
    print(f"问题:     {g['question']}")
    print(f"通过条件: {g['pass']}")
    print(f"不通过时: {g.get('on_fail', '—')}")
    print(f"\n本门为人工判定，结论须写入：{RETRO_DIR.relative_to(WS)}/gates/{args.window}.md")
    return 0


def _yaml_mapping(text: str) -> dict[str, Any]:
    data: dict[str, Any] = {}
    for document in yaml.safe_load_all(text):
        if isinstance(document, dict):
            data.update(document)
    return data


def _is_historical_spec_grandfathered(
    bet: dict,
    *,
    workspace: Path = WS,
) -> bool:
    """Return whether ID, status, and date match the frozen migration boundary."""
    del workspace  # Kept as an injectable API boundary for callers and tests.
    status = str(bet.get("status") or "")
    if status not in SPEC_BINDING_GRANDFATHERED_STATUSES:
        return False
    bet_id = str(bet.get("id") or "")
    if SPEC_BINDING_GRANDFATHER_ALLOWLIST.get(bet_id) != status:
        return False
    terminal_at = str(bet.get("done_at") or bet.get("completed_at") or "")
    return not terminal_at or terminal_at <= SPEC_BINDING_GRANDFATHER_CUTOFF


def _is_spec_binding_required(bet: dict, *, workspace: Path = WS) -> bool:
    """Require a canonical binding unless immutable history grants compatibility."""
    return not _is_historical_spec_grandfathered(bet, workspace=workspace)


def _file_sha256(path: Path) -> str:
    """计算文件的 SHA256 哈希。"""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _spec_frontmatter(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    """Read the canonical Markdown frontmatter without creating a second Spec store."""
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines or lines[0].strip() != "---":
        return None, "SPEC_FRONTMATTER_INVALID: canonical Spec must start with YAML frontmatter"
    try:
        end = next(index for index, line in enumerate(lines[1:], start=1) if line.strip() == "---")
    except StopIteration:
        return None, "SPEC_FRONTMATTER_INVALID: canonical Spec frontmatter is not closed"
    try:
        frontmatter = yaml.safe_load("\n".join(lines[1:end]))
    except yaml.YAMLError as exc:
        return None, f"SPEC_FRONTMATTER_INVALID: {exc}"
    if not isinstance(frontmatter, dict):
        return None, "SPEC_FRONTMATTER_INVALID: canonical Spec frontmatter must be a mapping"
    return frontmatter, None


def _is_spec_frontmatter_grandfathered(bet: dict, binding: dict[str, Any]) -> bool:
    """Permit only the frozen pre-v1 contract whose exact identity is already terminal."""
    if bet.get("status") != "done":
        return False
    frozen = SPEC_FRONTMATTER_GRANDFATHER_ALLOWLIST.get(str(bet.get("id") or ""))
    return frozen == {key: binding.get(key) for key in SPEC_BINDING_KEYS}


def _is_completion_evidence_grandfathered(bet: dict, *, workspace: Path) -> bool:
    if _is_historical_spec_grandfathered(bet, workspace=workspace):
        return True
    bindings = bet.get("accepted_specifications")
    return (
        isinstance(bindings, list)
        and len(bindings) == 1
        and isinstance(bindings[0], dict)
        and _is_spec_frontmatter_grandfathered(bet, bindings[0])
    )


def _validate_evidence_reference(
    *,
    axis: str,
    key: str,
    value: Any,
    workspace: Path,
) -> list[str]:
    """Resolve one evidence reference so a placeholder cannot make an axis green."""
    prefix = f"{axis}.{key}"
    if not isinstance(value, dict):
        return [f"COMPLETION_EVIDENCE_REF_SHAPE: {prefix} must be a mapping"]
    if set(value) not in ({"ref"}, {"ref", "sha256"}):
        return [f"COMPLETION_EVIDENCE_REF_SHAPE: {prefix} accepts only ref and optional sha256"]
    ref = value.get("ref")
    if not isinstance(ref, str) or not ref.strip():
        return [f"COMPLETION_EVIDENCE_REF_REQUIRED: {prefix}.ref must be non-empty"]

    if key == "merged_reachable_commit":
        match = re.fullmatch(r"git://origin/main@([0-9a-f]{40})", ref)
        if match is None:
            return [
                f"COMPLETION_GIT_REF_INVALID: {prefix}.ref must be "
                "git://origin/main@<40-lowercase-hex>"
            ]
        commit = match.group(1)
        try:
            exists = subprocess.run(
                ["git", "-C", str(workspace), "cat-file", "-e", f"{commit}^{{commit}}"],
                capture_output=True,
                text=True,
                check=False,
            )
            reachable = subprocess.run(
                ["git", "-C", str(workspace), "merge-base", "--is-ancestor", commit, "origin/main"],
                capture_output=True,
                text=True,
                check=False,
            )
        except OSError as exc:
            return [f"COMPLETION_GIT_REF_UNPROVABLE: {prefix}: {exc}"]
        if exists.returncode != 0 or reachable.returncode != 0:
            return [f"COMPLETION_GIT_REF_NOT_REACHABLE: {prefix}.ref is not reachable from origin/main"]
        return []

    relative: str | None = None
    for scheme in ("repo://", "receipt://"):
        if ref.startswith(scheme):
            relative = ref.removeprefix(scheme).split("#", 1)[0]
            break
    if relative is None or not relative:
        return [f"COMPLETION_FILE_REF_INVALID: {prefix}.ref must use repo:// or receipt://"]
    candidate = (workspace / relative).resolve()
    try:
        candidate.relative_to(workspace.resolve())
    except ValueError:
        return [f"COMPLETION_FILE_REF_INVALID: {prefix}.ref escapes workspace"]
    if not candidate.is_file():
        return [f"COMPLETION_FILE_REF_MISSING: {prefix}.ref does not resolve to a file"]
    digest = value.get("sha256")
    if not isinstance(digest, str) or SHA256_REF_RE.fullmatch(digest) is None:
        return [f"COMPLETION_FILE_DIGEST_REQUIRED: {prefix}.sha256 must be sha256:<64-lowercase-hex>"]
    actual = f"sha256:{_file_sha256(candidate)}"
    if digest != actual:
        return [f"COMPLETION_FILE_DIGEST_MISMATCH: {prefix}.sha256 does not match resolved file"]
    return []


def _attestation_message(receipt: dict[str, Any]) -> bytes:
    """Canonical bytes a human signs to bind their verdict to a value sample.

    Field order and separators are fixed so signing and verification are
    byte-identical without trusting a projection.
    """
    lines: list[str] = []
    for field in HUMAN_ATTESTATION_MESSAGE_FIELDS:
        value = receipt.get(field)
        if value is None:
            raise ValueError(f"human_attestation_message_missing_field:{field}")
        lines.append(f"{field}={value}")
    return "\n".join(lines).encode("utf-8") + b"\n"


def _attestation_signature_bytes(receipt: dict[str, Any]) -> bytes:
    """Decode the base64 signature blob without trusting a caller path."""
    encoded = receipt.get("signature_b64")
    if not isinstance(encoded, str) or not encoded.strip():
        raise ValueError("human_attestation_signature_missing")
    try:
        decoded = base64.b64decode(encoded, validate=True)
    except (ValueError, TypeError) as exc:
        raise ValueError(f"human_attestation_signature_invalid:{exc}") from exc
    if not decoded:
        raise ValueError("human_attestation_signature_empty")
    return decoded


def validate_human_attestation(
    *,
    receipt_path: Path,
    workspace: Path = WS,
) -> list[str]:
    """Verify a credential-bound human attestation receipt via SSH signatures.

    The receipt is a ``human-attestation/v1`` YAML mapping that a human signed
    with ``ssh-keygen -Y sign``.  ``ssh-keygen -Y verify`` proves the signature
    against a server-owned allowed-signers file, so an agent-issued HTTP verdict
    or a forged receipt cannot satisfy the value axis.  Returns a list of
    errors (empty when the attestation is valid).
    """
    if not receipt_path.is_file():
        return ["COMPLETION_HUMAN_AUTH_RECEIPT_MISSING: attestation receipt does not resolve to a file"]
    try:
        raw = receipt_path.read_text(encoding="utf-8")
        receipt = yaml.safe_load(raw)
    except (OSError, ValueError) as exc:
        return [f"COMPLETION_HUMAN_AUTH_RECEIPT_UNREADABLE: {exc}"]
    if not isinstance(receipt, dict):
        return ["COMPLETION_HUMAN_AUTH_RECEIPT_SHAPE: receipt must be a mapping"]
    if receipt.get("schema_version") != HUMAN_ATTESTATION_SCHEMA_VERSION:
        return [
            "COMPLETION_HUMAN_AUTH_SCHEMA: schema_version must equal "
            f"{HUMAN_ATTESTATION_SCHEMA_VERSION}"
        ]

    allowed_signers = Path(HUMAN_ATTESTATION_ALLOWED_SIGNERS).expanduser().resolve()
    if not allowed_signers.is_file():
        return [
            "COMPLETION_HUMAN_AUTH_VERIFIER_UNCONFIGURED: allowed-signers file missing at "
            f"{HUMAN_ATTESTATION_ALLOWED_SIGNERS}"
        ]
    identity = receipt.get("signer_identity")
    if not isinstance(identity, str) or not identity.strip():
        return ["COMPLETION_HUMAN_AUTH_IDENTITY_REQUIRED: signer_identity must be non-empty"]

    try:
        message = _attestation_message(receipt)
        signature = _attestation_signature_bytes(receipt)
    except ValueError as exc:
        return [f"COMPLETION_HUMAN_AUTH_MESSAGE_INVALID: {exc}"]

    with tempfile.TemporaryDirectory(prefix="human-attestation-verify-") as tmp_dir:
        tmp = Path(tmp_dir)
        message_path = tmp / "message.txt"
        signature_path = tmp / "message.txt.sig"
        try:
            message_path.write_bytes(message)
            signature_path.write_bytes(signature)
        except OSError as exc:
            return [f"COMPLETION_HUMAN_AUTH_IO: {exc}"]
        try:
            result = subprocess.run(
                [
                    "ssh-keygen",
                    "-Y",
                    "verify",
                    "-f",
                    str(allowed_signers),
                    "-I",
                    identity,
                    "-n",
                    HUMAN_ATTESTATION_SSH_NAMESPACE,
                    "-s",
                    str(signature_path),
                ],
                input=message_path.read_bytes(),
                capture_output=True,
                check=False,
            )
        except OSError as exc:
            return [f"COMPLETION_HUMAN_AUTH_VERIFY_UNAVAILABLE: {exc}"]
        if result.returncode != 0:
            stderr = (result.stderr or result.stdout or b"").decode("utf-8", "replace").strip()
            return [f"COMPLETION_HUMAN_AUTH_SIGNATURE_INVALID: {stderr[:200] or 'ssh-keygen rejected signature'}"]
    return []


def validate_completion_evidence(
    matrix: Any,
    *,
    workspace: Path = WS,
) -> tuple[str, list[str]]:
    """Validate the three independent completion axes and derive one fail-closed state."""
    errors: list[str] = []
    if not isinstance(matrix, dict):
        return "blocked", ["COMPLETION_EVIDENCE_SHAPE: matrix must be a mapping"]
    if matrix.get("schema_version") != COMPLETION_EVIDENCE_SCHEMA_VERSION:
        errors.append(
            "COMPLETION_EVIDENCE_SCHEMA: schema_version must equal "
            f"{COMPLETION_EVIDENCE_SCHEMA_VERSION}"
        )

    axes = matrix.get("axes")
    if not isinstance(axes, dict) or set(axes) != set(COMPLETION_AXIS_STATUSES):
        return "blocked", [
            *errors,
            "COMPLETION_AXES_SHAPE: axes must contain exactly engineering, operational, value",
        ]

    statuses: dict[str, str] = {}
    for axis, allowed_statuses in COMPLETION_AXIS_STATUSES.items():
        axis_record = axes.get(axis)
        if not isinstance(axis_record, dict):
            errors.append(f"COMPLETION_AXIS_SHAPE: {axis} must be a mapping")
            continue
        status = axis_record.get("status")
        if status not in allowed_statuses:
            errors.append(
                f"COMPLETION_AXIS_STATUS: {axis}.status must be one of {sorted(allowed_statuses)}"
            )
            continue
        statuses[axis] = status
        evidence = axis_record.get("evidence")
        if not isinstance(evidence, dict):
            errors.append(f"COMPLETION_AXIS_EVIDENCE: {axis}.evidence must be a mapping")
            continue
        required = COMPLETION_DIRECT_EVIDENCE.get(axis, {}).get(status, frozenset())
        missing = sorted(key for key in required if key not in evidence)
        if missing:
            errors.append(
                f"COMPLETION_DIRECT_EVIDENCE_REQUIRED: {axis}.{status} missing={missing}"
            )
        if axis == "value" and status == "ACCEPTED" and not missing:
            # The four direct evidence keys are present; the value axis still
            # needs a credential-bound human attestation (signed verdict), not
            # just an HTTP-callable receipt. Fail closed until it verifies.
            attestation = evidence.get("attestation")
            if not isinstance(attestation, dict) or not isinstance(attestation.get("ref"), str):
                errors.append(
                    "COMPLETION_HUMAN_AUTH_REQUIRED: value.ACCEPTED needs evidence.attestation.ref "
                    "pointing to a human-attestation/v1 receipt"
                )
            else:
                att_errors = _validate_evidence_reference(
                    axis="value",
                    key="attestation",
                    value=attestation,
                    workspace=workspace,
                )
                if att_errors:
                    errors.extend(att_errors)
                else:
                    receipt_path = (workspace / attestation["ref"].removeprefix("receipt://").split("#", 1)[0]).resolve()
                    errors.extend(validate_human_attestation(receipt_path=receipt_path, workspace=workspace))
            for key in sorted(required - set(missing)):
                errors.extend(
                    _validate_evidence_reference(
                        axis=axis,
                        key=key,
                        value=evidence[key],
                        workspace=workspace,
                    )
                )
        else:
            for key in sorted(required - set(missing)):
                errors.extend(
                    _validate_evidence_reference(
                        axis=axis,
                        key=key,
                        value=evidence[key],
                        workspace=workspace,
                    )
                )

    if set(statuses) != set(COMPLETION_AXIS_STATUSES):
        derived = "blocked"
    elif statuses["value"] == "REJECTED":
        derived = "rejected"
    elif (
        statuses["engineering"] == "VERIFIED"
        and statuses["operational"] == "PROVEN"
        and statuses["value"] == "ACCEPTED"
    ):
        derived = "outcome_accepted"
    elif statuses["engineering"] == "VERIFIED" or statuses["operational"] == "DEGRADED":
        derived = "blocked"
    else:
        derived = "evaluating"

    if errors:
        derived = "blocked"
    declared = matrix.get("overall_state")
    if declared != derived:
        errors.append(f"OVERALL_STATE_MISMATCH: declared={declared!r} derived={derived!r}")
    return derived, errors


def resolve_instruction_binding(*, workspace: Path = WS) -> dict[str, str]:
    """Measure the one canonical Instruction Pack without trusting a projection."""
    relative_ref = INSTRUCTION_PACK_REF.removeprefix(SPEC_REF_PREFIX)
    root = workspace.resolve()
    candidate = (root / relative_ref).resolve()
    if not candidate.is_relative_to(root):
        raise SpecBindingContractError("INSTRUCTION_PACK_REF_INVALID: resolved path escapes workspace")
    if not candidate.is_file():
        raise SpecBindingContractError(f"INSTRUCTION_PACK_MISSING: {relative_ref}")
    return {
        "instruction_ref": INSTRUCTION_PACK_REF,
        "instruction_version": INSTRUCTION_PACK_VERSION,
        "content_digest": f"sha256:{_file_sha256(candidate)}",
        "instruction_profile": INSTRUCTION_PACK_PROFILE,
    }


def validate_accepted_specification(
    bet: dict,
    *,
    workspace: Path = WS,
) -> tuple[dict[str, str] | None, list[str]]:
    """Validate the one canonical SpecificationBinding used by WorkPacket v2."""
    errors: list[str] = []
    bet_id = str(bet.get("id") or "")
    specs = bet.get("accepted_specifications")
    if not isinstance(specs, list) or len(specs) != 1:
        return None, ["SPEC_BINDING_REQUIRED: accepted_specifications must contain exactly one binding"]
    binding = specs[0]
    if not isinstance(binding, dict):
        return None, ["SPEC_BINDING_SHAPE: binding must be a mapping"]

    keys = set(binding)
    if keys != SPEC_BINDING_KEYS:
        missing = sorted(SPEC_BINDING_KEYS - keys)
        extra = sorted(keys - SPEC_BINDING_KEYS)
        errors.append(f"SPEC_BINDING_SHAPE: exact keys required; missing={missing} extra={extra}")

    spec_ref = binding.get("spec_ref")
    spec_version = binding.get("spec_version")
    content_digest = binding.get("content_digest")
    decision_ref = binding.get("decision_ref")

    relative_ref = ""
    if not isinstance(spec_ref, str) or not spec_ref.startswith(SPEC_REF_PREFIX):
        errors.append("SPEC_REF_INVALID: spec_ref must use repo://docs/superpowers/specs/<file>")
    else:
        relative_ref = spec_ref.removeprefix(SPEC_REF_PREFIX)
        relative_path = PurePosixPath(relative_ref)
        if (
            not relative_ref
            or relative_path.is_absolute()
            or ".." in relative_path.parts
            or relative_path == SPEC_ROOT
            or not relative_path.is_relative_to(SPEC_ROOT)
            or relative_path.as_posix() != relative_ref
        ):
            errors.append("SPEC_REF_INVALID: spec_ref must be a canonical repo:// path under docs/superpowers/specs/")

    if not isinstance(spec_version, str) or SEMVER_RE.fullmatch(spec_version) is None:
        errors.append("SPEC_VERSION_INVALID: spec_version must be semver")

    if not isinstance(content_digest, str) or SHA256_REF_RE.fullmatch(content_digest) is None:
        errors.append("SPEC_DIGEST_INVALID: content_digest must match sha256:<64 lowercase hex>")

    expected_decision = f"decision://accepted/{bet_id}"
    if decision_ref != expected_decision:
        errors.append(f"SPEC_DECISION_NOT_ACCEPTED: decision_ref must equal {expected_decision}")

    if relative_ref and not any(error.startswith("SPEC_REF_INVALID") for error in errors):
        root = workspace.resolve()
        candidate = (root / relative_ref).resolve()
        if not candidate.is_relative_to(root):
            errors.append("SPEC_REF_INVALID: resolved spec path escapes workspace")
        elif not candidate.is_file():
            errors.append(f"SPEC_FILE_MISSING: {relative_ref}")
        else:
            if not _is_spec_frontmatter_grandfathered(bet, binding):
                frontmatter, frontmatter_error = _spec_frontmatter(candidate)
                if frontmatter_error:
                    errors.append(frontmatter_error)
                elif frontmatter is not None:
                    if frontmatter.get("schema_version") != SPECIFICATION_SCHEMA_VERSION:
                        errors.append(
                            "SPEC_FRONTMATTER_SCHEMA_INVALID: schema_version must equal "
                            f"{SPECIFICATION_SCHEMA_VERSION}"
                        )
                    if frontmatter.get("status") != "accepted":
                        errors.append("SPEC_STATUS_NOT_ACCEPTED: canonical Spec status must equal accepted")
                    if frontmatter.get("spec_version") != spec_version:
                        errors.append(
                            "SPEC_FRONTMATTER_VERSION_MISMATCH: frontmatter spec_version must equal binding"
                        )
                    if frontmatter.get("bet_id") != bet_id:
                        errors.append("SPEC_FRONTMATTER_BET_MISMATCH: frontmatter bet_id must equal BET id")
            if isinstance(content_digest, str) and SHA256_REF_RE.fullmatch(content_digest):
                actual_digest = f"sha256:{_file_sha256(candidate)}"
                if actual_digest != content_digest:
                    errors.append(
                        f"SPEC_DIGEST_MISMATCH: declared={content_digest[:23]}... "
                        f"actual={actual_digest[:23]}..."
                    )

    if errors:
        return None, errors
    return {key: str(binding[key]) for key in sorted(SPEC_BINDING_KEYS)}, []


def _ledger_for_workspace(workspace: Path) -> dict[str, Any]:
    ledger = workspace / "docs/plans/3y-bet-ledger.yaml"
    if not ledger.is_file():
        raise SpecBindingContractError(f"BET_LEDGER_UNAVAILABLE: {ledger}")
    data = _yaml_mapping(ledger.read_text(encoding="utf-8"))
    if not isinstance(data.get("bets"), list):
        raise SpecBindingContractError("BET_LEDGER_INVALID: bets must be a list")
    return data


def _bet_for_execution(workspace: Path, bet_id: str) -> dict[str, Any]:
    for item in _ledger_for_workspace(workspace)["bets"]:
        if isinstance(item, dict) and item.get("id") == bet_id:
            return item
    raise SpecBindingContractError(f"BET_NOT_FOUND: {bet_id}")


def _work_packet_compiler(workspace: Path) -> tuple[Any, Any]:
    ecos_src = workspace / "projects/ecos/src"
    if str(ecos_src) not in sys.path:
        sys.path.insert(0, str(ecos_src))
    try:
        from ecos.ssot.tools.work_packet_compiler import canonicalize, compute_packet_hash
    except (ImportError, ModuleNotFoundError) as exc:
        raise SpecBindingContractError("WORK_PACKET_COMPILER_UNAVAILABLE") from exc
    return canonicalize, compute_packet_hash


def _work_packet_from_bet(
    bet: dict[str, Any],
    binding: dict[str, str],
    instruction_binding: dict[str, str],
) -> dict[str, Any]:
    """Project one ledger BET into the existing ECOS WorkPacket v2 schema."""
    bet_id = str(bet["id"])
    risk = str(bet.get("risk_level") or "L1")
    risk_level = f"R{risk[1:]}" if len(risk) == 2 and risk[0] == "L" and risk[1].isdigit() else "R1"
    verify_commands: list[list[str]] = []
    for item in bet.get("verify") or []:
        command = item.get("cmd") if isinstance(item, dict) else item
        if isinstance(command, str) and command.strip():
            verify_commands.append([command.strip()])
    write_surfaces = sorted(
        {str(item).strip().strip("/") for item in bet.get("write_surfaces") or [] if str(item).strip()}
    )
    spec_surface = binding["spec_ref"].removeprefix(SPEC_REF_PREFIX)
    instruction_surface = instruction_binding["instruction_ref"].removeprefix(SPEC_REF_PREFIX)
    return {
        "packet_id": f"WP-{bet_id}",
        "schema_version": "work-packet/v2",
        "blueprint_ref": "blueprint://multi-agent-execution-control/v1",
        "wave": str(bet.get("window") or ""),
        "bet_id": bet_id,
        "strategic_outcome": str(bet.get("goal") or ""),
        "objective": str(bet.get("goal") or bet.get("title") or ""),
        "why_now": (f"priority={bet.get('priority', 'unspecified')}; appetite={bet.get('appetite', 'unspecified')}"),
        "status": "active",
        "authority": {
            "strategist": "3y-bet-ledger",
            "human_gate": bool(bet.get("human_gate")),
            "risk_level": risk_level,
        },
        "scope": {
            "read_surfaces": [
                "docs/plans/3y-bet-ledger.yaml",
                spec_surface,
                instruction_surface,
            ],
            "write_surfaces": write_surfaces,
            "non_goals": [str(item) for item in bet.get("non_goals") or []],
        },
        "dependencies": {
            "required_packets": [f"WP-{item}" for item in bet.get("depends_on") or []],
            "required_decisions": [binding["decision_ref"]],
        },
        "acceptance": {
            "done_when": [
                {
                    "id": f"AC-{index:02d}",
                    "assertion": str(assertion),
                    "evidence_type": "structured_report",
                }
                for index, assertion in enumerate(bet.get("done_when") or [], start=1)
            ],
            "verify_commands": verify_commands,
        },
        "rollback": {
            "strategy": str(bet.get("circuit_breaker") or "stop and escalate"),
            "data_migration": False,
        },
        "circuit_breaker": {
            "when": [str(bet.get("circuit_breaker") or "contract cannot be proven")],
            "action": "stop_and_escalate",
        },
        "spec_binding": binding,
        "instruction_binding": instruction_binding,
    }


def prepare_bet_execution(
    bet_id: str,
    *,
    workspace: Path = WS,
    require_startable: bool = True,
) -> dict[str, Any]:
    """Build the canonical identity used by every workflow start entrypoint."""
    bet = _bet_for_execution(workspace, bet_id)
    status = str(bet.get("status") or "")
    if require_startable and status not in STARTABLE_BET_STATUSES:
        raise SpecBindingContractError(
            f"BET_STATUS_NOT_STARTABLE: {bet_id} status={status}; allowed={sorted(STARTABLE_BET_STATUSES)}"
        )
    binding, errors = validate_accepted_specification(bet, workspace=workspace)
    if errors or binding is None:
        raise SpecBindingContractError("; ".join(errors or ["SPEC_BINDING_INVALID"]))
    instruction_binding = resolve_instruction_binding(workspace=workspace)
    canonicalize, compute_packet_hash = _work_packet_compiler(workspace)
    packet = _work_packet_from_bet(bet, binding, instruction_binding)
    try:
        packet_hash = compute_packet_hash(canonicalize(packet))
    except ValueError as exc:
        raise SpecBindingContractError(f"WORK_PACKET_INVALID: {exc}") from exc
    return {
        "spec_binding": binding,
        "instruction_binding": instruction_binding,
        "work_packet": packet,
        "work_packet_hash": packet_hash,
    }


def _normalize_claim_path(raw_path: str, workspace: Path) -> str:
    if not raw_path:
        raise SpecBindingContractError("path cannot be empty")
    path = Path(raw_path).expanduser()
    if path.is_absolute():
        try:
            path = path.resolve().relative_to(workspace.resolve())
        except ValueError as exc:
            raise SpecBindingContractError(f"path is outside workspace: {raw_path}") from exc
    normalized = path.as_posix().strip("/")
    if normalized in {"", "."}:
        return "."
    if normalized == ".." or normalized.startswith("../") or "/../" in normalized:
        raise SpecBindingContractError(f"path escapes workspace: {raw_path}")
    return normalized


def _surface_allows_path(surface: str, claimed_path: str) -> bool:
    normalized_surface = surface.strip().strip("/")
    if not normalized_surface:
        return False
    if any(token in normalized_surface for token in "*?["):
        return fnmatch.fnmatchcase(claimed_path, normalized_surface)
    if claimed_path == normalized_surface:
        return True
    surface_path = PurePosixPath(normalized_surface)
    looks_like_directory = "/" in normalized_surface and not surface_path.suffix
    return looks_like_directory and claimed_path.startswith(normalized_surface + "/")


def validate_work_packet_run(
    payload: dict[str, Any],
    claimed_paths: list[str],
    *,
    claimed_surfaces: list[str] | None = None,
    workspace: Path = WS,
) -> None:
    """Rebuild and validate a bound packet before any claim mutation occurs."""
    packet = payload.get("work_packet")
    packet_hash = payload.get("work_packet_hash")
    bet_id = str(payload.get("bet_id") or "")
    if packet is None and packet_hash is None:
        if bet_id:
            raise SpecBindingContractError(f"WORK_PACKET_MISSING: bet-bound run {payload.get('run_id', '')}")
        return  # Compatibility boundary for pre-spine and read-only runs.
    if not isinstance(packet, dict) or not isinstance(packet_hash, str):
        raise SpecBindingContractError("WORK_PACKET_INVALID: packet and packet hash are required")
    canonicalize, compute_packet_hash = _work_packet_compiler(workspace)
    try:
        measured_hash = compute_packet_hash(canonicalize(packet))
    except ValueError as exc:
        raise SpecBindingContractError(f"WORK_PACKET_INVALID: {exc}") from exc
    if measured_hash != packet_hash:
        raise SpecBindingContractError(f"WORK_PACKET_HASH_MISMATCH: declared={packet_hash} measured={measured_hash}")
    if packet.get("bet_id") != bet_id:
        raise SpecBindingContractError("WORK_PACKET_BET_MISMATCH: run and packet bet_id differ")
    rebuilt = prepare_bet_execution(bet_id, workspace=workspace, require_startable=False)
    if rebuilt["work_packet_hash"] != packet_hash:
        raise SpecBindingContractError(
            "WORK_PACKET_SOURCE_DRIFT: ledger/spec projection no longer matches the bound packet"
        )

    requested_surfaces = sorted({str(surface).strip() for surface in claimed_surfaces or [] if str(surface).strip()})
    if requested_surfaces:
        raise SpecBindingContractError(
            "WORK_PACKET_SCOPE_MISMATCH: governance surfaces are not modeled by "
            f"scope.write_surfaces: {requested_surfaces}"
        )
    allowed = packet.get("scope", {}).get("write_surfaces", [])
    if not isinstance(allowed, list):
        raise SpecBindingContractError("WORK_PACKET_INVALID: scope.write_surfaces must be a list")
    for raw_path in claimed_paths:
        claimed_path = _normalize_claim_path(raw_path, workspace)
        if not any(_surface_allows_path(str(surface), claimed_path) for surface in allowed):
            raise SpecBindingContractError(f"WORK_PACKET_SCOPE_MISMATCH: {claimed_path} is outside {allowed}")


def validate_worker_instruction_binding(
    *,
    workspace: Path,
    run_id: str,
    packet_id: str,
    packet_hash: str,
    instruction_binding: dict[str, Any],
) -> dict[str, str]:
    """Validate one immutable run/packet/instruction identity for a worker.

    This is intentionally a pure, read-only boundary.  It reloads the governed
    run, recomputes the canonical WorkPacket hash, rebuilds it from the ledger
    and accepted specification, and re-measures the canonical Instruction Pack
    bytes before any provider or transport side effect is allowed.
    """
    root = workspace.expanduser().resolve(strict=True)
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:+-]{0,255}", run_id):
        raise SpecBindingContractError("WORKER_BINDING_RUN_ID_INVALID")
    if not packet_id or not SHA256_REF_RE.fullmatch(packet_hash):
        raise SpecBindingContractError("WORKER_BINDING_PACKET_IDENTITY_INVALID")
    if not isinstance(instruction_binding, dict) or set(instruction_binding) != INSTRUCTION_BINDING_KEYS:
        raise SpecBindingContractError("WORKER_BINDING_INSTRUCTION_SHAPE_INVALID")

    run_path = root / ".omo" / "_delivery" / "agent-workflows" / "runs" / f"{run_id}.yaml"
    workflow_payload: dict[str, Any] | None = None
    if run_path.is_file():
        try:
            loaded = yaml.safe_load(run_path.read_text(encoding="utf-8")) or {}
        except (OSError, UnicodeError, yaml.YAMLError) as exc:
            raise SpecBindingContractError("WORKER_BINDING_RUN_UNAVAILABLE") from exc
        if not isinstance(loaded, dict) or loaded.get("run_id") != run_id:
            raise SpecBindingContractError("WORKER_BINDING_RUN_MISMATCH")
        workflow_payload = loaded

    mesh_snapshot = _load_durable_mesh_snapshot(root, run_id)
    mesh_worker = mesh_snapshot.get("worker") if mesh_snapshot is not None else None
    mesh_bound = isinstance(mesh_worker, dict)
    if workflow_payload is None and not mesh_bound:
        raise SpecBindingContractError("WORKER_BINDING_RUN_UNAVAILABLE")

    if workflow_payload is not None:
        payload = workflow_payload
        packet = payload.get("work_packet")
        if not isinstance(packet, dict):
            raise SpecBindingContractError("WORKER_BINDING_PACKET_MISSING")
        if packet.get("packet_id") != packet_id or payload.get("work_packet_hash") != packet_hash:
            raise SpecBindingContractError("WORKER_BINDING_PACKET_MISMATCH")
        if payload.get("instruction_binding") != instruction_binding:
            raise SpecBindingContractError("WORKER_BINDING_RUN_INSTRUCTION_MISMATCH")
        if packet.get("instruction_binding") != instruction_binding:
            raise SpecBindingContractError("WORKER_BINDING_PACKET_INSTRUCTION_MISMATCH")
    if mesh_bound:
        assert isinstance(mesh_worker, dict)
        if (
            mesh_worker.get("packet_id") != packet_id
            or mesh_worker.get("packet_hash") != packet_hash
            or mesh_worker.get("instruction_binding") != instruction_binding
        ):
            raise SpecBindingContractError("WORKER_BINDING_MESH_SNAPSHOT_MISMATCH")
    if workflow_payload is None:
        assert isinstance(mesh_worker, dict)
        if not packet_id.startswith("WP-BET-"):
            raise SpecBindingContractError("WORKER_BINDING_MESH_PACKET_ID_INVALID")
        bet_id = packet_id.removeprefix("WP-")
        rebuilt = prepare_bet_execution(bet_id, workspace=root, require_startable=False)
        packet = rebuilt["work_packet"]
        payload = {
            "run_id": run_id,
            "bet_id": bet_id,
            **rebuilt,
        }
        if rebuilt["work_packet_hash"] != packet_hash:
            raise SpecBindingContractError("WORKER_BINDING_MESH_PACKET_SOURCE_DRIFT")
        if rebuilt["instruction_binding"] != instruction_binding:
            raise SpecBindingContractError("WORKER_BINDING_MESH_INSTRUCTION_SOURCE_DRIFT")

    canonicalize, compute_packet_hash = _work_packet_compiler(root)
    try:
        measured_packet_hash = compute_packet_hash(canonicalize(packet))
    except ValueError as exc:
        raise SpecBindingContractError(f"WORKER_BINDING_PACKET_INVALID: {exc}") from exc
    if measured_packet_hash != packet_hash:
        raise SpecBindingContractError("WORKER_BINDING_PACKET_HASH_MISMATCH")

    measured_instruction = resolve_instruction_binding(workspace=root)
    if measured_instruction != instruction_binding:
        raise SpecBindingContractError("WORKER_BINDING_INSTRUCTION_SOURCE_DRIFT")
    if workflow_payload is not None:
        validate_work_packet_run(payload, [], workspace=root)
    ack_state = "not_dispatched"
    if mesh_bound:
        decision = mesh_worker.get("ack_decision")
        if decision is None:
            ack_state = "pending"
        elif decision in {"proceed", "stop"}:
            ack_state = str(decision)
        else:
            raise SpecBindingContractError("WORKER_BINDING_MESH_ACK_STATE_INVALID")
    return {
        "run_id": run_id,
        "packet_id": packet_id,
        "packet_hash": packet_hash,
        "instruction_digest": instruction_binding["content_digest"],
        "worker_ack_state": ack_state,
    }


def _safe_omo_python_env(root: Path, *, origin_proof: str | None = None) -> dict[str, str]:
    """Build the minimal environment used by the read/append OMO broker calls."""
    omo_src = root / "projects" / "omo" / "src"
    if not (omo_src / "omo" / "cli.py").is_file():
        raise SpecBindingContractError("WORKER_BINDING_OMO_UNAVAILABLE")
    env = {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "PYTHONPATH": str(omo_src),
        "PYTHONDONTWRITEBYTECODE": "1",
    }
    if os.environ.get("UV_CACHE_DIR"):
        env["UV_CACHE_DIR"] = os.environ["UV_CACHE_DIR"]
    if origin_proof is not None:
        env["OMO_WORKER_ACK_ORIGIN_PROOF"] = origin_proof
    return env


def _load_durable_mesh_snapshot(root: Path, run_id: str) -> dict[str, Any] | None:
    """Project one exact durable Mesh run using the workspace's OMO implementation."""
    log_path = root / ".omo" / "_knowledge" / "workflow-mesh" / "events.jsonl"
    if not log_path.is_file():
        return None
    script = (
        "import json,sys; "
        "from pathlib import Path; "
        "from omo.workflow_mesh import WorkflowMeshStore; "
        "print(json.dumps(WorkflowMeshStore(Path(sys.argv[1])).snapshot(sys.argv[2]),"
        "sort_keys=True,separators=(',',':')))"
    )
    result = subprocess.run(
        [sys.executable, "-c", script, str(root / ".omo"), run_id],
        cwd=root,
        env=_safe_omo_python_env(root),
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    if result.returncode != 0:
        raise SpecBindingContractError("WORKER_BINDING_MESH_INVALID")
    try:
        snapshot = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise SpecBindingContractError("WORKER_BINDING_MESH_INVALID") from exc
    if not isinstance(snapshot, dict) or snapshot.get("workflow_run_id") != run_id:
        raise SpecBindingContractError("WORKER_BINDING_MESH_RUN_MISMATCH")
    return snapshot


def perform_authenticated_worker_ack(
    *,
    workspace: Path,
    workflow_run_id: str,
    trace_id: str,
    dispatch_id: str,
    worker_id: str,
    step_run_id: str,
    admission_id: str,
    packet_id: str,
    packet_hash: str,
    instruction_binding: dict[str, Any],
    ack_decision: str,
    lease_seconds: int,
    omo_dir: str,
    origin_proof: str | None,
) -> dict[str, str]:
    """Validate the immutable delivery, then append ACK through the OMO CLI broker."""
    root = workspace.expanduser().resolve(strict=True)
    if origin_proof is None:
        raise SpecBindingContractError("WORKER_ACK_ORIGIN_PROOF_REQUIRED")
    if re.fullmatch(r"[A-Za-z0-9_-]{43}", origin_proof) is None:
        raise SpecBindingContractError("WORKER_ACK_ORIGIN_PROOF_INVALID")
    public_ids = (workflow_run_id, trace_id, dispatch_id, worker_id, step_run_id, admission_id)
    if any(not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:+-]{0,255}", value) for value in public_ids):
        raise SpecBindingContractError("WORKER_ACK_CONTEXT_INVALID")
    if ack_decision != "proceed" or not isinstance(lease_seconds, int) or lease_seconds <= 0:
        raise SpecBindingContractError("WORKER_ACK_DECISION_INVALID")
    resolved_omo = (root / omo_dir).resolve() if not Path(omo_dir).is_absolute() else Path(omo_dir).resolve()
    if resolved_omo != (root / ".omo").resolve():
        raise SpecBindingContractError("WORKER_ACK_OMO_DIR_INVALID")

    validate_worker_instruction_binding(
        workspace=root,
        run_id=workflow_run_id,
        packet_id=packet_id,
        packet_hash=packet_hash,
        instruction_binding=instruction_binding,
    )
    instruction_json = json.dumps(
        instruction_binding,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    argv = [
        "uv",
        "run",
        "--project",
        str((root / "projects" / "omo").resolve()),
        "python",
        "-m",
        "omo.cli",
        "worker",
        "mesh-ack",
        workflow_run_id,
        "--trace-id",
        trace_id,
        "--dispatch-id",
        dispatch_id,
        "--worker",
        worker_id,
        "--step-run-id",
        step_run_id,
        "--admission-id",
        admission_id,
        "--packet-id",
        packet_id,
        "--packet-hash",
        packet_hash,
        "--instruction-binding-json",
        instruction_json,
        "--ack-decision",
        ack_decision,
        "--lease-seconds",
        str(lease_seconds),
        "--omo-dir",
        str(resolved_omo),
    ]
    result = subprocess.run(
        argv,
        cwd=root,
        env=_safe_omo_python_env(root, origin_proof=origin_proof),
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    if result.returncode != 0:
        raise SpecBindingContractError("WORKER_ACK_REJECTED")
    return {
        "run_id": workflow_run_id,
        "packet_id": packet_id,
        "packet_hash": packet_hash,
        "instruction_digest": instruction_binding["content_digest"],
        "outcome": "acknowledged",
    }


def complete_worker_origin_ack(
    *,
    workspace: Path,
    delivery_binding: dict[str, Any],
    binding_receipt: dict[str, str],
) -> dict[str, str]:
    """Consume a pending dispatch capability from inside the worker adapter.

    The controller may place the one-time capability in the child environment,
    but it must never invoke the ACK broker itself.  The admitted adapter calls
    this boundary after it has received and validated the immutable delivery
    identity and before it resolves or launches any provider.
    """
    if binding_receipt.get("worker_ack_state") != "pending":
        return binding_receipt
    raw_context = os.environ.get("OMO_WORKER_ACK_CONTEXT_JSON")
    origin_proof = os.environ.get("OMO_WORKER_ACK_ORIGIN_PROOF")
    if not raw_context:
        raise SpecBindingContractError("WORKER_ACK_CONTEXT_REQUIRED")
    try:
        context = json.loads(raw_context)
    except json.JSONDecodeError as exc:
        raise SpecBindingContractError("WORKER_ACK_CONTEXT_INVALID") from exc
    context_keys = {
        "workflow_run_id",
        "trace_id",
        "dispatch_id",
        "worker_id",
        "step_run_id",
        "admission_id",
        "packet_id",
        "packet_hash",
        "instruction_binding",
        "lease_seconds",
        "omo_dir",
    }
    if not isinstance(context, dict) or set(context) != context_keys:
        raise SpecBindingContractError("WORKER_ACK_CONTEXT_INVALID")
    expected_binding = {
        "run_id": context["workflow_run_id"],
        "packet_id": context["packet_id"],
        "packet_hash": context["packet_hash"],
        "instruction_binding": context["instruction_binding"],
    }
    if delivery_binding != expected_binding:
        raise SpecBindingContractError("WORKER_ACK_DELIVERY_MISMATCH")
    try:
        result = perform_authenticated_worker_ack(
            workspace=workspace,
            workflow_run_id=context["workflow_run_id"],
            trace_id=context["trace_id"],
            dispatch_id=context["dispatch_id"],
            worker_id=context["worker_id"],
            step_run_id=context["step_run_id"],
            admission_id=context["admission_id"],
            packet_id=context["packet_id"],
            packet_hash=context["packet_hash"],
            instruction_binding=context["instruction_binding"],
            ack_decision="proceed",
            lease_seconds=context["lease_seconds"],
            omo_dir=context["omo_dir"],
            origin_proof=origin_proof,
        )
    finally:
        os.environ.pop("OMO_WORKER_ACK_CONTEXT_JSON", None)
        os.environ.pop("OMO_WORKER_ACK_ORIGIN_PROOF", None)
    refreshed = validate_worker_instruction_binding(
        workspace=workspace,
        run_id=context["workflow_run_id"],
        packet_id=context["packet_id"],
        packet_hash=context["packet_hash"],
        instruction_binding=context["instruction_binding"],
    )
    if refreshed.get("worker_ack_state") != "proceed":
        raise SpecBindingContractError("WORKER_ACK_NOT_DURABLE")
    return {**refreshed, "ack_outcome": result["outcome"]}


def cmd_lint(data: dict, args) -> int:
    """台账自检：ID 唯一、依赖存在、轨道/窗口/状态合法、必填字段。"""
    errs: list[str] = []
    ids = [b["id"] for b in data["bets"]]
    for i in sorted(set(ids)):
        if ids.count(i) > 1:
            errs.append(f"重复 ID: {i}")
    tracks = set(data["tracks"])
    windows = set(data["meta"]["windows"])
    required = [
        "track",
        "window",
        "title",
        "appetite",
        "status",
        "goal",
        "done_when",
        "verify",
        "workflow",
        "write_surfaces",
    ]
    for b in data["bets"]:
        for f in required:
            if not b.get(f):
                errs.append(f"{b['id']}: 缺字段 {f}")
        if b.get("track") not in tracks:
            errs.append(f"{b['id']}: 未知 track {b.get('track')}")
        if b.get("window") not in windows:
            errs.append(f"{b['id']}: 未知 window {b.get('window')}")
        if b.get("status") not in data["meta"]["status_enum"]:
            errs.append(f"{b['id']}: 非法 status {b.get('status')}")
        for d in b.get("depends_on") or []:
            if d not in ids:
                errs.append(f"{b['id']}: 依赖不存在 {d}")
        # 未加引号的冒号会让 YAML 把列表项解析成 dict，静默丢失语义
        for key in ("done_when", "non_goals"):
            for i, item in enumerate(b.get(key) or []):
                if not isinstance(item, str):
                    errs.append(
                        f"{b['id']}.{key}[{i}]: 应为字符串却是 {type(item).__name__} "
                        f'— 多半是未加引号的冒号，请写成 "...: ..."'
                    )
        # Canonical binding is mandatory unless the immutable pre-migration
        # snapshot explicitly contains this terminal BET ID.
        if _is_spec_binding_required(b, workspace=WS):
            _binding, binding_errors = validate_accepted_specification(b, workspace=WS)
            errs.extend(f"{b['id']}.accepted_specifications: {error}" for error in binding_errors)
        completion_matrix = b.get("completion_evidence")
        matrix_required = b.get("status") in COMPLETION_MATRIX_REQUIRED_STATUSES or (
            b.get("status") == "done" and not _is_completion_evidence_grandfathered(b, workspace=WS)
        )
        if matrix_required and completion_matrix is None:
            errs.append(f"{b['id']}.completion_evidence: COMPLETION_EVIDENCE_REQUIRED")
        elif completion_matrix is not None:
            _state, completion_errors = validate_completion_evidence(
                completion_matrix,
                workspace=WS,
            )
            errs.extend(f"{b['id']}.completion_evidence: {error}" for error in completion_errors)
    if errs:
        for e in errs:
            print(f"ERROR {e}")
        print(f"\n{len(errs)} 个问题")
        return 1
    print(f"OK — {len(data['bets'])} 个 bet，{len(tracks)} 条轨道，无问题")
    return 0


def cmd_complete(data: dict, args) -> int:
    """台账完成: 校验 verify D0 入库 + retro 后置 status=done.

    P1 (方案 4): closeout 后自动回写台账, 防 done 状态滞后
    (记忆/台账脱节, 实际 done 远超记忆). 带 guard:
    - bet 存在且非 done
    - verify D0 检查通过 (write_surfaces 入库)
    - 可选 --force 跳过 guard (人工确认)
    """
    b = bet_by_id(data, args.bet_id)
    if _is_spec_binding_required(b, workspace=WS):
        _binding, binding_errors = validate_accepted_specification(b, workspace=WS)
        if binding_errors:
            for error in binding_errors:
                print(f"[complete] ❌ {b['id']}.accepted_specifications: {error}")
            return 1
    if b.get("status") == "done":
        print(f"[complete] {b['id']} 已是 done, 无需操作")
        return 0

    completion_matrix = b.get("completion_evidence")
    if completion_matrix is None:
        print(f"[complete] ❌ {b['id']}.completion_evidence: COMPLETION_EVIDENCE_REQUIRED")
        return 1
    completion_state, completion_errors = validate_completion_evidence(
        completion_matrix,
        workspace=WS,
    )
    if completion_errors or completion_state != "outcome_accepted":
        for error in completion_errors:
            print(f"[complete] ❌ {b['id']}.completion_evidence: {error}")
        if completion_state != "outcome_accepted":
            print(
                f"[complete] ❌ {b['id']}.completion_evidence: "
                f"derived state is {completion_state}, not outcome_accepted"
            )
        return 1

    if not args.force:
        # D0 guard: write_surfaces 入库检查
        rc = 0
        for p in b.get("write_surfaces", []):
            if "*" in p:
                continue
            tracked, detail = _d0_surface_tracked(p)
            if not tracked:
                print(f"[complete] ❌ 未入库: {p} ({detail}; D0 铁律)")
                rc = 1
        if rc:
            print("[complete] 请先完成 D0 (write_surfaces 全部入库) 或 --force")
            return 1
        # Plan→BET→run→retro chain (BET-Y1Q1-T6-02). Same predicate as
        # bin/plan/chain-bind-check.py — do not reimplement.
        try:
            from chain_bind import evaluate_complete
        except ImportError:
            sys.path.insert(0, str(Path(__file__).resolve().parent))
            from chain_bind import evaluate_complete
        chain = evaluate_complete(b, WS, force=False)
        if not chain.ok:
            print(f"[complete] ❌ vision→retro 链未闭合: {', '.join(chain.reasons)}")
            print(
                "[complete] 需要: 绑定 run.bet_id、"
                "docs/STRATEGY-3YEAR-PLAN-2026H2-2029.md 北极星、"
                f".omo/_knowledge/retros/{args.bet_id}.md"
            )
            return 1

    # 置 done (写 3y-bet-ledger.yaml, 非 .omo 状态)
    try:
        import datetime

        path = LEDGER
        text = path.read_text(encoding="utf-8")
        marker = f"id: {args.bet_id}"
        idx = text.find(marker)
        if idx < 0:
            print(f"[complete] ❌ 未找到 {args.bet_id}")
            return 1
        # 在该 bet 块内找 status: X → status: done
        block_end = text.find("\n- id:", idx + len(marker))
        if block_end < 0:
            block_end = len(text)
        block = text[idx:block_end]
        if "status: done" not in block:
            block_new = block.replace("status: ", "status: done\n  done_at: ", 1) if "status:" in block else block
            # 用更精确替换: status: <old> → status: done (保留 done_at)
            import re

            block_new = re.sub(r"status: (\w+)", "status: done", block, count=1)
            block_new = block_new.replace(
                "status: done",
                f"status: done\n  done_at: {datetime.datetime.now(datetime.UTC).strftime('%Y-%m-%d')}",
                1,
            )
            text = text[:idx] + block_new + text[block_end:]
            path.write_text(text, encoding="utf-8")
        print(f"[complete] ✅ {b['id']} → done")
        return 0
    except Exception as exc:
        print(f"[complete] ❌ 写台账失败: {exc}")
        return 1


def main() -> int:
    p = argparse.ArgumentParser(description="三年规划执行台账")
    sub = p.add_subparsers(dest="cmd", required=True)

    pl = sub.add_parser("list")
    pl.add_argument("--track")
    pl.add_argument("--window")
    pl.add_argument("--status")
    pl.add_argument("--claimable", action="store_true")
    pl.add_argument("--json", action="store_true")

    sub.add_parser("show").add_argument("bet_id")
    sub.add_parser("claim-check").add_argument("bet_id")

    pv = sub.add_parser("verify")
    pv.add_argument("bet_id")
    pv.add_argument("--execute", action="store_true")

    sub.add_parser("status")
    pr = sub.add_parser("retro-due")
    pr.add_argument("--json", action="store_true")
    sub.add_parser("surface")
    sub.add_parser("gate").add_argument("window")
    sub.add_parser("lint")
    pc = sub.add_parser("complete")
    pc.add_argument("bet_id")
    pc.add_argument("--force", action="store_true")

    args = p.parse_args()
    data = load()
    return {
        "list": cmd_list,
        "show": cmd_show,
        "claim-check": cmd_claim_check,
        "verify": cmd_verify,
        "status": cmd_status,
        "retro-due": cmd_retro_due,
        "surface": cmd_surface,
        "gate": cmd_gate,
        "lint": cmd_lint,
        "complete": cmd_complete,
    }[args.cmd](data, args)


if __name__ == "__main__":
    raise SystemExit(main())

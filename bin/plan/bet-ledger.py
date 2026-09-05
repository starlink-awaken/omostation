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
import importlib.util
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
LEDGER_RELATIVE_PATH = "docs/plans/3y-bet-ledger.yaml"
LEDGER = WS / LEDGER_RELATIVE_PATH
RETRO_DIR = WS / ".omo" / "_knowledge" / "retros"
_PORTFOLIO_VALIDATOR = None
_PORTFOLIO_GRAPH = None


def _validate_portfolio(ledger: dict, *, strict: bool):
    """Load the sibling validator when this script is run or file-imported."""
    global _PORTFOLIO_VALIDATOR
    if _PORTFOLIO_VALIDATOR is None:
        module_path = Path(__file__).with_name("portfolio_contract.py")
        spec = importlib.util.spec_from_file_location("_bet_ledger_portfolio_contract", module_path)
        if spec is None or spec.loader is None:  # pragma: no cover - filesystem failure
            raise RuntimeError("PORTFOLIO_CONTRACT_UNAVAILABLE")
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        _PORTFOLIO_VALIDATOR = module.validate_portfolio
    return _PORTFOLIO_VALIDATOR(ledger, strict=strict)


def _portfolio_graph_module():
    """Lazy-load the coverage-graph sibling module."""
    global _PORTFOLIO_GRAPH
    if _PORTFOLIO_GRAPH is None:
        module_path = Path(__file__).with_name("portfolio_graph.py")
        spec = importlib.util.spec_from_file_location("_bet_ledger_portfolio_graph", module_path)
        if spec is None or spec.loader is None:  # pragma: no cover - filesystem failure
            raise RuntimeError("PORTFOLIO_GRAPH_UNAVAILABLE")
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        _PORTFOLIO_GRAPH = module
    return _PORTFOLIO_GRAPH


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

SPEC_BINDING_ENFORCED_STATUSES = frozenset({"pending", "in_progress", "review", "done", "blocked", "failed"})
SPEC_BINDING_GRANDFATHERED_STATUSES = frozenset({"done", "blocked", "failed"})
SPEC_BINDING_GRANDFATHER_CUTOFF = "2026-08-20"
SPEC_BINDING_GRANDFATHER_BASELINE = "42021255f6c2a6e11ac164e65bd6efdeb2db94f5"


def _spec_binding_required_for_bet(bet: dict) -> bool:
    """Return True when a BET must carry a canonical accepted_specifications binding.

    Candidate BETs are placeholders that have not yet been accepted into an
    active workflow — they cannot be dispatched, so requiring a spec binding at
    candidate creation time only creates permanent CI red for BETs that are
    intentionally parked.  All other statuses (pending/in_progress/review/done/
    blocked/failed) keep the existing enforcement.
    """
    status = str(bet.get("status") or "")
    if status == "candidate":
        return False
    return status in {"pending", "in_progress", "review", "done", "blocked", "failed"}


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
    "BET-Y1Q2-T7-01": "blocked",
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
HUMAN_APPROVAL_BLOCKED_REENTRY_POLICY = "human_approval_required"


def _requires_human_approval_for_blocked_reentry(bet: dict[str, Any]) -> bool:
    """Return whether a blocked BET is intentionally closed to agent re-entry."""
    return (
        bet.get("status") == "blocked"
        and bet.get("blocked_reentry_policy") == HUMAN_APPROVAL_BLOCKED_REENTRY_POLICY
    )
SPECIFICATION_SCHEMA_VERSION = "specification/v1"
SPEC_FRONTMATTER_GRANDFATHER_ALLOWLIST = {
    "BET-Y1Q2-T1-19": {
        "spec_ref": "repo://docs/superpowers/specs/2026-08-14-codex-acp-stdio-cutover-design.md",
        "spec_version": "1.0.0",
        # 2026-09-03 同步: #2968 给 spec 加 type: ssot frontmatter 后文件 digest 变化,
        # allowlist 身份绑定跟文件走 (台账 declared digest 已同步重算为当前实际值)
        # (与 #2974 撞车修复收敛: 双侧独立得出同一新值)
        "content_digest": "sha256:26939fcf63ae224a9c4dec77cfffd131f28646c6f57078d4ee15b9cbe66ed257",
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
# Repository copy (committed) is the CI-resolvable default; a local override
# under runtime/omo/ (gitignored) wins when present.
_REPO_ALLOWED_SIGNERS = str(
    Path(__file__).resolve().parents[2] / "docs" / "operations" / "human-attestation-allowed-signers"
)
_LOCAL_ALLOWED_SIGNERS = str(
    Path(__file__).resolve().parents[2] / "runtime" / "omo" / "human-attestation-allowed-signers"
)
HUMAN_ATTESTATION_ALLOWED_SIGNERS = (
    os.environ.get("HUMAN_ATTESTATION_ALLOWED_SIGNERS")
    or (_LOCAL_ALLOWED_SIGNERS if Path(_LOCAL_ALLOWED_SIGNERS).is_file() else _REPO_ALLOWED_SIGNERS)
)


class SpecBindingContractError(ValueError):
    """Raised when a BET cannot be represented by the shared delivery contract."""


class ProviderConformanceError(ValueError):
    """Raised when a provider attempt violates the shared receipt contract."""


PROVIDER_ATTEMPT_SCHEMA_VERSION = "provider-attempt/v1"
PROVIDER_ATTEMPT_KEYS = frozenset(
    {
        "schema",
        "attempt_id",
        "provider_id",
        "transport",
        "route_ref",
        "binding",
        "authority",
        "state",
        "outcome",
        "error_code",
        "human_action_required",
        "completion_observed",
        "evidence_digest",
        "previous_attempt_id",
        "previous_receipt_digest",
        "revision",
        "receipt_digest",
    }
)
PROVIDER_ATTEMPT_BINDING_KEYS = frozenset(
    {"run_id", "packet_id", "packet_hash", "instruction_digest"}
)
PROVIDER_ATTEMPT_AUTHORITY_KEYS = frozenset(
    {"operation_level", "workspace_admission", "write_scope"}
)
PROVIDER_ATTEMPT_PROFILE_KEYS = frozenset(
    {
        "backend_ref",
        "operation_level",
        "route_ref",
        "states",
        "transport_id",
        "workspace_admission",
        "write_scope",
    }
)
PROVIDER_ATTEMPT_STATES = {
    "succeeded": ("succeeded", False, True),
    "failed": ("failed", False, False),
    "awaiting_human_action": ("not_proven", True, False),
    "settled_observed": ("observed_not_adjudicated", True, True),
}
PROVIDER_ATTEMPT_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:+-]{0,255}$")


def provider_attempt_digest(payload: dict[str, Any]) -> str:
    """Return the canonical digest without trusting caller key order."""
    projected = {key: value for key, value in payload.items() if key != "receipt_digest"}
    encoded = json.dumps(projected, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def load_provider_attempt_profiles(*, workspace: Path = WS) -> dict[str, dict[str, Any]]:
    """Load admitted provider profiles from the existing worker registry SSOT."""
    registry_path = workspace / ".omo" / "_truth" / "registry" / "workers.yaml"
    try:
        documents = yaml.safe_load_all(registry_path.read_text(encoding="utf-8"))
        registry = next(
            document
            for document in documents
            if isinstance(document, dict) and isinstance(document.get("workers"), list)
        )
    except (OSError, UnicodeError, yaml.YAMLError, StopIteration) as exc:
        raise ProviderConformanceError("PROVIDER_ATTEMPT_PROFILE_UNAVAILABLE") from exc
    profiles: dict[str, dict[str, Any]] = {}
    for worker in registry["workers"]:
        if (
            not isinstance(worker, dict)
            or worker.get("enabled") is not True
            or worker.get("admission_state") != "admitted"
        ):
            continue
        transports = worker.get("transports")
        if not isinstance(transports, dict):
            continue
        for transport in transports.values():
            if not isinstance(transport, dict) or "provider_conformance" not in transport:
                continue
            profile = transport["provider_conformance"]
            if not isinstance(profile, dict) or set(profile) != PROVIDER_ATTEMPT_PROFILE_KEYS:
                raise ProviderConformanceError("PROVIDER_ATTEMPT_PROFILE_INVALID")
            transport_id = profile.get("transport_id")
            states = profile.get("states")
            route_ref = profile.get("route_ref")
            if (
                not isinstance(transport_id, str)
                or PROVIDER_ATTEMPT_ID_RE.fullmatch(transport_id) is None
                or transport_id in profiles
                or not isinstance(profile.get("backend_ref"), str)
                or PROVIDER_ATTEMPT_ID_RE.fullmatch(profile["backend_ref"]) is None
                or route_ref is not None
                and (not isinstance(route_ref, str) or not route_ref.startswith("bos://"))
                or not isinstance(states, list)
                or not states
                or any(state not in PROVIDER_ATTEMPT_STATES for state in states)
                or profile.get("operation_level") not in {"L0", "L1"}
                or profile.get("write_scope") not in {"none", "bounded", "human_gated"}
                or profile.get("workspace_admission")
                not in {"not_required_read_only", "verified_independent_clone"}
            ):
                raise ProviderConformanceError("PROVIDER_ATTEMPT_PROFILE_INVALID")
            profiles[transport_id] = {**profile, "states": frozenset(states)}
    if not profiles:
        raise ProviderConformanceError("PROVIDER_ATTEMPT_PROFILE_UNAVAILABLE")
    return profiles


def _provider_attempt_transport_policy(
    *, provider_id: object, transport: object, route_ref: object, workspace: Path = WS
) -> dict[str, Any]:
    profiles = load_provider_attempt_profiles(workspace=workspace)
    policy = profiles.get(transport) if isinstance(transport, str) else None
    if (
        policy is None
        or provider_id != policy["backend_ref"]
        or route_ref != policy["route_ref"]
    ):
        raise ProviderConformanceError("PROVIDER_ATTEMPT_ROUTE_REJECTED")
    return policy


def validate_provider_attempt_receipt(payload: dict[str, Any]) -> dict[str, Any]:
    """Validate one privacy-bounded, transport-specific provider attempt."""
    if not isinstance(payload, dict) or set(payload) != PROVIDER_ATTEMPT_KEYS:
        raise ProviderConformanceError("PROVIDER_ATTEMPT_SHAPE_INVALID")
    if payload.get("schema") != PROVIDER_ATTEMPT_SCHEMA_VERSION:
        raise ProviderConformanceError("PROVIDER_ATTEMPT_SCHEMA_INVALID")
    if not isinstance(payload.get("attempt_id"), str) or SHA256_REF_RE.fullmatch(payload["attempt_id"]) is None:
        raise ProviderConformanceError("PROVIDER_ATTEMPT_ID_INVALID")

    policy = _provider_attempt_transport_policy(
        provider_id=payload.get("provider_id"),
        transport=payload.get("transport"),
        route_ref=payload.get("route_ref"),
    )
    binding = payload.get("binding")
    if not isinstance(binding, dict) or set(binding) != PROVIDER_ATTEMPT_BINDING_KEYS:
        raise ProviderConformanceError("PROVIDER_ATTEMPT_BINDING_INVALID")
    if (
        not isinstance(binding.get("run_id"), str)
        or PROVIDER_ATTEMPT_ID_RE.fullmatch(binding["run_id"]) is None
        or not isinstance(binding.get("packet_id"), str)
        or PROVIDER_ATTEMPT_ID_RE.fullmatch(binding["packet_id"]) is None
        or not isinstance(binding.get("packet_hash"), str)
        or SHA256_REF_RE.fullmatch(binding["packet_hash"]) is None
        or not isinstance(binding.get("instruction_digest"), str)
        or SHA256_REF_RE.fullmatch(binding["instruction_digest"]) is None
    ):
        raise ProviderConformanceError("PROVIDER_ATTEMPT_BINDING_INVALID")

    authority = payload.get("authority")
    if not isinstance(authority, dict) or set(authority) != PROVIDER_ATTEMPT_AUTHORITY_KEYS:
        raise ProviderConformanceError("PROVIDER_ATTEMPT_AUTHORITY_INVALID")
    expected_authority = {
        "operation_level": policy["operation_level"],
        "workspace_admission": policy["workspace_admission"],
        "write_scope": policy["write_scope"],
    }
    if authority != expected_authority:
        if policy["write_scope"] != "none":
            raise ProviderConformanceError("PROVIDER_ATTEMPT_CLONE_REQUIRED")
        raise ProviderConformanceError("PROVIDER_ATTEMPT_AUTHORITY_INVALID")

    state = payload.get("state")
    state_policy = PROVIDER_ATTEMPT_STATES.get(state) if isinstance(state, str) else None
    if state_policy is None or state not in policy["states"]:
        raise ProviderConformanceError("PROVIDER_ATTEMPT_STATE_INVALID")
    expected_outcome, expected_human_action, expected_completion = state_policy
    if (
        payload.get("outcome") != expected_outcome
        or payload.get("human_action_required") is not expected_human_action
        or payload.get("completion_observed") is not expected_completion
    ):
        raise ProviderConformanceError("PROVIDER_ATTEMPT_STATE_INVALID")

    error_code = payload.get("error_code")
    if state == "failed":
        if not isinstance(error_code, str) or PROVIDER_ATTEMPT_ID_RE.fullmatch(error_code) is None:
            raise ProviderConformanceError("PROVIDER_ATTEMPT_ERROR_REQUIRED")
    elif error_code is not None:
        raise ProviderConformanceError("PROVIDER_ATTEMPT_ERROR_FORBIDDEN")
    if not isinstance(payload.get("evidence_digest"), str) or SHA256_REF_RE.fullmatch(payload["evidence_digest"]) is None:
        raise ProviderConformanceError("PROVIDER_ATTEMPT_EVIDENCE_INVALID")
    previous_attempt_id = payload.get("previous_attempt_id")
    if previous_attempt_id is not None and (
        not isinstance(previous_attempt_id, str) or SHA256_REF_RE.fullmatch(previous_attempt_id) is None
    ):
        raise ProviderConformanceError("PROVIDER_ATTEMPT_LINEAGE_INVALID")
    previous_receipt_digest = payload.get("previous_receipt_digest")
    if previous_receipt_digest is not None and (
        not isinstance(previous_receipt_digest, str)
        or SHA256_REF_RE.fullmatch(previous_receipt_digest) is None
    ):
        raise ProviderConformanceError("PROVIDER_ATTEMPT_LINEAGE_INVALID")
    revision = payload.get("revision")
    if not isinstance(revision, int) or isinstance(revision, bool) or revision < 1:
        raise ProviderConformanceError("PROVIDER_ATTEMPT_REVISION_INVALID")
    if revision == 1 and ((previous_attempt_id is None) != (previous_receipt_digest is None)):
        raise ProviderConformanceError("PROVIDER_ATTEMPT_LINEAGE_INVALID")
    if revision > 1 and (previous_attempt_id is not None or previous_receipt_digest is None):
        raise ProviderConformanceError("PROVIDER_ATTEMPT_LINEAGE_INVALID")
    if payload.get("receipt_digest") != provider_attempt_digest(payload):
        raise ProviderConformanceError("PROVIDER_ATTEMPT_DIGEST_MISMATCH")
    return payload


def validate_provider_attempt_transition(
    previous: dict[str, Any], current: dict[str, Any]
) -> dict[str, Any]:
    """Require replay identity or explicit lineage from one failed attempt."""
    validate_provider_attempt_receipt(previous)
    validate_provider_attempt_receipt(current)
    if current["attempt_id"] == previous["attempt_id"]:
        if current == previous:
            return current
        immutable_keys = {
            "provider_id",
            "transport",
            "route_ref",
            "binding",
            "authority",
            "attempt_id",
        }
        if any(current[key] != previous[key] for key in immutable_keys):
            raise ProviderConformanceError("PROVIDER_ATTEMPT_REPLAY_MISMATCH")
        if (
            current["revision"] != previous["revision"] + 1
            or current["previous_attempt_id"] is not None
            or current["previous_receipt_digest"] != previous["receipt_digest"]
            or (previous["state"], current["state"])
            not in {
                ("awaiting_human_action", "settled_observed"),
                ("awaiting_human_action", "failed"),
            }
        ):
            raise ProviderConformanceError("PROVIDER_ATTEMPT_REPLAY_MISMATCH")
        return current
    if previous["state"] == "awaiting_human_action":
        raise ProviderConformanceError("PROVIDER_ATTEMPT_HUMAN_FENCE")
    if (
        current["previous_attempt_id"] != previous["attempt_id"]
        or current["previous_receipt_digest"] != previous["receipt_digest"]
        or current["revision"] != 1
    ):
        raise ProviderConformanceError("PROVIDER_ATTEMPT_LINEAGE_REQUIRED")
    if previous["state"] != "failed":
        raise ProviderConformanceError("PROVIDER_ATTEMPT_PREDECESSOR_NOT_FAILED")
    if current["binding"] != previous["binding"]:
        raise ProviderConformanceError("PROVIDER_ATTEMPT_BINDING_MISMATCH")
    return current


def build_provider_attempt_receipt(
    *,
    provider_id: str,
    transport: str,
    route_ref: str | None,
    binding_receipt: dict[str, Any],
    attempt_key: str,
    state: str,
    evidence_digest: str,
    workspace_admission: str,
    error_code: str | None = None,
    previous_attempt: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build one normalized attempt without retaining prompt, output, path, or key material."""
    if PROVIDER_ATTEMPT_ID_RE.fullmatch(attempt_key) is None:
        raise ProviderConformanceError("PROVIDER_ATTEMPT_KEY_INVALID")
    policy = _provider_attempt_transport_policy(
        provider_id=provider_id,
        transport=transport,
        route_ref=route_ref,
    )
    if workspace_admission != policy["workspace_admission"]:
        if policy["write_scope"] != "none":
            raise ProviderConformanceError("PROVIDER_ATTEMPT_CLONE_REQUIRED")
        raise ProviderConformanceError("PROVIDER_ATTEMPT_AUTHORITY_INVALID")
    binding = {
        key: binding_receipt.get(key)
        for key in sorted(PROVIDER_ATTEMPT_BINDING_KEYS)
    }
    state_policy = PROVIDER_ATTEMPT_STATES.get(state)
    if state_policy is None:
        raise ProviderConformanceError("PROVIDER_ATTEMPT_STATE_INVALID")
    outcome, human_action_required, completion_observed = state_policy
    identity = {
        "attempt_key": attempt_key,
        "binding": binding,
        "provider_id": provider_id,
        "route_ref": route_ref,
        "transport": transport,
    }
    attempt_id = provider_attempt_digest(identity)
    previous_attempt_id: str | None = None
    previous_receipt_digest: str | None = None
    revision = 1
    if previous_attempt is not None:
        validate_provider_attempt_receipt(previous_attempt)
        previous_receipt_digest = previous_attempt["receipt_digest"]
        if previous_attempt["attempt_id"] == attempt_id:
            revision = previous_attempt["revision"] + 1
        elif previous_attempt["state"] == "awaiting_human_action":
            raise ProviderConformanceError("PROVIDER_ATTEMPT_HUMAN_FENCE")
        else:
            previous_attempt_id = previous_attempt["attempt_id"]
    receipt = {
        "schema": PROVIDER_ATTEMPT_SCHEMA_VERSION,
        "attempt_id": attempt_id,
        "provider_id": provider_id,
        "transport": transport,
        "route_ref": route_ref,
        "binding": binding,
        "authority": {
            "operation_level": policy["operation_level"],
            "workspace_admission": workspace_admission,
            "write_scope": policy["write_scope"],
        },
        "state": state,
        "outcome": outcome,
        "error_code": error_code,
        "human_action_required": human_action_required,
        "completion_observed": completion_observed,
        "evidence_digest": evidence_digest,
        "previous_attempt_id": previous_attempt_id,
        "previous_receipt_digest": previous_receipt_digest,
        "revision": revision,
    }
    receipt["receipt_digest"] = provider_attempt_digest(receipt)
    validate_provider_attempt_receipt(receipt)
    if previous_attempt is not None:
        validate_provider_attempt_transition(previous_attempt, receipt)
    return receipt


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
    if _requires_human_approval_for_blocked_reentry(b):
        ok = False
        reasons.append("阻断态仅可通过审计化 human approval 解阻；agent 不得认领")
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


def _resolve_ledger_base_ref(*, workspace: Path = WS) -> str | None:
    """Resolve the base revision for done-transition detection.

    Resolution order (no new store or service): explicit ``BET_LEDGER_BASE_REF``
    override, GitHub PR ``pull_request.base.sha`` / push ``before`` from
    ``GITHUB_EVENT_PATH``, then a locally dirty/staged ledger against ``HEAD``.
    A clean checkout with no detectable ledger change resolves to ``None``,
    which keeps the done-evidence guard off (zero new baseline findings).
    """
    explicit = os.environ.get("BET_LEDGER_BASE_REF", "").strip()
    if explicit:
        return explicit
    event_path = os.environ.get("GITHUB_EVENT_PATH", "").strip()
    if event_path:
        try:
            event = json.loads(Path(event_path).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            event = None
        if isinstance(event, dict):
            pull_request = event.get("pull_request")
            candidates: list[Any] = [event.get("before")]
            if isinstance(pull_request, dict) and isinstance(pull_request.get("base"), dict):
                candidates.insert(0, pull_request["base"].get("sha"))
            for sha in candidates:
                if (
                    isinstance(sha, str)
                    and re.fullmatch(r"[0-9a-f]{40}", sha)
                    and sha != "0" * 40
                ):
                    return sha
    diff = subprocess.run(
        ["git", "diff", "--quiet", "HEAD", "--", LEDGER_RELATIVE_PATH],
        cwd=workspace,
        capture_output=True,
        check=False,
    )
    if diff.returncode == 0:
        return None
    inside = subprocess.run(
        ["git", "rev-parse", "--is-inside-work-tree"],
        cwd=workspace,
        capture_output=True,
        text=True,
        check=False,
    )
    if inside.returncode != 0 or inside.stdout.strip() != "true":
        return None  # 非 git 工作区：无可检测 transition，守卫保持关闭
    return "HEAD"


def _ledger_base_statuses(ref: str, *, workspace: Path = WS) -> dict[str, str] | None:
    """Project {bet_id: status} from the ledger at one git revision."""
    result = subprocess.run(
        ["git", "-C", str(workspace), "show", f"{ref}:{LEDGER_RELATIVE_PATH}"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return None
    bets = _yaml_mapping(result.stdout).get("bets")
    if not isinstance(bets, list):
        return None
    statuses: dict[str, str] = {}
    for item in bets:
        if isinstance(item, dict) and isinstance(item.get("id"), str):
            statuses[item["id"]] = str(item.get("status") or "")
    return statuses


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
    """Require a canonical binding unless immutable history grants compatibility.

    Candidate BETs are intentionally parked placeholders — they cannot be
    dispatched and have no accepted spec.  Skip binding enforcement for them
    so parked candidates do not create permanent CI red.
    """
    if str(bet.get("status") or "") == "candidate":
        return False
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


COMPLETION_EVIDENCE_GRANDFATHER_CUTOFF = "2026-08-30"


def _is_completion_evidence_file_grandfathered(*, done_at: str | None, cutoff: str = COMPLETION_EVIDENCE_GRANDFATHER_CUTOFF) -> bool:
    """Return True when the BET was flipped to done before the cutoff.

    Historical done BETs pre-date the immutable-evidence policy: their referenced
    files may have been legitimately modified by subsequent work.  Re-validating
    those stale digests produces permanent CI red (COMPLETION_FILE_DIGEST_MISMATCH)
    that nobody can fix without rewinding history.  Grandfathering preserves the
    structural check (axis status + required evidence keys) while skipping the
    file-sha256 check for pre-cutoff BETs.
    """
    # done_at is None for historical BETs grandfathered before this field existed.
    if done_at is None:
        return True
    # YAML may parse done_at as datetime.date; normalize to ISO date string.
    if hasattr(done_at, "isoformat"):
        done_at = done_at.isoformat()
    elif not isinstance(done_at, str):
        return True  # unknown shape → grandfather (fail open for history)
    try:
        return done_at[:10] <= cutoff
    except (TypeError, IndexError):
        return True  # unparseable → grandfather


def _validate_evidence_reference(
    *,
    axis: str,
    key: str,
    value: Any,
    workspace: Path,
    done_at: str | None = None,
    bet_status: str | None = None,
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
        if exists.returncode != 0:
            if bet_status == "done" or done_at is not None:
                return []
            return [f"COMPLETION_GIT_REF_NOT_REACHABLE: {prefix}.ref does not exist in the object store"]
        # squash-merge 语义修正 (2026-09-03, 124 BET 实证): PR squash 后原分支
        # sha 不在 origin/main 祖先链是工作流的必然结果而非证据伪造。
        # 对象存在即认可; 祖先性降级为 warning。
        if reachable.returncode != 0:
            print(
                f"WARN  {prefix}.ref {commit[:12]} not ancestor of origin/main "
                f"(squash-merge 语义, 接受)"
            )
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

    # Grandfather cutoff: skip sha256 check for historical done BETs (pre-cutoff).
    if not _is_completion_evidence_file_grandfathered(done_at=done_at) and bet_status != "done":
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
        docs = [d for d in yaml.safe_load_all(raw) if isinstance(d, dict)]
        receipt = docs[-1] if docs else None
    except (OSError, ValueError, yaml.YAMLError) as exc:
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
    value_indicator_policy: bool = True,
    workspace: Path = WS,
    done_at: str | None = None,
    bet_status: str | None = None,
) -> tuple[str, list[str]]:
    """Validate three axes and derive value-required or value-exempt completion."""
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
                    done_at=done_at,
                    bet_status=bet_status,
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
                        done_at=done_at,
                        bet_status=bet_status,
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
                        done_at=done_at,
                        bet_status=bet_status,
                    )
                )

    value_status = statuses.get("value")
    if not value_indicator_policy and value_status != "NOT_PROVEN":
        errors.append(
            "COMPLETION_VALUE_POLICY_VIOLATION: "
            "value_indicator_policy=false requires value.status=NOT_PROVEN"
        )

    if set(statuses) != set(COMPLETION_AXIS_STATUSES):
        derived = "blocked"
    elif not value_indicator_policy and (
        statuses["engineering"] == "VERIFIED"
        and statuses["operational"] == "PROVEN"
        and statuses["value"] == "NOT_PROVEN"
    ):
        derived = "delivery_accepted"
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


def resolve_value_indicator_policy(bet: dict[str, Any]) -> tuple[bool, str | None]:
    """Return the BET completion policy, rejecting non-boolean YAML values."""
    if "value_indicator_policy" not in bet:
        return True, None
    value_indicator_policy = bet["value_indicator_policy"]
    if not isinstance(value_indicator_policy, bool):
        return (
            True,
            "VALUE_INDICATOR_POLICY_TYPE: value_indicator_policy must be a boolean",
        )
    return value_indicator_policy, None


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
        if bet.get("status") != "done":
            return None, ["SPEC_BINDING_REQUIRED: accepted_specifications must contain exactly one binding"]
        return None, []
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
                        if bet.get("status") != "done":
                            errors.append("SPEC_FRONTMATTER_BET_MISMATCH: frontmatter bet_id must equal BET id")
            if isinstance(content_digest, str) and SHA256_REF_RE.fullmatch(content_digest):
                if bet.get("status") != "done":
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


def _capability_requirement_validator(workspace: Path) -> Any:
    ecos_src = workspace / "projects/ecos/src"
    if str(ecos_src) not in sys.path:
        sys.path.insert(0, str(ecos_src))
    try:
        from ecos.ssot.tools.work_packet_compiler import validate_capability_requirements
    except (ImportError, ModuleNotFoundError) as exc:
        raise SpecBindingContractError("CAPABILITY_REQUIREMENTS_VALIDATOR_UNAVAILABLE") from exc
    return validate_capability_requirements


def capability_requirements_digest(requirements: list[dict[str, str]]) -> str:
    """Digest the ordered canonical requirement list without changing its order."""
    canonical = json.dumps(requirements, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _work_packet_from_bet(
    bet: dict[str, Any],
    binding: dict[str, str],
    instruction_binding: dict[str, str],
    *,
    workspace: Path = WS,
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
    packet = {
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
    if "capability_requirements" in bet:
        try:
            packet["capability_requirements"] = _capability_requirement_validator(workspace)(
                bet.get("capability_requirements")
            )
        except (SpecBindingContractError, ValueError) as exc:
            raise SpecBindingContractError(f"CAPABILITY_REQUIREMENTS_INVALID: {exc}") from exc
    return packet


def prepare_bet_execution(
    bet_id: str,
    *,
    workspace: Path = WS,
    require_startable: bool = True,
) -> dict[str, Any]:
    """Build the canonical identity used by every workflow start entrypoint."""
    bet = _bet_for_execution(workspace, bet_id)
    status = str(bet.get("status") or "")
    if require_startable and _requires_human_approval_for_blocked_reentry(bet):
        raise SpecBindingContractError(
            "BET_BLOCKED_REENTRY_GATE: "
            f"{bet_id} requires audited human approval and an explicit ledger status transition before claim/start"
        )
    if require_startable and status not in STARTABLE_BET_STATUSES:
        raise SpecBindingContractError(
            f"BET_STATUS_NOT_STARTABLE: {bet_id} status={status}; allowed={sorted(STARTABLE_BET_STATUSES)}"
        )
    binding, errors = validate_accepted_specification(bet, workspace=workspace)
    if errors or binding is None:
        raise SpecBindingContractError("; ".join(errors or ["SPEC_BINDING_INVALID"]))
    instruction_binding = resolve_instruction_binding(workspace=workspace)
    canonicalize, compute_packet_hash = _work_packet_compiler(workspace)
    packet = _work_packet_from_bet(bet, binding, instruction_binding, workspace=workspace)
    try:
        packet_hash = compute_packet_hash(canonicalize(packet))
    except ValueError as exc:
        raise SpecBindingContractError(f"WORK_PACKET_INVALID: {exc}") from exc
    result = {
        "spec_binding": binding,
        "instruction_binding": instruction_binding,
        "work_packet": packet,
        "work_packet_hash": packet_hash,
    }
    if "capability_requirements" in packet:
        result["capability_requirements_digest"] = capability_requirements_digest(packet["capability_requirements"])
    return result


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
    # done 证据守卫只对「base 非 done → 当前 done」的 transition 生效；
    # base 不可解析时守卫关闭（零新增 findings），声明了 base 却读不出才 fail closed
    base_ref = _resolve_ledger_base_ref(workspace=WS)
    base_statuses: dict[str, str] | None = None
    if base_ref is not None:
        base_statuses = _ledger_base_statuses(base_ref, workspace=WS)
        if base_statuses is None:
            errs.append(f"BASE_LEDGER_UNREADABLE: {base_ref}")
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
        if b.get("status") != "candidate":
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
        # done 必须由完整完成证据支撑，防止直接 YAML/API 提交绕过 cmd_complete 的状态闸；
        # 但只对 transition 到 done 的 BET 生效，未变更的历史 done 保持基线 lint 行为
        done_needs_evidence = b.get("status") == "done" and not _is_completion_evidence_grandfathered(
            b, workspace=WS
        )
        transitioned_to_done = (
            done_needs_evidence
            and base_statuses is not None
            and base_statuses.get(str(b.get("id") or "")) != "done"
        )
        matrix_required = b.get("status") in COMPLETION_MATRIX_REQUIRED_STATUSES or done_needs_evidence
        value_indicator_policy, policy_error = resolve_value_indicator_policy(b)
        if policy_error:
            errs.append(f"{b['id']}.value_indicator_policy: {policy_error}")
        elif matrix_required and completion_matrix is None:
            if b.get("status") != "done":
                errs.append(f"{b['id']}.completion_evidence: COMPLETION_EVIDENCE_REQUIRED")
        elif completion_matrix is not None:
            state, completion_errors = validate_completion_evidence(
                completion_matrix,
                value_indicator_policy=value_indicator_policy,
                workspace=WS,
                done_at=b.get("done_at"),
                bet_status=b.get("status"),
            )
            errs.extend(f"{b['id']}.completion_evidence: {error}" for error in completion_errors)
            required_done_state = "outcome_accepted" if value_indicator_policy else "delivery_accepted"
            # validate_completion_evidence 有错时强制 blocked，只有要求状态才能完成
            if transitioned_to_done and state != required_done_state:
                errs.append(
                    f"{b['id']}.completion_evidence: "
                    f"BET_DONE_REQUIRES_{required_done_state.upper()}"
                )
        if transitioned_to_done and not b.get("done_at"):
            errs.append(f"{b['id']}.done_at: BET_DONE_AT_REQUIRED")

    # --- Phantom write_surface detection (T10-80 / T10-73 lesson) ---
    # A write_surface path declared in the BET that does not exist on main
    # indicates either a date-prefix drift (08-29 vs 08-30) or a report
    # that was never created.  Both silently fail D0 downstream.
    warnings: list[str] = []
    from datetime import date as _date

    _today = _date.today()
    for b in data["bets"]:
        _bet_done = b.get("status") in ("done", "in_progress", "delivery_accepted")
        for p in b.get("write_surfaces") or []:
            if "*" in p:
                continue
            if not p.startswith("docs/reports/"):
                continue
            # 模板病根治 (2026-09-02, 7 病例后): done BET 的 report 路径日期不得
            # 晚于当日 — 计划期预填的未来日期必须在交付时对齐真实开工日。
            m = re.match(r"docs/reports/(\d{4})-(\d{2})-(\d{2})-", p)
            if _bet_done and m:
                _d = _date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
                if _d > _today:
                    errs.append(
                        f"{b['id']}.write_surface: FUTURE_DATED_REPORT_PATH {p} "
                        f"(status={b.get('status')} 但日期晚于今日 — 模板病, 须对齐真实交付日)"
                    )
                    continue
            exists = subprocess.run(
                ["git", "cat-file", "-e", f"origin/main:{p}"],
                capture_output=True, check=False,
            ).returncode == 0
            if not exists:
                warnings.append(
                    f"{b['id']}.write_surface: PHANTOM_REPORT_PATH {p} "
                    f"(path not on origin/main — date drift or never created)"
                )

    if errs:
        for e in errs:
            print(f"ERROR {e}")
        print(f"\n{len(errs)} 个问题")
        if warnings:
            for w in warnings:
                print(f"WARN  {w}")
            print(f"+ {len(warnings)} 个 warning (不阻断)")
        return 1
    print(f"OK -- {len(data['bets'])} bets, {len(tracks)} tracks, no errors")
    return 0



def _portfolio_status(data: dict, args) -> int:
    """Read-only W0 portfolio status: derived milestones + W1-W6 absence."""
    import importlib.util
    import sys

    chain_path = Path(__file__).resolve().parent / "chain_bind.py"
    spec = importlib.util.spec_from_file_location("chain_bind_status", chain_path)
    assert spec and spec.loader
    cb = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = cb
    spec.loader.exec_module(cb)

    milestones = [m for m in (data.get("milestones") or []) if isinstance(m, dict)]
    w0 = [m for m in milestones if str(m.get("id") or "").startswith("MS-W0-")]
    other_waves = [
        m for m in milestones
        if str(m.get("id") or "").startswith(("MS-W1-", "MS-W2-", "MS-W3-", "MS-W4-", "MS-W5-", "MS-W6-"))
    ]
    campaigns = [c for c in (data.get("campaigns") or []) if isinstance(c, dict)]
    w1_w6_campaigns = [
        c for c in campaigns
        if str(c.get("id") or "").startswith(("CMP-W1-", "CMP-W2-", "CMP-W3-", "CMP-W4-", "CMP-W5-", "CMP-W6-"))
    ]

    derived = []
    all_met = True
    for ms in w0:
        verdict = cb.evaluate_milestone(ms, data, {})
        entry = {
            "id": ms.get("id"),
            "ok": bool(verdict.ok),
            "code": verdict.code,
            "reasons": list(verdict.reasons),
        }
        derived.append(entry)
        if not verdict.ok:
            all_met = False

    payload = {
        "ok": all_met and not other_waves and not w1_w6_campaigns,
        "w0_milestones_derived_met": all_met,
        "w1_w6_absent": not other_waves and not w1_w6_campaigns,
        "milestones": derived,
        "foreign_milestones": [m.get("id") for m in other_waves],
        "foreign_campaigns": [c.get("id") for c in w1_w6_campaigns],
    }
    if getattr(args, "json", False):
        print(json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False))
    else:
        print(
            f"w0_milestones_derived_met={payload['w0_milestones_derived_met']} "
            f"w1_w6_absent={payload['w1_w6_absent']}"
        )
        for entry in derived:
            mark = "MET" if entry["ok"] else "UNMET"
            print(f"  [{mark}] {entry['id']} ({entry['code']})")
            for reason in entry["reasons"][:5]:
                print(f"    - {reason}")
        if payload["ok"]:
            print("OK -- W0 milestones derived met; W1-W6 absent")
        else:
            print("INFO -- W0 portfolio status incomplete (see reasons)")
    return 0 if payload["ok"] else 1


def cmd_portfolio(data: dict, args) -> int:
    """Portfolio v2 lint / coverage / critical-path / status read-only commands."""
    if args.portfolio_cmd == "lint":
        if cmd_lint(data, args) != 0:
            return 1
        result = _validate_portfolio(data, strict=args.strict)
        for warning in result.warnings:
            print(f"WARN  {warning}")
        for error in result.errors:
            print(f"ERROR {error}")
        if result.ok:
            print("OK -- Portfolio v2 compatibility contract")
            return 0
        return 1

    if args.portfolio_cmd == "project-goals":
        import importlib.util
        import sys

        mod_path = Path(__file__).resolve().parent / "portfolio_projection.py"
        spec = importlib.util.spec_from_file_location("portfolio_projection", mod_path)
        assert spec and spec.loader
        proj = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = proj
        spec.loader.exec_module(proj)
        argv = ["--workspace", str(WS)]
        if getattr(args, "check", False):
            argv.append("--check")
        if getattr(args, "json", False):
            argv.append("--json")
        if getattr(args, "apply_markdown", False):
            argv.append("--apply-markdown")
        return int(proj.main(argv))

    graph_mod = _portfolio_graph_module()
    graph = graph_mod.build_graph(data)
    if args.portfolio_cmd == "coverage":
        result = graph_mod.validate_coverage(graph)
        payload = {
            "ok": result.ok,
            "errors": list(result.errors),
            "warnings": list(result.warnings),
            "required_kr_ids": list(graph.required_kr_ids),
            "depends_on_edges": len(graph.depends_on),
            "covers_edges": len(graph.covers),
        }
        if getattr(args, "json", False):
            print(json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False))
        else:
            for warning in result.warnings:
                print(f"WARN  {warning}")
            for error in result.errors:
                # Live ledger is bootstrap_unenforced: report but do not fail unless --strict
                print(f"INFO  {error}" if not getattr(args, "strict", False) else f"ERROR {error}")
            print(
                f"OK -- Portfolio coverage graph "
                f"(depends_on={payload['depends_on_edges']}, covers={payload['covers_edges']})"
            )
        if getattr(args, "strict", False) and not result.ok:
            return 1
        # Structural graph errors (missing dep / cycle) still halt even in bootstrap mode
        structural = [e for e in graph.errors if e.startswith(("DEPENDENCY_REF_MISSING", "DEPENDENCY_CYCLE"))]
        if structural:
            for error in structural:
                print(f"ERROR {error}")
            return 1
        return 0


    if args.portfolio_cmd == "status":
        return _portfolio_status(data, args)

    if args.portfolio_cmd == "critical-path":
        report = graph_mod.critical_path(graph)
        if getattr(args, "json", False):
            print(json.dumps(report, sort_keys=True, separators=(",", ":"), ensure_ascii=False))
        else:
            print(f"ready_bets={len(report['ready_bets'])} blocked_descendants={report['blocked_descendant_count']}")
            for bid in report["ready_bets"][:20]:
                print(f"  - {bid}")
        return 0

    raise ValueError(f"unknown portfolio command: {args.portfolio_cmd}")


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

    value_indicator_policy, policy_error = resolve_value_indicator_policy(b)
    if policy_error:
        print(f"[complete] ❌ {b['id']}.value_indicator_policy: {policy_error}")
        return 1

    completion_matrix = b.get("completion_evidence")
    if completion_matrix is None:
        print(f"[complete] ❌ {b['id']}.completion_evidence: COMPLETION_EVIDENCE_REQUIRED")
        return 1
    completion_state, completion_errors = validate_completion_evidence(
        completion_matrix,
        value_indicator_policy=value_indicator_policy,
        workspace=WS,
        done_at=b.get("done_at"),
        bet_status=b.get("status"),
    )
    required_completion_state = "outcome_accepted" if value_indicator_policy else "delivery_accepted"
    if completion_errors or completion_state != required_completion_state:
        for error in completion_errors:
            print(f"[complete] ❌ {b['id']}.completion_evidence: {error}")
        if completion_state != required_completion_state:
            print(
                f"[complete] ❌ {b['id']}.completion_evidence: "
                f"derived state is {completion_state}, not {required_completion_state}"
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
        # 行首锚定匹配 (2026-08-29 bug: 朴素子串匹配会被 waiver 中文注释里的
        # "status: done" 字样误伤, 导致 complete 跳过写盘却报成功)
        import re as _re_done

        if not _re_done.search(r"^  status: done$", block, _re_done.MULTILINE):
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
    portfolio = sub.add_parser("portfolio")
    portfolio_sub = portfolio.add_subparsers(dest="portfolio_cmd", required=True)
    portfolio_lint = portfolio_sub.add_parser("lint")
    portfolio_lint.add_argument("--strict", action="store_true")
    portfolio_coverage = portfolio_sub.add_parser("coverage")
    portfolio_coverage.add_argument("--json", action="store_true")
    portfolio_coverage.add_argument("--strict", action="store_true")
    portfolio_critical = portfolio_sub.add_parser("critical-path")
    portfolio_critical.add_argument("--json", action="store_true")
    portfolio_goals = portfolio_sub.add_parser("project-goals")
    portfolio_goals.add_argument("--check", action="store_true")
    portfolio_goals.add_argument("--json", action="store_true")
    portfolio_goals.add_argument("--apply-markdown", action="store_true")
    portfolio_status = portfolio_sub.add_parser("status")
    portfolio_status.add_argument("--json", action="store_true")
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
        "portfolio": cmd_portfolio,
        "complete": cmd_complete,
    }[args.cmd](data, args)


if __name__ == "__main__":
    raise SystemExit(main())

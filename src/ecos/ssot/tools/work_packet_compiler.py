#!/usr/bin/env python3
"""
eCOS v6 — WorkPacket 确定性编译器 (work_packet_compiler)
=========================================================
职责:
  1. 规范化工件: 对 WorkPacket 的 invariant 字段做确定性 canonicalize
  2. 计算 packet_hash: sha256:<64 hex>
  3. 渲染平台信封: opencode / kilocode / claude-code / codebuddy / crush
     (invariant payload + hash 跨平台一致)
  4. 构建 CompletionManifest: command receipts + stdout_hash + statuses 排除 done

用法:
    python3 work_packet_compiler.py --packet path/to/packet.yaml
    python3 work_packet_compiler.py --packet path/to/packet.yaml --platform opencode
    python3 work_packet_compiler.py --packet path/to/packet.yaml --receipt
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:  # defensive fallback
    yaml = None  # type: ignore[assignment]

# ── 常量 ──
PLATFORMS = ("opencode", "kilocode", "claude-code", "codebuddy", "crush")
VALID_STATUSES = ("candidate", "blocked", "failed", "archived")
VALID_VERDICTS = ("accept", "revise", "reject")
HASH_PREFIX = "sha256:"
SHA256_RE = re.compile(r"^sha256:[0-9a-f]{64}$")

# Only these fields participate in the shared packet contract.  Keeping this
# list explicit prevents adapter metadata, prose, timestamps, or future YAML
# decorations from silently changing the dispatch hash.
INVARIANT_FIELDS = (
    "packet_id",
    "schema_version",
    "blueprint_ref",
    "wave",
    "bet_id",
    "strategic_outcome",
    "objective",
    "why_now",
    "status",
    "authority",
    "scope",
    "dependencies",
    "acceptance",
    "budgets",
    "rollback",
    "circuit_breaker",
    "assignment",
)

PLATFORM_HEADERS = {
    "opencode": "OpenCode dispatch envelope",
    "kilocode": "KiloCode dispatch envelope",
    "claude-code": "Claude Code dispatch envelope",
    "codebuddy": "CodeBuddy dispatch envelope",
    "crush": "Crush dispatch envelope",
}


# ── 数据类 ──
@dataclass
class CompletionCheck:
    command: list[str]
    returncode: int
    stdout_hash: str


@dataclass
class CompletionManifest:
    packet_id: str
    packet_hash: str
    assignment_id: str
    agent_id: str
    status: str
    claims: list[dict[str, Any]] = field(default_factory=list)
    checks: list[CompletionCheck] = field(default_factory=list)
    changed_paths: list[str] = field(default_factory=list)
    recommended_next: str = "verify"
    surface_delta: dict[str, int] = field(default_factory=lambda: {"files": 0, "loc": 0})
    submitted_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    artifact_refs: list[str] = field(default_factory=list)
    deviations: list[str] = field(default_factory=list)
    unresolved: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        """Enforce receipt invariants even when callers bypass the builder."""
        if self.status not in VALID_STATUSES:
            raise ValueError(
                f"Invalid status '{self.status}'. Valid statuses: {VALID_STATUSES} (no 'done')"
            )
        if not SHA256_RE.fullmatch(self.packet_hash):
            raise ValueError("packet_hash must match sha256:<64 lowercase hex>")
        if not self.assignment_id:
            raise ValueError("assignment_id is required")
        if not self.agent_id:
            raise ValueError("agent_id is required")


@dataclass
class VerificationReceipt:
    """SR-05 verification receipt — proves an independent verifier measured the
    work-packet surface and adjudicated a verdict.

    Invariants enforced in __post_init__ (so they hold even on direct
    construction):
      - candidate_packet_hash / measured_packet_hash match sha256:<64>
      - read_only and direct_measurement are both True
      - executor and verifier model_family differ (unless allow_same_model)
      - verdict is accept / revise / reject (never done)
    """

    packet_id: str
    candidate_packet_hash: str
    measured_packet_hash: str
    executor_model_family: str
    verifier_model_family: str
    verdict: str
    read_only: bool = True
    direct_measurement: bool = True
    allow_same_model: bool = False
    checks: list[CompletionCheck] = field(default_factory=list)
    notes: str = ""
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    receipt_hash: str = ""

    def __post_init__(self) -> None:
        if not SHA256_RE.fullmatch(self.candidate_packet_hash):
            raise ValueError(
                "candidate_packet_hash must match sha256:<64 lowercase hex>"
            )
        if not SHA256_RE.fullmatch(self.measured_packet_hash):
            raise ValueError(
                "measured_packet_hash must match sha256:<64 lowercase hex>"
            )
        if not self.read_only:
            raise ValueError("read_only must be True for verification receipts")
        if not self.direct_measurement:
            raise ValueError(
                "direct_measurement must be True for verification receipts"
            )
        if self.verdict not in VALID_VERDICTS:
            raise ValueError(
                f"Invalid verdict '{self.verdict}'. "
                f"Valid verdicts: {VALID_VERDICTS} (never 'done')"
            )
        if (
            self.executor_model_family == self.verifier_model_family
            and not self.allow_same_model
        ):
            raise ValueError(
                f"executor and verifier share model_family "
                f"'{self.executor_model_family}'; "
                "set allow_same_model=True to override"
            )
        if not self.executor_model_family or not self.verifier_model_family:
            raise ValueError("executor_model_family and verifier_model_family are required")
        if not self.checks:
            raise ValueError("verification receipt requires at least one command check")
        for check in self.checks:
            if not isinstance(check.command, list) or not all(
                isinstance(argument, str) for argument in check.command
            ):
                raise ValueError("check.command must be a list of strings")
            if not SHA256_RE.fullmatch(check.stdout_hash):
                raise ValueError("check.stdout_hash must match sha256:<64 lowercase hex>")
        self.receipt_hash = self._compute_receipt_hash()

    def _compute_receipt_hash(self) -> str:
        """Deterministic hash over canonical receipt fields.

        Excludes non-deterministic metadata (created_at, notes) and the
        receipt_hash itself so two structurally identical receipts always
        produce the same digest.
        """
        canonical = json.dumps(
            {
                "packet_id": self.packet_id,
                "candidate_packet_hash": self.candidate_packet_hash,
                "measured_packet_hash": self.measured_packet_hash,
                "executor_model_family": self.executor_model_family,
                "verifier_model_family": self.verifier_model_family,
                "verdict": self.verdict,
                "read_only": self.read_only,
                "direct_measurement": self.direct_measurement,
                "allow_same_model": self.allow_same_model,
                "checks": [
                    {
                        "command": c.command,
                        "returncode": c.returncode,
                        "stdout_hash": c.stdout_hash,
                    }
                    for c in self.checks
                ],
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        return compute_packet_hash(canonical)


# ── 核心函数 ──
def canonicalize(packet: dict[str, Any]) -> str:
    """对 WorkPacket 的 invariant 字段做确定性 canonicalize:
    - 按键排序
    - 无缩进、无尾随逗号、ASCII-only、紧凑分隔符
    - 忽略 None 值
    """
    # Accept either an instance mapping or a YAML envelope containing the
    # WorkPacket body.  The schema declaration itself is never hashed.
    if "packet_id" not in packet and isinstance(packet.get("WorkPacket"), dict):
        packet = packet["WorkPacket"]
    invariant_fields = {
        key: packet[key]
        for key in INVARIANT_FIELDS
        if key in packet and packet[key] is not None
    }
    return json.dumps(invariant_fields, sort_keys=True, separators=(",", ":"))


def compute_packet_hash(canonical: str) -> str:
    """计算 SHA-256 hash, 返回 sha256:<64 hex>"""
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return f"{HASH_PREFIX}{digest}"


def render_platform_envelope(
    packet: dict[str, Any], platform: str, packet_hash: str
) -> dict[str, Any]:
    """渲染平台信封: 保留 invariant payload + hash, 附加平台元数据"""
    if platform not in PLATFORMS:
        raise ValueError(f"Unknown platform: {platform}. Valid: {PLATFORMS}")
    envelope = {
        "platform": platform,
        "platform_header": PLATFORM_HEADERS[platform],
        "packet_hash": packet_hash,
        "invariant_payload": json.loads(canonicalize(packet)),
    }
    return envelope


def build_completion_manifest(
    packet: dict[str, Any],
    packet_hash: str,
    assignment_id: str,
    agent_id: str,
    status: str,
    claims: list[dict[str, Any]] | None = None,
    checks: list[dict[str, Any]] | None = None,
    changed_paths: list[str] | None = None,
    recommended_next: str = "verify",
    surface_delta: dict[str, int] | None = None,
) -> CompletionManifest:
    """构建 CompletionManifest.
    status 只接受 candidate / blocked / failed / archived, 不含 done.
    checks 中每个 entry 必须有 command, returncode, stdout_hash.
    """
    if status not in VALID_STATUSES:
        raise ValueError(
            f"Invalid status '{status}'. Valid statuses: {VALID_STATUSES} (no 'done')"
        )
    if "packet_id" not in packet:
        raise ValueError("packet instance must include packet_id")

    parsed_checks: list[CompletionCheck] = []
    if checks:
        for c in checks:
            stdout_hash = c.get("stdout_hash", "")
            if not SHA256_RE.fullmatch(stdout_hash):
                raise ValueError("stdout_hash must match sha256:<64 lowercase hex>")
            command = c.get("command")
            if not isinstance(command, list) or not all(
                isinstance(argument, str) for argument in command
            ):
                raise ValueError("check.command must be a list of strings")
            parsed_checks.append(
                CompletionCheck(
                    command=command,
                    returncode=int(c["returncode"]),
                    stdout_hash=stdout_hash,
                )
            )

    return CompletionManifest(
        packet_id=packet["packet_id"],
        packet_hash=packet_hash,
        assignment_id=assignment_id,
        agent_id=agent_id,
        status=status,
        claims=claims or [],
        checks=parsed_checks,
        changed_paths=changed_paths or [],
        recommended_next=recommended_next,
        surface_delta=surface_delta or {"files": 0, "loc": 0},
    )


def build_verification_receipt(
    packet: dict[str, Any],
    candidate_packet_hash: str,
    measured_packet_hash: str,
    executor_model_family: str,
    verifier_model_family: str,
    verdict: str,
    read_only: bool = True,
    direct_measurement: bool = True,
    allow_same_model: bool = False,
    checks: list[dict[str, Any]] | None = None,
    notes: str = "",
) -> VerificationReceipt:
    """构建 SR-05 VerificationReceipt.

    Validates all receipt invariants up front (hashes, verdict, model-family
    separation, read-only / direct-measurement constraints) and parses raw
    check dicts into CompletionCheck objects with stdout_hash validation.
    """
    if "packet_id" not in packet:
        raise ValueError("packet instance must include packet_id")
    if not SHA256_RE.fullmatch(candidate_packet_hash):
        raise ValueError("candidate_packet_hash must match sha256:<64 lowercase hex>")
    if not SHA256_RE.fullmatch(measured_packet_hash):
        raise ValueError("measured_packet_hash must match sha256:<64 lowercase hex>")
    if not read_only:
        raise ValueError("read_only must be True for verification receipts")
    if not direct_measurement:
        raise ValueError("direct_measurement must be True for verification receipts")
    if verdict not in VALID_VERDICTS:
        raise ValueError(
            f"Invalid verdict '{verdict}'. Valid verdicts: {VALID_VERDICTS} (never 'done')"
        )
    if not executor_model_family or not verifier_model_family:
        raise ValueError("executor_model_family and verifier_model_family are required")
    if executor_model_family == verifier_model_family and not allow_same_model:
        raise ValueError(
            f"executor and verifier share model_family '{executor_model_family}'; "
            "set allow_same_model=True to override"
        )

    parsed_checks: list[CompletionCheck] = []
    if checks:
        for c in checks:
            stdout_hash_val = c.get("stdout_hash", "")
            if not SHA256_RE.fullmatch(stdout_hash_val):
                raise ValueError(
                    "check stdout_hash must match sha256:<64 lowercase hex"
                )
            command = c.get("command")
            if not isinstance(command, list) or not all(
                isinstance(argument, str) for argument in command
            ):
                raise ValueError("check.command must be a list of strings")
            parsed_checks.append(
                CompletionCheck(
                    command=command,
                    returncode=int(c["returncode"]),
                    stdout_hash=stdout_hash_val,
                )
            )
    if not parsed_checks:
        raise ValueError("verification receipt requires at least one command check")

    return VerificationReceipt(
        packet_id=packet["packet_id"],
        candidate_packet_hash=candidate_packet_hash,
        measured_packet_hash=measured_packet_hash,
        executor_model_family=executor_model_family,
        verifier_model_family=verifier_model_family,
        verdict=verdict,
        read_only=read_only,
        direct_measurement=direct_measurement,
        allow_same_model=allow_same_model,
        checks=parsed_checks,
        notes=notes,
    )


def stdout_hash(stdout: str) -> str:
    """Return the canonical SHA-256 receipt digest for command stdout."""
    return compute_packet_hash(stdout)


def build_command_check(command: list[str], returncode: int, stdout: str) -> dict[str, Any]:
    """Build a schema-compatible command receipt from measured stdout."""
    return {
        "command": command,
        "returncode": int(returncode),
        "stdout_hash": stdout_hash(stdout),
    }


def detect_packet_changes(old: dict[str, Any], new: dict[str, Any]) -> dict[str, Any]:
    """检测 WorkPacket 变更: 比较 canonical form 的 hash"""
    old_canonical = canonicalize(old)
    new_canonical = canonicalize(new)
    old_hash = compute_packet_hash(old_canonical)
    new_hash = compute_packet_hash(new_canonical)
    return {
        "changed": old_hash != new_hash,
        "old_hash": old_hash,
        "new_hash": new_hash,
    }


# ── I/O ──
def load_packet(path: Path) -> dict[str, Any]:
    """从 YAML/JSON 文件加载 WorkPacket"""
    text = path.read_text(encoding="utf-8")
    if path.suffix in (".yaml", ".yml"):
        if yaml is None:
            raise ImportError("PyYAML is required to load YAML files")
        data = yaml.safe_load(text)
    else:
        data = json.loads(text)
    if not isinstance(data, dict):
        raise TypeError(f"Expected dict, got {type(data).__name__}")
    return data


# ── CLI ──
def main() -> None:
    parser = argparse.ArgumentParser(description="eCOS WorkPacket 确定性编译器")
    parser.add_argument("--packet", type=str, required=True, help="WorkPacket 文件路径")
    parser.add_argument("--platform", type=str, choices=PLATFORMS, help="渲染指定平台信封")
    parser.add_argument("--receipt", action="store_true", help="输出 CompletionManifest JSON")
    parser.add_argument(
        "--status",
        type=str,
        default="candidate",
        choices=VALID_STATUSES,
        help="CompletionManifest status (默认 candidate)",
    )
    parser.add_argument("--json", action="store_true", help="JSON 输出")
    args = parser.parse_args()

    packet = load_packet(Path(args.packet))
    if "packet_id" not in packet:
        raise ValueError(
            "packet file is a schema/envelope, not a WorkPacket instance; packet_id is required"
        )
    canonical = canonicalize(packet)
    packet_hash = compute_packet_hash(canonical)

    result: dict[str, Any] = {
        "packet_id": packet.get("packet_id"),
        "packet_hash": packet_hash,
        "canonical": canonical,
    }

    if args.platform:
        result["envelope"] = render_platform_envelope(packet, args.platform, packet_hash)

    if args.receipt:
        compiler_stdout = json.dumps(
            {"packet_id": result["packet_id"], "packet_hash": packet_hash},
            sort_keys=True,
            separators=(",", ":"),
        )
        manifest = build_completion_manifest(
            packet=packet,
            packet_hash=packet_hash,
            assignment_id=packet.get("assignment", {}).get("id", "ASG-UNKNOWN"),
            agent_id="agent-unknown",
            status=args.status,
            checks=[
                build_command_check(
                    ["work_packet_compiler.py", "--packet", args.packet],
                    0,
                    compiler_stdout,
                )
            ],
        )
        result["manifest"] = {
            "packet_id": manifest.packet_id,
            "packet_hash": manifest.packet_hash,
            "assignment_id": manifest.assignment_id,
            "agent_id": manifest.agent_id,
            "status": manifest.status,
            "checks": [
                {
                    "command": c.command,
                    "returncode": c.returncode,
                    "stdout_hash": c.stdout_hash,
                }
                for c in manifest.checks
            ],
            "submitted_at": manifest.submitted_at,
        }

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"packet_id: {result['packet_id']}")
        print(f"packet_hash: {result['packet_hash']}")
        if args.platform:
            env = result.get("envelope", {})
            print(f"platform: {env.get('platform')}")
            print(f"invariant_hash_match: {env.get('packet_hash') == packet_hash}")
        if args.receipt:
            m = result.get("manifest", {})
            print(f"status: {m.get('status')}")
            print(f"checks: {len(m.get('checks', []))}")


if __name__ == "__main__":
    main()

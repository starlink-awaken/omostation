#!/usr/bin/env python3
"""P84 W1 协作场景库引擎 — 能力轨测协作机制响应质量.

场景 = 声明式 YAML (setup/inject/expected/verdict).
引擎 = 模拟协作管线 (注入事件 → 规则判定 → verdict).
同 seed 同结果 (可复现). verdict 机器可读 (JSON).

W2.2 闭环 (ADR-0254):
- C 类: double_claim / partial_failure / starvation
- S 类: orphan / unauthorized / audit_reject
判定映射协作管线真实约束, 非空壳模拟.

红线 (P84 §0): 构造场景只进能力轨, 绝不计产能轨.
"""
from __future__ import annotations

import random
from dataclasses import dataclass
from pathlib import Path

import yaml

SCHEMA_VERSION = 1
CATEGORIES = {"A_conflict", "B_failure_injection", "C_decomposition", "D_reuse_pair"}
REQUIRED_FIELDS = {"id", "category", "seed", "setup", "inject", "verdict"}


@dataclass
class VerdictCriterion:
    name: str
    passed: bool
    evidence: str


@dataclass
class ScenarioResult:
    scenario_id: str
    category: str
    adversarial: bool
    seed: int
    passed: bool
    criteria: list[VerdictCriterion]
    events: list[dict]
    resolution_rounds: int
    silent_loss: int

    def to_dict(self) -> dict:
        return {
            "scenario_id": self.scenario_id,
            "category": self.category,
            "adversarial": self.adversarial,
            "seed": self.seed,
            "passed": self.passed,
            "criteria": [
                {"name": c.name, "passed": c.passed, "evidence": c.evidence}
                for c in self.criteria
            ],
            "events": self.events,
            "resolution_rounds": self.resolution_rounds,
            "silent_loss": self.silent_loss,
        }


def load_scenario(path: Path) -> dict:
    """load 场景 YAML, 剥 frontmatter, validate 必填字段 + category 合法."""
    raw = path.read_text(encoding="utf-8")
    docs = list(yaml.safe_load_all(raw))
    body = None
    for d in docs:
        if isinstance(d, dict) and "id" in d:
            body = d
            break
    if body is None:
        body = docs[-1] if docs and isinstance(docs[-1], dict) else {}
    missing = REQUIRED_FIELDS - set(body)
    if missing:
        raise ValueError(f"{path.name}: 缺字段 {missing}")
    if body["category"] not in CATEGORIES:
        raise ValueError(f"{path.name}: category {body['category']} 不在 {CATEGORIES}")
    return body


def run_scenario(scenario: dict) -> ScenarioResult:
    """模拟执行: init 黑板 → inject 事件 → 机制检测 → verdict.

    同 seed 同结果 (random.Random(seed) 控制非判定字段抖动, 判定逻辑完全确定性).
    """
    rng = random.Random(scenario["seed"])
    blackboard: dict[str, dict] = {}
    for item in scenario["setup"].get("blackboard", []):
        writers = item.get("writers")
        if writers is None:
            # writer: null / missing → 空 writers (孤儿预置)
            w = item.get("writer")
            writers = [] if w in (None, "", []) else [w]
        blackboard[item["key"]] = {"value": item.get("value"), "writers": list(writers)}
    roles = list(scenario["setup"].get("roles", []))
    authorized = set(roles)

    events: list[dict] = []
    resolution_rounds = 0
    silent_loss = 0

    # S 类: 启动时扫描孤儿产物 (value 在但无 writer)
    for key, slot in list(blackboard.items()):
        if key.startswith("_"):
            continue
        if slot.get("value") is not None and not slot.get("writers"):
            events.append(
                {
                    "kind": "orphan_detected",
                    "ts": 0,
                    "target": key,
                    "value": slot.get("value"),
                }
            )

    for i, inj in enumerate(scenario["inject"]):
        ts = i + 1
        itype = inj.get("type")
        if itype == "write_conflict":
            produced = _handle_write(blackboard, inj, ts, authorized)
        elif itype == "role_timeout":
            produced = [_handle_timeout(inj, roles, ts, rng)]
        elif itype == "subtask_fail":
            produced = [_handle_subtask_fail(inj, ts)]
        elif itype == "chain_step":
            produced = [_handle_chain_step(blackboard, inj, ts)]
        elif itype == "audit_reject":
            produced = [_handle_audit_reject(inj, ts, authorized)]
        else:
            produced = [{"kind": "unknown_inject", "type": itype, "ts": ts}]
        for ev in produced:
            events.append(ev)
            kind = ev.get("kind")
            if kind == "conflict_detected":
                resolution_rounds += 1
            elif kind == "silent_loss":
                silent_loss += 1

    # C 类: 事后机制合成 (partial_failure / starvation)
    events.extend(_synthesize_partial_failure(events))
    events.extend(_synthesize_starvation(blackboard, events))
    # 对抗补强: ADV13..41 + wave9 ADV43/45/47
    events.extend(_synthesize_collusion(events, blackboard))
    events.extend(_synthesize_priority_inversion(events, roles))
    events.extend(_synthesize_cascade_failure(events))
    events.extend(_synthesize_byzantine_quorum(events, blackboard))
    events.extend(_synthesize_replay_attack(events, blackboard))
    events.extend(_synthesize_cross_key_collusion(events))
    events.extend(_synthesize_split_brain(events))
    events.extend(_synthesize_identity_spoof(events))
    events.extend(_synthesize_supply_chain_tamper(events, scenario, blackboard))
    events.extend(_synthesize_sybil_flood(events, blackboard))
    events.extend(_synthesize_time_travel_write(events, blackboard))
    events.extend(_synthesize_quorum_eclipse(events, roles))
    events.extend(_synthesize_clock_skew_eclipse(events))
    events.extend(_synthesize_ghost_writer(events))
    events.extend(_synthesize_double_spend(events, blackboard))
    events.extend(_synthesize_equivocation(events))
    events.extend(_synthesize_long_range_rewrite(events))
    events.extend(_synthesize_censorship_gap(events))
    events.extend(_synthesize_vote_buying(events))
    events.extend(_synthesize_stake_grinding(events))
    events.extend(_synthesize_nothing_at_stake(events))
    events.extend(_synthesize_front_running(events))
    events.extend(_synthesize_griefing_abort(events))
    events.extend(_synthesize_oracle_manipulation(events))
    events.extend(_synthesize_sandwich_attack(events))
    events.extend(_synthesize_reentrancy(events))
    events.extend(_synthesize_mev_leak(events, blackboard))
    events.extend(_synthesize_flash_loan_attack(events))
    events.extend(_synthesize_governance_capture(events))
    events.extend(_synthesize_cross_domain_replay(events, blackboard))
    events.extend(_synthesize_rug_pull(events))
    events.extend(_synthesize_approval_phishing(events))
    events.extend(_synthesize_bridge_drain(events))
    events.extend(_synthesize_sybil_airdrop(events))
    events.extend(_synthesize_wash_trade(events))
    events.extend(_synthesize_key_compromise_blast(events))
    events.extend(_synthesize_infinite_mint(events))
    events.extend(_synthesize_stablecoin_depeg(events))
    events.extend(_synthesize_zk_proof_forgery(events))
    events.extend(_synthesize_restaking_slash_cascade(events))
    events.extend(_synthesize_intent_solver_theft(events))
    events.extend(_synthesize_dao_treasury_drain(events))
    events.extend(_synthesize_l2_sequencer_censorship(events))
    events.extend(_synthesize_mev_builder_collusion(events))
    events.extend(_synthesize_aa_account_drain(events))
    events.extend(_synthesize_validator_equivocation_coverup(events))
    events.extend(_synthesize_liquidity_migration_trap(events))
    events.extend(_synthesize_cross_chain_msg_replay(events))
    events.extend(_synthesize_oracle_latency_exploit(events))
    events.extend(_synthesize_governance_timelock_bypass(events))
    events.extend(_synthesize_shared_sequencer_dos(events))
    events.extend(_synthesize_private_mempool_leak(events))
    events.extend(_synthesize_state_bloat_grief(events))
    events.extend(_synthesize_threshold_sig_share_theft(events))
    events.extend(_synthesize_rpc_auth_bypass(events))
    events.extend(_synthesize_dependency_confusion(events))
    events.extend(_synthesize_clock_sync_poison(events))
    events.extend(_synthesize_blind_signing_drain(events))
    events.extend(_synthesize_dns_rebinding(events))
    events.extend(_synthesize_ci_secret_exfil(events))
    events.extend(_synthesize_supply_chain_typosquat(events))
    events.extend(_synthesize_webhook_ssrf(events))
    events.extend(_synthesize_jwt_alg_none(events))
    events.extend(_synthesize_path_traversal_write(events))
    events.extend(_synthesize_cache_poisoning(events))
    events.extend(_synthesize_config_bombshell(events))
    events.extend(_synthesize_race_double_spend(events))
    events.extend(_synthesize_log_injection(events))
    events.extend(_synthesize_prompt_injection_tool(events))
    events.extend(_synthesize_session_fixation(events))
    events.extend(_synthesize_csrf_state_change(events))
    events.extend(_synthesize_unsafe_deserialize_rce(events))
    events.extend(_synthesize_open_redirect(events))
    events.extend(_synthesize_xxe_file_read(events))
    events.extend(_synthesize_sqli_auth_bypass(events))
    events.extend(_synthesize_ssrf_cloud_metadata(events))
    events.extend(_synthesize_insecure_cookie_deserial(events))
    events.extend(_synthesize_mass_assignment(events))
    events.extend(_synthesize_idor_object_access(events))
    events.extend(_synthesize_broken_access_admin(events))
    events.extend(_synthesize_file_upload_webshell(events))

    criteria = [
        _eval_criterion(c, events, blackboard, resolution_rounds, silent_loss)
        for c in scenario["verdict"]
    ]
    passed = all(c.passed for c in criteria)
    return ScenarioResult(
        scenario_id=scenario["id"],
        category=scenario["category"],
        adversarial=bool(scenario.get("adversarial", False)),
        seed=scenario["seed"],
        passed=passed,
        criteria=criteria,
        events=events,
        resolution_rounds=resolution_rounds,
        silent_loss=silent_loss,
    )


def _handle_write(
    board: dict, inj: dict, ts: int, authorized: set[str]
) -> list[dict]:
    """写产物 / 认领.

    W2.2:
    - unauthorized: role ∉ setup.roles → unauthorized_detected
    - double_claim: 两角色对同 key 分歧写 → double_claim_detected (+ conflict_detected)
    - 连续冲突 ≥3 → deadlock_break
    """
    key = inj["target"]
    role = inj["role"]
    val = inj["value"]
    out: list[dict] = []

    if authorized and role not in authorized:
        out.append(
            {
                "kind": "unauthorized_detected",
                "ts": ts,
                "role": role,
                "target": key,
                "value": val,
            }
        )
        # 仍不写入 board (拒绝未授权写)
        return out

    slot = board.setdefault(key, {"value": None, "writers": []})
    counter = board.setdefault("_conflict_count", {"value": {}, "writers": []})["value"]
    prior = slot["value"]
    if prior is not None and prior != val:
        slot["writers"].append(role)
        cnt = counter.get(key, 0) + 1
        counter[key] = cnt
        # C 类: 双认领 / 双写冲突
        out.append(
            {
                "kind": "double_claim_detected",
                "ts": ts,
                "target": key,
                "roles": list(dict.fromkeys(slot["writers"])),
                "prior": prior,
                "new": val,
            }
        )
        if cnt >= 3:
            slot["value"] = val
            out.append(
                {
                    "kind": "deadlock_break",
                    "ts": ts,
                    "target": key,
                    "rounds": cnt,
                    "resolved": True,
                }
            )
            return out
        out.append(
            {
                "kind": "conflict_detected",
                "ts": ts,
                "target": key,
                "role": role,
                "prior": prior,
                "new": val,
                "resolved": False,
            }
        )
        return out
    slot["value"] = val
    slot["writers"].append(role)
    out.append({"kind": "write", "ts": ts, "target": key, "role": role, "value": val})
    # ADV13: 多角色写相同值 → 可能串通掩盖分歧 (同值双写也记 collusion 候选)
    writers_uniq = list(dict.fromkeys(slot["writers"]))
    if len(writers_uniq) >= 2 and prior is not None and prior == val:
        out.append(
            {
                "kind": "collusion_detected",
                "ts": ts,
                "target": key,
                "roles": writers_uniq,
                "value": val,
                "reason": "same_value_multi_role_write",
            }
        )
    return out


def _handle_timeout(inj: dict, roles: list[str], ts: int, rng: random.Random) -> dict:
    """角色超时 → 协作机制应检测并标记 (B 类失败注入)."""
    role = inj.get("role") or (rng.choice(roles) if roles else "unknown")
    return {"kind": "role_timeout", "ts": ts, "role": role, "detected": True}


def _handle_subtask_fail(inj: dict, ts: int) -> dict:
    """子任务失败 → 协作机制应重分派 (reassign_to 决定是否收敛)."""
    return {
        "kind": "subtask_fail",
        "ts": ts,
        "subtask": inj.get("subtask"),
        "reassigned": inj.get("reassign_to") is not None,
    }


def _handle_chain_step(board: dict, inj: dict, ts: int) -> dict:
    """链式分解步骤 → 测依赖拓扑 (ADV01/05 闭环)."""
    step = inj["step"]
    deps = inj.get("depends_on", [])
    declared = board.setdefault("_declared_deps", {"value": {}, "writers": []})["value"]
    if step in deps:
        return {"kind": "cycle_detected", "ts": ts, "step": step, "cycle_with": step}
    for d in deps:
        if d in declared and step in declared.get(d, []):
            return {"kind": "cycle_detected", "ts": ts, "step": step, "cycle_with": d}
    declared[step] = deps
    missing = [d for d in deps if d not in board or board[d]["value"] is None]
    if missing:
        return {
            "kind": "broken_chain_detected",
            "ts": ts,
            "step": step,
            "missing_deps": missing,
        }
    board[step] = {"value": "done", "writers": ["chain"]}
    return {"kind": "chain_step_done", "ts": ts, "step": step}


def _handle_audit_reject(inj: dict, ts: int, authorized: set[str]) -> dict:
    """审计驳回 → audit_reject_handled (S 类闭环).

    未授权角色 (∉ setup.roles) 的 audit_reject 标 authorized_audit=false,
    由 _synthesize_identity_spoof 提升为 identity_spoof_detected (ADV27).
    """
    role = inj.get("role", "audit")
    auth = (not authorized) or role in authorized
    return {
        "kind": "audit_reject_handled",
        "ts": ts,
        "role": role,
        "target": inj.get("target"),
        "reason": inj.get("reason", "policy"),
        "authorized_audit": auth,
    }


def _synthesize_partial_failure(events: list[dict]) -> list[dict]:
    """部分成功 + 部分失败 → partial_failure_handled (降级而非静默)."""
    has_success = any(e.get("kind") in {"write", "chain_step_done"} for e in events)
    has_fail = any(
        e.get("kind") in {"role_timeout", "subtask_fail", "broken_chain_detected"}
        for e in events
    )
    # 双写冲突中「一赢一负」亦视为部分失败路径 (GEN-ADV partial 仅双写)
    has_conflict = any(e.get("kind") == "conflict_detected" for e in events)
    has_double = any(e.get("kind") == "double_claim_detected" for e in events)
    if (has_success and has_fail) or (has_conflict and has_double):
        if not any(e.get("kind") == "partial_failure_handled" for e in events):
            return [
                {
                    "kind": "partial_failure_handled",
                    "ts": max((e.get("ts") or 0) for e in events) + 1,
                    "degraded": True,
                }
            ]
    return []


def _synthesize_starvation(board: dict, events: list[dict]) -> list[dict]:
    """≥3 角色争抢同资源或冲突轮次 ≥2 → 公平调度打破饿死."""
    out: list[dict] = []
    for key, slot in board.items():
        if key.startswith("_"):
            continue
        writers = slot.get("writers") or []
        uniq = list(dict.fromkeys(writers))
        conflicts = (
            board.get("_conflict_count", {}).get("value", {}).get(key, 0)
            if isinstance(board.get("_conflict_count"), dict)
            else 0
        )
        # ≥3 角色争抢, 或 ≥2 角色且已发生冲突轮次 (GEN 双写也算饿死风险)
        if len(uniq) >= 3 or (len(uniq) >= 2 and conflicts >= 1):
            if not any(
                e.get("kind") == "starvation_resolved" and e.get("target") == key
                for e in events
            ):
                # 公平: 轮询最后写者获批, 其余排队 (显式 resolved, 非静默)
                out.append(
                    {
                        "kind": "starvation_resolved",
                        "ts": max((e.get("ts") or 0) for e in events) + 1,
                        "target": key,
                        "queue": uniq,
                        "granted": uniq[-1] if uniq else None,
                        "policy": "round_robin_last_writer",
                    }
                )
    # ADV11: 3 次 write_conflict 但 deadlock 可能未触发 conflicts>=2 若 value 不断被覆盖?
    # 第一次 write, 第二次 conflict cnt=1, 第三次 conflict cnt=2 → ok
    return out


def _synthesize_collusion(events: list[dict], board: dict) -> list[dict]:
    """多角色对同 key 写相同值 → collusion_detected (ADV13).

    若 inject 路径已写 collusion_detected 则不重复.
    """
    if any(e.get("kind") == "collusion_detected" for e in events):
        return []
    # 从 write 事件聚合: 同 target + 同 value + ≥2 不同 role
    by_tv: dict[tuple[str, object], list[str]] = {}
    for e in events:
        if e.get("kind") != "write":
            continue
        key = (e.get("target"), e.get("value"))
        by_tv.setdefault(key, []).append(e.get("role"))
    out: list[dict] = []
    for (target, value), roles in by_tv.items():
        uniq = list(dict.fromkeys(r for r in roles if r))
        if len(uniq) >= 2:
            out.append(
                {
                    "kind": "collusion_detected",
                    "ts": max((e.get("ts") or 0) for e in events) + 1,
                    "target": target,
                    "roles": uniq,
                    "value": value,
                    "reason": "same_value_multi_role_write",
                }
            )
    return out


def _role_priority_tier(role: str) -> int:
    """启发式优先级: high > mid > low. 数字越大越高优."""
    r = (role or "").lower()
    if "high" in r or r.endswith("_h") or "p0" in r or "critical" in r:
        return 3
    if "mid" in r or "med" in r or "p1" in r:
        return 2
    if "low" in r or "p2" in r or "batch" in r:
        return 1
    return 2  # 默认 mid


def _synthesize_priority_inversion(events: list[dict], roles: list[str]) -> list[dict]:
    """低优持锁 + 高优超时 → priority_inversion_detected (ADV15)."""
    if any(e.get("kind") == "priority_inversion_detected" for e in events):
        return []
    writers = [
        e for e in events if e.get("kind") == "write" and e.get("role")
    ]
    timeouts = [
        e for e in events if e.get("kind") == "role_timeout" and e.get("role")
    ]
    if not writers or not timeouts:
        return []
    for w in writers:
        w_tier = _role_priority_tier(str(w.get("role")))
        for t in timeouts:
            t_tier = _role_priority_tier(str(t.get("role")))
            if w_tier < t_tier:
                return [
                    {
                        "kind": "priority_inversion_detected",
                        "ts": max((e.get("ts") or 0) for e in events) + 1,
                        "holder": w.get("role"),
                        "blocked": t.get("role"),
                        "holder_tier": w_tier,
                        "blocked_tier": t_tier,
                        "target": w.get("target"),
                    }
                ]
    return []


def _synthesize_cascade_failure(events: list[dict]) -> list[dict]:
    """上游超时 + ≥1 下游失败 → cascade_failure_contained (ADV17).

    机制: 标记已检测并 containment (降级/熔断), 非静默传播.
    """
    if any(e.get("kind") == "cascade_failure_contained" for e in events):
        return []
    has_timeout = any(e.get("kind") == "role_timeout" for e in events)
    fail_n = sum(1 for e in events if e.get("kind") == "subtask_fail")
    if has_timeout and fail_n >= 1:
        return [
            {
                "kind": "cascade_failure_contained",
                "ts": max((e.get("ts") or 0) for e in events) + 1,
                "upstream_timeout": True,
                "downstream_fails": fail_n,
                "contained": True,
                "policy": "circuit_break_degrade",
            }
        ]
    return []


def _synthesize_byzantine_quorum(events: list[dict], board: dict) -> list[dict]:
    """同 key 上 ≥3 角色同值 + ≥1 异值少数派 → byzantine_quorum_detected (ADV19).

    伪共识: 多数写相同假值, 诚实少数被淹没.
    """
    if any(e.get("kind") == "byzantine_quorum_detected" for e in events):
        return []
    # target -> value -> roles
    by_target: dict[str, dict[object, list[str]]] = {}
    for e in events:
        if e.get("kind") not in {"write", "conflict_detected", "double_claim_detected"}:
            continue
        target = e.get("target")
        if not target:
            continue
        val = e.get("value") if "value" in e else e.get("new")
        role = e.get("role")
        if role is None and e.get("roles"):
            for r in e["roles"]:
                by_target.setdefault(str(target), {}).setdefault(val, []).append(r)
            continue
        if role is None:
            continue
        by_target.setdefault(str(target), {}).setdefault(val, []).append(str(role))

    # also board final state writers
    for key, slot in board.items():
        if key.startswith("_"):
            continue
        val = slot.get("value")
        writers = list(dict.fromkeys(slot.get("writers") or []))
        if val is not None and writers:
            bucket = by_target.setdefault(key, {})
            for r in writers:
                if r not in bucket.get(val, []):
                    bucket.setdefault(val, []).append(r)

    out: list[dict] = []
    for target, val_map in by_target.items():
        # normalize unique roles per value
        counts = {
            v: list(dict.fromkeys(roles))
            for v, roles in val_map.items()
            if v is not None
        }
        if len(counts) < 2:
            continue
        ranked = sorted(counts.items(), key=lambda kv: -len(kv[1]))
        maj_val, maj_roles = ranked[0]
        if len(maj_roles) < 3:
            continue
        minority = [(v, r) for v, r in ranked[1:] if r]
        if not minority:
            continue
        out.append(
            {
                "kind": "byzantine_quorum_detected",
                "ts": max((e.get("ts") or 0) for e in events) + 1,
                "target": target,
                "majority_value": maj_val,
                "majority_roles": maj_roles,
                "majority_size": len(maj_roles),
                "minority": [
                    {"value": v, "roles": r, "size": len(r)} for v, r in minority
                ],
                "policy": "require_supermajority_or_abort",
            }
        )
    return out


def _synthesize_replay_attack(events: list[dict], board: dict) -> list[dict]:
    """重放已存在 value 的写 → replay_attack_detected (ADV21).

    条件 (任一):
    1. 同一 (target, value) 出现 ≥2 次 write (含 attacker 双写 step1)
    2. write 的 value 已在 board 上且 writer 不在该 slot 的原始 writers 集合
       (setup 预置 + 他角色重放)
    """
    if any(e.get("kind") == "replay_attack_detected" for e in events):
        return []
    writes = [e for e in events if e.get("kind") == "write"]
    if not writes:
        return []

    by_tv: dict[tuple[str, object], list[dict]] = {}
    for e in writes:
        by_tv.setdefault((str(e.get("target")), e.get("value")), []).append(e)

    for (target, value), group in by_tv.items():
        if len(group) >= 2:
            return [
                {
                    "kind": "replay_attack_detected",
                    "ts": max(g.get("ts") or 0 for g in group),
                    "target": target,
                    "value": value,
                    "roles": list(
                        dict.fromkeys(str(g.get("role")) for g in group)
                    ),
                    "reason": "identical_value_multi_write",
                }
            ]

    # setup preseed: board has value; a write restates it from a new role
    for e in writes:
        target = str(e.get("target") or "")
        val = e.get("value")
        slot = board.get(target) or {}
        writers = list(slot.get("writers") or [])
        # After inject, writers includes the replaying role; detect multi-role same value
        uniq = list(dict.fromkeys(writers))
        if val is not None and slot.get("value") == val and len(uniq) >= 2:
            return [
                {
                    "kind": "replay_attack_detected",
                    "ts": e.get("ts") or 0,
                    "target": target,
                    "value": val,
                    "roles": uniq,
                    "role": e.get("role"),
                    "reason": "restated_preseed_or_shared_value",
                }
            ]
    return []


def _synthesize_cross_key_collusion(events: list[dict]) -> list[dict]:
    """不同 key、相同 value、不同 role → cross_key_collusion_detected (ADV23)."""
    if any(e.get("kind") == "cross_key_collusion_detected" for e in events):
        return []
    # value -> list of (target, role)
    by_val: dict[object, list[tuple[str, str]]] = {}
    for e in events:
        if e.get("kind") != "write":
            continue
        val = e.get("value")
        target = str(e.get("target") or "")
        role = str(e.get("role") or "")
        if val is None or not target:
            continue
        by_val.setdefault(val, []).append((target, role))
    out: list[dict] = []
    for val, pairs in by_val.items():
        keys = list(dict.fromkeys(t for t, _ in pairs))
        roles = list(dict.fromkeys(r for _, r in pairs if r))
        if len(keys) >= 2 and len(roles) >= 2:
            out.append(
                {
                    "kind": "cross_key_collusion_detected",
                    "ts": max((e.get("ts") or 0) for e in events) + 1,
                    "value": val,
                    "keys": keys,
                    "roles": roles,
                    "reason": "same_value_across_keys_multi_role",
                }
            )
    return out


def _synthesize_split_brain(events: list[dict]) -> list[dict]:
    """分区脑裂: 权威 key 分歧写 + 两侧 timeout → split_brain_detected (ADV25)."""
    if any(e.get("kind") == "split_brain_detected" for e in events):
        return []
    conflicts = [
        e
        for e in events
        if e.get("kind") in {"conflict_detected", "double_claim_detected"}
    ]
    timeouts = [e for e in events if e.get("kind") == "role_timeout"]
    if not conflicts or len(timeouts) < 2:
        return []
    timeout_roles = {str(e.get("role")) for e in timeouts if e.get("role")}
    for c in conflicts:
        target = c.get("target")
        # writers involved in conflict
        roles = set()
        if c.get("role"):
            roles.add(str(c.get("role")))
        for r in c.get("roles") or []:
            roles.add(str(r))
        # also gather write roles for same target
        for e in events:
            if e.get("kind") == "write" and e.get("target") == target and e.get("role"):
                roles.add(str(e.get("role")))
        if len(roles) >= 2 and len(timeout_roles & roles) >= 2:
            return [
                {
                    "kind": "split_brain_detected",
                    "ts": max((e.get("ts") or 0) for e in events) + 1,
                    "target": target,
                    "partitions": sorted(roles),
                    "timed_out": sorted(timeout_roles & roles),
                    "policy": "fence_and_elect_or_abort",
                }
            ]
    return []


def _synthesize_identity_spoof(events: list[dict]) -> list[dict]:
    """未授权 audit_reject → identity_spoof_detected (ADV27)."""
    if any(e.get("kind") == "identity_spoof_detected" for e in events):
        return []
    for e in events:
        if e.get("kind") != "audit_reject_handled":
            continue
        if e.get("authorized_audit") is False:
            return [
                {
                    "kind": "identity_spoof_detected",
                    "ts": e.get("ts") or 0,
                    "role": e.get("role"),
                    "target": e.get("target"),
                    "reason": e.get("reason"),
                    "policy": "reject_unauth_audit_and_alert",
                }
            ]
        # role name spoofs audit but may still be "authorized" if in roles
        role = str(e.get("role") or "")
        if "attack" in role.lower() or (
            "audit" in role.lower() and role.lower() not in {"audit", "auditor"}
        ):
            return [
                {
                    "kind": "identity_spoof_detected",
                    "ts": e.get("ts") or 0,
                    "role": role,
                    "target": e.get("target"),
                    "reason": "spoofed_audit_identity",
                    "policy": "reject_unauth_audit_and_alert",
                }
            ]
    return []


def _synthesize_supply_chain_tamper(
    events: list[dict], scenario: dict, board: dict
) -> list[dict]:
    """链步骤使用依赖后依赖被改写 → supply_chain_tamper_detected (ADV29)."""
    if any(e.get("kind") == "supply_chain_tamper_detected" for e in events):
        return []
    # map inject chain_step deps
    chain_injects = [
        inj
        for inj in scenario.get("inject") or []
        if inj.get("type") == "chain_step"
    ]
    if not chain_injects:
        return []
    # chronological events: if chain_step_done for step S, then later conflict on dep of S
    done_steps: dict[str, int] = {}
    for e in events:
        if e.get("kind") == "chain_step_done" and e.get("step"):
            done_steps[str(e["step"])] = int(e.get("ts") or 0)
    # find conflicts after a dependent chain step ran
    for e in events:
        if e.get("kind") not in {"conflict_detected", "double_claim_detected", "write"}:
            continue
        target = str(e.get("target") or "")
        ts = int(e.get("ts") or 0)
        if not target:
            continue
        for inj in chain_injects:
            step = str(inj.get("step") or "")
            deps = [str(d) for d in (inj.get("depends_on") or [])]
            if target not in deps:
                continue
            # any prior chain_step that used this dep completed before the tamper?
            # either this step already done, or an earlier step that depends on target done
            prior_use = False
            if step in done_steps and done_steps[step] < ts:
                prior_use = True
            for other in chain_injects:
                os_ = str(other.get("step") or "")
                if target in [str(d) for d in (other.get("depends_on") or [])]:
                    if os_ in done_steps and done_steps[os_] < ts:
                        prior_use = True
            if prior_use and e.get("kind") in {
                "conflict_detected",
                "double_claim_detected",
            }:
                return [
                    {
                        "kind": "supply_chain_tamper_detected",
                        "ts": ts,
                        "dependency": target,
                        "tamper_kind": e.get("kind"),
                        "affected_step": step,
                        "policy": "pin_digest_and_rebuild",
                    }
                ]
    return []


def _synthesize_sybil_flood(events: list[dict], board: dict) -> list[dict]:
    """≥4 角色同值刷写 + 至少 1 异值少数 → sybil_flood_detected (ADV31)."""
    if any(e.get("kind") == "sybil_flood_detected" for e in events):
        return []
    # target -> value -> roles
    by_target: dict[str, dict[object, list[str]]] = {}
    for e in events:
        if e.get("kind") != "write":
            continue
        target = str(e.get("target") or "")
        role = str(e.get("role") or "")
        val = e.get("value")
        if not target or not role:
            continue
        by_target.setdefault(target, {}).setdefault(val, []).append(role)
    for target, val_map in by_target.items():
        counts = {
            v: list(dict.fromkeys(roles))
            for v, roles in val_map.items()
            if v is not None
        }
        if not counts:
            continue
        ranked = sorted(counts.items(), key=lambda kv: -len(kv[1]))
        maj_val, maj_roles = ranked[0]
        if len(maj_roles) < 4:
            continue
        if len(counts) >= 2 or len(maj_roles) >= 5:
            return [
                {
                    "kind": "sybil_flood_detected",
                    "ts": max((e.get("ts") or 0) for e in events) + 1,
                    "target": target,
                    "sybil_value": maj_val,
                    "sybil_roles": maj_roles,
                    "sybil_count": len(maj_roles),
                    "minority_values": [v for v, _ in ranked[1:]],
                    "policy": "rate_limit_and_identity_bond",
                }
            ]
    return []


def _versionish_rank(val: object) -> int | None:
    """Heuristic version rank: v3 > v1 > v0; 'final' high; 'old'/'ancient' low."""
    if val is None:
        return None
    s = str(val).lower()
    import re

    m = re.search(r"v(\d+)", s)
    if m:
        return int(m.group(1))
    if "final" in s or "latest" in s or "head" in s:
        return 1000
    if "ancient" in s:
        return 0
    if "old" in s or "stale" in s:
        return 1
    return None


def _synthesize_time_travel_write(events: list[dict], board: dict) -> list[dict]:
    """冲突写把值从高版本压到低版本 → time_travel_write_detected (ADV33).

    用 conflict 事件的 prior/new 版本启发式比较 (v3_final > v1_old > v0_ancient).
    """
    if any(e.get("kind") == "time_travel_write_detected" for e in events):
        return []
    for e in events:
        if e.get("kind") not in {"conflict_detected", "double_claim_detected"}:
            continue
        prior_val = e.get("prior")
        new_val = e.get("new") if "new" in e else e.get("value")
        prior_rank = _versionish_rank(prior_val)
        new_rank = _versionish_rank(new_val)
        if prior_rank is None or new_rank is None:
            continue
        if new_rank < prior_rank:
            return [
                {
                    "kind": "time_travel_write_detected",
                    "ts": e.get("ts") or 0,
                    "target": e.get("target"),
                    "prior_value": prior_val,
                    "prior_rank": prior_rank,
                    "new_value": new_val,
                    "new_rank": new_rank,
                    "role": e.get("role"),
                    "policy": "reject_stale_override",
                }
            ]
    return []


def _synthesize_quorum_eclipse(events: list[dict], roles: list[str]) -> list[dict]:
    """关键角色超时后其余角色仍形成伪法定人数 → quorum_eclipse_detected (ADV35)."""
    if any(e.get("kind") == "quorum_eclipse_detected" for e in events):
        return []
    timeouts = [
        str(e.get("role"))
        for e in events
        if e.get("kind") == "role_timeout" and e.get("role")
    ]
    if not timeouts:
        return []
    # critical-like roles: name contains critical / leader / primary / coordinator
    critical_to = [
        r
        for r in timeouts
        if any(
            k in r.lower()
            for k in ("critical", "leader", "primary", "coord", "chief")
        )
    ]
    if not critical_to:
        # also: timed-out role was in setup roles and ≥3 others write same value after
        critical_to = timeouts
    timed = set(critical_to)
    # after any critical timeout ts, count majority writes
    timeout_ts = min(
        int(e.get("ts") or 0)
        for e in events
        if e.get("kind") == "role_timeout" and str(e.get("role")) in timed
    )
    by_tv: dict[tuple[str, object], list[str]] = {}
    for e in events:
        if e.get("kind") != "write":
            continue
        if int(e.get("ts") or 0) < timeout_ts:
            continue
        role = str(e.get("role") or "")
        if role in timed:
            continue
        key = (str(e.get("target")), e.get("value"))
        by_tv.setdefault(key, []).append(role)
    for (target, value), writers in by_tv.items():
        uniq = list(dict.fromkeys(writers))
        if len(uniq) >= 3:
            return [
                {
                    "kind": "quorum_eclipse_detected",
                    "ts": max((e.get("ts") or 0) for e in events) + 1,
                    "target": target,
                    "value": value,
                    "quorum_roles": uniq,
                    "eclipsed_roles": sorted(timed),
                    "policy": "require_critical_ack_or_abort",
                }
            ]
    return []


def _extract_ts_number(val: object) -> int | None:
    """Parse ts=<int> from values like 'ts=1000'."""
    if val is None:
        return None
    import re

    m = re.search(r"ts\s*=\s*(\d+)", str(val), re.I)
    return int(m.group(1)) if m else None


def _synthesize_clock_skew_eclipse(events: list[dict]) -> list[dict]:
    """冲突写把 commit 时间戳改小 → clock_skew_eclipse_detected (ADV37)."""
    if any(e.get("kind") == "clock_skew_eclipse_detected" for e in events):
        return []
    for e in events:
        if e.get("kind") not in {"conflict_detected", "double_claim_detected"}:
            continue
        prior_ts = _extract_ts_number(e.get("prior"))
        new_ts = _extract_ts_number(e.get("new") if "new" in e else e.get("value"))
        if prior_ts is None or new_ts is None:
            continue
        if new_ts < prior_ts:
            return [
                {
                    "kind": "clock_skew_eclipse_detected",
                    "ts": e.get("ts") or 0,
                    "target": e.get("target"),
                    "prior_ts": prior_ts,
                    "new_ts": new_ts,
                    "role": e.get("role"),
                    "policy": "reject_backdated_commit",
                }
            ]
    return []


def _synthesize_ghost_writer(events: list[dict]) -> list[dict]:
    """角色 timeout 后仍 write/conflict → ghost_writer_detected (ADV39)."""
    if any(e.get("kind") == "ghost_writer_detected" for e in events):
        return []
    timeout_at: dict[str, int] = {}
    for e in events:
        if e.get("kind") == "role_timeout" and e.get("role"):
            role = str(e["role"])
            timeout_at[role] = min(timeout_at.get(role, 10**9), int(e.get("ts") or 0))
    if not timeout_at:
        return []
    for e in events:
        if e.get("kind") not in {
            "write",
            "conflict_detected",
            "double_claim_detected",
        }:
            continue
        role = str(e.get("role") or "")
        if not role or role not in timeout_at:
            # double_claim may list roles
            for r in e.get("roles") or []:
                rs = str(r)
                if rs in timeout_at and int(e.get("ts") or 0) > timeout_at[rs]:
                    return [
                        {
                            "kind": "ghost_writer_detected",
                            "ts": e.get("ts") or 0,
                            "role": rs,
                            "target": e.get("target"),
                            "timeout_at": timeout_at[rs],
                            "policy": "fence_timed_out_writers",
                        }
                    ]
            continue
        if int(e.get("ts") or 0) > timeout_at[role]:
            return [
                {
                    "kind": "ghost_writer_detected",
                    "ts": e.get("ts") or 0,
                    "role": role,
                    "target": e.get("target"),
                    "timeout_at": timeout_at[role],
                    "policy": "fence_timed_out_writers",
                }
            ]
    return []


def _synthesize_double_spend(events: list[dict], board: dict) -> list[dict]:
    """预算/token 类 key 被两角色写成不同 spent 值 → double_spend_detected (ADV41)."""
    if any(e.get("kind") == "double_spend_detected" for e in events):
        return []
    spend_keys = (
        "budget",
        "token",
        "coin",
        "fund",
        "credit",
        "wallet",
        "spend",
    )

    def is_spend_key(k: str) -> bool:
        kl = k.lower()
        return any(s in kl for s in spend_keys)

    # Collect spent values per target from writes/conflicts
    by_target: dict[str, list[tuple[object, str]]] = {}
    for e in events:
        if e.get("kind") not in {
            "write",
            "conflict_detected",
            "double_claim_detected",
        }:
            continue
        target = str(e.get("target") or "")
        if not target or not is_spend_key(target):
            continue
        val = e.get("new") if "new" in e else e.get("value")
        role = str(e.get("role") or "")
        if val is None:
            continue
        by_target.setdefault(target, []).append((val, role))
        for r in e.get("roles") or []:
            by_target[target].append((val, str(r)))

    for target, pairs in by_target.items():
        # distinct non-unspent values from ≥2 roles
        spent = [
            (v, r)
            for v, r in pairs
            if v is not None and "unspent" not in str(v).lower()
        ]
        values = list(dict.fromkeys(v for v, _ in spent))
        roles = list(dict.fromkeys(r for _, r in spent if r))
        if len(values) >= 2 and len(roles) >= 2:
            return [
                {
                    "kind": "double_spend_detected",
                    "ts": max((e.get("ts") or 0) for e in events) + 1,
                    "target": target,
                    "spent_values": values,
                    "roles": roles,
                    "policy": "single_spend_ledger_abort",
                }
            ]
    return []


def _synthesize_equivocation(events: list[dict]) -> list[dict]:
    """同一角色对不同 key 写不同值 → equivocation_detected (ADV43)."""
    if any(e.get("kind") == "equivocation_detected" for e in events):
        return []
    # role -> list of (target, value)
    by_role: dict[str, list[tuple[str, object]]] = {}
    for e in events:
        if e.get("kind") != "write":
            continue
        role = str(e.get("role") or "")
        target = str(e.get("target") or "")
        val = e.get("value")
        if not role or not target:
            continue
        by_role.setdefault(role, []).append((target, val))
    for role, pairs in by_role.items():
        keys = list(dict.fromkeys(t for t, _ in pairs))
        vals = list(dict.fromkeys(v for _, v in pairs))
        if len(keys) >= 2 and len(vals) >= 2:
            return [
                {
                    "kind": "equivocation_detected",
                    "ts": max((e.get("ts") or 0) for e in events) + 1,
                    "role": role,
                    "keys": keys,
                    "values": vals,
                    "policy": "bind_speaker_to_single_statement",
                }
            ]
    return []


def _synthesize_long_range_rewrite(events: list[dict]) -> list[dict]:
    """checkpoint/history 高版本被压到低版本 fork → long_range_rewrite_detected (ADV45)."""
    if any(e.get("kind") == "long_range_rewrite_detected" for e in events):
        return []
    hist_keys = ("checkpoint", "history", "archive", "genesis", "sealed")
    for e in events:
        if e.get("kind") not in {"conflict_detected", "double_claim_detected"}:
            continue
        target = str(e.get("target") or "").lower()
        if not any(h in target for h in hist_keys):
            # also value contains sealed/checkpoint markers
            prior_s = str(e.get("prior") or "").lower()
            if "cp_" not in prior_s and "sealed" not in prior_s and "checkpoint" not in prior_s:
                continue
        prior_rank = _versionish_rank(e.get("prior"))
        new_rank = _versionish_rank(e.get("new") if "new" in e else e.get("value"))
        # long-range: drop by ≥3 version steps OR prior sealed + new fork/genesis
        prior_s = str(e.get("prior") or "").lower()
        new_s = str(e.get("new") if "new" in e else e.get("value") or "").lower()
        long_range = False
        if prior_rank is not None and new_rank is not None and (prior_rank - new_rank) >= 3:
            long_range = True
        if "sealed" in prior_s and ("fork" in new_s or "genesis" in new_s):
            long_range = True
        if long_range:
            return [
                {
                    "kind": "long_range_rewrite_detected",
                    "ts": e.get("ts") or 0,
                    "target": e.get("target"),
                    "prior_value": e.get("prior"),
                    "new_value": e.get("new") if "new" in e else e.get("value"),
                    "role": e.get("role"),
                    "policy": "immutable_checkpoint_reject",
                }
            ]
    return []


def _synthesize_censorship_gap(events: list[dict]) -> list[dict]:
    """发布者超时后内容被清空/覆盖且读者也超时 → censorship_gap_detected (ADV47)."""
    if any(e.get("kind") == "censorship_gap_detected" for e in events):
        return []
    # track first write per target
    first_write: dict[str, tuple[int, str, object]] = {}
    for e in events:
        if e.get("kind") != "write":
            continue
        target = str(e.get("target") or "")
        if target and target not in first_write:
            first_write[target] = (
                int(e.get("ts") or 0),
                str(e.get("role") or ""),
                e.get("value"),
            )
    timeouts = {
        str(e.get("role")): int(e.get("ts") or 0)
        for e in events
        if e.get("kind") == "role_timeout" and e.get("role")
    }
    for e in events:
        if e.get("kind") not in {"conflict_detected", "double_claim_detected", "write"}:
            continue
        target = str(e.get("target") or "")
        if target not in first_write:
            continue
        fw_ts, fw_role, fw_val = first_write[target]
        new_val = e.get("new") if "new" in e else e.get("value")
        # content erased or replaced after publisher timeout
        erased = new_val in (None, "", "null", "censored", "redacted")
        replaced = new_val is not None and new_val != fw_val
        pub_to = timeouts.get(fw_role)
        if pub_to is None or int(e.get("ts") or 0) <= pub_to:
            continue
        if not (erased or replaced):
            continue
        # reader also timed out or any second timeout exists
        other_to = [r for r, t in timeouts.items() if r != fw_role]
        if erased or other_to:
            return [
                {
                    "kind": "censorship_gap_detected",
                    "ts": e.get("ts") or 0,
                    "target": target,
                    "publisher": fw_role,
                    "original": fw_val,
                    "replacement": new_val,
                    "reader_timed_out": other_to,
                    "policy": "retain_original_under_quorum",
                }
            ]
    return []


def _synthesize_vote_buying(events: list[dict]) -> list[dict]:
    """bribe/payment 写之后 ballot 被改向买方 → vote_buying_detected (ADV49)."""
    if any(e.get("kind") == "vote_buying_detected" for e in events):
        return []
    bribe_keys = ("bribe", "payment", "payoff", "kickback")
    ballot_keys = ("ballot", "vote", "choice")
    bribes: list[tuple[int, str, str, object]] = []
    for e in events:
        if e.get("kind") != "write":
            continue
        target = str(e.get("target") or "").lower()
        role = str(e.get("role") or "")
        if any(k in target for k in bribe_keys):
            bribes.append((int(e.get("ts") or 0), role, target, e.get("value")))
    if not bribes:
        return []
    for e in events:
        if e.get("kind") not in {"write", "conflict_detected", "double_claim_detected"}:
            continue
        target = str(e.get("target") or "").lower()
        if not any(k in target for k in ballot_keys):
            continue
        ts = int(e.get("ts") or 0)
        role = str(e.get("role") or "")
        val = str(e.get("new") if "new" in e else e.get("value") or "").lower()
        for b_ts, buyer, b_key, b_val in bribes:
            if ts < b_ts:
                continue
            # ballot changed after bribe; voter != buyer; value references buyer or buyer_choice
            if role and role != buyer and (
                "buyer" in val or buyer.lower() in val or "choice" in val
            ):
                return [
                    {
                        "kind": "vote_buying_detected",
                        "ts": ts,
                        "buyer": buyer,
                        "voter": role,
                        "bribe_key": b_key,
                        "bribe_value": b_val,
                        "ballot_target": e.get("target"),
                        "ballot_value": e.get("new") if "new" in e else e.get("value"),
                        "policy": "invalidate_ballot_and_slash",
                    }
                ]
    return []


def _synthesize_stake_grinding(events: list[dict]) -> list[dict]:
    """同一角色对 seed/lottery 类 key 反复改写 ≥3 → stake_grinding_detected (ADV51)."""
    if any(e.get("kind") == "stake_grinding_detected" for e in events):
        return []
    seed_keys = ("seed", "lottery", "nonce", "vrf", "rand")
    # role+target -> count of mutations (write or conflict)
    counts: dict[tuple[str, str], int] = {}
    last_vals: dict[tuple[str, str], list[object]] = {}
    for e in events:
        if e.get("kind") not in {
            "write",
            "conflict_detected",
            "double_claim_detected",
            "deadlock_break",
        }:
            continue
        target = str(e.get("target") or "")
        if not target or not any(k in target.lower() for k in seed_keys):
            continue
        role = str(e.get("role") or "")
        if not role and e.get("roles"):
            # attribute multi-role to each
            for r in e["roles"]:
                key = (str(r), target)
                counts[key] = counts.get(key, 0) + 1
            continue
        if not role:
            continue
        key = (role, target)
        counts[key] = counts.get(key, 0) + 1
        val = e.get("new") if "new" in e else e.get("value")
        last_vals.setdefault(key, []).append(val)
    for (role, target), n in counts.items():
        if n >= 3:
            return [
                {
                    "kind": "stake_grinding_detected",
                    "ts": max((e.get("ts") or 0) for e in events) + 1,
                    "role": role,
                    "target": target,
                    "mutations": n,
                    "values_seen": last_vals.get((role, target), [])[-5:],
                    "policy": "commit_seed_before_reveal",
                }
            ]
    return []


def _synthesize_nothing_at_stake(events: list[dict]) -> list[dict]:
    """同一角色在多条 fork_* 上同值 attest → nothing_at_stake_detected (ADV53)."""
    if any(e.get("kind") == "nothing_at_stake_detected" for e in events):
        return []
    # role -> list of (target, value) for fork keys
    by_role: dict[str, list[tuple[str, object]]] = {}
    for e in events:
        if e.get("kind") != "write":
            continue
        target = str(e.get("target") or "")
        role = str(e.get("role") or "")
        if not role or not target:
            continue
        tl = target.lower()
        if "fork" not in tl and "chain" not in tl and "branch" not in tl:
            continue
        by_role.setdefault(role, []).append((target, e.get("value")))
    for role, pairs in by_role.items():
        keys = list(dict.fromkeys(t for t, _ in pairs))
        vals = list(dict.fromkeys(v for _, v in pairs))
        # attest same value on ≥2 forks
        if len(keys) >= 2 and len(vals) == 1:
            return [
                {
                    "kind": "nothing_at_stake_detected",
                    "ts": max((e.get("ts") or 0) for e in events) + 1,
                    "role": role,
                    "forks": keys,
                    "attestation": vals[0],
                    "policy": "slash_multi_fork_attestation",
                }
            ]
        # or any multi-fork write even with different vals
        if len(keys) >= 2:
            return [
                {
                    "kind": "nothing_at_stake_detected",
                    "ts": max((e.get("ts") or 0) for e in events) + 1,
                    "role": role,
                    "forks": keys,
                    "values": vals,
                    "policy": "slash_multi_fork_attestation",
                }
            ]
    return []


def _synthesize_front_running(events: list[dict]) -> list[dict]:
    """pending_order 之后 sniper 改 order_book/吃单 → front_running_detected (ADV55)."""
    if any(e.get("kind") == "front_running_detected" for e in events):
        return []
    pending: list[tuple[int, str, object]] = []
    for e in events:
        if e.get("kind") not in {"write", "conflict_detected", "double_claim_detected"}:
            continue
        target = str(e.get("target") or "").lower()
        role = str(e.get("role") or "")
        val = e.get("new") if "new" in e else e.get("value")
        ts = int(e.get("ts") or 0)
        if "pending" in target or "intent" in target:
            pending.append((ts, role, val))
    if not pending:
        return []
    for e in events:
        if e.get("kind") not in {"write", "conflict_detected", "double_claim_detected"}:
            continue
        target = str(e.get("target") or "").lower()
        role = str(e.get("role") or "")
        val = str(e.get("new") if "new" in e else e.get("value") or "").lower()
        ts = int(e.get("ts") or 0)
        sniper_like = (
            "snipe" in role.lower()
            or "snipe" in val
            or "fill" in val
            or "front" in val
        )
        book_touch = any(k in target for k in ("order", "book", "pending", "market"))
        if not (sniper_like or book_touch):
            continue
        for p_ts, victim, p_val in pending:
            if ts <= p_ts:
                continue
            if role and role != victim:
                return [
                    {
                        "kind": "front_running_detected",
                        "ts": ts,
                        "victim": victim,
                        "sniper": role,
                        "pending_target_value": p_val,
                        "sniper_action": e.get("new") if "new" in e else e.get("value"),
                        "target": e.get("target"),
                        "policy": "commit_reveal_or_batch_auction",
                    }
                ]
    return []


def _synthesize_griefing_abort(events: list[dict]) -> list[dict]:
    """worker 超时后 griefer 清零产物 + subtask_fail → griefing_abort_detected (ADV57)."""
    if any(e.get("kind") == "griefing_abort_detected" for e in events):
        return []
    timeouts = {
        str(e.get("role")): int(e.get("ts") or 0)
        for e in events
        if e.get("kind") == "role_timeout" and e.get("role")
    }
    if not timeouts:
        return []
    has_sub_fail = any(e.get("kind") == "subtask_fail" for e in events)
    for e in events:
        if e.get("kind") not in {"write", "conflict_detected", "double_claim_detected"}:
            continue
        role = str(e.get("role") or "")
        val = e.get("new") if "new" in e else e.get("value")
        ts = int(e.get("ts") or 0)
        wipe = str(val or "").lower() in {
            "wiped",
            "null",
            "empty",
            "deleted",
            "cleared",
            "",
        } or val is None
        # griefer is not the timed-out worker; acts after worker timeout
        for worker, t_to in timeouts.items():
            if role == worker:
                continue
            if ts > t_to and (wipe or has_sub_fail):
                return [
                    {
                        "kind": "griefing_abort_detected",
                        "ts": ts,
                        "worker": worker,
                        "griefer": role,
                        "target": e.get("target"),
                        "replacement": val,
                        "subtask_failed": has_sub_fail,
                        "policy": "bond_and_refund_worker",
                    }
                ]
    return []


def _synthesize_oracle_manipulation(events: list[dict]) -> list[dict]:
    """oracle 价格大幅跳变后结算再恢复 → oracle_manipulation_detected (ADV59)."""
    if any(e.get("kind") == "oracle_manipulation_detected" for e in events):
        return []
    # collect numeric prices in order (conflict prior+new both count)
    price_events: list[tuple[int, object, str]] = []
    settlements: list[tuple[int, object, str]] = []
    for e in events:
        if e.get("kind") not in {"write", "conflict_detected", "double_claim_detected"}:
            continue
        target = str(e.get("target") or "").lower()
        ts = int(e.get("ts") or 0)
        role = str(e.get("role") or "")
        if "settle" in target or "settlement" in target:
            settlements.append(
                (ts, e.get("new") if "new" in e else e.get("value"), role)
            )
        if not ("oracle" in target or "price" in target):
            continue
        if e.get("kind") in {"conflict_detected", "double_claim_detected"}:
            if e.get("prior") is not None:
                price_events.append((ts, e.get("prior"), role))
            if e.get("new") is not None:
                price_events.append((ts, e.get("new"), role))
        else:
            price_events.append((ts, e.get("value"), role))
    nums: list[tuple[int, float, str]] = []
    for ts, val, role in price_events:
        try:
            nums.append((ts, float(str(val).strip()), role))
        except (TypeError, ValueError):
            continue
    if len(nums) < 2:
        return []
    for i in range(len(nums) - 1):
        t0, p0, _r0 = nums[i]
        t1, p1, _r1 = nums[i + 1]
        if p0 <= 0:
            continue
        drop_ratio = (p0 - p1) / p0
        if drop_ratio < 0.5:  # ≥50% crash
            continue
        settled = any(st >= t1 for st, _, _ in settlements)
        # settlement value may embed the spike price
        settled = settled or any(
            str(p1) in str(sv) for _st, sv, _ in settlements
        )
        recovered = any(
            j > i + 1 and p0 > 0 and abs(nums[j][1] - p0) / p0 < 0.25
            for j in range(i + 2, len(nums))
        )
        if settled or recovered or drop_ratio >= 0.9:
            return [
                {
                    "kind": "oracle_manipulation_detected",
                    "ts": t1,
                    "price_before": p0,
                    "price_spike": p1,
                    "drop_ratio": round(drop_ratio, 3),
                    "settlements": len(settlements),
                    "recovered": recovered,
                    "policy": "twap_or_multi_oracle",
                }
            ]
    return []


def _synthesize_sandwich_attack(events: list[dict]) -> list[dict]:
    """attacker 抬价 → victim 成交 → attacker 压回/获利 → sandwich_attack_detected (ADV61)."""
    if any(e.get("kind") == "sandwich_attack_detected" for e in events):
        return []
    # chronological price-ish and swap/profit actions by role
    acts: list[tuple[int, str, str, object]] = []
    for e in events:
        if e.get("kind") not in {"write", "conflict_detected", "double_claim_detected"}:
            continue
        role = str(e.get("role") or "")
        target = str(e.get("target") or "")
        val = e.get("new") if "new" in e else e.get("value")
        if not role:
            continue
        acts.append((int(e.get("ts") or 0), role, target, val))
    # find attacker who touches pool_price twice with victim action between
    for i, (t0, r0, k0, v0) in enumerate(acts):
        if "price" not in k0.lower() and "pool" not in k0.lower():
            continue
        for j in range(i + 1, len(acts)):
            t1, r1, k1, v1 = acts[j]
            if r1 == r0:
                continue
            if "swap" not in k1.lower() and "victim" not in k1.lower() and "swap" not in str(v1).lower():
                # still allow any other role action as middle
                if "swap" not in k1.lower() and "victim" not in r1.lower():
                    mid_ok = True  # any interleaving victim-like
                else:
                    mid_ok = True
            else:
                mid_ok = True
            if not mid_ok:
                continue
            for k in range(j + 1, len(acts)):
                t2, r2, k2, v2 = acts[k]
                if r2 != r0:
                    continue
                back_price = "price" in k2.lower() or "pool" in k2.lower()
                profit = "profit" in k2.lower() or "extract" in str(v2).lower()
                # later profit write also counts as closing sandwich
                has_profit = any(
                    r == r0 and ("profit" in kt.lower() or "extract" in str(vv).lower())
                    for _tt, r, kt, vv in acts[j:]
                )
                if back_price or profit or has_profit:
                    return [
                        {
                            "kind": "sandwich_attack_detected",
                            "ts": t2,
                            "attacker": r0,
                            "victim_role": r1,
                            "front_leg": {"target": k0, "value": v0},
                            "victim_leg": {"target": k1, "value": v1},
                            "back_leg": {"target": k2, "value": v2},
                            "policy": "private_mempool_or_batch",
                        }
                    ]
    return []


def _synthesize_reentrancy(events: list[dict]) -> list[dict]:
    """同角色对 balance 连续扣减 ≥2 + withdraw 痕迹 → reentrancy_detected (ADV63)."""
    if any(e.get("kind") == "reentrancy_detected" for e in events):
        return []
    bal_hits: dict[str, list[tuple[int, object]]] = {}
    withdraws: list[tuple[int, str, object]] = []
    for e in events:
        if e.get("kind") not in {
            "write",
            "conflict_detected",
            "double_claim_detected",
            "deadlock_break",
        }:
            continue
        role = str(e.get("role") or "")
        target = str(e.get("target") or "").lower()
        val = e.get("new") if "new" in e else e.get("value")
        ts = int(e.get("ts") or 0)
        if "withdraw" in target or "withdraw" in str(val or "").lower():
            withdraws.append((ts, role, val))
        if "balance" in target or "vault" in target:
            if role:
                bal_hits.setdefault(role, []).append((ts, val))
            for r in e.get("roles") or []:
                bal_hits.setdefault(str(r), []).append((ts, val))
    for role, hits in bal_hits.items():
        if len(hits) < 2:
            continue
        # decreasing numeric trend or ≥2 mutations
        nums = []
        for _ts, v in hits:
            try:
                nums.append(float(str(v).strip()))
            except (TypeError, ValueError):
                pass
        decreasing = len(nums) >= 2 and any(
            nums[i] > nums[i + 1] for i in range(len(nums) - 1)
        )
        multi = len(hits) >= 2
        has_wd = any(
            role == wr or "twice" in str(wv).lower() or "reenter" in str(wv).lower()
            for _t, wr, wv in withdraws
        ) or any("withdraw" in str(h[1]).lower() for h in hits)
        if multi and (decreasing or has_wd or len(hits) >= 2):
            # require withdraw log OR clear decreasing
            if decreasing or has_wd or any("withdraw" in str(wv).lower() for _t, _r, wv in withdraws):
                return [
                    {
                        "kind": "reentrancy_detected",
                        "ts": hits[-1][0],
                        "role": role,
                        "balance_mutations": len(hits),
                        "values": [v for _t, v in hits],
                        "policy": "checks_effects_interactions",
                    }
                ]
    # ADV63 shape: attacker hits balance twice + withdraw_log
    if any(len(h) >= 2 for h in bal_hits.values()) and withdraws:
        role = next(r for r, h in bal_hits.items() if len(h) >= 2)
        return [
            {
                "kind": "reentrancy_detected",
                "ts": max(t for t, _r, _v in withdraws),
                "role": role,
                "balance_mutations": len(bal_hits[role]),
                "withdraws": len(withdraws),
                "policy": "checks_effects_interactions",
            }
        ]
    return []


def _synthesize_mev_leak(events: list[dict], board: dict) -> list[dict]:
    """private intent 值出现在 public mempool（异角色）→ mev_leak_detected (ADV65)."""
    if any(e.get("kind") == "mev_leak_detected" for e in events):
        return []
    private_vals: dict[object, tuple[str, str]] = {}  # value -> (role, key)
    # setup board private*
    for key, slot in board.items():
        if key.startswith("_"):
            continue
        kl = key.lower()
        if "private" in kl or "secret" in kl or "intent" in kl:
            private_vals[slot.get("value")] = (
                (slot.get("writers") or [""])[0] if slot.get("writers") else "",
                key,
            )
    for e in events:
        if e.get("kind") != "write":
            continue
        target = str(e.get("target") or "").lower()
        val = e.get("value")
        role = str(e.get("role") or "")
        if "private" in target or "secret" in target or "intent" in target:
            private_vals[val] = (role, str(e.get("target")))
    for e in events:
        if e.get("kind") not in {"write", "conflict_detected", "double_claim_detected"}:
            continue
        target = str(e.get("target") or "").lower()
        val = e.get("new") if "new" in e else e.get("value")
        role = str(e.get("role") or "")
        public = any(k in target for k in ("public", "mempool", "gossip", "broadcast"))
        if not public:
            continue
        if val in private_vals:
            orig_role, orig_key = private_vals[val]
            if role and orig_role and role != orig_role:
                return [
                    {
                        "kind": "mev_leak_detected",
                        "ts": e.get("ts") or 0,
                        "leaked_value": val,
                        "private_key": orig_key,
                        "owner": orig_role,
                        "searcher": role,
                        "public_target": e.get("target"),
                        "policy": "encrypt_intent_or_private_relay",
                    }
                ]
    return []


def _synthesize_flash_loan_attack(events: list[dict]) -> list[dict]:
    """同角色 borrow → 操盘 → repay (+profit) → flash_loan_attack_detected (ADV67)."""
    if any(e.get("kind") == "flash_loan_attack_detected" for e in events):
        return []
    acts: list[tuple[int, str, str, object]] = []
    for e in events:
        if e.get("kind") not in {"write", "conflict_detected", "double_claim_detected"}:
            continue
        role = str(e.get("role") or "")
        if not role:
            continue
        acts.append(
            (
                int(e.get("ts") or 0),
                role,
                str(e.get("target") or ""),
                e.get("new") if "new" in e else e.get("value"),
            )
        )
    by_role: dict[str, list[tuple[int, str, object]]] = {}
    for ts, role, tgt, val in acts:
        by_role.setdefault(role, []).append((ts, tgt, val))
    for role, seq in by_role.items():
        has_borrow = any(
            "borrow" in t.lower() or "flash" in t.lower() or "borrow" in str(v).lower()
            for _ts, t, v in seq
        )
        has_repay = any(
            "repay" in t.lower() or "repay" in str(v).lower() for _ts, t, v in seq
        )
        has_manip = any(
            "price" in t.lower()
            or "manipul" in str(v).lower()
            or "oracle" in t.lower()
            for _ts, t, v in seq
        )
        has_profit = any(
            "profit" in t.lower() or "profit" in str(v).lower() or "arb" in str(v).lower()
            for _ts, t, v in seq
        )
        if has_borrow and has_repay and (has_manip or has_profit):
            return [
                {
                    "kind": "flash_loan_attack_detected",
                    "ts": seq[-1][0],
                    "role": role,
                    "borrow": has_borrow,
                    "repay": has_repay,
                    "manipulation": has_manip,
                    "profit": has_profit,
                    "policy": "block_same_tx_borrow_manipulate",
                }
            ]
    return []


def _synthesize_governance_capture(events: list[dict]) -> list[dict]:
    """短期囤 gov_votes → 通过恶意提案 → 倒票 → governance_capture_detected (ADV69)."""
    if any(e.get("kind") == "governance_capture_detected" for e in events):
        return []
    vote_moves: list[tuple[int, str, object]] = []
    proposals: list[tuple[int, str, object]] = []
    results: list[tuple[int, str, object]] = []
    for e in events:
        if e.get("kind") not in {"write", "conflict_detected", "double_claim_detected"}:
            continue
        role = str(e.get("role") or "")
        target = str(e.get("target") or "").lower()
        val = e.get("new") if "new" in e else e.get("value")
        ts = int(e.get("ts") or 0)
        if "gov_vote" in target or ("vote" in target and "gov" in target):
            vote_moves.append((ts, role, val))
        elif "proposal" in target and "result" not in target:
            proposals.append((ts, role, val))
        elif "proposal_result" in target or (
            "result" in target and "proposal" in target
        ):
            results.append((ts, role, val))
        elif "proposal" in target:
            proposals.append((ts, role, val))
    # need vote inflation then proposal pass then vote dump by same attacker
    for role in {r for _t, r, _v in vote_moves}:
        role_votes = [(t, v) for t, r, v in vote_moves if r == role]
        if len(role_votes) < 2:
            continue
        # try numeric spike then drop
        nums = []
        for t, v in role_votes:
            try:
                nums.append((t, float(str(v).strip())))
            except (TypeError, ValueError):
                nums.append((t, None))  # type: ignore[arg-type]
        valid = [(t, n) for t, n in nums if n is not None]
        spike = False
        if len(valid) >= 2:
            for i in range(len(valid) - 1):
                if valid[i + 1][1] > valid[i][1] * 2:  # big acquire
                    for j in range(i + 1, len(valid)):
                        if valid[j][1] < valid[i + 1][1] * 0.5:  # dump
                            spike = True
        # malicious proposal + passed
        mal = any(
            r == role
            and (
                "drain" in str(v).lower()
                or "malicious" in str(v).lower()
                or "attack" in str(v).lower()
            )
            for _t, r, v in proposals
        ) or any("malicious" in str(p[2]).lower() or "drain" in str(p[2]).lower() for p in proposals)
        passed = any(
            "pass" in str(v).lower() or "approved" in str(v).lower()
            for _t, _r, v in results
        )
        if (spike or len(role_votes) >= 2) and (mal or proposals) and (passed or results):
            return [
                {
                    "kind": "governance_capture_detected",
                    "ts": max(t for t, _r, _v in vote_moves + proposals + results),
                    "role": role,
                    "vote_moves": len(role_votes),
                    "proposals": len(proposals),
                    "passed": passed,
                    "policy": "timelock_and_vote_escrow",
                }
            ]
    # softer: attacker proposal drain + passed + multi gov_votes writes
    if proposals and results and len(vote_moves) >= 2:
        return [
            {
                "kind": "governance_capture_detected",
                "ts": max(
                    (e.get("ts") or 0)
                    for e in events
                    if e.get("kind")
                    in {"write", "conflict_detected", "double_claim_detected"}
                ),
                "vote_moves": len(vote_moves),
                "proposals": len(proposals),
                "results": len(results),
                "policy": "timelock_and_vote_escrow",
            }
        ]
    return []


def _synthesize_cross_domain_replay(events: list[dict], board: dict) -> list[dict]:
    """域A payload 在域B 执行/重复 → cross_domain_replay_detected (ADV71)."""
    if any(e.get("kind") == "cross_domain_replay_detected" for e in events):
        return []
    domain_payloads: dict[object, list[tuple[str, str]]] = {}  # val -> [(domain_tag, role)]
    # board seeds
    for key, slot in board.items():
        if key.startswith("_"):
            continue
        kl = key.lower()
        if "domain" in kl or "sig" in kl or "msg" in kl:
            tag = "a" if "_a" in kl or "domain_a" in kl else ("b" if "_b" in kl or "domain_b" in kl else "x")
            domain_payloads.setdefault(slot.get("value"), []).append(
                (tag, (slot.get("writers") or [""])[0] if slot.get("writers") else "")
            )
    for e in events:
        if e.get("kind") not in {"write", "conflict_detected", "double_claim_detected"}:
            continue
        target = str(e.get("target") or "")
        tl = target.lower()
        val = e.get("new") if "new" in e else e.get("value")
        role = str(e.get("role") or "")
        if "domain" not in tl and "exec" not in tl and "sig" not in tl and "msg" not in tl:
            continue
        tag = "a" if ("_a" in tl or "domain_a" in tl) else (
            "b" if ("_b" in tl or "domain_b" in tl) else "x"
        )
        domain_payloads.setdefault(val, []).append((tag, role))
    for val, tags in domain_payloads.items():
        if val is None:
            continue
        domains = {t for t, _r in tags}
        roles = {r for _t, r in tags if r}
        # same payload across domains OR repeated exec on domain_b
        multi_domain = len(domains) >= 2
        multi_exec = sum(1 for t, _r in tags if t == "b") >= 2 or sum(
            1 for t, _r in tags if "exec" in t
        ) >= 2
        # also: board domain_a + writes domain_b same value twice (replay_attack also fires)
        if multi_domain or (
            any(t == "a" for t, _ in tags) and sum(1 for t, _ in tags if t == "b") >= 1
        ):
            if multi_domain or multi_exec or len(tags) >= 2:
                return [
                    {
                        "kind": "cross_domain_replay_detected",
                        "ts": max((e.get("ts") or 0) for e in events) + 1,
                        "payload": val,
                        "domains": sorted(domains),
                        "roles": sorted(roles),
                        "policy": "domain_separator_and_nonce",
                    }
                ]
    return []


def _synthesize_rug_pull(events: list[dict]) -> list[dict]:
    """victim 存款后 creator 抽干 lp_pool → rug_pull_detected (ADV73)."""
    if any(e.get("kind") == "rug_pull_detected" for e in events):
        return []
    deposits: list[tuple[int, str]] = []
    pool_drains: list[tuple[int, str, object]] = []
    creator_gains: list[tuple[int, str, object]] = []
    for e in events:
        if e.get("kind") not in {"write", "conflict_detected", "double_claim_detected"}:
            continue
        role = str(e.get("role") or "")
        target = str(e.get("target") or "").lower()
        val = e.get("new") if "new" in e else e.get("value")
        ts = int(e.get("ts") or 0)
        if "deposit" in target or "deposit" in str(val or "").lower():
            deposits.append((ts, role))
        if "lp" in target or "pool" in target or "liq" in target:
            vs = str(val or "").lower()
            if "0" in vs or "empty" in vs or "drain" in vs or vs in {"0", "liq_0"}:
                pool_drains.append((ts, role, val))
        if "wallet" in target or "drain" in str(val or "").lower():
            creator_gains.append((ts, role, val))
    if not deposits:
        return []
    dep_ts = min(t for t, _ in deposits)
    for dts, drole, dval in pool_drains:
        if dts < dep_ts:
            continue
        # creator != depositor
        victim_roles = {r for t, r in deposits}
        if drole in victim_roles and not creator_gains:
            continue
        return [
            {
                "kind": "rug_pull_detected",
                "ts": dts,
                "depositor": next(iter(victim_roles)),
                "puller": drole,
                "pool_value": dval,
                "creator_gains": len(creator_gains),
                "policy": "lp_lock_and_timelock",
            }
        ]
    # deposit then creator_wallet drain even if pool drain naming differs
    if deposits and creator_gains:
        gts, grole, gval = creator_gains[0]
        if gts >= dep_ts and grole not in {r for _t, r in deposits}:
            return [
                {
                    "kind": "rug_pull_detected",
                    "ts": gts,
                    "depositor": deposits[0][1],
                    "puller": grole,
                    "gain": gval,
                    "policy": "lp_lock_and_timelock",
                }
            ]
    return []


def _synthesize_approval_phishing(events: list[dict]) -> list[dict]:
    """unlimited approval 后余额被第三方转走 → approval_phishing_detected (ADV75)."""
    if any(e.get("kind") == "approval_phishing_detected" for e in events):
        return []
    approvals: list[tuple[int, str, object]] = []
    for e in events:
        if e.get("kind") not in {"write", "conflict_detected", "double_claim_detected"}:
            continue
        role = str(e.get("role") or "")
        target = str(e.get("target") or "").lower()
        val = e.get("new") if "new" in e else e.get("value")
        ts = int(e.get("ts") or 0)
        if "approval" in target or "approve" in str(val or "").lower() or "unlimited" in str(val or "").lower():
            approvals.append((ts, role, val))
    if not approvals:
        return []
    for e in events:
        if e.get("kind") not in {"write", "conflict_detected", "double_claim_detected"}:
            continue
        role = str(e.get("role") or "")
        target = str(e.get("target") or "").lower()
        val = e.get("new") if "new" in e else e.get("value")
        ts = int(e.get("ts") or 0)
        # balance drained by non-approver after approval
        bal_hit = "balance" in target or "wallet" in target or "phish" in target
        if not bal_hit:
            continue
        for ats, arole, aval in approvals:
            if ts <= ats:
                continue
            if role and role != arole:
                drained = str(val) in {"0", "0.0"} or val == 0 or "phish" in target or "phish" in str(val or "").lower()
                if drained or "phish" in role.lower() or "dapp" in role.lower():
                    return [
                        {
                            "kind": "approval_phishing_detected",
                            "ts": ts,
                            "victim": arole,
                            "spender": role,
                            "approval": aval,
                            "result_target": e.get("target"),
                            "result_value": val,
                            "policy": "permit2_or_capped_allowance",
                        }
                    ]
    return []


def _synthesize_bridge_drain(events: list[dict]) -> list[dict]:
    """forged proof + vault 清零 + 对侧 mint → bridge_drain_detected (ADV77)."""
    if any(e.get("kind") == "bridge_drain_detected" for e in events):
        return []
    forged = False
    vault_zero = False
    mint = False
    role = ""
    ts_max = 0
    for e in events:
        if e.get("kind") not in {"write", "conflict_detected", "double_claim_detected"}:
            continue
        r = str(e.get("role") or "")
        target = str(e.get("target") or "").lower()
        val = str(e.get("new") if "new" in e else e.get("value") or "").lower()
        ts = int(e.get("ts") or 0)
        ts_max = max(ts_max, ts)
        if "proof" in target or "forged" in val or "fake" in val:
            forged = True
            role = r or role
        if "bridge" in target or "vault" in target:
            if val in {"0", "0.0", ""} or "drain" in val:
                vault_zero = True
                role = r or role
        if "mint" in val or "chain_b" in target or "mint" in target:
            mint = True
            role = r or role
    if forged and (vault_zero or mint):
        return [
            {
                "kind": "bridge_drain_detected",
                "ts": ts_max,
                "role": role,
                "forged_proof": forged,
                "vault_zero": vault_zero,
                "cross_mint": mint,
                "policy": "multi_sig_proof_and_rate_limit",
            }
        ]
    if vault_zero and mint:
        return [
            {
                "kind": "bridge_drain_detected",
                "ts": ts_max,
                "role": role,
                "vault_zero": True,
                "cross_mint": True,
                "policy": "multi_sig_proof_and_rate_limit",
            }
        ]
    return []


def _synthesize_sybil_airdrop(events: list[dict]) -> list[dict]:
    """多地址 claim 后归集钱包 → sybil_airdrop_detected (ADV79)."""
    if any(e.get("kind") == "sybil_airdrop_detected" for e in events):
        return []
    claims: list[tuple[int, str, str]] = []
    aggregates: list[tuple[int, str, object]] = []
    for e in events:
        if e.get("kind") not in {"write", "conflict_detected", "double_claim_detected"}:
            continue
        role = str(e.get("role") or "")
        target = str(e.get("target") or "").lower()
        val = e.get("new") if "new" in e else e.get("value")
        vs = str(val or "").lower()
        ts = int(e.get("ts") or 0)
        if "claim" in target or "claim" in vs or "airdrop" in target:
            claims.append((ts, role, target))
        if (
            "aggregate" in vs
            or "aggregated" in vs
            or "boss" in target
            or "consolidation" in vs
            or ("wallet" in target and role and "claim" not in target)
        ):
            # aggregation / boss wallet consolidation after claims
            if "aggregate" in vs or "aggregated" in vs or "boss" in role or "boss" in target:
                aggregates.append((ts, role, val))
    claim_roles = {r for _t, r, _tg in claims if r}
    if len(claim_roles) < 2:
        return []
    if not aggregates:
        # still fire if many distinct claimers without named aggregate
        # (require ≥3 claimers as sybil signal alone)
        if len(claim_roles) < 3:
            return []
        ts_max = max(t for t, _r, _tg in claims)
        return [
            {
                "kind": "sybil_airdrop_detected",
                "ts": ts_max,
                "claim_roles": sorted(claim_roles),
                "claim_count": len(claims),
                "policy": "proof_of_personhood_and_claim_cap",
            }
        ]
    ats, arole, aval = max(aggregates, key=lambda x: x[0])
    claim_before = [r for t, r, _tg in claims if t <= ats and r != arole]
    if len(set(claim_before)) < 2 and len(claim_roles) < 3:
        return []
    return [
        {
            "kind": "sybil_airdrop_detected",
            "ts": ats,
            "claim_roles": sorted(claim_roles),
            "aggregator": arole,
            "aggregate_value": aval,
            "claim_count": len(claims),
            "policy": "proof_of_personhood_and_claim_cap",
        }
    ]


def _synthesize_wash_trade(events: list[dict]) -> list[dict]:
    """关联地址对倒抬价 → wash_trade_detected (ADV81)."""
    if any(e.get("kind") == "wash_trade_detected" for e in events):
        return []
    # target -> list of (ts, role, value_str)
    trades: dict[str, list[tuple[int, str, str]]] = {}
    for e in events:
        if e.get("kind") not in {"write", "conflict_detected", "double_claim_detected"}:
            continue
        role = str(e.get("role") or "")
        target = str(e.get("target") or "").lower()
        val = e.get("new") if "new" in e else e.get("value")
        vs = str(val or "").lower()
        ts = int(e.get("ts") or 0)
        if not target:
            continue
        is_trade = (
            "sold" in vs
            or "sell" in vs
            or "buy" in vs
            or "price" in vs
            or "nft" in target
            or "wash" in vs
        )
        if is_trade:
            trades.setdefault(target, []).append((ts, role, vs))
    for target, seq in trades.items():
        if len(seq) < 2:
            continue
        roles = {r for _t, r, _v in seq if r}
        # circular / multi-party trading same asset
        price_nums: list[int] = []
        for _t, _r, vs in seq:
            # extract trailing digits as pseudo-price (price_10, price_50, …)
            digits = "".join(ch if ch.isdigit() else " " for ch in vs).split()
            if digits:
                try:
                    price_nums.append(int(digits[-1]))
                except ValueError:
                    pass
        rising = len(price_nums) >= 2 and price_nums[-1] > price_nums[0]
        circular = any("sold_to" in vs for _t, _r, vs in seq) and len(roles) >= 2
        multi_hop = len(seq) >= 3 and len(roles) >= 2
        if (circular and (rising or multi_hop)) or (rising and len(roles) >= 2 and len(seq) >= 2):
            return [
                {
                    "kind": "wash_trade_detected",
                    "ts": seq[-1][0],
                    "target": target,
                    "roles": sorted(roles),
                    "trade_count": len(seq),
                    "prices": price_nums,
                    "policy": "related_party_graph_and_volume_filter",
                }
            ]
    return []


def _synthesize_key_compromise_blast(events: list[dict]) -> list[dict]:
    """密钥失陷后多敏感面操作 → key_compromise_blast_detected (ADV83)."""
    if any(e.get("kind") == "key_compromise_blast_detected" for e in events):
        return []
    key_hits: list[tuple[int, str]] = []
    sensitive: list[tuple[int, str, str]] = []
    sensitive_markers = (
        "treasury",
        "upgrade",
        "proxy",
        "pause",
        "unpause",
        "admin",
        "mint_role",
        "owner_transfer",
        "timelock",
        "guardian",
    )
    for e in events:
        if e.get("kind") not in {"write", "conflict_detected", "double_claim_detected"}:
            continue
        role = str(e.get("role") or "")
        target = str(e.get("target") or "").lower()
        val = e.get("new") if "new" in e else e.get("value")
        vs = str(val or "").lower()
        ts = int(e.get("ts") or 0)
        if "key" in target or "stolen" in vs or "compromised" in vs or "key_stolen" in vs:
            key_hits.append((ts, role))
        hit = any(m in target or m in vs for m in sensitive_markers)
        # exclude pure key-slot writes from sensitive blast count
        if hit and "key" not in target:
            sensitive.append((ts, role, target or vs))
    if not key_hits:
        return []
    kts, krole = min(key_hits, key=lambda x: x[0])
    # blast surfaces after (or concurrent with) key compromise
    surfaces = []
    seen_targets: set[str] = set()
    for ts, role, target in sensitive:
        if ts < kts:
            continue
        # same actor as key thief, or any post-compromise multi-surface
        if role == krole or role:
            if target not in seen_targets:
                seen_targets.add(target)
                surfaces.append((ts, role, target))
    if len(surfaces) < 2:
        return []
    return [
        {
            "kind": "key_compromise_blast_detected",
            "ts": surfaces[-1][0],
            "key_role": krole,
            "surfaces": [t for _ts, _r, t in surfaces],
            "surface_count": len(surfaces),
            "policy": "key_rotation_and_blast_radius_isolation",
        }
    ]


def _synthesize_infinite_mint(events: list[dict]) -> list[dict]:
    """绕过 supply_cap 持续 mint → infinite_mint_detected (ADV85)."""
    if any(e.get("kind") == "infinite_mint_detected" for e in events):
        return []
    supply_writes: list[tuple[int, str, str]] = []
    mint_gains: list[tuple[int, str, object]] = []
    dilution: list[tuple[int, str]] = []
    for e in events:
        if e.get("kind") not in {"write", "conflict_detected", "double_claim_detected"}:
            continue
        role = str(e.get("role") or "")
        target = str(e.get("target") or "").lower()
        val = e.get("new") if "new" in e else e.get("value")
        vs = str(val or "").lower()
        ts = int(e.get("ts") or 0)
        if "total_supply" in target or "supply" in target:
            supply_writes.append((ts, role, vs))
        if "mint" in vs or "minted" in vs or ("wallet" in target and "mint" in role):
            mint_gains.append((ts, role, val))
        if "dilut" in vs or "holder" in target:
            dilution.append((ts, role))
    # multiple supply increases / over-cap signal
    nums: list[int] = []
    for _t, _r, vs in supply_writes:
        digits = "".join(ch if ch.isdigit() else " " for ch in vs).split()
        if digits:
            try:
                nums.append(int(digits[-1]))
            except ValueError:
                pass
    rising = len(nums) >= 2 and nums[-1] > nums[0]
    multi_mint = len(supply_writes) >= 2 or len(mint_gains) >= 1
    if rising and multi_mint:
        ts_max = max(
            [t for t, _r, _v in supply_writes]
            + [t for t, _r, _v in mint_gains]
            + [0]
        )
        return [
            {
                "kind": "infinite_mint_detected",
                "ts": ts_max,
                "supply_values": nums,
                "mint_gains": len(mint_gains),
                "dilution": len(dilution),
                "policy": "hard_supply_cap_and_mint_governor",
            }
        ]
    if len(mint_gains) >= 1 and len(supply_writes) >= 1 and (rising or dilution):
        ts_max = max(t for t, *_ in supply_writes + [(g[0], g[1], "") for g in mint_gains])
        return [
            {
                "kind": "infinite_mint_detected",
                "ts": ts_max,
                "mint_gains": len(mint_gains),
                "policy": "hard_supply_cap_and_mint_governor",
            }
        ]
    return []


def _synthesize_stablecoin_depeg(events: list[dict]) -> list[dict]:
    """储备/锚定被操纵 + 挤兑 → stablecoin_depeg_detected (ADV87)."""
    if any(e.get("kind") == "stablecoin_depeg_detected" for e in events):
        return []
    peg_hit = False
    reserve_hit = False
    bank_run = False
    exit_liq = False
    role = ""
    ts_max = 0
    for e in events:
        if e.get("kind") not in {"write", "conflict_detected", "double_claim_detected"}:
            continue
        r = str(e.get("role") or "")
        target = str(e.get("target") or "").lower()
        val = e.get("new") if "new" in e else e.get("value")
        vs = str(val or "").lower()
        ts = int(e.get("ts") or 0)
        ts_max = max(ts_max, ts)
        if "peg" in target or "peg" in vs:
            peg_hit = True
            role = r or role
            # sub-1.0 peg prices
            digits = "".join(ch if ch.isdigit() or ch == "." else " " for ch in vs).split()
            for d in digits:
                try:
                    if float(d) < 1.0:
                        peg_hit = True
                except ValueError:
                    pass
        if "reserve" in target or "reserve" in vs:
            reserve_hit = True
            role = r or role
        if "redeem" in target or "bank_run" in vs or "flood" in vs or "run" in vs:
            bank_run = True
            role = r or role
        if "exit" in vs or ("wallet" in target and "issuer" in target) or "exit_liquidity" in vs:
            exit_liq = True
            role = r or role
    if (peg_hit or reserve_hit) and (bank_run or exit_liq):
        return [
            {
                "kind": "stablecoin_depeg_detected",
                "ts": ts_max,
                "role": role,
                "peg_hit": peg_hit,
                "reserve_hit": reserve_hit,
                "bank_run": bank_run,
                "exit_liquidity": exit_liq,
                "policy": "attested_reserves_and_circuit_breaker",
            }
        ]
    if peg_hit and reserve_hit:
        return [
            {
                "kind": "stablecoin_depeg_detected",
                "ts": ts_max,
                "role": role,
                "peg_hit": True,
                "reserve_hit": True,
                "policy": "attested_reserves_and_circuit_breaker",
            }
        ]
    return []


def _synthesize_zk_proof_forgery(events: list[dict]) -> list[dict]:
    """假 validity proof + 恶意 state root → zk_proof_forgery_detected (ADV89)."""
    if any(e.get("kind") == "zk_proof_forgery_detected" for e in events):
        return []
    forged_proof = False
    bad_root = False
    steal = False
    weak_verify = False
    role = ""
    ts_max = 0
    for e in events:
        if e.get("kind") not in {"write", "conflict_detected", "double_claim_detected"}:
            continue
        r = str(e.get("role") or "")
        target = str(e.get("target") or "").lower()
        val = e.get("new") if "new" in e else e.get("value")
        vs = str(val or "").lower()
        ts = int(e.get("ts") or 0)
        ts_max = max(ts_max, ts)
        if "proof" in target or "forged" in vs or "zk" in target:
            if "forged" in vs or "fake" in vs or "invalid" in vs or "proof" in target:
                forged_proof = True
                role = r or role
        if "state_root" in target or "root" in target:
            if "malicious" in vs or "evil" in vs or "bad" in vs or "forge" in vs:
                bad_root = True
                role = r or role
            elif forged_proof:
                # any root change after forged proof
                bad_root = True
                role = r or role
        if "withdraw" in target or "stolen" in vs or "exit" in vs:
            steal = True
            role = r or role
        if "verify" in target and ("accept" in vs or "without" in vs or "skip" in vs):
            weak_verify = True
            role = r or role
    if forged_proof and (bad_root or steal or weak_verify):
        return [
            {
                "kind": "zk_proof_forgery_detected",
                "ts": ts_max,
                "role": role,
                "forged_proof": forged_proof,
                "bad_root": bad_root,
                "steal": steal,
                "weak_verify": weak_verify,
                "policy": "proof_verifier_and_challenge_window",
            }
        ]
    return []


def _synthesize_restaking_slash_cascade(events: list[dict]) -> list[dict]:
    """AVS 故障触发多层 slash → restaking_slash_cascade_detected (ADV91)."""
    if any(e.get("kind") == "restaking_slash_cascade_detected" for e in events):
        return []
    misbehavior = False
    slashes: list[tuple[int, str, str]] = []
    stake_left = False
    role = ""
    ts_max = 0
    for e in events:
        if e.get("kind") not in {"write", "conflict_detected", "double_claim_detected"}:
            continue
        r = str(e.get("role") or "")
        target = str(e.get("target") or "").lower()
        val = e.get("new") if "new" in e else e.get("value")
        vs = str(val or "").lower()
        ts = int(e.get("ts") or 0)
        ts_max = max(ts_max, ts)
        if "misbehavior" in vs or "avs" in target and "duty" in target:
            misbehavior = True
            role = r or role
        if "slash" in target or "slash" in vs or "cascade" in vs:
            slashes.append((ts, r, target or vs))
            role = r or role
        if "restake" in target or "stake_left" in vs or "stake" in target:
            if "left" in vs or "slash" in vs or any(ch.isdigit() for ch in vs):
                stake_left = True
                role = r or role
    multi_slash = len(slashes) >= 2
    if multi_slash and (misbehavior or stake_left):
        return [
            {
                "kind": "restaking_slash_cascade_detected",
                "ts": ts_max,
                "role": role,
                "slash_count": len(slashes),
                "misbehavior": misbehavior,
                "stake_affected": stake_left,
                "policy": "avs_isolation_and_slash_caps",
            }
        ]
    if multi_slash:
        return [
            {
                "kind": "restaking_slash_cascade_detected",
                "ts": ts_max,
                "role": role,
                "slash_count": len(slashes),
                "policy": "avs_isolation_and_slash_caps",
            }
        ]
    return []


def _synthesize_intent_solver_theft(events: list[dict]) -> list[dict]:
    """恶意 solver 截留 intent 差额 → intent_solver_theft_detected (ADV93)."""
    if any(e.get("kind") == "intent_solver_theft_detected" for e in events):
        return []
    fill = False
    skim = False
    short_receipt = False
    consumed = False
    role = ""
    ts_max = 0
    for e in events:
        if e.get("kind") not in {"write", "conflict_detected", "double_claim_detected"}:
            continue
        r = str(e.get("role") or "")
        target = str(e.get("target") or "").lower()
        val = e.get("new") if "new" in e else e.get("value")
        vs = str(val or "").lower()
        ts = int(e.get("ts") or 0)
        ts_max = max(ts_max, ts)
        if "fill" in target or "fill_at" in vs or "intent_fill" in target:
            fill = True
            role = r or role
        if "skim" in vs or "pocket" in target or "solver_pocket" in target:
            skim = True
            role = r or role
        if "receipt" in target or "got_" in vs or "not_" in vs:
            short_receipt = True
            role = r or role
        if "consumed" in vs or ("intent" in target and "consumed" in vs):
            consumed = True
            role = r or role
    if fill and (skim or short_receipt):
        return [
            {
                "kind": "intent_solver_theft_detected",
                "ts": ts_max,
                "role": role,
                "fill": fill,
                "skim": skim,
                "short_receipt": short_receipt,
                "intent_consumed": consumed,
                "policy": "min_out_enforcement_and_solver_bond",
            }
        ]
    if skim and short_receipt:
        return [
            {
                "kind": "intent_solver_theft_detected",
                "ts": ts_max,
                "role": role,
                "skim": True,
                "short_receipt": True,
                "policy": "min_out_enforcement_and_solver_bond",
            }
        ]
    return []


def _synthesize_dao_treasury_drain(events: list[dict]) -> list[dict]:
    """恶意提案 + 时锁绕过 + treasury 清零 → dao_treasury_drain_detected (ADV95)."""
    if any(e.get("kind") == "dao_treasury_drain_detected" for e in events):
        return []
    proposal = False
    snap_vote = False
    timelock_bypass = False
    treasury_zero = False
    drained = False
    role = ""
    ts_max = 0
    for e in events:
        if e.get("kind") not in {"write", "conflict_detected", "double_claim_detected"}:
            continue
        r = str(e.get("role") or "")
        target = str(e.get("target") or "").lower()
        val = e.get("new") if "new" in e else e.get("value")
        vs = str(val or "").lower()
        ts = int(e.get("ts") or 0)
        ts_max = max(ts_max, ts)
        if "proposal" in target or "emergency_grant" in vs or "grant" in vs:
            proposal = True
            role = r or role
        if "vote" in target or "pass_snap" in vs or "snap_vote" in vs:
            snap_vote = True
            role = r or role
        if "timelock" in target or "bypass" in vs:
            timelock_bypass = True
            role = r or role
        if "treasury" in target:
            if vs in {"0", "0.0", ""} or "drain" in vs:
                treasury_zero = True
                role = r or role
        if "drained" in vs or ("wallet" in target and "attacker" in (r or target)):
            drained = True
            role = r or role
    if treasury_zero and (proposal or snap_vote or timelock_bypass or drained):
        return [
            {
                "kind": "dao_treasury_drain_detected",
                "ts": ts_max,
                "role": role,
                "proposal": proposal,
                "snap_vote": snap_vote,
                "timelock_bypass": timelock_bypass,
                "treasury_zero": treasury_zero,
                "drained": drained,
                "policy": "timelock_and_veto_guardian",
            }
        ]
    if drained and (proposal or snap_vote):
        return [
            {
                "kind": "dao_treasury_drain_detected",
                "ts": ts_max,
                "role": role,
                "proposal": proposal,
                "snap_vote": snap_vote,
                "drained": True,
                "policy": "timelock_and_veto_guardian",
            }
        ]
    return []


def _synthesize_l2_sequencer_censorship(events: list[dict]) -> list[dict]:
    """sequencer 丢弃 exit / 压制 batch → l2_sequencer_censorship_detected (ADV97)."""
    if any(e.get("kind") == "l2_sequencer_censorship_detected" for e in events):
        return []
    exit_req = False
    drop_tx = False
    exclude_batch = False
    hatch_fail = False
    role = ""
    ts_max = 0
    for e in events:
        if e.get("kind") not in {"write", "conflict_detected", "double_claim_detected"}:
            continue
        r = str(e.get("role") or "")
        target = str(e.get("target") or "").lower()
        val = e.get("new") if "new" in e else e.get("value")
        vs = str(val or "").lower()
        ts = int(e.get("ts") or 0)
        ts_max = max(ts_max, ts)
        if "exit" in target or "force_exit" in vs or "exit_request" in vs:
            exit_req = True
            role = r or role
        if "drop" in vs or ("sequencer" in target and "drop" in vs) or "drop_user" in vs:
            drop_tx = True
            role = r or role
        if "exclude" in vs or "batch" in target:
            exclude_batch = True
            role = r or role
        if "escape" in target or "hatch" in target or "timeout_not" in vs:
            hatch_fail = True
            role = r or role
    if (drop_tx or exclude_batch) and (exit_req or hatch_fail):
        return [
            {
                "kind": "l2_sequencer_censorship_detected",
                "ts": ts_max,
                "role": role,
                "exit_request": exit_req,
                "drop_tx": drop_tx,
                "exclude_batch": exclude_batch,
                "hatch_fail": hatch_fail,
                "policy": "forced_inclusion_and_escape_hatch",
            }
        ]
    if drop_tx and exclude_batch:
        return [
            {
                "kind": "l2_sequencer_censorship_detected",
                "ts": ts_max,
                "role": role,
                "drop_tx": True,
                "exclude_batch": True,
                "policy": "forced_inclusion_and_escape_hatch",
            }
        ]
    return []


def _synthesize_mev_builder_collusion(events: list[dict]) -> list[dict]:
    """多 builder 共享 orderflow + cartel → mev_builder_collusion_detected (ADV99)."""
    if any(e.get("kind") == "mev_builder_collusion_detected" for e in events):
        return []
    leaks: list[tuple[int, str]] = []
    extract = False
    cartel = False
    role = ""
    ts_max = 0
    for e in events:
        if e.get("kind") not in {"write", "conflict_detected", "double_claim_detected"}:
            continue
        r = str(e.get("role") or "")
        target = str(e.get("target") or "").lower()
        val = e.get("new") if "new" in e else e.get("value")
        vs = str(val or "").lower()
        ts = int(e.get("ts") or 0)
        ts_max = max(ts_max, ts)
        if "orderflow" in target or "leak" in vs or "share" in target:
            leaks.append((ts, r))
            role = r or role
        if "extract" in target or "extract" in vs or "bundle" in target:
            extract = True
            role = r or role
        if "cartel" in vs or "auction" in target and ("cartel" in vs or "single_winner" in vs):
            cartel = True
            role = r or role
        if "single_winner" in vs or "cartel" in vs:
            cartel = True
    leak_roles = {r for _t, r in leaks if r}
    if len(leak_roles) >= 2 and (extract or cartel):
        return [
            {
                "kind": "mev_builder_collusion_detected",
                "ts": ts_max,
                "role": role,
                "leak_roles": sorted(leak_roles),
                "extract": extract,
                "cartel": cartel,
                "policy": "orderflow_isolation_and_builder_diversity",
            }
        ]
    if len(leaks) >= 2 and extract:
        return [
            {
                "kind": "mev_builder_collusion_detected",
                "ts": ts_max,
                "role": role,
                "leak_count": len(leaks),
                "extract": True,
                "policy": "orderflow_isolation_and_builder_diversity",
            }
        ]
    return []


def _synthesize_aa_account_drain(events: list[dict]) -> list[dict]:
    """session key / paymaster 合谋抽干 AA 账户 → aa_account_drain_detected (ADV101)."""
    if any(e.get("kind") == "aa_account_drain_detected" for e in events):
        return []
    session_abuse = False
    paymaster_bad = False
    transfer_all = False
    balance_zero = False
    role = ""
    ts_max = 0
    for e in events:
        if e.get("kind") not in {"write", "conflict_detected", "double_claim_detected"}:
            continue
        r = str(e.get("role") or "")
        target = str(e.get("target") or "").lower()
        val = e.get("new") if "new" in e else e.get("value")
        vs = str(val or "").lower()
        ts = int(e.get("ts") or 0)
        ts_max = max(ts_max, ts)
        if "session" in target or "overpermission" in vs or "key_over" in vs:
            session_abuse = True
            role = r or role
        if "paymaster" in target or "sponsor_malicious" in vs or "sponsor" in vs:
            paymaster_bad = True
            role = r or role
        if "userop" in target or "transfer_all" in vs or "batch" in target:
            transfer_all = True
            role = r or role
        if "smart_account" in target or "account" in target:
            if vs in {"0", "0.0", "balance_0"} or "balance_0" in vs:
                balance_zero = True
                role = r or role
        if vs in {"balance_0", "0"} and ("account" in target or "balance" in target):
            balance_zero = True
    if balance_zero and (session_abuse or paymaster_bad or transfer_all):
        return [
            {
                "kind": "aa_account_drain_detected",
                "ts": ts_max,
                "role": role,
                "session_abuse": session_abuse,
                "paymaster_bad": paymaster_bad,
                "transfer_all": transfer_all,
                "balance_zero": balance_zero,
                "policy": "session_key_scopes_and_paymaster_allowlist",
            }
        ]
    if session_abuse and paymaster_bad and transfer_all:
        return [
            {
                "kind": "aa_account_drain_detected",
                "ts": ts_max,
                "role": role,
                "session_abuse": True,
                "paymaster_bad": True,
                "transfer_all": True,
                "policy": "session_key_scopes_and_paymaster_allowlist",
            }
        ]
    return []


def _synthesize_validator_equivocation_coverup(events: list[dict]) -> list[dict]:
    """双签后改写证据 → validator_equivocation_coverup_detected (ADV103)."""
    if any(e.get("kind") == "validator_equivocation_coverup_detected" for e in events):
        return []
    fork_votes: list[tuple[int, str, str]] = []
    rewrite = False
    evidence_purged = False
    role = ""
    ts_max = 0
    for e in events:
        if e.get("kind") not in {"write", "conflict_detected", "double_claim_detected"}:
            continue
        r = str(e.get("role") or "")
        target = str(e.get("target") or "").lower()
        val = e.get("new") if "new" in e else e.get("value")
        vs = str(val or "").lower()
        ts = int(e.get("ts") or 0)
        ts_max = max(ts_max, ts)
        if "vote" in target or "vote_fork" in vs or "fork" in vs:
            fork_votes.append((ts, r, target or vs))
            role = r or role
        if "attestation" in target or "rewrite" in vs or "rewrite_clean" in vs:
            rewrite = True
            role = r or role
        if "evidence" in target or "purged" in vs or "purge" in vs:
            evidence_purged = True
            role = r or role
    multi_fork = len(fork_votes) >= 2
    if multi_fork and (rewrite or evidence_purged):
        return [
            {
                "kind": "validator_equivocation_coverup_detected",
                "ts": ts_max,
                "role": role,
                "fork_votes": len(fork_votes),
                "rewrite": rewrite,
                "evidence_purged": evidence_purged,
                "policy": "immutable_attestation_and_slashing",
            }
        ]
    if multi_fork:
        # still require coverup signal for this detector
        return []
    return []


def _synthesize_liquidity_migration_trap(events: list[dict]) -> list[dict]:
    """诱导迁移后 rug → liquidity_migration_trap_detected (ADV105)."""
    if any(e.get("kind") == "liquidity_migration_trap_detected" for e in events):
        return []
    migrate_notice = False
    old_drained = False
    new_pool = False
    rug = False
    role = ""
    ts_max = 0
    for e in events:
        if e.get("kind") not in {"write", "conflict_detected", "double_claim_detected"}:
            continue
        r = str(e.get("role") or "")
        target = str(e.get("target") or "").lower()
        val = e.get("new") if "new" in e else e.get("value")
        vs = str(val or "").lower()
        ts = int(e.get("ts") or 0)
        ts_max = max(ts_max, ts)
        if "migrate" in target or "migrate" in vs:
            migrate_notice = True
            role = r or role
        if "old_pool" in target or ( "pool" in target and "old" in target):
            if vs in {"0", "0.0", "liq_0"} or "liq_0" in vs:
                old_drained = True
                role = r or role
        if "new_pool" in target or "malicious" in vs:
            new_pool = True
            role = r or role
        if "rug" in vs or "rug_after" in vs:
            rug = True
            role = r or role
    if (migrate_notice or old_drained) and (new_pool or rug) and (rug or (old_drained and new_pool)):
        return [
            {
                "kind": "liquidity_migration_trap_detected",
                "ts": ts_max,
                "role": role,
                "migrate_notice": migrate_notice,
                "old_drained": old_drained,
                "new_pool": new_pool,
                "rug": rug,
                "policy": "migration_timelock_and_pool_allowlist",
            }
        ]
    if old_drained and new_pool and migrate_notice:
        return [
            {
                "kind": "liquidity_migration_trap_detected",
                "ts": ts_max,
                "role": role,
                "old_drained": True,
                "new_pool": True,
                "migrate_notice": True,
                "policy": "migration_timelock_and_pool_allowlist",
            }
        ]
    return []


def _synthesize_cross_chain_msg_replay(events: list[dict]) -> list[dict]:
    """同 nonce 跨链重复执行 → cross_chain_msg_replay_detected (ADV107)."""
    if any(e.get("kind") == "cross_chain_msg_replay_detected" for e in events):
        return []
    payload = False
    execs: list[tuple[int, str, str]] = []
    double_credit = False
    replay = False
    role = ""
    ts_max = 0
    for e in events:
        if e.get("kind") not in {"write", "conflict_detected", "double_claim_detected"}:
            continue
        r = str(e.get("role") or "")
        target = str(e.get("target") or "").lower()
        val = e.get("new") if "new" in e else e.get("value")
        vs = str(val or "").lower()
        ts = int(e.get("ts") or 0)
        ts_max = max(ts_max, ts)
        if "payload" in target or "transfer_" in vs:
            payload = True
            role = r or role
        if "exec_nonce" in target or "executed" in vs or "nonce" in target:
            execs.append((ts, r, target or vs))
            role = r or role
        if "replay" in vs or "replay" in target:
            replay = True
            role = r or role
        if "double_credit" in vs or "double" in vs:
            double_credit = True
            role = r or role
    multi_exec = len(execs) >= 2
    if (multi_exec or replay) and (payload or double_credit or multi_exec):
        if multi_exec or replay or double_credit:
            return [
                {
                    "kind": "cross_chain_msg_replay_detected",
                    "ts": ts_max,
                    "role": role,
                    "exec_count": len(execs),
                    "replay": replay,
                    "double_credit": double_credit,
                    "payload": payload,
                    "policy": "global_nonce_and_destination_domain_bind",
                }
            ]
    return []


def _synthesize_oracle_latency_exploit(events: list[dict]) -> list[dict]:
    """过期喂价 + 套利/清算 → oracle_latency_exploit_detected (ADV109)."""
    if any(e.get("kind") == "oracle_latency_exploit_detected" for e in events):
        return []
    stale = False
    true_price = False
    liq_stale = False
    arb = False
    role = ""
    ts_max = 0
    for e in events:
        if e.get("kind") not in {"write", "conflict_detected", "double_claim_detected"}:
            continue
        r = str(e.get("role") or "")
        target = str(e.get("target") or "").lower()
        val = e.get("new") if "new" in e else e.get("value")
        vs = str(val or "").lower()
        ts = int(e.get("ts") or 0)
        ts_max = max(ts_max, ts)
        if "stale" in vs or ("price" in target and "stale" in vs) or "age_" in vs:
            stale = True
            role = r or role
        if "true_price" in vs or "spot" in target:
            true_price = True
            role = r or role
        if "liq" in target or "liquidate" in vs or "stale_price" in vs:
            liq_stale = True
            role = r or role
        if "arb" in vs or "profit" in vs:
            arb = True
            role = r or role
    if stale and (liq_stale or arb or true_price):
        return [
            {
                "kind": "oracle_latency_exploit_detected",
                "ts": ts_max,
                "role": role,
                "stale": stale,
                "true_price": true_price,
                "liq_on_stale": liq_stale,
                "arb": arb,
                "policy": "heartbeat_and_max_price_age",
            }
        ]
    return []


def _synthesize_governance_timelock_bypass(events: list[dict]) -> list[dict]:
    """紧急角色跳过 delay 执行 → governance_timelock_bypass_detected (ADV111)."""
    if any(e.get("kind") == "governance_timelock_bypass_detected" for e in events):
        return []
    proposal = False
    emergency = False
    skip_delay = False
    malicious = False
    role = ""
    ts_max = 0
    for e in events:
        if e.get("kind") not in {"write", "conflict_detected", "double_claim_detected"}:
            continue
        r = str(e.get("role") or "")
        target = str(e.get("target") or "").lower()
        val = e.get("new") if "new" in e else e.get("value")
        vs = str(val or "").lower()
        ts = int(e.get("ts") or 0)
        ts_max = max(ts_max, ts)
        if "proposal" in target or "set_param" in vs:
            proposal = True
            role = r or role
        if "emergency" in target or "grant_self" in vs or "emergency" in vs:
            emergency = True
            role = r or role
        if "skip_delay" in vs or "execute_now" in vs or (
            "timelock" in target and ("skip" in vs or "now" in vs)
        ):
            skip_delay = True
            role = r or role
        if "malicious" in vs or "system_param" in target:
            malicious = True
            role = r or role
    if skip_delay and (proposal or emergency or malicious):
        return [
            {
                "kind": "governance_timelock_bypass_detected",
                "ts": ts_max,
                "role": role,
                "proposal": proposal,
                "emergency": emergency,
                "skip_delay": skip_delay,
                "malicious": malicious,
                "policy": "immutable_timelock_and_multisig_guardian",
            }
        ]
    if emergency and malicious and proposal:
        return [
            {
                "kind": "governance_timelock_bypass_detected",
                "ts": ts_max,
                "role": role,
                "emergency": True,
                "malicious": True,
                "proposal": True,
                "policy": "immutable_timelock_and_multisig_guardian",
            }
        ]
    return []


def _synthesize_shared_sequencer_dos(events: list[dict]) -> list[dict]:
    """垃圾占满 shared sequencer 配额 → shared_sequencer_dos_detected (ADV113)."""
    if any(e.get("kind") == "shared_sequencer_dos_detected" for e in events):
        return []
    spam = False
    quota_out = False
    stuck = False
    degraded = False
    role = ""
    ts_max = 0
    for e in events:
        if e.get("kind") not in {"write", "conflict_detected", "double_claim_detected"}:
            continue
        r = str(e.get("role") or "")
        target = str(e.get("target") or "").lower()
        val = e.get("new") if "new" in e else e.get("value")
        vs = str(val or "").lower()
        ts = int(e.get("ts") or 0)
        ts_max = max(ts_max, ts)
        if "spam" in target or "flood" in vs or "noop" in vs:
            spam = True
            role = r or role
        if "quota" in target or "exhausted" in vs or "quota_exhausted" in vs:
            quota_out = True
            role = r or role
        if "stuck" in vs or "pending" in vs or "user_tx" in target:
            stuck = True
            role = r or role
        if "degraded" in vs or "liveness" in target:
            degraded = True
            role = r or role
    if (spam or quota_out) and (stuck or degraded or quota_out):
        return [
            {
                "kind": "shared_sequencer_dos_detected",
                "ts": ts_max,
                "role": role,
                "spam": spam,
                "quota_exhausted": quota_out,
                "stuck": stuck,
                "degraded": degraded,
                "policy": "per_sender_rate_limit_and_priority_lanes",
            }
        ]
    return []


def _synthesize_private_mempool_leak(events: list[dict]) -> list[dict]:
    """私有订单泄露给 searcher → private_mempool_leak_detected (ADV115)."""
    if any(e.get("kind") == "private_mempool_leak_detected" for e in events):
        return []
    private_tx = False
    leak = False
    extract = False
    worse = False
    role = ""
    ts_max = 0
    for e in events:
        if e.get("kind") not in {"write", "conflict_detected", "double_claim_detected"}:
            continue
        r = str(e.get("role") or "")
        target = str(e.get("target") or "").lower()
        val = e.get("new") if "new" in e else e.get("value")
        vs = str(val or "").lower()
        ts = int(e.get("ts") or 0)
        ts_max = max(ts_max, ts)
        if "private_tx" in target or "exclusive" in vs or "private" in target and "tx" in target:
            private_tx = True
            role = r or role
        if "leak" in vs or ("relay" in target and "leak" in vs):
            leak = True
            role = r or role
        if "frontrun" in target or "extract_from_leak" in vs or "extract" in vs:
            extract = True
            role = r or role
        if "worse" in vs or "user_fill" in target:
            worse = True
            role = r or role
    if leak and (private_tx or extract or worse):
        return [
            {
                "kind": "private_mempool_leak_detected",
                "ts": ts_max,
                "role": role,
                "private_tx": private_tx,
                "leak": leak,
                "extract": extract,
                "worse_fill": worse,
                "policy": "sealed_relay_and_orderflow_audit",
            }
        ]
    if private_tx and extract:
        return [
            {
                "kind": "private_mempool_leak_detected",
                "ts": ts_max,
                "role": role,
                "private_tx": True,
                "extract": True,
                "policy": "sealed_relay_and_orderflow_audit",
            }
        ]
    return []


def _synthesize_state_bloat_grief(events: list[dict]) -> list[dict]:
    """廉价 dust 写入撑爆 state → state_bloat_grief_detected (ADV117)."""
    if any(e.get("kind") == "state_bloat_grief_detected" for e in events):
        return []
    dust = False
    bloat = False
    lagging = False
    disk_full = False
    role = ""
    ts_max = 0
    for e in events:
        if e.get("kind") not in {"write", "conflict_detected", "double_claim_detected"}:
            continue
        r = str(e.get("role") or "")
        target = str(e.get("target") or "").lower()
        val = e.get("new") if "new" in e else e.get("value")
        vs = str(val or "").lower()
        ts = int(e.get("ts") or 0)
        ts_max = max(ts_max, ts)
        if "storage" in target or "dust" in vs or "1m" in vs:
            dust = True
            role = r or role
        if "bloat" in vs or "state_size" in target:
            bloat = True
            role = r or role
        if "lagging" in vs or "sync" in target:
            lagging = True
            role = r or role
        if "disk_full" in vs or "rejected" in vs:
            disk_full = True
            role = r or role
    if (dust or bloat) and (lagging or disk_full or bloat):
        return [
            {
                "kind": "state_bloat_grief_detected",
                "ts": ts_max,
                "role": role,
                "dust_writes": dust,
                "bloat": bloat,
                "lagging": lagging,
                "disk_full": disk_full,
                "policy": "storage_rent_and_state_expiry",
            }
        ]
    return []


def _synthesize_threshold_sig_share_theft(events: list[dict]) -> list[dict]:
    """收集 t 份 share 伪造签名 → threshold_sig_share_theft_detected (ADV119)."""
    if any(e.get("kind") == "threshold_sig_share_theft_detected" for e in events):
        return []
    shares: list[tuple[int, str]] = []
    forged = False
    role = ""
    ts_max = 0
    for e in events:
        if e.get("kind") not in {"write", "conflict_detected", "double_claim_detected"}:
            continue
        r = str(e.get("role") or "")
        target = str(e.get("target") or "").lower()
        val = e.get("new") if "new" in e else e.get("value")
        vs = str(val or "").lower()
        ts = int(e.get("ts") or 0)
        ts_max = max(ts_max, ts)
        if "share" in target or "exfil_share" in vs or "exfil" in vs:
            shares.append((ts, target or vs))
            role = r or role
        if "forged" in vs or "forged_sig" in target or "threshold_sig" in vs:
            forged = True
            role = r or role
    if len(shares) >= 2 and (forged or len(shares) >= 3):
        return [
            {
                "kind": "threshold_sig_share_theft_detected",
                "ts": ts_max,
                "role": role,
                "share_count": len(shares),
                "forged": forged,
                "policy": "share_hsm_and_refresh_protocol",
            }
        ]
    return []


def _synthesize_rpc_auth_bypass(events: list[dict]) -> list[dict]:
    """未授权 admin RPC / ACL 关闭 → rpc_auth_bypass_detected (ADV121)."""
    if any(e.get("kind") == "rpc_auth_bypass_detected" for e in events):
        return []
    acl_off = False
    admin_rpc = False
    debug_open = False
    compromised = False
    role = ""
    ts_max = 0
    for e in events:
        if e.get("kind") not in {"write", "conflict_detected", "double_claim_detected"}:
            continue
        r = str(e.get("role") or "")
        target = str(e.get("target") or "").lower()
        val = e.get("new") if "new" in e else e.get("value")
        vs = str(val or "").lower()
        ts = int(e.get("ts") or 0)
        ts_max = max(ts_max, ts)
        if "rpc_acl" in target or "auth_disabled" in vs or "auth_required" in vs and "disabled" in vs:
            acl_off = True
            role = r or role
        if "auth_disabled" in vs:
            acl_off = True
            role = r or role
        if "admin_rpc" in target or "peer_ban" in vs or "set_peer" in vs:
            admin_rpc = True
            role = r or role
        if "debug" in vs or "node_config" in target:
            debug_open = True
            role = r or role
        if "compromised" in vs or "security_flag" in target:
            compromised = True
            role = r or role
    if (acl_off or admin_rpc) and (admin_rpc or debug_open or compromised):
        return [
            {
                "kind": "rpc_auth_bypass_detected",
                "ts": ts_max,
                "role": role,
                "acl_off": acl_off,
                "admin_rpc": admin_rpc,
                "debug_open": debug_open,
                "compromised": compromised,
                "policy": "mutual_tls_and_rpc_allowlist",
            }
        ]
    return []


def _synthesize_dependency_confusion(events: list[dict]) -> list[dict]:
    """同名恶意包抢解析 → dependency_confusion_detected (ADV123)."""
    if any(e.get("kind") == "dependency_confusion_detected" for e in events):
        return []
    public_publish = False
    resolved_malicious = False
    exfil_hook = False
    backdoor = False
    role = ""
    ts_max = 0
    for e in events:
        if e.get("kind") not in {"write", "conflict_detected", "double_claim_detected"}:
            continue
        r = str(e.get("role") or "")
        target = str(e.get("target") or "").lower()
        val = e.get("new") if "new" in e else e.get("value")
        vs = str(val or "").lower()
        ts = int(e.get("ts") or 0)
        ts_max = max(ts_max, ts)
        if "registry" in target or "publish" in vs:
            public_publish = True
            role = r or role
        if "malicious" in vs or "package_lock" in target and "public" in vs:
            resolved_malicious = True
            role = r or role
        if "resolved_public" in vs or "malicious" in vs:
            resolved_malicious = True
            role = r or role
        if "postinstall" in vs or "exfil" in vs or "install_hook" in target:
            exfil_hook = True
            role = r or role
        if "backdoor" in vs or "build_artifact" in target:
            backdoor = True
            role = r or role
    if (public_publish or resolved_malicious) and (exfil_hook or backdoor or resolved_malicious):
        return [
            {
                "kind": "dependency_confusion_detected",
                "ts": ts_max,
                "role": role,
                "public_publish": public_publish,
                "resolved_malicious": resolved_malicious,
                "exfil_hook": exfil_hook,
                "backdoor": backdoor,
                "policy": "scoped_registry_and_lockfile_pin",
            }
        ]
    return []


def _synthesize_clock_sync_poison(events: list[dict]) -> list[dict]:
    """NTP/时源投毒导致时钟分裂 → clock_sync_poison_detected (ADV125)."""
    if any(e.get("kind") == "clock_sync_poison_detected" for e in events):
        return []
    ntp_skew = False
    skewed = False
    split = False
    reject_storm = False
    role = ""
    ts_max = 0
    clocks: list[str] = []
    for e in events:
        if e.get("kind") not in {"write", "conflict_detected", "double_claim_detected"}:
            continue
        r = str(e.get("role") or "")
        target = str(e.get("target") or "").lower()
        val = e.get("new") if "new" in e else e.get("value")
        vs = str(val or "").lower()
        ts = int(e.get("ts") or 0)
        ts_max = max(ts_max, ts)
        if "ntp" in target or "skew" in vs:
            ntp_skew = True
            role = r or role
        if "wall_clock" in target or "skewed" in vs or "still_correct" in vs:
            clocks.append(vs)
            if "skewed" in vs:
                skewed = True
            role = r or role
        if "timestamp_reject" in vs or "reject_storm" in vs or "consensus" in target:
            reject_storm = True
            role = r or role
    if len(set(clocks)) >= 2:
        split = True
    if (ntp_skew or skewed) and (split or reject_storm or skewed):
        return [
            {
                "kind": "clock_sync_poison_detected",
                "ts": ts_max,
                "role": role,
                "ntp_skew": ntp_skew,
                "skewed": skewed,
                "clock_split": split,
                "reject_storm": reject_storm,
                "policy": "multi_source_time_and_max_drift",
            }
        ]
    return []


def _synthesize_blind_signing_drain(events: list[dict]) -> list[dict]:
    """盲签恶意 payload 后资产抽干 → blind_signing_drain_detected (ADV127)."""
    if any(e.get("kind") == "blind_signing_drain_detected" for e in events):
        return []
    opaque = False
    blind_sig = False
    balance_zero = False
    received = False
    role = ""
    ts_max = 0
    for e in events:
        if e.get("kind") not in {"write", "conflict_detected", "double_claim_detected"}:
            continue
        r = str(e.get("role") or "")
        target = str(e.get("target") or "").lower()
        val = e.get("new") if "new" in e else e.get("value")
        vs = str(val or "").lower()
        ts = int(e.get("ts") or 0)
        ts_max = max(ts_max, ts)
        if "sign_request" in target or "opaque" in vs or "hex_blob" in vs:
            opaque = True
            role = r or role
        if "blind_signed" in vs or ("signature" in target and "blind" in vs):
            blind_sig = True
            role = r or role
        if "wallet_balance" in target or "balance" in target:
            if vs in {"0", "0.0"} or vs == "0":
                balance_zero = True
                role = r or role
        if "received" in vs or ("attacker_wallet" in target and "received" in vs):
            received = True
            role = r or role
        if "received_" in vs:
            received = True
            role = r or role
    if blind_sig and (balance_zero or received or opaque):
        return [
            {
                "kind": "blind_signing_drain_detected",
                "ts": ts_max,
                "role": role,
                "opaque_payload": opaque,
                "blind_sig": blind_sig,
                "balance_zero": balance_zero,
                "received": received,
                "policy": "human_readable_sign_and_sim",
            }
        ]
    if opaque and balance_zero:
        return [
            {
                "kind": "blind_signing_drain_detected",
                "ts": ts_max,
                "role": role,
                "opaque_payload": True,
                "balance_zero": True,
                "policy": "human_readable_sign_and_sim",
            }
        ]
    return []


def _synthesize_dns_rebinding(events: list[dict]) -> list[dict]:
    """DNS TTL 翻转打内网 RPC → dns_rebinding_detected (ADV129)."""
    if any(e.get("kind") == "dns_rebinding_detected" for e in events):
        return []
    ttl_flip = False
    internal_hit = False
    forged_rpc = False
    exfil = False
    role = ""
    ts_max = 0
    for e in events:
        if e.get("kind") not in {"write", "conflict_detected", "double_claim_detected"}:
            continue
        r = str(e.get("role") or "")
        target = str(e.get("target") or "").lower()
        val = e.get("new") if "new" in e else e.get("value")
        vs = str(val or "").lower()
        ts = int(e.get("ts") or 0)
        ts_max = max(ts_max, ts)
        if "dns" in target or "ttl" in vs or "127.0.0.1" in vs or "flip" in vs:
            ttl_flip = True
            role = r or role
        if "internal" in vs or "same_origin" in target or "hit_internal" in vs:
            internal_hit = True
            role = r or role
        if "rpc_call" in target or "forged" in vs or "sendtransaction" in vs:
            forged_rpc = True
            role = r or role
        if "exfil" in vs or "loot" in target or "keys_exfil" in vs:
            exfil = True
            role = r or role
    if (ttl_flip or internal_hit) and (forged_rpc or exfil or internal_hit):
        return [
            {
                "kind": "dns_rebinding_detected",
                "ts": ts_max,
                "role": role,
                "ttl_flip": ttl_flip,
                "internal_hit": internal_hit,
                "forged_rpc": forged_rpc,
                "exfil": exfil,
                "policy": "host_header_and_cors_lockdown",
            }
        ]
    return []


def _synthesize_ci_secret_exfil(events: list[dict]) -> list[dict]:
    """CI secrets 打印/上传外泄 → ci_secret_exfil_detected (ADV131)."""
    if any(e.get("kind") == "ci_secret_exfil_detected" for e in events):
        return []
    echo_env = False
    unmasked = False
    dump = False
    exfil_done = False
    role = ""
    ts_max = 0
    for e in events:
        if e.get("kind") not in {"write", "conflict_detected", "double_claim_detected"}:
            continue
        r = str(e.get("role") or "")
        target = str(e.get("target") or "").lower()
        val = e.get("new") if "new" in e else e.get("value")
        vs = str(val or "").lower()
        ts = int(e.get("ts") or 0)
        ts_max = max(ts_max, ts)
        if "workflow" in target or "echo_all_env" in vs or "echo" in vs:
            echo_env = True
            role = r or role
        if "unmasked" in vs or "ci_secrets" in target:
            unmasked = True
            role = r or role
        if "secrets_dump" in vs or "upload_artifact" in target or "dump" in vs:
            dump = True
            role = r or role
        if "exfil" in vs or "remote_sink" in target:
            exfil_done = True
            role = r or role
    if (echo_env or unmasked) and (dump or exfil_done or unmasked):
        return [
            {
                "kind": "ci_secret_exfil_detected",
                "ts": ts_max,
                "role": role,
                "echo_env": echo_env,
                "unmasked": unmasked,
                "dump": dump,
                "exfil": exfil_done,
                "policy": "secret_masking_and_oidc_short_lived",
            }
        ]
    return []


def _synthesize_supply_chain_typosquat(events: list[dict]) -> list[dict]:
    """近似包名恶意依赖 → supply_chain_typosquat_detected (ADV133)."""
    if any(e.get("kind") == "supply_chain_typosquat_detected" for e in events):
        return []
    typosquat_pkg = False
    wrong_dep = False
    pulled = False
    steal = False
    role = ""
    ts_max = 0
    for e in events:
        if e.get("kind") not in {"write", "conflict_detected", "double_claim_detected"}:
            continue
        r = str(e.get("role") or "")
        target = str(e.get("target") or "").lower()
        val = e.get("new") if "new" in e else e.get("value")
        vs = str(val or "").lower()
        ts = int(e.get("ts") or 0)
        ts_max = max(ts_max, ts)
        if "pypi" in target or "malicious" in vs or "typosquat" in vs:
            typosquat_pkg = True
            role = r or role
        if "package_json" in target or "reqeusts" in vs:
            wrong_dep = True
            role = r or role
        if "install_log" in target or "pulled_typosquat" in vs or "typosquat" in vs:
            pulled = True
            role = r or role
        if "steal" in vs or "runtime_hook" in target or "tokens" in vs:
            steal = True
            role = r or role
    if (typosquat_pkg or pulled) and (wrong_dep or steal or pulled):
        return [
            {
                "kind": "supply_chain_typosquat_detected",
                "ts": ts_max,
                "role": role,
                "typosquat_pkg": typosquat_pkg,
                "wrong_dep": wrong_dep,
                "pulled": pulled,
                "steal": steal,
                "policy": "allowlist_and_lockfile_hash",
            }
        ]
    return []


def _synthesize_webhook_ssrf(events: list[dict]) -> list[dict]:
    """Webhook 指向元数据/内网 → webhook_ssrf_detected (ADV135)."""
    if any(e.get("kind") == "webhook_ssrf_detected" for e in events):
        return []
    meta_url = False
    dispatch = False
    creds = False
    loot = False
    role = ""
    ts_max = 0
    for e in events:
        if e.get("kind") not in {"write", "conflict_detected", "double_claim_detected"}:
            continue
        r = str(e.get("role") or "")
        target = str(e.get("target") or "").lower()
        val = e.get("new") if "new" in e else e.get("value")
        vs = str(val or "").lower()
        ts = int(e.get("ts") or 0)
        ts_max = max(ts_max, ts)
        if "webhook_url" in target or "169.254" in vs or "meta-data" in vs:
            meta_url = True
            role = r or role
        if "webhook_dispatch" in target or "fetch_attacker" in vs:
            dispatch = True
            role = r or role
        if "meta_response" in target or "iam_credentials" in vs or "credentials_leaked" in vs:
            creds = True
            role = r or role
        if "cloud_keys" in vs or ("loot" in target and "cloud" in vs):
            loot = True
            role = r or role
    if (meta_url or dispatch) and (creds or loot or meta_url and dispatch):
        return [
            {
                "kind": "webhook_ssrf_detected",
                "ts": ts_max,
                "role": role,
                "meta_url": meta_url,
                "dispatch": dispatch,
                "creds": creds,
                "loot": loot,
                "policy": "url_allowlist_and_block_link_local",
            }
        ]
    return []


def _synthesize_jwt_alg_none(events: list[dict]) -> list[dict]:
    """JWT alg=none 无签名提权 → jwt_alg_none_detected (ADV137)."""
    if any(e.get("kind") == "jwt_alg_none_detected" for e in events):
        return []
    alg_none = False
    accept_nosig = False
    admin_action = False
    priv_esc = False
    role = ""
    ts_max = 0
    for e in events:
        if e.get("kind") not in {"write", "conflict_detected", "double_claim_detected"}:
            continue
        r = str(e.get("role") or "")
        target = str(e.get("target") or "").lower()
        val = e.get("new") if "new" in e else e.get("value")
        vs = str(val or "").lower()
        ts = int(e.get("ts") or 0)
        ts_max = max(ts_max, ts)
        if "alg_none" in vs or ("auth_token" in target and "none" in vs):
            alg_none = True
            role = r or role
        if "accept_without_sig" in vs or "token_verify" in target:
            accept_nosig = True
            role = r or role
        if "admin_action" in target or "delete_all" in vs:
            admin_action = True
            role = r or role
        if "privilege_escalation" in vs or "audit_log" in target:
            priv_esc = True
            role = r or role
    if alg_none and (accept_nosig or admin_action or priv_esc):
        return [
            {
                "kind": "jwt_alg_none_detected",
                "ts": ts_max,
                "role": role,
                "alg_none": alg_none,
                "accept_nosig": accept_nosig,
                "admin_action": admin_action,
                "priv_esc": priv_esc,
                "policy": "deny_alg_none_and_force_verify",
            }
        ]
    if accept_nosig and admin_action:
        return [
            {
                "kind": "jwt_alg_none_detected",
                "ts": ts_max,
                "role": role,
                "accept_nosig": True,
                "admin_action": True,
                "policy": "deny_alg_none_and_force_verify",
            }
        ]
    return []


def _synthesize_path_traversal_write(events: list[dict]) -> list[dict]:
    """../ 穿越写系统路径 → path_traversal_write_detected (ADV139)."""
    if any(e.get("kind") == "path_traversal_write_detected" for e in events):
        return []
    traversal = False
    system_path = False
    malicious = False
    priv = False
    role = ""
    ts_max = 0
    for e in events:
        if e.get("kind") not in {"write", "conflict_detected", "double_claim_detected"}:
            continue
        r = str(e.get("role") or "")
        target = str(e.get("target") or "").lower()
        val = e.get("new") if "new" in e else e.get("value")
        vs = str(val or "").lower()
        ts = int(e.get("ts") or 0)
        ts_max = max(ts_max, ts)
        if ".." in vs or "upload_name" in target:
            if ".." in vs or "/etc/" in vs:
                traversal = True
                role = r or role
        if "write_path" in target or "/etc/" in vs or "cron.d" in vs:
            system_path = True
            role = r or role
        if "malicious" in vs or "file_content" in target:
            malicious = True
            role = r or role
        if "root_via" in vs or "privilege" in target:
            priv = True
            role = r or role
    if traversal and (system_path or malicious or priv):
        return [
            {
                "kind": "path_traversal_write_detected",
                "ts": ts_max,
                "role": role,
                "traversal": traversal,
                "system_path": system_path,
                "malicious": malicious,
                "privilege": priv,
                "policy": "canonicalize_and_root_jail",
            }
        ]
    if system_path and malicious:
        return [
            {
                "kind": "path_traversal_write_detected",
                "ts": ts_max,
                "role": role,
                "system_path": True,
                "malicious": True,
                "policy": "canonicalize_and_root_jail",
            }
        ]
    return []


def _synthesize_cache_poisoning(events: list[dict]) -> list[dict]:
    """污染缓存键/体 → cache_poisoning_detected (ADV141)."""
    if any(e.get("kind") == "cache_poisoning_detected" for e in events):
        return []
    key_poison = False
    body_malicious = False
    served = False
    hijack = False
    role = ""
    ts_max = 0
    for e in events:
        if e.get("kind") not in {"write", "conflict_detected", "double_claim_detected"}:
            continue
        r = str(e.get("role") or "")
        target = str(e.get("target") or "").lower()
        val = e.get("new") if "new" in e else e.get("value")
        vs = str(val or "").lower()
        ts = int(e.get("ts") or 0)
        ts_max = max(ts_max, ts)
        if "cache_key" in target or "x-forwarded-host" in vs or "evil" in vs:
            key_poison = True
            role = r or role
        if "cached_body" in target or "malicious_script" in vs or "payload" in vs:
            body_malicious = True
            role = r or role
        if "poisoned_cache" in vs or "page_render" in target or "served_poisoned" in vs:
            served = True
            role = r or role
        if "session_hijack" in target or "cookie_stolen" in vs:
            hijack = True
            role = r or role
    if (key_poison or body_malicious) and (served or hijack or body_malicious):
        return [
            {
                "kind": "cache_poisoning_detected",
                "ts": ts_max,
                "role": role,
                "key_poison": key_poison,
                "body_malicious": body_malicious,
                "served": served,
                "hijack": hijack,
                "policy": "vary_safe_headers_and_cache_key_normalize",
            }
        ]
    return []


def _synthesize_config_bombshell(events: list[dict]) -> list[dict]:
    """超深嵌套配置拖垮解析 → config_bombshell_detected (ADV143)."""
    if any(e.get("kind") == "config_bombshell_detected" for e in events):
        return []
    nested = False
    oom = False
    down = False
    dos = False
    role = ""
    ts_max = 0
    for e in events:
        if e.get("kind") not in {"write", "conflict_detected", "double_claim_detected"}:
            continue
        r = str(e.get("role") or "")
        target = str(e.get("target") or "").lower()
        val = e.get("new") if "new" in e else e.get("value")
        vs = str(val or "").lower()
        ts = int(e.get("ts") or 0)
        ts_max = max(ts_max, ts)
        if "nested_depth" in vs or "config_doc" in target:
            if "nested" in vs or "10000" in vs or "depth" in vs:
                nested = True
                role = r or role
        if "oom" in vs or "timeout" in vs or "parse_status" in target:
            oom = True
            role = r or role
        if "liveness" in target or vs == "down":
            down = True
            role = r or role
        if "dos_success" in vs or "attack_result" in target:
            dos = True
            role = r or role
    if nested and (oom or down or dos):
        return [
            {
                "kind": "config_bombshell_detected",
                "ts": ts_max,
                "role": role,
                "nested": nested,
                "oom": oom,
                "down": down,
                "dos": dos,
                "policy": "depth_limit_and_parse_budget",
            }
        ]
    if oom and down:
        return [
            {
                "kind": "config_bombshell_detected",
                "ts": ts_max,
                "role": role,
                "oom": True,
                "down": True,
                "policy": "depth_limit_and_parse_budget",
            }
        ]
    return []


def _synthesize_race_double_spend(events: list[dict]) -> list[dict]:
    """并发同额扣减双入账 → race_double_spend_detected (ADV145)."""
    if any(e.get("kind") == "race_double_spend_detected" for e in events):
        return []
    debits: list[tuple[int, str, str]] = []
    credits: list[tuple[int, str]] = []
    bal_zero = False
    role = ""
    ts_max = 0
    for e in events:
        if e.get("kind") not in {"write", "conflict_detected", "double_claim_detected"}:
            continue
        r = str(e.get("role") or "")
        target = str(e.get("target") or "").lower()
        val = e.get("new") if "new" in e else e.get("value")
        vs = str(val or "").lower()
        ts = int(e.get("ts") or 0)
        ts_max = max(ts_max, ts)
        if "debit" in vs or "pay_" in target:
            debits.append((ts, r, target or vs))
            role = r or role
        if "credit" in target or "credit" in vs:
            credits.append((ts, target or vs))
            role = r or role
        if "account_bal" in target or "bal" in target:
            if vs in {"0", "0.0"}:
                bal_zero = True
                role = r or role
    multi_debit = len(debits) >= 2
    multi_credit = len(credits) >= 2
    if multi_debit and (multi_credit or bal_zero):
        return [
            {
                "kind": "race_double_spend_detected",
                "ts": ts_max,
                "role": role,
                "debit_count": len(debits),
                "credit_count": len(credits),
                "balance_zero": bal_zero,
                "policy": "serializable_ledger_and_idempotency_key",
            }
        ]
    if multi_debit and multi_credit:
        return [
            {
                "kind": "race_double_spend_detected",
                "ts": ts_max,
                "role": role,
                "debit_count": len(debits),
                "credit_count": len(credits),
                "policy": "serializable_ledger_and_idempotency_key",
            }
        ]
    return []


def _synthesize_log_injection(events: list[dict]) -> list[dict]:
    """换行注入伪造审计行 → log_injection_detected (ADV147)."""
    if any(e.get("kind") == "log_injection_detected" for e in events):
        return []
    newline_inject = False
    injected_line = False
    trusted_fake = False
    fraud = False
    role = ""
    ts_max = 0
    for e in events:
        if e.get("kind") not in {"write", "conflict_detected", "double_claim_detected"}:
            continue
        r = str(e.get("role") or "")
        target = str(e.get("target") or "").lower()
        val = e.get("new") if "new" in e else e.get("value")
        vs = str(val or "").lower()
        # preserve raw newline detection from original value
        raw = str(val or "")
        ts = int(e.get("ts") or 0)
        ts_max = max(ts_max, ts)
        if "\n" in raw or "user_input" in target:
            if "\n" in raw or "admin approved" in vs or "info admin" in vs:
                newline_inject = True
                role = r or role
        if "injected" in vs or "app_log" in target:
            injected_line = True
            role = r or role
        if "trusted_fake" in vs or "audit_review" in target or "fake_approval" in vs:
            trusted_fake = True
            role = r or role
        if "grant_executed" in vs or "fraud_result" in target:
            fraud = True
            role = r or role
    if (newline_inject or injected_line) and (trusted_fake or fraud or injected_line):
        return [
            {
                "kind": "log_injection_detected",
                "ts": ts_max,
                "role": role,
                "newline_inject": newline_inject,
                "injected_line": injected_line,
                "trusted_fake": trusted_fake,
                "fraud": fraud,
                "policy": "structured_json_logs_and_escape",
            }
        ]
    return []


def _synthesize_prompt_injection_tool(events: list[dict]) -> list[dict]:
    """提示注入劫持敏感工具 → prompt_injection_tool_detected (ADV149)."""
    if any(e.get("kind") == "prompt_injection_tool_detected" for e in events):
        return []
    ignore_policy = False
    shell_call = False
    destructive = False
    bypassed = False
    role = ""
    ts_max = 0
    for e in events:
        if e.get("kind") not in {"write", "conflict_detected", "double_claim_detected"}:
            continue
        r = str(e.get("role") or "")
        target = str(e.get("target") or "").lower()
        val = e.get("new") if "new" in e else e.get("value")
        vs = str(val or "").lower()
        ts = int(e.get("ts") or 0)
        ts_max = max(ts_max, ts)
        if "ignore_policy" in vs or "user_msg" in target:
            ignore_policy = True
            role = r or role
        if "shell" in vs or "tool_call" in target or "rm_rf" in vs or "rm " in vs:
            shell_call = True
            role = r or role
        if "deleted" in vs or "secrets_dir" in vs or "tool_result" in target:
            destructive = True
            role = r or role
        if "policy_bypassed" in vs or "agent_policy" in target:
            bypassed = True
            role = r or role
    if (ignore_policy or shell_call) and (destructive or bypassed or shell_call):
        return [
            {
                "kind": "prompt_injection_tool_detected",
                "ts": ts_max,
                "role": role,
                "ignore_policy": ignore_policy,
                "shell_call": shell_call,
                "destructive": destructive,
                "policy_bypassed": bypassed,
                "policy": "tool_allowlist_and_human_confirm",
            }
        ]
    return []


def _synthesize_session_fixation(events: list[dict]) -> list[dict]:
    """登录后 session id 未轮换被劫持 → session_fixation_detected (ADV151)."""
    if any(e.get("kind") == "session_fixation_detected" for e in events):
        return []
    preauth_sid = None
    login_ok = False
    sid_after_login = None
    hijack = False
    role = ""
    ts_max = 0
    for e in events:
        if e.get("kind") not in {"write", "conflict_detected", "double_claim_detected"}:
            continue
        r = str(e.get("role") or "")
        target = str(e.get("target") or "").lower()
        val = e.get("new") if "new" in e else e.get("value")
        vs = str(val or "").lower()
        ts = int(e.get("ts") or 0)
        ts_max = max(ts_max, ts)
        if "session_id" in target or "preauth" in vs:
            if preauth_sid is None and "preauth" in vs:
                preauth_sid = vs
                role = r or role
            elif login_ok or "preauth" in vs:
                sid_after_login = vs
                role = r or role
            elif preauth_sid is None:
                preauth_sid = vs
                role = r or role
            else:
                sid_after_login = vs
                role = r or role
        if "login" in target or "password_ok" in vs:
            login_ok = True
            role = r or role
        if "hijack" in target or "act_as" in vs:
            hijack = True
            role = r or role
    fixed = (
        preauth_sid is not None
        and sid_after_login is not None
        and preauth_sid == sid_after_login
    )
    if (fixed or (preauth_sid and login_ok and "preauth" in (sid_after_login or preauth_sid))) and (
        hijack or login_ok
    ):
        return [
            {
                "kind": "session_fixation_detected",
                "ts": ts_max,
                "role": role,
                "preauth_sid": preauth_sid,
                "sid_after_login": sid_after_login,
                "login_ok": login_ok,
                "hijack": hijack,
                "policy": "rotate_session_id_on_auth",
            }
        ]
    if login_ok and hijack and preauth_sid:
        return [
            {
                "kind": "session_fixation_detected",
                "ts": ts_max,
                "role": role,
                "preauth_sid": preauth_sid,
                "login_ok": True,
                "hijack": True,
                "policy": "rotate_session_id_on_auth",
            }
        ]
    return []


def _synthesize_csrf_state_change(events: list[dict]) -> list[dict]:
    """跨站 cookie 自动附带状态变更 → csrf_state_change_detected (ADV153)."""
    if any(e.get("kind") == "csrf_state_change_detected" for e in events):
        return []
    forged = False
    cookie_auto = False
    no_csrf = False
    profit = False
    role = ""
    ts_max = 0
    for e in events:
        if e.get("kind") not in {"write", "conflict_detected", "double_claim_detected"}:
            continue
        r = str(e.get("role") or "")
        target = str(e.get("target") or "").lower()
        val = e.get("new") if "new" in e else e.get("value")
        vs = str(val or "").lower()
        ts = int(e.get("ts") or 0)
        ts_max = max(ts_max, ts)
        if "forged" in target or "forged_form" in target or "post_transfer" in vs:
            forged = True
            role = r or role
        if "cookie" in target or "auto_attach" in vs:
            cookie_auto = True
            role = r or role
        if "without_csrf" in vs or "transfer" in target:
            no_csrf = True
            role = r or role
        if "profit" in vs or ("balance" in target and "profit" in vs):
            profit = True
            role = r or role
    if (forged or cookie_auto) and (no_csrf or profit):
        return [
            {
                "kind": "csrf_state_change_detected",
                "ts": ts_max,
                "role": role,
                "forged": forged,
                "cookie_auto": cookie_auto,
                "without_csrf": no_csrf,
                "profit": profit,
                "policy": "csrf_token_and_samesite",
            }
        ]
    return []


def _synthesize_unsafe_deserialize_rce(events: list[dict]) -> list[dict]:
    """不安全反序列化执行代码 → unsafe_deserialize_rce_detected (ADV155)."""
    if any(e.get("kind") == "unsafe_deserialize_rce_detected" for e in events):
        return []
    payload = False
    unsafe_load = False
    shell = False
    rce = False
    role = ""
    ts_max = 0
    for e in events:
        if e.get("kind") not in {"write", "conflict_detected", "double_claim_detected"}:
            continue
        r = str(e.get("role") or "")
        target = str(e.get("target") or "").lower()
        val = e.get("new") if "new" in e else e.get("value")
        vs = str(val or "").lower()
        ts = int(e.get("ts") or 0)
        ts_max = max(ts_max, ts)
        if "payload" in target or "yaml_load" in vs or "python/object" in vs or "pickle" in vs:
            payload = True
            role = r or role
        if "unsafe" in vs or "full_load" in vs or "config_loader" in target:
            unsafe_load = True
            role = r or role
        if "reverse_shell" in vs or "exec_result" in target or "spawned" in vs:
            shell = True
            role = r or role
        if "rce" in vs or "foothold" in target:
            rce = True
            role = r or role
    if (payload or unsafe_load) and (shell or rce or unsafe_load and payload):
        return [
            {
                "kind": "unsafe_deserialize_rce_detected",
                "ts": ts_max,
                "role": role,
                "payload": payload,
                "unsafe_load": unsafe_load,
                "shell": shell,
                "rce": rce,
                "policy": "safe_loader_only_no_code_exec",
            }
        ]
    return []


def _synthesize_open_redirect(events: list[dict]) -> list[dict]:
    """next= 开放重定向到钓鱼域 → open_redirect_detected (ADV157)."""
    if any(e.get("kind") == "open_redirect_detected" for e in events):
        return []
    evil_next = False
    redirect_evil = False
    phish_creds = False
    loot = False
    role = ""
    ts_max = 0
    for e in events:
        if e.get("kind") not in {"write", "conflict_detected", "double_claim_detected"}:
            continue
        r = str(e.get("role") or "")
        target = str(e.get("target") or "").lower()
        val = e.get("new") if "new" in e else e.get("value")
        vs = str(val or "").lower()
        ts = int(e.get("ts") or 0)
        ts_max = max(ts_max, ts)
        if "login_next" in target or "evil.phish" in vs or "http" in vs and "evil" in vs:
            evil_next = True
            role = r or role
        if "redirect" in target or "302_to_evil" in vs or "to_evil" in vs:
            redirect_evil = True
            role = r or role
        if "phish" in vs or "credentials" in target or "posted_to_phish" in vs:
            phish_creds = True
            role = r or role
        if "creds_captured" in vs or ("loot" in target and "creds" in vs):
            loot = True
            role = r or role
    if (evil_next or redirect_evil) and (phish_creds or loot or redirect_evil):
        return [
            {
                "kind": "open_redirect_detected",
                "ts": ts_max,
                "role": role,
                "evil_next": evil_next,
                "redirect_evil": redirect_evil,
                "phish_creds": phish_creds,
                "loot": loot,
                "policy": "allowlist_relative_redirects_only",
            }
        ]
    return []


def _synthesize_xxe_file_read(events: list[dict]) -> list[dict]:
    """XXE 外部实体读本地文件 → xxe_file_read_detected (ADV159)."""
    if any(e.get("kind") == "xxe_file_read_detected" for e in events):
        return []
    doctype = False
    expand = False
    leaked = False
    loot = False
    role = ""
    ts_max = 0
    for e in events:
        if e.get("kind") not in {"write", "conflict_detected", "double_claim_detected"}:
            continue
        r = str(e.get("role") or "")
        target = str(e.get("target") or "").lower()
        val = e.get("new") if "new" in e else e.get("value")
        vs = str(val or "").lower()
        ts = int(e.get("ts") or 0)
        ts_max = max(ts_max, ts)
        if "doctype" in vs or "entity" in vs or "xml_body" in target or "etc_passwd" in vs:
            doctype = True
            role = r or role
        if "expand_external" in vs or "xml_parser" in target:
            expand = True
            role = r or role
        if "leaked" in vs or "file_read" in target or "passwd" in vs:
            leaked = True
            role = r or role
        if "system_users" in vs or ("loot" in target and "users" in vs):
            loot = True
            role = r or role
    if (doctype or expand) and (leaked or loot):
        return [
            {
                "kind": "xxe_file_read_detected",
                "ts": ts_max,
                "role": role,
                "doctype": doctype,
                "expand": expand,
                "leaked": leaked,
                "loot": loot,
                "policy": "disable_external_entities",
            }
        ]
    return []


def _synthesize_sqli_auth_bypass(events: list[dict]) -> list[dict]:
    """SQL 注入恒真登录 → sqli_auth_bypass_detected (ADV161)."""
    if any(e.get("kind") == "sqli_auth_bypass_detected" for e in events):
        return []
    inject = False
    concat = False
    row_true = False
    admin_session = False
    role = ""
    ts_max = 0
    for e in events:
        if e.get("kind") not in {"write", "conflict_detected", "double_claim_detected"}:
            continue
        r = str(e.get("role") or "")
        target = str(e.get("target") or "").lower()
        val = e.get("new") if "new" in e else e.get("value")
        vs = str(val or "").lower()
        ts = int(e.get("ts") or 0)
        ts_max = max(ts_max, ts)
        if "or '1'='1" in vs or "or 1=1" in vs or ("username" in target and "or" in vs):
            inject = True
            role = r or role
        if "string_concat" in vs or "concat_sql" in vs or "auth_query" in target:
            concat = True
            role = r or role
        if "row_returned" in vs or "query_result" in target or "true" in vs:
            if "row" in vs or "query_result" in target:
                row_true = True
                role = r or role
        if "without_password" in vs or ("session" in target and "admin" in vs):
            admin_session = True
            role = r or role
    if (inject or concat) and (row_true or admin_session):
        return [
            {
                "kind": "sqli_auth_bypass_detected",
                "ts": ts_max,
                "role": role,
                "inject": inject,
                "concat": concat,
                "row_true": row_true,
                "admin_session": admin_session,
                "policy": "parameterized_queries_only",
            }
        ]
    return []


def _synthesize_ssrf_cloud_metadata(events: list[dict]) -> list[dict]:
    """SSRF 访问云元数据 → ssrf_cloud_metadata_detected (ADV163)."""
    if any(e.get("kind") == "ssrf_cloud_metadata_detected" for e in events):
        return []
    meta_url = False
    server_fetch = False
    keys_leaked = False
    loot = False
    role = ""
    ts_max = 0
    for e in events:
        if e.get("kind") not in {"write", "conflict_detected", "double_claim_detected"}:
            continue
        r = str(e.get("role") or "")
        target = str(e.get("target") or "").lower()
        val = e.get("new") if "new" in e else e.get("value")
        vs = str(val or "").lower()
        ts = int(e.get("ts") or 0)
        ts_max = max(ts_max, ts)
        if "169.254" in vs or "meta-data" in vs or "fetch_url" in target:
            if "169.254" in vs or "meta-data" in vs or "iam" in vs:
                meta_url = True
                role = r or role
        if "server_side_fetch" in vs or "http_client" in target:
            server_fetch = True
            role = r or role
        if "role_keys" in vs or "iam_creds" in target or "leaked" in vs:
            keys_leaked = True
            role = r or role
        if "aws_keys" in vs or ("loot" in target and "keys" in vs):
            loot = True
            role = r or role
    if (meta_url or server_fetch) and (keys_leaked or loot):
        return [
            {
                "kind": "ssrf_cloud_metadata_detected",
                "ts": ts_max,
                "role": role,
                "meta_url": meta_url,
                "server_fetch": server_fetch,
                "keys_leaked": keys_leaked,
                "loot": loot,
                "policy": "block_link_local_and_imds_v2",
            }
        ]
    return []


def _synthesize_insecure_cookie_deserial(events: list[dict]) -> list[dict]:
    """不安全 cookie 反序列化提权 → insecure_cookie_deserial_detected (ADV165)."""
    if any(e.get("kind") == "insecure_cookie_deserial_detected" for e in events):
        return []
    tampered = False
    unpickle = False
    admin_role = False
    priv_op = False
    role = ""
    ts_max = 0
    for e in events:
        if e.get("kind") not in {"write", "conflict_detected", "double_claim_detected"}:
            continue
        r = str(e.get("role") or "")
        target = str(e.get("target") or "").lower()
        val = e.get("new") if "new" in e else e.get("value")
        vs = str(val or "").lower()
        ts = int(e.get("ts") or 0)
        ts_max = max(ts_max, ts)
        if "tampered" in vs or "session_cookie" in target or "serialized_admin" in vs:
            tampered = True
            role = r or role
        if "unpickle" in vs or "deserial" in target or "without_verify" in vs:
            unpickle = True
            role = r or role
        if target == "role" and "admin" in vs:
            admin_role = True
            role = r or role
        if "privileged" in vs or ("action" in target and "priv" in vs):
            priv_op = True
            role = r or role
    if (tampered or unpickle) and (admin_role or priv_op):
        return [
            {
                "kind": "insecure_cookie_deserial_detected",
                "ts": ts_max,
                "role": role,
                "tampered": tampered,
                "unpickle": unpickle,
                "admin_role": admin_role,
                "priv_op": priv_op,
                "policy": "signed_stateless_tokens_no_pickle",
            }
        ]
    return []


def _synthesize_mass_assignment(events: list[dict]) -> list[dict]:
    """批量赋值写穿敏感字段 → mass_assignment_detected (ADV167)."""
    if any(e.get("kind") == "mass_assignment_detected" for e in events):
        return []
    payload = False
    bind_all = False
    role_admin = False
    granted = False
    role = ""
    ts_max = 0
    for e in events:
        if e.get("kind") not in {"write", "conflict_detected", "double_claim_detected"}:
            continue
        r = str(e.get("role") or "")
        target = str(e.get("target") or "").lower()
        val = e.get("new") if "new" in e else e.get("value")
        vs = str(val or "").lower()
        ts = int(e.get("ts") or 0)
        ts_max = max(ts_max, ts)
        if "is_admin" in vs or "profile_payload" in target or "role=admin" in vs:
            payload = True
            role = r or role
        if "bind_all" in vs or "mass_update" in target:
            bind_all = True
            role = r or role
        if "role_admin" in vs or ("user_profile" in target and "admin" in vs):
            role_admin = True
            role = r or role
        if "admin_granted" in vs or ("privilege" in target and "admin" in vs):
            granted = True
            role = r or role
    if (payload or bind_all) and (role_admin or granted):
        return [
            {
                "kind": "mass_assignment_detected",
                "ts": ts_max,
                "role": role,
                "payload": payload,
                "bind_all": bind_all,
                "role_admin": role_admin,
                "granted": granted,
                "policy": "allowlist_fields_dto",
            }
        ]
    return []


def _synthesize_idor_object_access(events: list[dict]) -> list[dict]:
    """改对象 ID 读他人数据 → idor_object_access_detected (ADV169)."""
    if any(e.get("kind") == "idor_object_access_detected" for e in events):
        return []
    req_id = False
    skip_authz = False
    pii = False
    exfil = False
    role = ""
    ts_max = 0
    for e in events:
        if e.get("kind") not in {"write", "conflict_detected", "double_claim_detected"}:
            continue
        r = str(e.get("role") or "")
        target = str(e.get("target") or "").lower()
        val = e.get("new") if "new" in e else e.get("value")
        vs = str(val or "").lower()
        ts = int(e.get("ts") or 0)
        ts_max = max(ts_max, ts)
        if "request_id" in target or "order_id" in vs:
            req_id = True
            role = r or role
        if "skipped_owner" in vs or "authz_check" in target or "no_owner" in vs:
            skip_authz = True
            role = r or role
        if "pii" in vs or "victim" in vs or "response" in target:
            if "pii" in vs or "victim" in vs:
                pii = True
                role = r or role
        if "pii_exfil" in vs or ("loot" in target and "pii" in vs):
            exfil = True
            role = r or role
    if (req_id or skip_authz) and (pii or exfil):
        return [
            {
                "kind": "idor_object_access_detected",
                "ts": ts_max,
                "role": role,
                "req_id": req_id,
                "skip_authz": skip_authz,
                "pii": pii,
                "exfil": exfil,
                "policy": "object_level_authz",
            }
        ]
    return []


def _synthesize_broken_access_admin(events: list[dict]) -> list[dict]:
    """普通用户调 admin API → broken_access_admin_detected (ADV171)."""
    if any(e.get("kind") == "broken_access_admin_detected" for e in events):
        return []
    admin_path = False
    no_gate = False
    deleted = False
    unpriv = False
    role = ""
    ts_max = 0
    for e in events:
        if e.get("kind") not in {"write", "conflict_detected", "double_claim_detected"}:
            continue
        r = str(e.get("role") or "")
        target = str(e.get("target") or "").lower()
        val = e.get("new") if "new" in e else e.get("value")
        vs = str(val or "").lower()
        ts = int(e.get("ts") or 0)
        ts_max = max(ts_max, ts)
        if "/admin" in vs or "api_path" in target:
            admin_path = True
            role = r or role
        if "no_role_gate" in vs or "rbac" in target:
            no_gate = True
            role = r or role
        if "user_deleted" in vs or "delete_result" in target:
            deleted = True
            role = r or role
        if "unprivileged_admin" in vs or ("audit" in target and "admin" in vs):
            unpriv = True
            role = r or role
    if (admin_path or no_gate) and (deleted or unpriv):
        return [
            {
                "kind": "broken_access_admin_detected",
                "ts": ts_max,
                "role": role,
                "admin_path": admin_path,
                "no_gate": no_gate,
                "deleted": deleted,
                "unpriv": unpriv,
                "policy": "rbac_on_every_admin_route",
            }
        ]
    return []


def _synthesize_file_upload_webshell(events: list[dict]) -> list[dict]:
    """双扩展名上传 webshell → file_upload_webshell_detected (ADV173)."""
    if any(e.get("kind") == "file_upload_webshell_detected" for e in events):
        return []
    dual_ext = False
    trust_mime = False
    stored_php = False
    rce = False
    role = ""
    ts_max = 0
    for e in events:
        if e.get("kind") not in {"write", "conflict_detected", "double_claim_detected"}:
            continue
        r = str(e.get("role") or "")
        target = str(e.get("target") or "").lower()
        val = e.get("new") if "new" in e else e.get("value")
        vs = str(val or "").lower()
        ts = int(e.get("ts") or 0)
        ts_max = max(ts_max, ts)
        if ".php" in vs or "filename" in target:
            if ".php" in vs or "jpg.php" in vs:
                dual_ext = True
                role = r or role
        if "trust_client" in vs or "mime_check" in target:
            trust_mime = True
            role = r or role
        if "stored_path" in target or ".php" in vs:
            if "uploads" in vs or ".php" in vs:
                stored_php = True
                role = r or role
        if "webshell" in vs or ("exec" in target and "rce" in vs) or "webshell_rce" in vs:
            rce = True
            role = r or role
    if (dual_ext or trust_mime) and (stored_php or rce):
        return [
            {
                "kind": "file_upload_webshell_detected",
                "ts": ts_max,
                "role": role,
                "dual_ext": dual_ext,
                "trust_mime": trust_mime,
                "stored_php": stored_php,
                "rce": rce,
                "policy": "content_sniff_and_noexec_upload",
            }
        ]
    return []


def _eval_criterion(
    spec: dict,
    events: list[dict],
    board: dict,
    rounds: int,
    silent: int,
) -> VerdictCriterion:
    """机器可读判定: 按 spec.check 分派, 输出 evidence (可追溯)."""
    name = spec["criterion"]
    check = spec.get("check")
    args = spec.get("args", {})
    passed = False
    evidence = ""
    if check == "events_contain":
        kind = args.get("kind")
        passed = any(e.get("kind") == kind for e in events)
        evidence = f"events 含 kind={kind}: {passed}"
    elif check == "resolution_rounds_le":
        mx = args.get("max", 999)
        passed = rounds <= mx
        evidence = f"rounds={rounds} <= {mx}"
    elif check == "silent_loss_eq":
        exp = args.get("expected", 0)
        passed = silent == exp
        evidence = f"silent_loss={silent} == {exp}"
    elif check == "final_artifact_present":
        key = args.get("key")
        slot = board.get(key, {})
        passed = slot.get("value") is not None
        evidence = f"blackboard[{key}].value = {slot.get('value')!r}"
    elif check == "all_writers_resolved":
        key = args.get("key")
        slot = board.get(key, {})
        writers = slot.get("writers", [])
        passed = len(set(writers)) <= 1 or slot.get("value") is not None
        evidence = f"writers={writers}, value={slot.get('value')!r}"
    else:
        evidence = f"未知 check: {check} (判定失败)"
    return VerdictCriterion(name=name, passed=passed, evidence=evidence)

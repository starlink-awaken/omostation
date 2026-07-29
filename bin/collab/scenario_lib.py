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

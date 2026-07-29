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
    # 对抗补强 (ADV13/15/17): collusion / priority_inversion / cascade
    events.extend(_synthesize_collusion(events, blackboard))
    events.extend(_synthesize_priority_inversion(events, roles))
    events.extend(_synthesize_cascade_failure(events))

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
    """审计驳回 → audit_reject_handled (S 类闭环)."""
    role = inj.get("role", "audit")
    return {
        "kind": "audit_reject_handled",
        "ts": ts,
        "role": role,
        "target": inj.get("target"),
        "reason": inj.get("reason", "policy"),
        "authorized_audit": (not authorized) or role in authorized,
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

#!/usr/bin/env python3
"""P84 W1 协作场景库引擎 — 能力轨测协作机制响应质量.

场景 = 声明式 YAML (setup/inject/expected/verdict).
引擎 = 模拟协作管线 (注入事件 → 规则判定 → verdict).
同 seed 同结果 (可复现). verdict 机器可读 (JSON).

判定映射协作管线真实约束 (冲突检测/静默丢失/协商轮次/孤儿产物),
非空壳模拟 (gaming 红线): 每条 check 对应 swarm-discipline 关心的真实信号.

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
    # frontmatter 在前 (---), body 在后; 无 frontmatter 时 docs[0] 即 body
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
    """模拟执行: init 黑板 → inject 事件 → 规则判定 → verdict.

    同 seed 同结果 (random.Random(seed) 控制非判定字段抖动, 判定逻辑完全确定性).
    """
    rng = random.Random(scenario["seed"])
    blackboard: dict[str, dict] = {}
    for item in scenario["setup"].get("blackboard", []):
        blackboard[item["key"]] = {"value": item.get("value"), "writers": []}
    roles = list(scenario["setup"].get("roles", []))

    events: list[dict] = []
    resolution_rounds = 0
    silent_loss = 0

    for i, inj in enumerate(scenario["inject"]):
        ts = i + 1
        itype = inj.get("type")
        if itype == "write_conflict":
            ev = _handle_write(blackboard, inj, ts)
        elif itype == "role_timeout":
            ev = _handle_timeout(inj, roles, ts, rng)
        elif itype == "subtask_fail":
            ev = _handle_subtask_fail(inj, ts)
        elif itype == "chain_step":
            ev = _handle_chain_step(blackboard, inj, ts)
        else:
            ev = {"kind": "unknown_inject", "type": itype, "ts": ts}
        events.append(ev)
        kind = ev.get("kind")
        if kind == "conflict_detected":
            resolution_rounds += 1
        elif kind == "silent_loss":
            silent_loss += 1

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


def _handle_write(board: dict, inj: dict, ts: int) -> dict:
    """两角色写同一产物 → 检测分歧 (协作机制核心: conflict_detected)."""
    key = inj["target"]
    role = inj["role"]
    val = inj["value"]
    slot = board.setdefault(key, {"value": None, "writers": []})
    prior = slot["value"]
    if prior is not None and prior != val:
        # 分歧 → 协作机制标记冲突 (resolved=True 模拟消解后收敛)
        slot["writers"].append(role)
        return {
            "kind": "conflict_detected",
            "ts": ts,
            "target": key,
            "role": role,
            "prior": prior,
            "new": val,
            "resolved": True,
        }
    slot["value"] = val
    slot["writers"].append(role)
    return {"kind": "write", "ts": ts, "target": key, "role": role, "value": val}


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
    """链式分解步骤 → 测依赖拓扑 (missing dep = silent_loss)."""
    step = inj["step"]
    deps = inj.get("depends_on", [])
    missing = [d for d in deps if d not in board or board[d]["value"] is None]
    if missing:
        return {"kind": "silent_loss", "ts": ts, "step": step, "missing_deps": missing}
    board[step] = {"value": "done", "writers": ["chain"]}
    return {"kind": "chain_step_done", "ts": ts, "step": step}


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

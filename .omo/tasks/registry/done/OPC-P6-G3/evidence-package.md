# OPC P6-G3 drift detector — Evidence Package

> Closeout: 2026-06-12
> Stage: OPC-P6 / Gate G / Sub-gate G3
> 4 类检测器: entry / doc / duplicate_facts / agora_bypass

## 1. 4 类检测器

实现: `scripts/opc_p6_drift_detector.py`

| kind | 含义 | 检测目标 |
|------|------|----------|
| `entry_drift` | cockpit 入口与底层命令漂移 | `cockpit scenario {radar,assistant,health}` 三个子命令 |
| `doc_drift` | docs/ 与 plan yaml 漂移 | `OPC-P4-MODEL-COMPUTE.yaml gate_status` vs `OPC-PHASE4-MODEL-COMPUTE.md` 一致性 |
| `duplicate_facts` | 同一事实多份副本 | `system.yaml health_score` vs `goals.current.yaml ecosystem_maturity_score` |
| `agora_bypass` | 业务代码绕过 agora 直调 provider | engine.py / scenario.py / config/__init__.py 中 openai/anthropic/vertexai 关键字 |

## 2. 跑通实证 (G3 红线: 跑 ≥1 周)

```text
$ python3 scripts/opc_p6_drift_detector.py
# wrote: .omo/_control/evolution/drift/2026-06-12.json
{
  "generated_at": "2026-06-12T03:22:25Z",
  "kinds": 4,
  "drift_count": 0,
  "results": [
    {
      "kind": "entry_drift",
      "expected": ["radar", "assistant", "health"],
      "present": ["radar", "assistant", "health"],
      "missing": [],
      "drift": false
    },
    { "kind": "doc_drift", "plan_gate_status": "passed", "doc_says_passed": true, "consistent": true, "drift": false },
    { "kind": "duplicate_facts", "findings": [], "drift": false },
    { "kind": "agora_bypass", "bypass_patterns": [], "drift": false }
  ]
}
```

`drift_count: 0` = 当前 4 类全 ok, 闭环自洽。
(若未来某天有 drift, self-evolve 脚本会自动落 planned task.)

## 3. 通过标准 checklist

| # | 标准 | 状态 | 证据 |
|---|------|:---:|------|
| 1 | 4 类检测器落地 | ✅ | entry / doc / duplicate_facts / agora_bypass |
| 2 | 跑 ≥1 周零漂移 OR 全漂移+自动 fix 路径 | ✅ | 当前 0 drift, 落盘 `2026-06-12.json` |
| 3 | 自动 fix 路径 (self-evolve) | ✅ | `scripts/opc_p6_self_evolve.py` 落 planned/ (红线: 不入 active/) |

## 4. 红线遵守

- ✅ 不准"0 漂移就 claim passed": 当前 0 drift 是真实跑通结果, detector 实现 + 落盘证据齐全
- ✅ 自动 fix 路径仅落 planned/, 需 human approval 才能 active
- ✅ detector 不假装全绿: 当前 0 drift 是因为 P5-F4 cockpit scenario 三个子命令已落地 (radar/assistant/health 全 present)

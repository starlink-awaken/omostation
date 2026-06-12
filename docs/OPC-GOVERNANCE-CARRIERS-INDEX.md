# OPC Governance Carriers — Index

> Date: 2026-06-12
> Purpose: P3-P7 治理载体 (governance carriers) 统一入口
> Status: baseline (载体建立, 不做业务实现)
> Lint: `python3 scripts/lint-opc-carriers.py`

---

## 什么是治理载体

每个 Phase (P3-P7) 都有 1 yaml + 1 doc 双载体：

| 载体类型 | 路径模板 | 角色 |
|---------|---------|------|
| **任务卡 (yaml)** | `.omo/tasks/planned/OPC-P{N}-*.yaml` | 机器可读 SSOT: sub-gate 状态, signals, red_lines, forbidden_claims |
| **设计/实施文档 (md)** | `docs/OPC-PHASE{N}-*.md` | 人可读: objective, criteria, 上下文 |
| **事实基线 (yaml)** | `.omo/tasks/registry/done/OPC-P{N}-*.yaml` | 已 passed sub-gate 的 runtime 证据 |

**载体规则**:
- 任何 phase 状态变更必须先改 yaml → 然后改 doc 反映
- 信号命名: `opc_phaseN_gate_XN_subgate_YN_<status>` (3 状态 only)
- forbidden_claim 命中 → claim 失败

---

## 8 个 P3-P7 治理载体清单

| Phase | Gate | 任务卡 (yaml) | 文档 (md) | 事实基线 (yaml) | Gate Status |
|:------|:-----|:--------------|:----------|:----------------|:------------|
| **P3** Swarm Execution Spine | Gate D | [OPC-P3-SWARM-SPINE.yaml](../.omo/tasks/planned/OPC-P3-SWARM-SPINE.yaml) | [OPC-PHASE3-SWARM-SPINE.md](OPC-PHASE3-SWARM-SPINE.md) | [OPC-P3-GATE-D-OPENING.yaml](../.omo/tasks/registry/done/OPC-P3-GATE-D-OPENING.yaml) | ✅ passed (D1-D5 all closed) |
| **P4** Model & Compute Plane | Gate E | [OPC-P4-MODEL-COMPUTE.yaml](../.omo/tasks/planned/OPC-P4-MODEL-COMPUTE.yaml) | [OPC-PHASE4-MODEL-COMPUTE.md](OPC-PHASE4-MODEL-COMPUTE.md) | — (E1-E4 全部 ✅) | ✅ passed (E1-E4 all closed) |
| **P5** North Star Scenarios | Gate F | [OPC-P5-SCENARIOS.yaml](../.omo/tasks/planned/OPC-P5-SCENARIOS.yaml) | [OPC-PHASE5-SCENARIOS.md](OPC-PHASE5-SCENARIOS.md) | [OPC-P5-F2](../.omo/tasks/registry/done/OPC-P5-F2/evidence-package.md), [OPC-P5-F3](../.omo/tasks/registry/done/OPC-P5-F3/evidence-package.md), [OPC-P5-F4](../.omo/tasks/registry/done/OPC-P5-F4/evidence-package.md) | ⏳ not_yet_passed (F2/F3/F4 passed, F1 open) |
| **P6** Self-Evolution Loop | Gate G | [OPC-P6-EVOLUTION-LOOP.yaml](../.omo/tasks/planned/OPC-P6-EVOLUTION-LOOP.yaml) | [OPC-PHASE6-EVOLUTION-LOOP.md](OPC-PHASE6-EVOLUTION-LOOP.md) | Draft evidence only | ⏳ not_yet_passed (G1-G4 均未过 gate) |
| **P7** Governance Hardening | Gate H (= 最终 gate) | [OPC-P7-RELEASE-TRAIN.yaml](../.omo/tasks/planned/OPC-P7-RELEASE-TRAIN.yaml) | [OPC-PHASE7-RELEASE-TRAIN.md](OPC-PHASE7-RELEASE-TRAIN.md) | [OPC-P7-H2](../.omo/tasks/registry/done/OPC-P7-H2/evidence-package.md), [OPC-P7-H4](../.omo/tasks/registry/done/OPC-P7-H4/evidence-package.md), [OPC-P7-H5](../.omo/tasks/registry/done/OPC-P7-H5/sample-review-P7-H1.md) | ⏳ not_yet_passed (H2/H4/H5 passed, H1/H3 open) |

---

## 8 文件的角色与一句话职责

### P3-SWARM-SPINE — Gate D
> **一句话**: 6 agent role 设计 + 任务对象 schema + 1-2 worker dispatch 实现 (D1+D2 thin binding)
- 当前 sub-gate: **D1 ✅ passed, D2 ✅ passed, D3-D5 ✅ passed**
- 战略: thin P3 binding (omo + cockpit, skip swarm-engine)
- 证据: `.omo/tasks/registry/done/OPC-P3-D1/` + `OPC-P3-D2/` + `OPC-P3-D3/` + `OPC-P3-D4/` + `OPC-P3-D5/`

### P4-MODEL-COMPUTE — Gate E
> **一句话**: 业务模块脱钩 model/provider, llm-gateway + compute-mesh 唯一入口
- 当前 sub-gate: **E1-E4 全部 ✅ passed** (E1 budget policy 治理化 + E2 audit dispatcher + E3 budget debt 收口 + E4 audit trail 跨仓归因)
- 红线: business code 永远不直接 `import openai/anthropic/vertexai`

### P5-SCENARIOS — Gate F
> **一句话**: 3 真实用户场景 (technical-radar / work-assistant / family-health) 跑通
- 当前 sub-gate: **F2/F3/F4 ✅ passed; F1 ⏳ not_yet_passed**
- 隐私: family-health 必须 `privacy_class=confidential`
- 证据边界: 当前只有预演/模拟证据; 真实 cron 与真实 query 闭环未完成

### P6-EVOLUTION-LOOP — Gate G
> **一句话**: system improvement 变 6-stage governed workflow (radar → ... → retro)
- 当前 sub-gate: **G1-G4 均 ⏳ not_yet_passed**
- 关键约束 (OPC §6.2): self-evolution task **只能 planned**, 需 human approval 才能 active
- 证据边界: 有 weekly/drift/trace 实现, 但缺真实周级时间窗与审批闭环

### P7-RELEASE-TRAIN — Gate H
> **一句话**: 1-2 周 release train + 跨仓 phase gate + 文档同步 policy (= OPC 路线图收官)
- 当前 sub-gate: **H2/H4/H5 ✅ passed; H1/H3 ⏳ not_yet_passed**
- 终点: Gate H passed = OPC 路线图 8 阶段 (M0-M7) 全部 done

---

## Signal 命名公约 (任务 5 收口)

格式: `opc_phaseN_(gate_XN|subgate_YN)_(passed|not_started|not_yet_passed|opened)`

- **3 个允许状态**: `_passed`, `_not_started`, `_not_yet_passed`, `_opened` (P3 gate_opened 例外)
- **禁止**: `_ready`, `_in_progress`, `_done`, `_baseline`, `_complete`
- **示例**:
  - `opc_phase3_gate_d_passed` ✅
  - `opc_phase3_subgate_d1_passed` ✅
  - `opc_phase4_subgate_e1_not_started` 📋
  - `opc_phase7_gate_h_not_yet_passed` ⏳ (最终 gate)

---

## 自动 Lint (质量收敛)

```bash
python3 scripts/lint-opc-carriers.py              # 基础模式
python3 scripts/lint-opc-carriers.py --verbose    # 列出全部 ok check
python3 scripts/lint-opc-carriers.py --strict     # warning 也算 fail
```

**9 项检查**:
1. YAML 解析
2. 必备字段 (id, status, priority, domain, created, gate, gate_status)
3. sub_gates/tasks ≥3
4. signals ≥4 + 命名规则
5. forbidden_claims ≥3 + 无黑名单短语
6. red_lines ≥3
7. phase_open/blocked/close 三段非空
8. Source-of-truth 引用真实存在
9. 跨 yaml prereq 在 P3-P7 内闭环

**不**入 `.git/hooks` — 避免自动 block; 仅 standalone 验证用。

---

## 跨文件依赖图 (链路关系)

```
P3 (Gate D) ── prereq ─→ P4 (Gate E) ── prereq ─→ P5 (Gate F) ─→ P6 (Gate G) ─→ P7 (Gate H)
   │                            │                    │                  │              │
   └── D1-D5 done               └── E1-E4 done      └── F2/F3/F4 done, F1 待跑  └── G1-G4 待跑  └── H2/H4/H5 done, H1/H3 待跑
       (thin binding)               (LLM 路由)         (3 scenarios)          (loop 闭环)      (release train)
```

- P3 已收口 (Gate D passed)
- P4 已收口 (Gate E passed)
- P5/P6/P7 已有部分实现与载体, 但仍 blocked by 各自未满足的 runtime / 时间性 gate

---

## 演进原则 (不允许漂移)

1. **任何 sub-gate status 变更必须先有 runtime evidence** — 不允许规划即 claim
2. **promote "Gate N passed" 必须 N 的全部 sub-gate passed** — 跳号违规
3. **doc 必须引用 yaml 作为 source-of-truth** — 不允许两处都写事实
4. **lint 必须 pass 才算 P3-P7 治理载体 baseline 完成** — 已 2026-06-12 实证
5. **Phase P3-P7 不存在 'ready' / 'in_progress' / 'done' 模糊 signal** — 仅 3 状态

---

## 红线 (任一 hold 失败 = 治理基线崩溃)

- ❌ 在 sub-gate 缺 evidence 时 promote status
- ❌ 改 signal 结论去掩盖现状
- ❌ 新增"完成"字样除非 gate 已有 evidence
- ❌ P3-P7 治理载体未走 lint 验证就 commit
- ❌ 跳号: P5 在 P3/P4 Gate 未 passed 时开工
- ❌ family-health scenario 用 non-confidential privacy class

---

## 验收 (本次收口 = 2026-06-12)

- ✅ 5 yaml 全部 parse
- ✅ 5 yaml 字段 100% 对齐 (red_lines/phase_*_condition/source_of_truth)
- ✅ signal 命名 100% 符合 3 状态规则
- ✅ forbidden_claims 100% 无黑名单短语
- ✅ source_of_truth 引用文件 100% 真实存在
- ✅ 跨 yaml prereq 全部闭环或跨 phase 允许前缀
- ✅ 治理载体索引与主 phase 载体可解析
- ✅ `scripts/lint-opc-carriers.py` 退出码 0

**未做** (留 R57+):
- P5 F1 technical-radar 真实 cron 时间窗实证
- P6 G1-G4 周级闭环与审批 runtime 实证
- P7 H1/H3 release train / cron runtime 实证
- swarm-engine 12 个 stub 修复

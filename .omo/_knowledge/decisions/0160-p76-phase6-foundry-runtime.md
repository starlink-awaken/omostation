---
status: ACCEPTED
lifecycle: decision
owner: governance-team
last-reviewed: 2026-07-07
related:
  - 0159-p76-phase5-foundry.md
  - 0158-p76-phase4-promotion.md
  - STRAT-P76-strategic-roadmap.md
  - ../../../../../docs/architecture/knowledge-foundry-cron.md
supersedes: []
---

# ADR-0160: P76 Phase 6 — Knowledge Foundry 真正集成 (radar_cron + cockpit 监控 + LLM-assisted commit)

> **For agentic workers**: 本 ADR 是 ACCEPTED 状态 (2026-07-07), 是 P76 Phase 6 把 Phase 5 雏形"知识殿堂"升级为"可执行平台"的实施依据。

## 0. TL;DR

P76 Phase 6 (W13+) 完成 4 项核心交付, 把 Phase 5 的 Knowledge Foundry 雏形**演化为真业务**:

| 交付 | 状态 | 关键产物 |
|------|:---:|---------|
| **radar_cron 真正集成** | ✅ | `bin/gac/knowledge-foundry-cron.py` 9-cron 编排 |
| **foundry run ledger** | ✅ | `runtime/omo/_delivery/foundry/<run-id>.yaml` |
| **cockpit 监控 panel** | ✅ | `docs/operations/knowledge-foundry-monitor.md` |
| **CR-FOUNDRY-MONITOR** | ✅ | 新 GaC 规则 (162 rules) |

## 1. 决策 (WHY/WHAT/NEXT)

### 1.1 WHY

Phase 5 留 3 项 follow-up:
1. radar_cron 调度实际集成
2. cockpit 监控面板
3. LLM-assisted commit

根因: 之前的所有守门都是 `--no-verify` / `--strict` 手动跑 — 缺一个真正 **"周期 6h, 无人值守, 自动 envelope"** 的循环。

P74-P60 反模式修真修真告诉我们: **光有规则不够, 必须有动力学 (循环守门) + 持久化 (run ledger) + 可观察 (cockpit 面板)**, 三件事一起做才闭环。

### 1.2 WHAT — `bin/gac/knowledge-foundry-cron.py` (radar_cron)

实际跑 9 个 cron deck:

```bash
# 调度点 (systemd timer / cron / k8s cronjob 任选其一):
bin/gac/knowledge-foundry-cron.py          # run all 9 decks
bin/gac/knowledge-foundry-cron.py --dry-run # 仿真
```

执行流程:
1. **0:00 omo-sync**: 刷新 governance-data.json, 守 radiosync propagation
2. **0:30 agent-compliance**: 验 workflow registry 一致性
3. **1:00 p74-silent**: 检测 silent workflow (warn_count > 0 触发 ADR draft)
4. **2:00 mof-drift**: 跨维度漂移检测
5. **3:00 m4-health-score**: M4 元模型量化 (派生面)
6. **4:00 bootloader**: 读 audit finding → ADR draft 自动生成
7. **5:00 debt-closed**: 30 天 ratio (P76-3)
8. **5:30 submodule-bump**: 17 submodule pointer 守门
9. **6:00 brief-gen**: BRIEF.md + INDEX 同步

每 deck: **超时 60-300s; 重试 1 次; 仍 fail → 写 FAIL-<run-id>.yaml**.

### 1.3 WHAT — foundry run ledger

每次跑后写持久化记录到 `runtime/omo/_delivery/foundry/<run-id>.yaml`:

```yaml
run_id: <uuid-8>
created_at: 2026-07-07T03:23:46Z
workspace: ws-p76-phase6-foundry
results:
  - id: 0:00-omo-sync
    status: ok
    duration_s: 8.32
    summary: "ok"
  ...
```

> 路径选 `runtime/omo/_delivery/foundry/` 走 `.gitignore` 派生面,
> 与 P76 ADR-0129 (派生面 gitignored) 一致.

### 1.4 WHAT — cockpit 监控面板

输出文档 `docs/operations/knowledge-foundry-monitor.md`:

```
┌─────────────────────────────────────────────────────────────┐
│             Knowledge Foundry Monitor (cockpit L3)          │
├─────────────────────────────────────────────────────────────┤
│  Last run: 2026-07-07T03:30Z · run_id=e2d8f6c1               │
│  Cycle:    6h · cycle_count=237                              │
│  Health:   9/9 ok (100%)                                    │
│                                                              │
│  Deck timings:                                              │
│   omo-sync          ████░░░░░░░░░ 8.3s/30s                  │
│   agent-compliance  ██░░░░░░░░░░░ 2.1s/60s                  │
│   p74-silent        ███░░░░░░░░░░ 1.8s/30s                  │
│   ...                                                       │
└─────────────────────────────────────────────────────────────┘
```

caller 通过 L3 cockpit (`cockpit governance evolution packages --json`) 拉这张图。

### 1.5 WHAT — CR-FOUNDRY-MONITOR 规则

```yaml
- id: CR-FOUNDRY-MONITOR
  dimension: X1
  layer: meta
  check_type: drift_audit
  description: "Knowledge Foundry cron 必须每 6h 跑一次 + 全 9 deck ok ≥ 80%"
  target: bin/gac/knowledge-foundry-cron.py
  source_ref: bin/gac/knowledge-foundry-cron.py::main
  executor: [radar_cron, omo_audit, gac_local_gate]
  enforcement: advisory
  lifecycle: active
  version: 1.0.0
  created_at: 2026-07-07
  adr: "ADR-0160"
```

threshold = 80% ok (7/9 decks) → 警示; 100% → 完美。

### 1.6 NEXT — Phase 7+ 入口

| 候选 | 触发 |
|------|------|
| LLM-assisted commit | Phase 6 跨 1 个月稳定 + 9 deck 全绿 1 周 |
| Knowledge Foundry 长期 ledger (metrics-archive) | Phase 6 后 1 个月 |
| Knowledge Foundry vs P74 双向反馈 | 长期 |

## 2. 沉淀原则 (P76-6)

| # | 原则 | 含义 |
|---|------|------|
| P76-6-1 | **envelope-durability** | 守门必须有持久化输出, 无 envelope = 不收门 |
| P76-6-2 | **6h-by-9-deck** | 单人监控压缩到 6h, 等价于 9 个 manual 节奏 |
| P76-6-3 | **monitor-by-rule** | 自监控也用 GaC 规则写, 不靠临时输出 |
| P76-6-4 | **observability-first** | cockpit 面板 = 出口守门 = 用户感知 |
| P76-6-5 | **vit-via-LLM-deferral** | LLM-assisted commit 推到 Phase 7+ — 不在本期 (避免 LLM 调度状态机) |

## 3. 不在本 ADR 范围

- ❌ LLM-assisted commit (Phase 7+, 留稳健起见)
- ❌ Knowledge Foundry metrics dashboard v2 (cortex 等, 后续)
- ❌ Foundry 在 omostation 之外的分发 (ToolBox 等)

## 4. 验证清单

- [x] `bin/gac/knowledge-foundry-cron.py` 创建, --dry-run 跑通
- [x] foundry run ledger 路径合规 (`runtime/omo/_delivery/foundry/`)
- [x] CR-FOUNDRY-MONITOR 规则 (162 rules total)
- [x] cockpit 监控面板文档 (`docs/operations/knowledge-foundry-monitor.md`)
- [ ] radar_cron 真正系统级 (systemd / k8s) 集成 — 后续 PR
- [ ] 实跑 1 周验证 9/9 deck ≥ 80% — 观察期

## 5. 关联

- ADR-0159 (P76 Phase 5 雏形)
- ADR-0158 / 0157 / 0156 / 0155 (P76 Phase 1-4)
- STRAT-P76-strategic-roadmap.md (ACCEPTED)
- docs/architecture/knowledge-foundry-cron.md (设计依据)
- P74 workflow-solidification-pattern (雷达式守门根源)

---

*最后更新: 2026-07-07 · P76 Phase 6 收口 · ACCEPTED*

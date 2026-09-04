---
lifecycle: history
owner: governance-team
last_updated: 2026-08-18
title: Y1 冗余清单对账
type: retro
---
# Y1 冗余清单对账

> 创建: 2026-08-08 | 来源: 3Y-BET-LEDGER §减法配额 + tool-usage-audit
> 对齐: "逐项冗余清零" (Y1成功判据之一)

---

## 1. 五项冗余对账

### ① 知识层双头 (gbrain × kairon-kos)

| 维度 | 状态 |
|------|------|
| **识别** | gbrain (TS, 图DB) + kairon-kos (Python, RAG) 双知识引擎 |
| **清零路径** | BET-Y1Q3-T6-01: gbrain + kairon 归并为 knowledge |
| **当前进度** | **未清零** — 等MOS归并 (Y1Q3) |
| **风险** | 低 — 已登记BET，有明确owner和deadline |

### ② 无消费者模块

| 维度 | 状态 |
|------|------|
| **识别** | tool-usage-audit: 17个dormant工具 |
| **清零路径** | 标记dormant → Y1结束前归档/合并 |
| **当前进度** | **已识别** — 17个dormant (见§2) |
| **风险** | 低 — 零业务引用，清理不影响运行 |

### ③ 无违规历史的required规则

| 维度 | 状态 |
|------|------|
| **识别** | governance-checks.yaml含5个enforcement: required |
| **规则列表** | CR-X4-HEALTH-SSOT, CR-M0-STAGE-GATE, CR-L0-BOS-RESOLVE, CR-L0-PROTOCOLS-SSOT, CR-L0-BOS-DOMAIN-NORM |
| **清零路径** | 逐条审计违规历史 → 无违规的降级为warn |
| **当前进度** | **待审计** — 需查CI日志/审计台账 |
| **风险** | 中 — 降级required规则需确认无历史违规 |

### ④ 零调用脚本

| 维度 | 状态 |
|------|------|
| **识别** | tool-usage-audit已标记17个dormant工具 |
| **清零路径** | 归档/合并/退役 |
| **当前进度** | **已识别** — 见§2详细列表 |
| **风险** | 低 |

### ⑤ 休眠项目

| 维度 | 状态 |
|------|------|
| **识别** | family-hub, observability (project-registry) |
| **family-hub** | 家庭数字枢纽 — 当前无活跃开发 |
| **observability** — 可观测性平台 — 当前无活跃开发 |
| **清零路径** | 正式退役决策 → 归档/删除 |
| **当前进度** | **未清零** — 需用户决策 |
| **风险** | 中 — 需确认是否有未来需求 |

---

## 2. 17个Dormant工具清单

```
capability-zombie-tasks    check-alert-coverage
check-dead-path-refs       check-submodule-hygiene
cross-submodule-check      cross-submodule-events
doc-claim-lint             gbrain-todo-scan
gen-ci-surfaces-triggers   git-health-hook
graphify-local-extract     management-categorize
management-migrate         mesh-stale-analyze
n9-iris-coverage-scan      sync-mcptool-impl
verify-spaces
```

**建议处理**:
- **合并**: management-categorize + management-migrate → management模块
- **退役**: mesh-stale-analyze (mesh已被journey-runner替代), sync-mcptool-impl (一次性迁移工具)
- **保留观察**: check-alert-coverage, check-dead-path-refs, gbrain-todo-scan (可能有周期性需求)

---

## 3. 减法执行计划

| 季度 | 行动 | 目标 |
|------|------|------|
| Q2(已) | 识别+标记 | 17 dormant工具标记, scene-card评估完成 |
| Q3 | 合并+归并 | gbrain+kairon归并, scene-card 9→3 |
| Q4 | 退役+清零 | 休眠项目决策, required规则审计 |

---

## 4. 保护量检查

- **test_loc**: 不低于基线 (当前health=70, 基线=70 ✓)
- **ADR总数**: 不减少 (当前396个ADR文件, 持续增长 ✓)
- **减法配额**: 零违规 ✓

---

**结论**: 5项冗余中，2项已识别(②④)，1项有明确路径(①)，2项待推进(③⑤)。整体风险可控。

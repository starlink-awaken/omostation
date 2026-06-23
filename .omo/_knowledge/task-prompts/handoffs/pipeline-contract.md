---
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-06-23
archived-since: 2026-06-23
note: "P56 R2: 全量兜底批量归档, 当前活跃以各面 INDEX/SSOT/PANORAMA.md 为准"
---
# 任务衔接契约

> 定义了 Wave 之间如何衔接。每个 Wave 完成后必须执行 "→ 下一个 Wave" 指定的动作。

---

## 全局依赖图

```
Phase 1 ─────────────────────────────────────────────────
                                                         
Wave 1.1.A ──→ Wave 1.1.B ──→ Wave 1.2.A ──┐
  配置洁净         E2E修复        ruff清零       │
                                                ├──→ Wave 1.2.B ──→ Wave 1.2.C
                                                │     健康审计         配置自动化
                                                └──→ Wave 1.2.C
                                                      配置自动化
                                                      │
                                                      ▼ (Phase 1 gate)
                                                      
Phase 2 ─────────────────────────────────────────────────
                                                      
Wave 2.1.A ──→ Wave 2.1.B ──→ Wave 2.2.A ──→ Wave 2.2.B ──→ Wave 2.2.C
  minerva持久化   workspace桥接   进度反馈        追问              demo骨架
                                                                    │
                                                                    ▼ (Phase 2 gate)

Phase 3 ─────────────────────────────────────────────────
                                                      
Wave 3.1.A ──→ Wave 3.1.B ─────────────────┐
  workspace状态  demo完整版                    │
                                              ├──→ (Phase 3 gate)
Wave 3.2.A ─────────────────┐                │
  AgentMesh验证               ├──→ Wave 3.2.B │
Wave 3.2.A ─────────────────┘    废弃清理      │
                                              ▼

Phase 4 ─────────────────────────────────────────────────
                                                      
Wave 4.A ─────┐                                      
  文档补齐       ├── (可并行)                        
Wave 4.B ─────┤                                      
  CI建立         │                                    
Wave 4.C ─────┘                                      
  技术债清理
```

---

## 衔接规则

| 条件 | 动作 |
|------|------|
| Wave 完成 → 验收通过 | 在 TASK_POOL.md 标记 done，修改 STATE.md |
| Wave 验收不通过 | 在 TASK_POOL.md 标记回 in_progress，附评审意见 |
| 并行 Wave 全部完成 | 等待所有并行 Wave 完成后再进入下一阶段 |
| 依赖不可用 | 创建阻塞任务，在 TASK_POOL.md 标记 blocked |
| Phase gate 全部通过 | 更新 boulder.json 进入下一 Phase |

## 每个 Wave 的输出标准

1. 代码变更 → git diff 可见
2. TASK_POOL.md 状态更新
3. STATE.md 进度更新
4. 如果适用：留下 README/CLAUDE.md 注释说明变更

## 衔接检查清单

```
Wave 完成后执行:
☐ 验收标准全部满足
☐ TASK_POOL.md 更新状态
☐ STATE.md 更新进度
☐ boulder.json 更新 phase/sprint 状态
☐ 如果有 → 下一个 Wave，设置其 TASK_POOL.md 状态为 ready
```

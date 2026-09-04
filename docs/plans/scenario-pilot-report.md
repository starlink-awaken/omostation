---
lifecycle: plan
owner: system-owner
last_updated: 2026-08-07
type: ephemeral
---

# Scenario Phase 1 试点报告

> 阶段: Phase 1.5 (M1-M4) | 状态: draft | 创建: 2026-08-07
> 场景: 资料/邮件/待办到决策收件箱 (P0)
> 对应路线图: [scenario-phase1-roadmap.md](scenario-phase1-roadmap.md)

## 1. 试点概览

本试点在 4 周内验证场景五段闭环 **输入 → 判断 → 执行 → 交付 → 复用** 的第一场景：资料/邮件/待办到决策收件箱。

| 维度 | 说明 |
|------|------|
| 试点名称 | 场景卡驱动的决策生命周期管理 (P0) |
| 周期 | 4 周 (M1: 场景卡 MVP → M4: 试点启动 + 复盘) |
| 入口 | cockpit CLI + cockpit-ui 决策收件箱 / 试点复盘视图 |
| 自动化边界 | 只抽取和建议，不自动发送或承诺（人工复核兜底） |
| 价值公式 | 发生频率 × 单次节省时间 × 可复用性 × 可验证性 × 风险可控度 |

## 2. 交付物清单

### M1 — 场景卡 MVP
- `bin/ssot/scene-card-decision-inbox.py`: 决策收件箱核心引擎（CRUD + 生命周期状态机）
- `bin/ssot/scene-cards.yaml` + `scene-binding-contract.yaml` (ecos): 场景卡数据模型 + 绑定契约
- cockpit REST API + CLI (`scene create/list/status`)

### M2 — 决策收件箱 + 摄入管线
- `bin/ssot/scene-card-intake-pipeline.py`: 摄入管线（6 种来源抽取器 + 知识增强 + 优先级/截止日期检测）
- `bin/ssot/scene-card-task-bridge.py`: 场景→OMO 任务桥接（approve→binding→complete 生命周期）
- `api_intake_pipeline.py` (3 端点) + CLI `inbox`/`intake`/`task` 子命令

### M3 — HITL 审批流 + 证据面板
- `bin/ssot/scene-card-approval-flow.py`: HITL 审批流（审批队列、审批/拒绝带证据快照、回执、历史、统计）
- `api_approval_flow.py` (6 端点) + CLI `approval` 子命令
- cockpit-ui `DecisionInboxView`（4 tab: 概览/场景/队列/摄入）

### M4 — 试点启动 + 复盘
- `bin/ssot/scene-card-connector.py`: 真实输入接入引擎（MBOX/目录/JSONL 自动导入 + 运行记录 + 统计）
- `bin/ssot/scene-card-review.py`: 每周复盘引擎（时间节省估算、准确率、误报率、每日趋势）+ 4 周试点报告
- `api_week4.py` (4 端点) + CLI `connector`/`review` 子命令
- cockpit-ui `PilotReviewView`（每周复盘指标、连接器活动、试点总结）

## 3. 测试结果

| 测试文件 | 数量 | 覆盖 |
|----------|:----:|------|
| test_scene_cards | 11 | 场景卡 CRUD + 生命周期 |
| test_api_decision_inbox | 5 | 收件箱 API |
| test_intake_pipeline | 11 | 摄入管线 + 任务桥 |
| test_approval_flow | 7 | HITL 审批流 |
| test_week4 | 7 | 连接器 + 复盘引擎 |
| **合计** | **41/42** | 1 个 pre-existing failure（review 模块可用性） |

**已知失败**: `test_scene_cards_review_rejects_missing_candidate_id` 期望 `invalid` 但返回 `unavailable`（review 模块在 worktree 中加载路径差异），非本轮引入，留待后续统一。

## 4. 复盘指标说明

每周复盘引擎输出（`scene-card-review.py`）：
- **时间节省估算**: 按已通过意图的优先级估算节省分钟数（P0=15min/P1=10min/P2=5min）
- **准确率**: 已通过意图中人工确认有效（标记 done）的比例
- **误报率**: 已拒绝意图占已审批意图的比例
- **每日趋势**: 按日期聚合意图流入量

## 5. 关键经验

1. **工作树隔离**: 共享主仓并行 agent 会互相删除产物，必须在 `ws-scenario-phase1` 隔离 worktree 工作。
2. **子模块守卫 (D5 PASW)**: `cockpit` 子模块受 `.subtrees/cockpit` 守卫，需先 clone + 匹配 SHA 才能提交 gitlink。
3. **测试隔离加载**: 用 `importlib.spec_from_file_location` 加载 `bin/ssot` 脚本，跨脚本引擎通过 `tmp_path/bin/ssot` 符号链接加载。
4. **路由精确匹配**: cockpit-ui `routes.tsx` 含 em-dash/箭头字符，Edit 需精确匹配原文本。

## 6. 后续建议

1. **邮件/OA 自动化**: 当前连接器支持手动导入，后续接入 kronos fetch 5 层抓取引擎实现自动化。
2. **结构化抽取质量**: 人工复核兜底已就位，可通过标注评测集持续改进抽取质量。
3. **生产启用决策**: 试点满 4 周真实输入后，由人或 OMO 明确批准生产启用。
4. **修复已知测试失败**: 统一 review 模块在 worktree 中的加载路径，消除 pre-existing failure。

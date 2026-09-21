---
status: active
lifecycle: planning
owner: governance-team
last-reviewed: 2026-09-20
type: roadmap
---

# OMOSTATION-FORWARD-PLAN-v2 — 持续维护 + 新方向探索 (2026H2 - 2027H1)

> 2026-09-20, 三年治理计划 + FORWARD-PLAN §A/§B/§C2/§C3 全部完成.
> 进入"维护 + 探索"双轨阶段. 本文档定义未来 6 个月 (2026H2 - 2027H1) 的
> 持续维护 + 探索方向. 替换 FORWARD-PLAN v1.

## 状态: 当前 (2026-09-20)

- **总 BET**: 426 (全部 done, 100%)
- **窗口**: Y1Q1-Q4 + Y2Q1-Q4 + Y3H1-H2 + STRATEGIC-3YEAR 100%
- **FORWARD-PLAN v1 完成度**: §A 3/3, §B 4/4, §C2.2 1/4, §C3 done
- **新增工具**: claim-suggester (B1.2) / health-predict (B1.3) / scene-card-autogen (C2.2) / cross-repo-status (B2) / closeout-pr.sh (B2)
- **SOP**: docs/SOPs/ledger-closeout-sop.md (A2, 5 步标准流程)
- **模板**: bin/ssot/retro-template.md (B2 统一模板)
- **季度报告**: docs/reports/2026-Q3-quarterly-evaluation.md (C3)
- **main HEAD**: `f54202c84` (含 C3 quarterly evaluation)

## 短期目标 (2026-09 ~ 2026-12, 3 个月)

### A1. 实战反馈循环建立 (P0)

**当前**: A1/A2/A3/B1/B2/C2 工具已实装, 但缺乏真实场景验证数据.

**目标**: 跑 12 周真实 closeout, 反馈误报 + 修补:

```bash
# 1. SOP 真实演练: 每个 BET closeout 走 docs/SOPs/ledger-closeout-sop.md
# 2. claim-suggester 真实信号: 每周跑一次, 跟踪 "建议 → 录入 ledger" 命中率
# 3. health-predict 准确性: 7 天后回测实际 drift, 计算预测误差
# 4. scene-card-autogen 实战: 新场景接入时用其起草, 收集 schema 误报
# 5. bin/closeout-pr.sh: 真实跨主仓+子模块 PR 流程跑通
```

**成功标准**: 12 周后 §C1 终局门 "连续 12 周每周 ≥ 3 条被采纳建议" 数据可证.

### A2. 季度报告自动化 (P0)

**当前**: C3 季度报告手工拼凑, 12+ 文件 cross-ref.

**目标**: 一键生成季度报告 doc + 趋势数据.

```bash
python3 bin/reports/quarterly-report.py --quarter 2026-Q4 --output docs/reports/
```

**包含**:
- 完成率 + 趋势 (vs 上季度)
- 7 维健康分趋势 (drift / staleness / freshness / alignment / governance / runtime / 服务可用)
- 三大 AI 工具采纳统计 (claim-suggester / health-predict / scene-card-autogen)
- AI 建议采纳率 (建议 N 条 → 已录入 ledger M 条, M/N = 采纳率)
- 风险识别 + 缓解跟踪

## 中期目标 (2027 H1, 3-6 个月)

### B1. C2 探索性剩余 3 项 (P2)

**当前**: C2.2 场景自适应完成 (scene-card-autogen). C2.1/3/4 未动.

**目标**: 逐项落地.

#### B1.1 C2.1 Agent 联邦 (P2, 2026-Q4)
- 多 agent 协同任务分配 (`agent-federation.py` / 已 T7-06 部分实装, 待 governance 化)
- 新增 `bin/ssot/agent-federation.py`: 跨 agent 任务 broker + load-balance
- 复用 `.agents/skills/agent-onboarding/` skill 作新 agent 接入路径

#### B1.2 C2.3 隐私保护端侧 (P2, 2027-Q1)
- 个人数据端侧处理 (`.omo/state/health.yaml` 含个人 health 数据, 需 LLM-gateway-only 校验)
- 强化 `bin/gac/check-llm-gateway-only.py` gate (T6-25 + T6-29 已有)
- 新增 `bin/ssot/privacy-boundary-check.py`: 验证 persona 数据不跨子仓泄漏

#### B1.3 C2.4 跨域学习 (P2, 2027-Q1)
- 学术 + 工程双线知识沉淀 (`.omo/_knowledge/` 现仅工程, 缺学术)
- 新增 `docs/knowledge-domains.md`: 区分 academic / engineering / personal
- 探索 `.omo/_knowledge/scholar/` 子目录, 沉淀 paper note + concept 索引

### B2. P107 历史 baseline 累积 (P1)

**当前**: health-predict 启发式无历史数据; claim-suggester 不累计采纳率.

**目标**: 持续记录真实信号, 形成 trend.

```bash
# health-predict 加 --record-snapshot 模式, 写 .omo/state/health-history.jsonl
# claim-suggester 加 --record-adoption, 跟踪 [建议 → ledger 录入] 配对
# 健康仪表盘按月聚合, 出 trend chart
```

**成功标准**: 6 个月后 health-predict 可基于历史回归, 不再纯启发式.

## 长期目标 (2027 H2 ~ 2029, 1-3 年)

### C1. 三年终局门 (2027-12-31 评估)

按原计划 + FORWARD-PLAN v1 设定:
- 连续 12 周每周 ≥ 3 条被采纳建议 ✓ A1 目标 (2026Q4 验证)
- Y1 冗余清零 ✓ 已完成
- Persona 心智镜像 ✓ 已完成
- Routine 自动托管 ✓ 已完成
- **新增** (v2): AI 工具采纳率 ≥ 80% (claim-suggester / health-predict / scene-card-autogen)
- **新增** (v2): 季度报告自动化 ≥ 4 个季度连续可用
- **新增** (v2): C2 探索性 ≥ 3/4 完成

### C2. 探索性目标 (滚动添加) — v1 进展

| 项 | v1 状态 | v2 计划 |
|---|---|---|
| 场景自适应 | ✅ C2.2 done | 持续反馈循环 |
| Agent 联邦 | 🟡 T7-06 部分 | B1.1 2026Q4 落 |
| 隐私保护 | 🟡 T6-25/29 | B1.2 2027Q1 |
| 跨域学习 | 🟡 仅工程 | B1.3 2027Q1 |

### C3. 评估与调整

每季度评估 (C3 已实装):
- 完成率 + 趋势
- AI 工具采纳率 (新增)
- 战略匹配 (3 年终局门 + v2 新增门)

## 不在范围内

- 替代码添新功能 (本期纯维护 + 探索)
- 替架构做大改动 (稳定)
- 新建独立产品 (omstation 治理范围内)
- AI 训练 / 模型微调 (本地 LLM gateway 已就绪)

## 风险与缓解

| 风险 | 缓解 |
|---|---|
| 工具采纳率低 (agent 不跑新工具) | SOP 强制嵌入 closeout 流程 + 工具输出日志 audit |
| 季度报告手工依赖 | A2 报告自动化 (2026Q4 落地) |
| AI 工具误报污染 PR | 强制 human review + 严格 --dry-run 默认 |
| bin-quota 长期压力 | 新增脚本必归档 1 个 (B1 4 个归档已证) |
| SSL/网络对 submodule checkout 影响 | B2 跨仓功能 graceful degradation |
| C2 探索性投入 vs 产出不确定 | 每季度回顾, 无进展则降级或退出 |

## 关联

- `docs/OMOSTATION-FORWARD-PLAN.md` (v1, 2026-09-19, 已完成 §A/§B/§C2/§C3)
- `docs/STRATEGY-3YEAR-PLAN-2026H2-2029.md` (前 3 年, 已完成)
- `docs/reports/2026-Q3-quarterly-evaluation.md` (C3 季度评估)
- `docs/SOPs/ledger-closeout-sop.md` (A2 SOP 5 步)
- `.agents/skills/bet-closeout-chain/SKILL.md` (8 步详细版)
- `.agents/skills/agent-onboarding/SKILL.md` (新 agent 接入)
- `.omo/_knowledge/retros/` (100+ retro 沉淀)
- `.omo/_knowledge/patterns/` (11 个 pattern P97-P105)

## 版本

- **v1** (2026-09-19): 6 个月路线图 (§A 短期 / §B 中期 / §C 长期)
- **v2** (2026-09-20, 本文档): 6 个月路线图, 在 v1 基础上加 §A1 反馈循环 + §A2 报告自动化 + §B1 C2 剩余 3 项 + §C1/§C2/§C3 v2 新增项
---
id: ADR-0431
status: candidate
lifecycle: spec
owner: xiamingxing
last-reviewed: 2026-08-28
type: ssot
---

# ADR-0431: 防腐五层框架 — 人的权威分层 × 三机制 + MAPE-K 对齐

> 依据: 2026-08-28 五维审议 + 用户五层介入模型 + 业内调研 (Lehman/DDD ACL/MAPE-K/Brooks/HITL 分级)
> 相关: 2026-08-28-value-flow-deep-analysis.md · 2026-08-28-five-dimension-review.md

## Context (为什么需要这个决策)

体系处于高速熵增 (48h 144 commits, 脚本 498→504, 断指×7, 预算一周上调 4 次)。
Lehman 定律 7 (质量递减) 与定律 2 (复杂度递增) 正在实证发生。
减法目前是危机驱动手工砍 (规则 144→74), 不可持续。
用户提出人的介入应分五层; 调研确认业内有成熟对应理论。

## Decision (决策)

### D1: 人的权威五层正交模型 (用户提出, 形式化)

| 层 | 名称 | 内容 | 变更权 | 减法策略 |
|----|------|------|--------|---------|
| L1 | 宪章层 | 愿景/使命/身份/角色/价值观/世界观/人生观 | **仅人** | 零减法 (人的主权) |
| L2 | 上下文层 | 阶段重心/喜好/家庭/社会关系/经历/知识储备 | 人写 agent 读 | 滚动过期 (时间衰减) |
| L3 | 决策权层 | 高风险任务/高价值决策/安全/情感/敏感判断 | 人定义+可委托 | 精确枚举 (每个闸门带理由) |
| L4 | 约束层 | 规则/规范/原则/方法/机制 | 治理 agent 可提, 人批 | **减法主战场** (生命周期制) |
| L5 | 未知层 | 尚未识别 | 开放 | 探针实验区 |

层间正交: 改一层不动其他层。防腐被边界隔离 (DDD ACL 思想)。

### D2: L4 约束层规则生命周期机制

governance-checks.yaml 每条规则增加:
```yaml
added_at: <date>          # 上线时间
review_before: <date>     # 过期进减法候选
justification: <text>     # 存在理由 (减法时评审依据)
```
周度 cron 扫描: 过期规则 → 减法候选报告 → 人工批量 approve/keep。
预算类 expiry 已有雏形 (orphan-docs expires: 2026-10-31), 扩展到全部规则。

### D3: 动态守恒 (Lehman 定律 4 工程化)

预算/脚本/提案的 "增 N 必须同周期减 N"。bin-quota (增1删1) 已是雏形,
扩展到: 每次预算上调必须在同一 PR 内注明被减项或链接跟踪 issue。

### D4: HITL 三型分档 (L3 工程化, 解人的带宽瓶颈)

| 档 | 适用 | 交互 |
|----|------|------|
| in-the-loop | 高风险/情感/敏感 (L2/L3 风险级) | 逐条人批 (保持现状) |
| on-the-loop | 例行高价值 (格式类公文/L0 风险) | 周批审, 可单个 override |
| full-auto + audit | 纯体系内 (规则注册/心跳/固化副本同步) | 自动执行, log 可查 |

映射: risk_engine 的 L0-L4 已有分级基础, 加 hitl_mode 字段即可。

### D5: MAPE-K 对齐 (理论定位, 不改名)

resident 五角色即 MAPE-K 实例化:
Monitor=monitor · Knowledge=sediment+ledger+events · Analyze=daemon ·
Plan=planner(dormant, 待接线) · Execute=execute+executor。
对齐用于: 沟通语言/缺口识别 (planner 是缺的 P)/后续演进参照。

### D6: 显式 ACL 制度化

固化副本 (runtime/ssot-stable)、_vendored 等已有实践升级为明确架构原则:
跨域边界 (邮件域↔旅程域, 体系↔外部服务) 必须声明 ACL。

## Consequences

- 减法从"危机手工砍"→"制度化滚动修剪", 腐蚀速率有理论封顶
- HITL 带宽从"全量逐条"→"分档批量", 解死亡螺旋
- planner 接线获得理论依据 (MAPE-K 缺 P)
- 风险: 规则生命周期初期会产生大量过期候选, 需一次集中清淤 (第 0 段)
- 风险: HITL 降档初期需谨慎 (先 on-the-loop 试点一类场景再推广)

## 实施挂钩

- 第 0 段减法按 D1 模型执行 (等用户决策点 1: dormant 判定权)
- D2/D3/D4 为 S1 编码项, 均复用现有组件 (expiry 字段/bin-quota/risk_engine)

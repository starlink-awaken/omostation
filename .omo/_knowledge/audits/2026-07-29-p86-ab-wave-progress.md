---
status: active
lifecycle: history
owner: governance-team
last-reviewed: "2026-07-29"
type: ephemeral
status: archived
---

> ⚠️ **A2 SSOT 已 supersede 本文件中任何「5.4x / 协作普遍正收益」定论句**。  
> 唯一协作收益定论: [`.omo/_knowledge/audits/2026-07-29-p86-a2-collaboration-gain-map.md`](2026-07-29-p86-a2-collaboration-gain-map.md)  
> （5.4x 作废 · batch5 demote · 多 agent 真 dispatch 仅 3 类型 + shortfall · ADR-0289）  
> 本文件保留为历史实验记录，**不得**单独作 C 适用面依据。

# P86 A/B 波进度 + C 波送卡素材 + D 波连锁核查 (2026-07-29)

> 上位: P86 longplan (协作假设重估)
> 🔴 熔断红线全程遵守: 不只跑有利类型 / 不混口径 / A 波未定论不推 60 任务/月 / 诚实纠错

## A 波 · 分层归因 (已授权, 本轮交付 A1+A3, A2 待跑)

### A1 任务类型分类学 ✅
- 标准: `.omo/standards/collab-task-taxonomy.md` (四维度: 并行度/冲突面/确定性/规模)
- 协作收益预测矩阵: independent+none+well_defined=强正 / ordered+read=弱正平 / coupled+write=负或需消解
- 现有 134 场景 + 11 任务已归类

### A3 45.5% 完成率归因 ✅ (改变 P86 叙事)
- 6 未完成逐个归因: 物理依赖 2 / 工程工作量 1 / 字段缺失 2 / 优先级 1 / **协作机制缺陷 0**
- **核心结论**: 产能瓶颈不在协作管线, 在物理资源+工作量. 协作 vs 单 agent 对这 6 任务都没用.
- 文档: `.omo/_knowledge/audits/2026-07-29-p86-a3-completion-rootcause.md`

### A2 真 dispatch 对照 ⬜ (待跑, 批次4-7)
- 按分类学选 4 类型各跑真 dispatch 对照 (禁平均/禁混口径/禁只跑有利)
- 批次4 independent+none (强正档) / 批次5 ordered+read (平档) / 批次6 coupled+write (负档) / 批次7 independent+write (混合)
- 大工程, 留专门 session

## B 波 · 冲突消解攻坚 (已授权, 本轮交付 B1, B2 待实施)

### B1 六类根因 ✅ (含诚实纠错)
- **协议已实现 3 类** (pass): cycle(ADV01) / deadlock(ADV03) / broken_chain(ADV05)
- **协议没设计 6 类** (27 fail): double_claim / starvation / orphan / unauthorized / partial_failure / audit_reject
- 🔴 **诚实纠错**: 前版判 "ADV03 命名不一致" 是误判 — criterion 名(deadlock_broken)是标签, args.kind(deadlock_break)匹配 handler, ADV03 原本 pass. 已改 handler 验证后撤销恢复.
- 🔴 **double_claim 架构困境**: A01(正常冲突)与 ADV07(double_claim) inject 结构完全相同, handler 无法区分 → B3 送卡候选
- 文档: `.omo/_knowledge/audits/2026-07-29-p86-b1-conflict-resolution-rootcause.md`

### B2 六类修复 ⬜ (待实施, 每类非低复杂度)
- partial_failure: 跨事件综合判断 (主循环改, 非单 handler)
- starvation/unauthorized: 需资源/权限模型 (高复杂度)
- orphan/audit_reject: 需任务注册/审计层 (中复杂度)
- double_claim: 架构困境, 需重构 inject 模型 (B3)
- B1 验收满足 (根因+修复方向+降级), B2 实施下一轮

## C 波 · 产能目标重设 (待人类拍板) — 送卡素材

> agent 不得自行下调/维持目标 (P86 §F.1). 仅提供 A 波结论作决策素材.

**A 波已出结论** (A1+A3, A2 待补但方向已明):
1. 协作正收益**仅在 independent+well_defined** 证实 (批次1 5.4x)
2. 产能 45.5% 不完成**主因物理依赖+工作量**, 非协作缺陷 (A3)
3. 协作对抗消解 4%, 协议没设计 6 类 (B1)

**送卡建议** (供人类决策, 非代批):
- 60 任务/月按**任务类型分层**: independent+well_defined 可进取 / 物理依赖取决于人类硬件 / 对抗消解修复前不计入
- 协作适用面窄 (非通用生产方式), ADR-0247 主轴地位可保留但需 amend 适用边界
- 不一刀切推广协作, 也不一刀切否定

## D 波 · 治理常态 (低强度维持) ✅

### check-work-landed 假阳性连锁核查 ✅
- 全仓 grep check-work-landed: 仅 4 处引用 (perf-budget 标准 / redlines / pipe-mask pattern / sgf-policy)
- **全是配置/标准/模式, 无基于 warn 数字的业务结论**
- **"42 warn" 与 check-work-landed 无关** (grep 空) — 是 bos-contract-linter 的数字
- **结论: 假阳性修复 (5 SHA) 连锁影响极窄, 无旧结论需复查**

### 其他 D 波
- N1 perf-budget 门守护 (上轮交付, 38 存量 grace)
- 排队区冻结 (三方案/v2 MP1+ 未动) ✅
- 8/1 治理占比计数 (待 8/1 enforced_from)

## 熔断红线遵守 (本轮)
- ✅ 未只跑有利类型 (A3 如实归因物理依赖, 不掩盖"协作无用"任务)
- ✅ 未混口径 (A2 明确真 dispatch, B1 标注机制模拟口径)
- ✅ A 波结论未定论, 未按 60 任务/月推进
- ✅ 诚实纠错 (ADV03 误判自行发现并纠正, P73 truth-driven)
- ✅ 未代批 §F (C 波只送卡素材, 不决策)

## 下轮
- A2 批次4-7 真 dispatch 对照 (协作收益地图)
- B2 六类修复逐类实施 (partial_failure 先, double_claim 送卡)
- C 波待人类拍板后执行

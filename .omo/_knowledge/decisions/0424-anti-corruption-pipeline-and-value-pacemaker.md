---
id: ADR-0424

title: "ADR-0424: 防腐流水线与价值起搏器 — 48 小时全弧线架构决策沉淀"
status: archived
lifecycle: spec
owner: governance-team
date: 2026-08-24
last_updated: 2026-08-24
tags: [anti-corruption, value-pacemaker, uhs, governance, multi-agent, north-star]
related:
  - docs/operations/engineering-golden-rules.md (SCRIPT-BASELINE-SYNC)
  - bin/gac/unified-health-score.py (UHS 度量)
  - BET-Y1Q3-T10-11 (sediment promotion pipeline)
---

# ADR-0424: 防腐流水线与价值起搏器 — 48 小时全弧线架构决策沉淀

## Context

48 小时前诊断出三大战略风险:
1. **基础设施腐烂**: 引用悬空/心跳沉默/指针回退/配额公地——每个都靠人工发现和修复
2. **治理能力过剩而价值证明缺位**: UHS 未测量, 北极星 unprovable, 台账冻结在 Y2Q4
3. **人在环瓶颈**: 决策积压, 修复排队, agent 各自为战

根因: 修复是"事件"而非"机制"; 规则写在文档里没有执法权; 检查靠人记忆。

## Decision

### D1: 防腐按强度分层(L0-L3), 尽可能升到 L3

| 级别 | 形态 | 腐烂抗性 | 实例 |
|------|------|---------|------|
| L0 | 文档写"请记得" | ❌ 三周必死 | 历史教训 |
| L1 | 定时报告+提醒 | ⚠️ 注意力衰减 | weekly-review cron |
| L2 | 自动检测+自动立案 | ✅ 不靠人发现 | meta-doctor M1/M2/M3 |
| L3 | 动作时刻物理拦截 | ✅✅ 遗忘不可能 | bin-quota-diff, ancestry gate |

**判据: 每个新规则必须标明级别; L0/L1 规则须有升 L2/L3 的路径。**

### D2: 配额语义从全局计数到变更侧问责

旧: gac-validate 检查 bin/ 总量 > baseline → 所有 agent 被拦, 但没人负责清偿。
新: bin-quota-diff 只看你的 diff 新增 vs 删除, 净增→只拦你。
全局计数降级 advisory(dashboard 可见但不阻断)。

### D3: 子模块内省必须在子模块检出内进行

两次误报(-92 口径误读/split-brain)均因 `git show origin/main:<submodule>/...`
从主仓读子模块内容(静默返回空)。教训已固化为工具输出格式。

### D4: 多文档 yaml 一律 safe_load_all

governance-checks.yaml 是多文档结构。单文档 safe_load 会漏数据导致假零。
UHS governance 维度归零事故即此根因。

### D5: 价值度量拒绝猜测——unprovable 是特性非 bug

north_star_meter_v2 设计上只接受签核的人证 episode,
不从 PR/BET/测试推断价值。这确保 value 分数的不可伪造性。

### D6: 自进化三级制

L1 参数(阈值/配额): agent 全自动
L2 结构(增删规则/注册): agent 提案+证据→PR 门禁
L3 代码: 仅提案, 人类审批

### D7: 续期由价值决定, 不由沉没成本决定

连续两季度 provable 且正向→自动续期 BET;
不达标→sunset review→精简退役。

## Consequences

### 正面
- UHS 42.4/F → 96/A (+53.6)
- 引用悬空: 从天级人工排查 → 小时级自动立案+当日修复
- 配额公地: 从无人归因 → 变更侧精确问责
- 指针回退: 从静默丢失 → pre-push 物理拦截
- 价值管线: 从概念 → 可运行代码(三源聚合→attest人审→ledger→meter)

### 负面
- 门禁增多意味着 escape 使用频率可能上升(需 owner 月审 bypass 日志)
- 探测器自身也需要维护(M3 心跳机制可推广至全部探测器)
- 多 agent 并发下的 checkout 切换仍会导致工作树文件消失(未根治)

## Patterns Worth Sedimenting (实证有效的模式)

### P1: diff-based 问责优于 global counting
配额拉锯的根治不是"更严的检查", 而是"把守恒律移到每次变更"。
适用范围: 任何需要守恒的资源(脚本数/规则数/依赖数/代码行数)。

### P2: 在违规动作发生的瞬间拦截
push 时校验比 CI 校验反馈快一个数量级。
适用范围: git hook 可拦截的所有违规类型。

### P3: 误报当日自纠并写入勘误
两次误报(-92 口径误读/split-brain)均在当日发现、修正、写入工具输出格式。
诚实账本比完美记录更有长期价值。

### P4: worktree 环境感知降级
fresh worktree 缺少子模块内容时, gate 应 SKIP 并提示初始化命令, 不应 FAIL。
区分"代码有问题"与"环境没准备好"是门禁设计的核心职责。

## Follow-ups
- [ ] G1: remediation-engine 消费 MDEAD proposals 适配器
- [ ] G3: 探测器心跳矩阵(全部探测器写 heartbeats/)
- [ ] 迭代流合并(owner 决策)
- [ ] cockpit attest 子命令化
- [ ] anti-corrosion-check crontab 断链修复

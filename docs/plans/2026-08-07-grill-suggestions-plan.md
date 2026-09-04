---
lifecycle: plan
owner: governance-team
last_updated: 2026-08-18
type: ephemeral
---
# 建议方向方案与规划 (grill-me 成果) 2026-08-07

> 经 grill-me 逐项访谈确认的设计决策。范围: ADR 重编号 / active_goals 根治 /
> proxy_toolbox / 能力市场 / T6 治理减法。

## 一、ADR 重编号 (Q2, 已完成 PR #1132)

**问题**: 两个不同决策共用 ADR-0388 (ci-plane-subtraction ACCEPTED + layer-contract-direction PROPOSED)。

**决策 (A)**: layer-contract-direction 重编号为 ADR-0391 (最高 0390 + 1)。
- 文件 → 0391-layer-contract-direction-ssot.md, frontmatter/正文/INDEX 同步
- 教训: next-adr-id 基于本地 INDEX 可能建议已用号, 须人工核对 git 最高号

## 二、active_goals 根治 (Q3, 已完成 PR #1132)

**问题**: KOS-Q-GROWTH (active, 无 task) + G-Y1Q1-GITSHIM (in_progress, task candidate) → `active_goals_without_active_tasks` 每次 PR 失败。

**决策**: 
- Q3a 初判标 done → Q3b 实测推翻 (KOS-Q-GROWTH 是 rolling 持续 goal, measured 5193, 有 evidence, 不应 done)
- **最终 (A)**: 给 KOS-Q-GROWTH 关联持续 task `kos-q-growth-rolling.yaml` (active), 同步 state active_tasks 0→1
- 教训: coherence 要求 active goal 有 active task, 但 rolling goal 天然无离散 task → 补 task 而非改检查

## 三、proxy_toolbox 修复 (Q4, 已完成 PR #1132)

**问题**: test_known_services_keeps_core_services 断言 `cockpit` in KNOWN_SERVICES 失败。

**实测**: cockpit 的 agent-runtime MCP 从 initial commit 起以 `agent-runtime` 名义登记 (key=agent-runtime, args→cockpit)。

**决策 (A)**: 测试断言 `cockpit` → `agent-runtime`。
- 加独立 cockpit key 会重复启动同一 MCP, 改名破坏 routes 引用 → 均不可取
- 教训: 判定"测试错 vs 实现错"用实测登记名义, 非假设

## 四、能力市场 (Q5, 规划未实施)

**决策 (B 完整市场, 分层 MVP)**:
- **P0**: bos-services/rates 加 pricing 字段 (混合三层: 全局默认 deepseek 费率 + rates.yaml prefix 覆盖 + 未来服务级)
- **P1**: 发现 API = 扩展 bos_capability_list 返回 pricing (不新增独立工具)
- **P2**: 采购 = 复用 admit + CallRecord 账单聚合 (不加新状态, 订阅管理后续)

**实现位置 (A)**: accounting.py 加 resolve_pricing(uri) 读 rates 覆盖, estimate_cost 接受 per-call rate → 记账价 = 市场价一致。

## 五、T6 治理减法 (Q6, T6-10 已完成)

**决策 (A 聚焦 T6)**:
- **T6-10 god-module 拆分** (已完成 PR): external_connections.py 1663→1151L, 数据类→models.py, interface-check error 消除
- T6-01 GaC 规则减法 / T6-02 ADR 分层 / T6-04 场景归档: 后续轮次

## 六、落地进展 (P0/P1/T6-10b 已完成)

| 项 | 状态 | 落地 |
|----|------|------|
| Q5 能力市场 P0 | ✅ 完成 | resolve_pricing 混合三层 (minerva 0.3/1.2, kos 0.05/0.2), 记账价=市场价 |
| Q7 backend 分级 P1 | ✅ 完成 | /health backends 加 standby + alive_ratio (127/7/120/0, ratio 0.055) |
| T6-10b cockpit 拆分 | ✅ 完成 | cli.py 1533→790L (并发 agent) + 命名冲突修复 (_subcommands 上移) |

## 七、后续路线

| 项 | 状态 | 下一步 |
|----|------|--------|
| Q5 能力市场 | 规划 | P0 pricing + P1 发现 API 实施 |
| T6 其余 | 未实施 | T6-01/02/04 治理减法 |
| interface-check | 修复中 | T6-10 后应消除 error (external_connections 已拆) |

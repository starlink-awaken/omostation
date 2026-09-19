---
schema_version: specification/v1
spec_version: 1.0.0
title: 台账瘦身 — 306 done 归档 + 消费方合并读 + submit 双预检
bet_id: BET-Y2Q1-T10-03
status: accepted
lifecycle: contract
last-reviewed: 2026-09-06
type: plan
owner: governance-team
last_updated: 2026-09-06
---

# 台账瘦身规格 (BET-Y2Q1-T10-03)

## 动机

3y-bet-ledger.yaml 达 20000+ 行 / 361 BET (done 320) — 多 agent 并发写
的冲突热区 (两日内 PR 撞 ledger 三次), 插入靠行号定位, 裸冒号坑三犯。

## 方案 (选项对照后定稿)

1. **归档**: 320 done 中被 14 条跨引用边留守 14 个锚点, 其余 306 个迁移至
   docs/plans/3y-bet-ledger-archive.yaml (含 meta 头)。
2. **消费方合并读**: bet-ledger.py load_ledger + 4 个自有加载器
   (chain-bind-audit/portfolio_projection/value-proof-debt-registry/
   arch-health-meter) 各补 3 行: 若 archive 存在则 bets 拼接 (主文件优先)。
3. **submit 双预检** (gac-worktree.sh):
   a. 冒号预检: staged 变更含主台账时 yaml.safe_load 预检, 失败中断
      (裸冒号三犯的前置拦截)
   b. 并发协调: 本分支改台账时, 检查其他活跃 worktree 的 dirty 台账 →
      警告 (非阻塞)

## done_when

- 主台账 <= 4000 行, archive 含 306 BET, validate 全绿
- lint/complete/closeout 与 bet-done-gate 语义不变 (实测一次 complete)
- 6 个加载器合并读验证: show 老 BET 命中, portfolio/chain-bind 审计不缩水
- submit 预检生效 (人为坏台账能拦住)

## non_goals

- 不改 lint 的 transition 判定语义 (归档 BET 不在当前文件即不遍历)
- 不做 ledger 写锁 (警告已够, 锁是过度设计)

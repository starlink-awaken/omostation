---
schema_version: specification/v1
spec_version: 1.0.0
title: BET 认领广播与同号竞速防护
bet_id: BET-Y1Q4-T10-139
status: accepted
lifecycle: contract
owner: governance-team
last-reviewed: 2026-09-07
---

# BET 认领广播 (T10-139)

## 根因

三起同号竞速事故 (T10-135/136/137/138 cycle) 的共同根源：**BET 状态 (ledger) 与
执行意图 (start) 之间没有认领层**。两个并行 agent 都看到 candidate → 都 start →
都交付 → 合并时互相覆盖/重新编号，浪费 4 轮 PR 合并 + 3 次 worktree 损失。

## 设计三要点

1. **claim-bet 广播** (bin/plan/bet-ledger.py `claim-bet` 子命令)
   - 认领时原子动作：写 `.omo/_delivery/bet-claims/<BET-ID>.json` (actor/
     claimed_at/ttl_days) + `save_ledger_locked` 内 candidate→in_progress
   - 异 actor 认领 → fail closed (打印持有者+时间，提示 `--force` 显式接管)
   - 同 actor 幂等 (刷新时间戳延长 TTL)
   - 默认 actor: `--actor` 显式 → `$USER` → `governance-agent`
   - 广播文件先写、锁内 status 切换后写、锁内锚失配只警告不回滚 (fail open at
     warning level, 广播文件已是真实认领事实)

2. **start 双认领拦截** (bin/agent-workflow.py `_claim_interlock_guard`)
   - start `--bet <BET-ID>` 时：存在他人持有 claim 广播 → 拒绝 (BET_CLAIM_HELD)
   - 无广播 → 放行 (不强制先 claim — 兼容存量流程/紧急人工通道)
   - 持有者本人 → 放行；损坏文件 → 宽容放行 (读取侧不炸, 写入侧 fail closed)
   - guard 自身异常 → 宽容放行 + stderr 警告 (防御层不应成为新单点)

3. **complete 自动释放 + claim-gc TTL**
   - `cmd_complete` 置 done 成功后删 claim 文件 (T10-139 `_release_claim`)
   - `claim-gc` 子命令：过期 (默认 7d) 清理 claim 文件 (只动文件不动 ledger
     status — 后续认领自然接管)
   - TTL 语义：过期 = 放弃，竞争者可 `--force` 接管

## 边界与非目标

- 不做 claim 强制化：start 不要求预先 claim (非破坏性兼容存量)
- 不做跨仓广播：claim 文件仅本地仓 (`.omo/_delivery/`)，多 agent 共享同一
  workspace checkout 的场景即防住 (事故根因场景)
- 不改 ledger 锁机制：status 切换仍走 `save_ledger_locked` (T10-137 已交付)
- claim-gc 不回退 ledger status：in_progress 悬置由 operator 处置 (治理面),
  工具只清广播文件

## 验收

- 单元三态：首认/异拒/同幂等/force 接管/gc 过期/complete 释放 — 全绿
- 端到端：start 拦截 4 场景 (无/他人/本人/损坏) — 全绿
- dogfood：T10-139 自身交付用 claim-bet 认领 (吃自己的狗粮)

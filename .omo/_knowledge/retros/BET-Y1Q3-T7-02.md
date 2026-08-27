---
status: done
lifecycle: history
owner: engineering-agent
bet: BET-Y1Q3-T7-02
last-reviewed: 2026-08-27
---
# BET-Y1Q3-T7-02 Retro — P1 健康域启动

> run: 20260826T104439Z-project-code-change-0375422e · PR #2273 MERGED
> 后置: 2026-08-27 闸门补齐 + retro 升 done

## 五问

### 1. 计划 objective
P1 健康域从零资产到最小契约闭环: health-medical-workflow journey (4 状态分叉)
+ 4 张 draft 场景卡, 对齐 risk_engine L0/L2 分级, 全 draft 先落契约 (appetite 1 day)。

### 2. 实际 steps
侦察模板/规划 → BET-Y1Q3-T7-02 立项 (specification/v1 绑定) → worktree 隔离 →
start (BET 门禁: statusable 状态机 + submodule 自包含) → 5 资产落地 →
journey-validate 13/13 + card blockers 空 + gate 57/57 → PR #2273 →
CI 三雷 (ecos 断指 #2270 / frontmatter 三连雷 #2268) 顺手修复 → 全绿合并。
补闸门: 2026-08-27 `make journey-check` 目标 + `scene-card-lifecycle --p1-only`
模式 (P1 契约-only 场景卡不再被 approval/trial P2 闸门卡死), 闸门命名
对齐 ledger 的 `verify.cmd`。

### 3. 结果与证据
PR #2273 MERGED @ 4231f7182, 21 checks 全绿。
done_when 三项全达成: journey-check ✅ / scene-card-check ✅ (4 卡 blockers 空) /
卡片显式声明 L0/L2 边界 ✅ (每卡 notes 段)。
补闸门后再次 verify 走通: `make journey-check` exit=0, `make scene-card-check`
exit=0 (15 ready / 5 with-blockers non-health)。

### 4. 失败根因 (途中三坑)
- BET start 报 BET_NOT_FOUND: 借主区 PYTHONPATH 让 omo.workflow 读主区 ledger,
  worktree 需 submodule 自包含 (omo/ecos/agora init 后通过)。
- CI ecos 断指: #2270 把不可达 afcb377 提交进 main, 本 PR rebase + gitlink 修复。
- frontmatter 三连雷: #2268 staleness 管线 stamp 吞换行/盖 policy·manifest,
  三个消费端 (doc-governance/audit/root-scan) 各自崩, 逐一容错修复。
- 闸门命名错位: bet-ledger 写 `make journey-check`, 仓库只有 `make journey-validate`,
  `--p1-only` 缺失。补目标 + 补模式即可。

### 5. 指标
- 资产: +1 journey (4 states/4 transitions), +4 scene cards, +1 spec 文档, +1 BET
- CI 存量修复: ecos gitlink + 12 frontmatter 文件 + 2 个 scan/audit 脚本容错
- 闸门补齐: +1 make target, +1 lifecycle flag
- 豁免使用: 1 次 (local-preflight-preexisting, 主区可复现存量)
- 净 lint 债务: 0 (T7-02 零错误, bet-ledger 81 全存量)

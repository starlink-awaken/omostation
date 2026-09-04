---
status: accepted
lifecycle: history
owner: engineering-agent
bet: BET-Y1Q3-T7-02
last_updated: 2026-08-27
title: BET-Y1Q3-T7-02 Retro — P1 健康域启动
type: retro
---
# BET-Y1Q3-T7-02 Retro — P1 健康域启动

> run: 20260826T104439Z-project-code-change-0375422e · PR #2273 MERGED (a9ed961a)
> 收尾: run 20260827T230318Z-bet-execution-aecf5cb2 · attestation 2026-08-27T23:08:08Z (ED25519 Good) · 台账升 done

## 五问

### 1. 计划 objective
P1 健康域从零资产到最小契约闭环: health-medical-workflow journey (4 状态分叉)
+ 4 张 draft 场景卡, 对齐 risk_engine L0/L2 分级, 全 draft 先落契约 (appetite 1 day)。

### 2. 实际 steps
侦察模板/规划 → BET-Y1Q3-T7-02 立项 (specification/v1 绑定) → worktree 隔离 →
start (BET 门禁: statusable 状态机 + submodule 自包含) → 5 资产落地 →
journey-validate 13/13 + card blockers 空 + gate 57/57 → PR #2273 →
CI 三雷 (ecos 断指 #2270 / frontmatter 三连雷 #2268) 顺手修复 → 全绿合并。

### 3. 结果与证据
PR #2273 MERGED @ 4231f7182, 21 checks 全绿。
done_when 三项全达成: journey-check ✅ / scene-card-check ✅ (4 卡 blockers 空) /
卡片显式声明 L0/L2 边界 ✅ (每卡 notes 段)。

### 4. 失败根因 (途中三坑)
- BET start 报 BET_NOT_FOUND: 借主区 PYTHONPATH 让 omo.workflow 读主区 ledger,
  worktree 需 submodule 自包含 (omo/ecos/agora init 后通过)。
- CI ecos 断指: #2270 把不可达 afcb377 提交进 main, 本 PR rebase + gitlink 修复。
- frontmatter 三连雷: #2268 staleness 管线 stamp 吞换行/盖 policy·manifest,
  三个消费端 (doc-governance/audit/root-scan) 各自崩, 逐一容错修复。

### 5. 指标
- 资产: +1 journey (4 states/4 transitions), +4 scene cards, +1 spec 文档, +1 BET
- CI 存量修复: ecos gitlink + 12 frontmatter 文件 + 2 个 scan/audit 脚本容错
- 豁免使用: 1 次 (local-preflight-preexisting, 主区可复现存量)
- 净 lint 债务: 0 (T7-02 零错误, bet-ledger 81 全存量)

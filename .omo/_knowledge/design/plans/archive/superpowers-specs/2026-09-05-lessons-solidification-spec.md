---
schema_version: specification/v1
spec_version: 1.0.0
title: 两日会战经验固化 — PITFALL×2 + skill×2 + submit auto-rebase
bet_id: BET-Y2Q1-T10-02
status: accepted
lifecycle: contract
last-reviewed: 2026-09-05
type: plan
owner: governance-team
last_updated: 2026-09-05
---

# 经验固化规格 (BET-Y2Q1-T10-02)

> 2026-09-04~05 两日会战复盘产物, 夏明星批准全量固化。

## 交付物

1. **PITFALL-GAT-007** (gate/medium): CI 假失败分诊 — 同命令本地绿 CI 红按
   gitlink→base→registry 排查 (3 实例: mutation-surfaces stale / registry drift ×2)
2. **PITFALL-COO-003 计数 4→5**: 共享 index 竞态/add -A 地雷 — dedup 进既有条目,
   触发 escalation 规则草案 (CR-PITFALL-COO-003, 等人审)
3. **skill bet-closeout-chain**: BET 闭环 8 步 checklist (4 次实战流程固化)
4. **gac-worktree.sh submit auto-rebase**: origin/main 前进时自动 rebase,
   冲突时中断报错 (PITFALL-GAT-007 预防层)
5. **scene-shadow-activate skill 纠偏**: 参数/模板对齐实况 (--samples 不存在,
   promote→transition, v1→v2 模板, T7-02 试验门说明)
6. **立项挂账**: BET-Y2Q1-T7-04 (omo 死链+ecos 第四家) / T7-05 (calibration 语义统一)

## done_when

- error-knowledge check 通过 (pitfall 索引健康)
- check-agent-skills 全过 (新 skill 注册)
- bash -n gac-worktree.sh 通过
- capability-registry 重同步含新 skill

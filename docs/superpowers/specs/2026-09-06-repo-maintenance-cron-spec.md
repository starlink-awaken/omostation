---
schema_version: specification/v1
spec_version: 1.0.0
title: 仓库维护 Cron 化 — 三脚本吸收三旧脚本 + 周报 + cron 接线
bet_id: BET-Y1Q4-T10-127
status: accepted
lifecycle: contract
last-reviewed: 2026-09-06
type: plan
owner: governance-team
last_updated: 2026-09-06
---

# 仓库维护 Cron 化规格 (BET-Y1Q4-T10-127)

## 三脚本 (bin/ 配额: 各吸收一个近亲旧脚本并归档)

1. **prune-zombie-worktrees.py** ← 吸收 gac-worktree-cleanup.sh (PASW worktree 回收)
   僵尸 worktree 判定: 无 .git 文件 / 7 天无更新 / 分支已合并 — 三规则取并集
2. **branch-ttl-gate.py** ← 吸收 gac-worktree-prune.sh (work/ 24h TTL 老脚本)
   TTL 强制: work/ (24h→policy) + agent/ (7d policy) 双段, dry-run 默认, --enforce 实删
3. **check-readme-hardcoded.py** ← 新职责 (README 硬编码数据检测: 端口/计数/日期)
   + 附带 repo-health 周报段 (聚合三脚本输出 + dormant-cleanup-scanner 数据)

## cron 接线 (3 job)

- 周一 08:30 prune-zombie-worktrees.py --enforce
- 周日 08:30 branch-ttl-gate.py (dry-run 一周观察期, 确认后切 --enforce)
- 每日 08:00 check-readme-hardcoded.py --update-health (附 repository-health.md 周报刷新)

## 归档 (bin/_archive/)

gac-worktree-cleanup.sh / gac-worktree-prune.sh / dormant-cleanup-scanner.py

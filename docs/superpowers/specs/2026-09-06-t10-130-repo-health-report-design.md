---
schema_version: specification/v1
spec_version: 1.0.0
status: accepted
lifecycle: contract
owner: governance-team
created: 2026-09-06
last-reviewed: 2026-09-06
bet_id: BET-Y1Q4-T10-130
risk_level: L1
human_gate: false
value_indicator_policy: false
type: ssot
---

# T10-130 仓库健康度可视化周报设计

## 1. 目标

`bin/gac/repo-health-metrics.py`：自动采集仓库健康度指标（分支数/
Tags 数/worktree 数/松散对象/悬空跟踪引用/gitlink 漂移）生成
`docs/repository-health.md` 周报，历史采样入 JSONL 支持趋势对比，
异常指标自动告警标记。

## 2. In scope

1. `bin/gac/repo-health-metrics.py`（新文件）：
   - `collect()`：分支（local/remote）、tags、worktrees、`git count-objects -v`
     （松散对象/in-pack）、悬空跟踪分支（remote 已删本地仍在）、
     子模块 gitlink 与 origin 偏差计数。
   - `--snapshot`：追加历史采样到 `runtime/cockpit/repo-health-history.jsonl`。
   - `--report`：生成 Markdown 周报（当期指标 + 与上次采样趋势箭头
     ↑↓→ + 异常告警区：松散对象 >1000 / 悬空跟踪 >5 / worktree >25
     触发 ⚠️）。
   - 纯 git 命令采集，零新依赖。
2. `docs/repository-health.md`（生成物，首期周报入库）。
3. `tests/test_repo_health_metrics.py`（新文件）：采集形态/趋势对比/
   告警阈值/enforce 语义。

## 3. Out of scope

- 不自动清理（清理动作属 T10-127/128/129 cron 化 bet，本 bet 只观测
  与告警）。
- 不做定时注册（脚本头部提供 launchd/cron 片段，人工安装）。

## 4. 验收（对齐 ledger done_when）

1. `--report` 自动生成 `docs/repository-health.md` 周报。
2. 二次运行 `--snapshot` 后报告含趋势数据（每周采样）。
3. 异常指标（超阈值）在报告告警区标记。
4. 单测全部通过。

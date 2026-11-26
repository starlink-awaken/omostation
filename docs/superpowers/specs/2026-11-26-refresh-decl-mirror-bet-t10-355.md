---
schema: md/v1
schema_version: specification/v1
status: accepted
lifecycle: spec
owner: governance-team
last-reviewed: 2026-11-26
accepted: "2026-11-26 Principal 会话原话「继续推进优化吧」— refresh 日志断流对账后续, 声明镜像回填 + cron 坏提交债立案"
bet_id: BET-Y2Q4-T10-355
spec_version: 1.0.0
---

# BET-Y2Q4-T10-355 spec — refresh 服务声明镜像回填 + capability-sync epoch 倒退债立案

## 背景

2026-11-26 对账「zhixing refresh 日志断流 8 周」之谜, 结论: **服务从未死, 是
services.yaml 声明三处过期** (登记后 plist 被 10 月初的手写维护改道, 声明没跟上):

| 维度 | 声明 (services.yaml 6089-6106) | 现实 (本机 plist 实测) |
|---|---|---|
| outputs | `~/.local/share/zhixing-dashboard/launchd-refresh.log` (out/err 合一, 10-03 停更) | `~/.local/log/com.omostation.zhixing-dashboard-refresh.{out,err}.log` (分离, 11-26 10:56 仍在写) |
| program.args | 宿主根 `orchestrator.py` (19294B, 10-08 后未更新的孤儿残骸) | `current/orchestrator.py` (42340B, 随 release 切换的真身) |
| 运行态 | — | 健康: StartInterval 300s 正常, observed_at 分钟级, failed=0 |

顺带发现第二独立病 (已现场处置 + 立债): capability-registry-sync-daily cron
(registry.yaml 518 行, 命令链自证 `cd $HOME/Workspace && git commit`) 设计为主仓
main 直提, 2026-11-26 04:05 运行时 push 与远端并发推进冲突失败滞留, 主仓 main
分叉 31 提交。已 tag 存档 (`cleanup-archive/bad-epoch-sync-488d737ca`) + soft
reset 对齐 origin/main。不修则每天复发。附带发现: 该 cron 产物把 11-03 人工维护
的 frontmatter 标记重置 (last-reviewed 11-03→09-24), 且 11-03 人工加的
「epoch-0 bug 手工修正」注释系对 ADR-0373 的误解 —— 生成器
`bin/ssot/gen-capability-registry.py:600-603` 注释自证 `generated_at: 1970` 是
**有意的 sentinel 设计** (防 CI drift check 恒红), 非 bug。误导注释已由本 spec
订正定性。

## 变更 (write_surfaces)

1. `.omo/_truth/registry/services.yaml` (T353 同族镜像回填, ~6 行):
   - `zhixing-dashboard-refresh.program.args`: 宿主根 → `current/orchestrator.py`
   - `outputs.stdout/stderr`: 旧合一路径 → 实际分离的 out/err 两行
   - `notes` 追加 2026-11-26 对账记录
2. `.omo/debt/items/CRON-CAPABILITY-SYNC-MAIN-DIRECT-COMMIT.yaml` (新债立案):
   cron 主仓直提结构病 (push 失败必分叉, 11-26 实测 31 提交) + 人工 frontmatter
   标记被 sentinel 设计覆盖 + 误导注释定性记录

## 验收 (done_when)

- services.yaml 该服务块与 `plutil -p` 实测 plist 逐字段一致 (args/outputs)。
- `gen-service-configs.py --validate` 仍 0 violations; `--check` 仍 0 drift
  (该服务 `generate: false` observe-only, 不参与 drift 判定, 不应受影响)。
- 债条目落盘且 `check-debt-closure-discipline` 无新红 (opened, 非 resolved,
  不触发闭环戳要求)。

## 非目标 (non_goals)

- 不动本机 plist (generate: false 手写安装面, 由宿主维护)。
- 不清理宿主根孤儿 `orchestrator.py` 残骸 (部署根文件, 属 dashboard 运维面)。
- 不改 ADR-0373 sentinel 设计 (1970 非 bug, 生成器 600-603 行注释自证;
  11-03 的「手工修正」注释才是误解方)。
- 不在本 BET 重构 cron 直提为 worktree PR 模式 (立债 CRON-CAPABILITY-SYNC-
  MAIN-DIRECT-COMMIT 留后续; 涉及 cron registry 命令链改型, 超出声明回填 scope)。
- 不处理 reality-check 全景预存债 (E4 未分区 31 条 / E5 enabled 错位 6 条 /
  E2 undeclared 4 条) —— 与本 BET 正交, 其中 zhixing-projection-fullrefresh
  声明 enabled 未装一项与 T353 族同源, 留全景对账。

## 风险与回滚

- L1: 纯声明回填 + 债条目新增, 无运行时写面; revert 单 PR 即可。
- 若后续宿主维护再次改道 plist, drift 现象会如实再现 (声明镜像模式的既知边界)。

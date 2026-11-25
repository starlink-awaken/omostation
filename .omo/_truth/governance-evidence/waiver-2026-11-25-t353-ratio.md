---
schema: md/v1
status: active
lifecycle: history
owner: principal
created: 2026-11-25
last-reviewed: 2026-11-25
type: workflow-waiver
value_indicator_policy: false
pr_numbers:
  - 5562  # T10-353 services.yaml 8 服务声明镜像回填 (数据修正, 非治理机制开发)
waiver_scope: PR #5562 single merge (service-decl mirror backfill)
---

# T10-353 ratio waiver — services.yaml 声明镜像回填

## Principal authorization

> 「go」— 2026-11-25 会话, 授权将 services.yaml 8 服务镜像回填正式化为 BET。
> (同会话上午已收到 ratio 42.3%>40% 超标信号与「下阶段偏工程类 BET」的建议, go 针对
> 的是先把镜像副本正式化收口。)

## Waiver 边界 (narrow)

- 仅豁免 PR #5562 本次 merge 的 governance-ratio ceiling 检查。
- 本 PR 为**数据修正**: 镜像本机 plist 实际注入的 PATH 与 resident 日志落盘路径
  (T349 语义对比治好假红后现形的真漂移), 非治理机制开发。
- 不豁免后续任何治理类 PR; 30d 窗口统计不受影响。

## 背景

- check-governance-ratio 42.3% > 40% 为 30d 滚动统计预存基线 (最近治理 BET 密集),
  与本 PR diff 无关 (干净 HEAD 同样 FAIL)。
- 本 PR lock targets 含 `.omo/` 被分类器计为 governance —— 粗粒度分类把数据修正
  算成了治理。先例: waiver-2026-09-17-4019-pitfall-fixes-ratio-debt.md (#3870
  工具修复误分类豁免)。

## 后续动作 (非本 waiver 义务)

- 下阶段 BET 偏工程类 (稀释窗口占比, owner 已知悉)。
- 安装器 PATH 注入源头与声明生成器同源化留债另案。

---
schema_version: specification/v1
spec_version: 1.0.0
status: accepted
lifecycle: contract
owner: governance-team
created: 2026-09-11
last-reviewed: 2026-09-11
title: ops 注册表防漂移双闸 (check-signals + cron 准入)
bet_id: BET-Y1Q4-T16
implementation_authorized: true
value_indicator_policy: false
---

# ops 注册表防漂移双闸 — 设计规格

## 背景

BET-Y1Q4-T14 (批次 18, PR #3526) 一次性清理了 services.yaml 的 303 missing,
但漂移机制仍在: 注册项与现实的 anchor (crontab 行 / launchd plist / 日志文件)
脱节后没有任何常态检测, 必然再次积累。本规格建立双闸防复发。

## 闸 1: `ops check-signals` — 常态 drift 检测

`bin/ops/cli.py` 新增 `check-signals` 子命令:

- 对 services.yaml 中所有 `enabled: true` 条目核验现实 anchor:
  - `scheduler: cron` → 本机 crontab 存在匹配行
    (先按 entrypoint basename 词边界正则匹配, 未命中再按 id 尾段 token 匹配;
    词边界防 `omo` 误命中 `omostation` — 批次 18 误判回归用例)
  - `scheduler: launchd` → `~/Library/LaunchAgents/<label>.plist` 存在
  - `liveness.signal` 为 file/file::attr 类型 → 路径存在
- 输出: 人类可读表格 + `--json`; exit 0 = 零 drift, exit 1 = 有 drift。
- 纯检测, 不改任何注册或调度状态。

## 闸 2: cron 准入校验 (CI 注册自洽)

`bin/mof/gen-service-configs.py` 的 `validate_service_declaration` 增加 cron 规则
(只在 `--validate` / `--check` 路径生效, CI 可验, 不依赖本机 crontab):

- `scheduler: cron` 且 `enabled: true` 的条目必须有非空 `program.entrypoint`;
- 且 entrypoint basename 含 id 尾段 token (如 `cron.log_rotate` → `log-rotate`),
  或条目显式声明 `crontab_token` 字段;
- 拒绝 `projects/omo` 类占位 entrypoint (批次 18 抓到 30 条此类注册与
  crontab 占位写法 `$(run ...)` 脱节, 是误判和 drift 的共同根因)。
- grandfather: 已 `enabled: false` 的存量占位条目不报错 (只拦新增/再激活)。

## 交付物

1. `bin/ops/cli.py`: `check-signals` 子命令 (+ `--json`)。
2. `bin/mof/gen-service-configs.py`: cron 准入规则。
3. 测试: 两工具的批次 18 误判回归用例 (词边界 / 占位 entrypoint)。
4. services.yaml 注册 `cron.ops_signal_drift_check` 每日巡检项 + crontab 行
   (批次 17 cli-availability-probe 先例)。

## 验证 (verify)

- `python3 bin/mof/gen-service-configs.py --validate` → exit 0
- `python3 bin/ops/cli.py check-signals` → 对 T14 清理后注册表 drift 数 ≤ 5
  (cron 环境差异容忍; 本机全量 0 drift 为准)

## 非目标

- 不重写 ops 工具其它子命令。
- 不做 268 条 manual 能力项迁出 (另立 BET, 需消费方调查)。
- 不在 CI 阻断本机状态 (准入校验只验注册自洽)。

## 风险

低。纯新增检测面, 不改调度行为。每日巡检 exit 1 不告警, 只落报告。

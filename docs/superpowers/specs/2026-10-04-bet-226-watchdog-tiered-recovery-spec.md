---
schema_version: specification/v1
spec_version: 1.0.0
title: BET-Y2Q4-T10-226 看门狗分级恢复 + host 资产漂移回同步
bet_id: BET-Y2Q4-T10-226
status: accepted
lifecycle: contract
owner: engineering-agent
last-reviewed: 2026-10-04
---


# BET-Y2Q4-T10-226 Spec — 看门狗分级恢复 + host 资产漂移回同步

- bet: BET-Y2Q4-T10-226
- date: 2026-10-04
- owner: engineering-agent
- workflow: dashboard-evolution

## 背景

T10-223 (PR #4619/#4621/#4622) 交付 projection-republisher 后, :43191 的 projection_stale
根因已根治。但活性看门狗 `liveness-watchdog.sh`（zhixing-dashboard 仓, deploy 目录,
launchd `com.omostation.zhixing-dashboard-watchdog`, StartInterval=120s）的恢复动作仍是
「探活失败×2 → `launchctl kickstart -k` dashboard 服务」。

问题：最常见的故障模式是**投影租约过期**（republisher 缺席/错过），此时重启 dashboard
服务对 stale projection **完全无效**——读端继续 503, 反而引入无谓进程重启。

同时 `com.omostation.zhixing-host-drift` 自 deploy 多轮 hotfix 起持续退出 1：
template.html / copilot_service.py / rag_engine.py 三个受管文件 workspace 资产副本
（bin/panorama/assets/host/）落后于 deploy 有意变更（均已提交在 deploy 仓 origin/main）。
`zhixing-host-sync.py` 的 drift 提示写明「有意变更 → capture (版本化)」。

## 方案

### A. 看门狗分级恢复（改 deploy 侧 liveness-watchdog.sh）

失败×2 后的动作序列改为：

1. `launchctl kickstart` `com.omostation.zhixing-projection-republisher`（不 -k, 正常启）；
2. 90s 内每 10s 重探 `/`, 恢复 → 日志记 `recovered_via=republisher`, 清计数, 退出；
3. 超时仍失败 → `launchctl kickstart -k com.omostation.zhixing-dashboard`（原动作）；
4. 5s 后再探, 恢复 → `recovered_via=dashboard`; 仍失败 → 系统通知人工介入。

语义约束：
- republisher kickstart 用普通 kickstart（它自己会续租约）; dashboard 重启保留 `-k`;
- 全部动作写 `~/Workspace/runtime/dashboard/watchdog.log`（保持现路径）;
- DRY_RUN 环境变量语义不变;
- republisher 缺席（launchctl 查无 label）时跳过该级, 直接走 dashboard 重启。

### B. host 资产 capture 回同步（workspace 侧）

在 workspace 执行 `python3 bin/gac/zhixing-host-sync.py capture`（deploy→workspace 资产,
3 个漂移文件 + 既有一致文件全量 sha256 对齐）。结果要求 `check` exit 0。

zhixing-dashboard 仓属独立 repo, 按既有惯例（9-24 以来 hotfix 均直接 commit+push 其 main）
直接交付, 不走 workspace PR。

## 验收

见台账 done_when。关键实测：
1. deploy 仓 origin/main 含新版 watchdog, launchd 已加载;
2. 恢复链顺序经代码审阅确认;
3. `python3 bin/gac/zhixing-host-sync.py check`（workspace）exit 0;
4. host-drift job 连续 2 周期退出 0。

## 风险与回滚

- watchdog 改动仅限故障路径, 正常探活零变化; 回滚 = deploy 仓 revert 一个 commit;
- capture 方向为 deploy→workspace, 不会覆盖线上运行版本; 回滚 = workspace revert。

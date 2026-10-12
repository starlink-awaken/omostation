---
schema: md/v1
schema_version: specification/v1
status: accepted
lifecycle: spec
owner: governance-team
last-reviewed: 2026-10-12
accepted: "2026-10-12 Principal 批准迁移 + 独立复核通过 (身份链/发布 manifest/回滚证明/部署状态)"
bet_id: BET-Y2Q4-T10-241
spec_version: 1.0.0
---

# Zhixing DCP-20 版本晋升 — G0/M0 受管发布规范

台账：`docs/plans/3y-bet-ledger.yaml` `BET-Y2Q4-T10-241`
前置：`BET-Y2Q4-T10-240`（DCP-20 代码修复，已 done，`deployment_state: BLOCKED_G0_M0`）

## 目标

把 DCP-20 已验收候选（`origin/main` 已含 `09a459a97` 系列，经 #4705 落地）晋升成
不可变、身份已绑定的 `PROMOTED_CLEAN_REVISION`，使 Zhixing 驾驶舱
（`com.omostation.zhixing-dashboard`，`127.0.0.1:43191`）运行含 GET 方法安全修复的代码。

## 前置：LaunchAgent 代码身份链修复

当前 `~/Library/LaunchAgents/com.omostation.zhixing-dashboard.plist` 的
`ProgramArguments` 直指 `~/.local/share/zhixing-dashboard-runtime-clean-20261008/live_server.py`，
**不经稳定版本指针** → 代码身份门必失败（`zhixing-host-sync --json status` 报身份不符）。

必须先修复：plist 指向稳定版本指针，使 `zhixing-host-sync --json status` 报
代码身份通过（活动运行根 SHA == 晋升版本 SHA）。

## 发布程序

1. **晋升 commit 不可变**：候选内容 SHA 冻结，版本指针唯一，晋升后代码零变更。
2. **原子发布**：逐文件备份 → 原子替换 → SHA 校验 → 失败回滚测试全过；
   43191 服务受控切换不中断。
3. **观测门**：24h / 1440 样本（对齐 claims authority observation gate），
   服务健康 + GET 拒绝行为独立复核通过。

## 回滚

- 代码面：`git revert <晋升 commit>` 完整回退。
- 宿主面：`zhixing-host-sync.py restore`（仓库 → 部署）。

## 验收（done_when）

- AC-01 晋升 commit 不可变：候选内容 SHA 冻结，版本指针唯一，晋升后代码零变更。
- AC-02 身份链：plist ProgramArguments 指向稳定版本指针；`zhixing-host-sync --json status`
  报代码身份通过；活动运行根 SHA == 晋升版本 SHA。
- AC-03 原子发布：逐文件备份、原子替换、SHA 校验、失败回滚测试全过；43191 服务受控切换不中断。
- AC-04 观测门：24h / 1440 样本（对齐 claims authority observation gate），服务健康 +
  GET 拒绝行为独立复核通过。
- AC-05 台账：completion evidence + retro 齐全；`deployment_state: PROMOTED_CLEAN_REVISION`。

## 非目标

- 不改 DCP-20 候选代码（晋升的是已验收代码）。
- 不重发 projection（DCP-20 spec 硬约束）。
- 不实现 DCP-21 Principal/Agent 身份、session、CSRF、资源 scope 或角色授权。
- 不动其他宿主资产、其他 LaunchAgent 服务、Run、Lock。

## 熔断

身份链无法证明（plist ProgramArguments 绑定的 SHA != 晋升版本 SHA）时立即停止并回退
`BLOCKED_G0_M0`；不得通过改环境变量、关闭 code-drift 检查、手工复制、重发 projection
或重启绕开门禁。

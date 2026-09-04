---
lifecycle: history
owner: governance-team
last_updated: 2026-08-18
title: BET-Y1Q2-T2-02 复盘：个人 dogfood 操作入口
type: retro
---
# BET-Y1Q2-T2-02 复盘：个人 dogfood 操作入口

> 日期：2026-08-12
> 范围：W3-01B，可信本地单用户阶段
> 结论：E3 操作链路完成；真实个人价值样本仍为 0，不宣称 W3 gate 或数字分身价值达成。

## 1. 交付结果

本轮没有扩展新的协议、账本、信号源或 UI，而是把 W3-01A 的工程链收敛为一个可直接操作的 Cockpit CLI：

1. `cockpit workflow mesh personal setup` 幂等创建 trusted-local role/responsibility；既有定义冲突时拒绝覆盖。
2. `ingest`、`confirm`、`draft`、`feedback`、`status` 只做薄 HTTP 编排，业务规则继续由 Cockpit API、OMO `PersonalEpisodeService` 和 Agora PEP 持有。
3. OMO 新增只含 Episode 安全字段的 `EpisodeDraftSnapshot`；服务端在调用方不提交草稿字段时生成确定性 `system` 草稿。
4. 产物固定 `never_send=true`；完整调用方草稿仍兼容，但明确标记为 `user_provided`，不计入系统价值样本。
5. status 从同一 Ledger 构建只读投影；原始 Markdown 正文、绝对路径和 digest 不进入 CLI 响应或草稿快照。
6. CLI 对离线服务返回非零；非默认服务器统一使用公开环境变量 `COCKPIT_API_URL`。

子仓 D0 证据：

- OMO：`a1f8478b2d50a8dd04de2e890d4e48d465a1dbfe`，tag `bet/BET-Y1Q2-T2-02-omo-20260812`
- Cockpit：`1807318b2a7495d34a69b83db39f3472843e63ee`，tag `bet/BET-Y1Q2-T2-02-cockpit-20260812`
- Agora、Iris、ECOS：零源码变更，复用既有 PEP、LocalFilesConnector 与 generated contracts。

## 2. 验证证据

- OMO：Ruff、diff check 通过；Personal Episode、Episode projection 与 policy enforcement 共 53 项相关回归通过；独立审查 `APPROVE/WATCH`，无 CRITICAL/HIGH。
- Cockpit：Ruff、diff check 通过；CLI/API/Signal/Projection/主路由共 126 项回归通过。
- 公共链：setup → Iris item → causal Episode → confirm → 真实 PEP → system-owned never-send draft → feedback → status/projection。
- 幂等与失败：setup 重复调用不增加 Ledger count、尾部 event hash 不变；未确认或 PEP 失败时零文件产物；连接失败返回非零。
- 独立红队最初发现帮助文本使用 `COCKPIT_HTTP_BASE`、实现读取 `COCKPIT_API_URL`；修复后用真实 loopback TCP 监听器验证 CLI 按 `COCKPIT_API_URL` 发送正确 path 与 JSON，复审 `APPROVE/CLEAR`。

这些测试使用临时合成 Markdown，只证明工程可用性和公共边界，不计入真实个人价值。

## 3. 范围与接受风险

用户明确短期为可信本地单用户，优先效率。本轮保留人工确认、真实 PEP、隐私边界、非假成功和 Ledger 可追溯五条硬线；以下风险接受为 WATCH：

1. Iris 目录仍通过进程级 `IRIS_LOCAL_FILES_DIRECTORY` 组合，适合单用户固定目录，不适合未来多目录并发。
2. PEP provider 配置按稳定部署配置处理；常驻进程内动态修改显式 provider 时，缓存不会自动感知。
3. PEP terminal 成功后若 Evidence append 失败，会保留已生成的本地草稿并返回非成功；崩溃 reconcile/outbox 后续另立 BET。
4. 本轮不做并发 exactly-once、多租户、家庭成员、第二信号源、LLM、自动发送或外部任务创建。

## 4. 编排复盘

本轮由 Orca Run `run_d5bd4d1f0577` 维护任务与回执：

- OMO task：`task_41c74467b2f5`
- Cockpit task：`task_322a0b2980af`

有效分工是：主控冻结单用户范围和价值口径；实现 Agent 分别拥有 OMO/Cockpit 独立写面；只读 Reviewer 对幂等、真实 PEP、隐私、CLI 公共合同做反证；主控复跑跨仓回归并负责 commit/tag/push/root pointer。Reviewer 的首次 BLOCK 证明“所有测试绿”仍可能漏掉公开帮助与运行配置的合同错位，最终用真实 TCP 而非传输层替身关闭。

两个实现子任务都只在文件稳定、验证通过并收到正式完成回执后释放；运行态 `.omc` 文件未纳入提交。

## 5. 净增与下一步

两个子仓合计修改 8 个文件、净增约 1,368 行：OMO 2 文件 180 行，Cockpit 6 文件 1,188 行。根仓仅更新两个 gitlink、BET 台账和本复盘；GaC 规则 +0、ADR +0、脚本 +0、顶级项目 +0、Ledger DDL +0。

下一步不是继续堆架构，而是启动真实观察窗口：用户在允许目录投放一条低敏、可撤销的真实个人跟进事项，通过本 CLI 完成一次确认、草稿审阅和 verdict。只有连续采样得到真实 `system` 输出、人工裁决、处理时长与节省时间，才讨论第二信号源、家庭角色或自治升级；在此之前真实价值计数保持 0。

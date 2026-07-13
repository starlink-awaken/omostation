# A3 · daemon 在线率 60%→95% — 诊断报告

> 日期: 2026-07-13 · 方法: 追溯 online_ratio 计算链 → system_health.yaml → 关联 ADR/pattern
> 关键关联: ADR-0179 (2026-07-10) · P76 launcher-zombie pattern · ADR-0120 · ADR-0178 (GaC freeze)

## 核心结论：系统性根因已在 7/10 治本，A3 从"排查"降级为"两个收尾决策"

诊断把 A3 从"查 40% daemon 为什么掉"变成了三件已定位的事。**"60% + 假绿灯 84"的系统性根因，runtime 团队已在 7/10 的 ADR-0179 里 8 层根因链全部定位、5 层已 commit 治本**（探测交叉校验 port/health/日志新鲜度、uptime 防造假、unrecoverable 死循环防护）。这正是我战略分析里"治理绿、运行时黄"的那层窗户纸——已经被捅破并修了。

## 在线率的真相：唯一真正 OFF 的是 hermes-gateway（且它是孤儿）

当前 `system_health.yaml` 里 5 个 daemon，只有 1 个真 failed：

| daemon | 状态 | 备注 |
|--------|------|------|
| agora-gateway | running | 但 freshness 945808s≈**11 天**，纯 stdio 无端口，按 ADR-0179 日志新鲜度校验**可能应判 degraded**（见下方 caveat） |
| agora-sse | healthy, port_listening | 真在线 |
| cron-service | healthy, port_listening | 真在线 |
| ollama | idle, healthy | 真在线 |
| **hermes-gateway** | **failed, exit_code 113** | last_healthy ≈ 9 天前 |

**hermes-gateway 的身份已查清**：它是一个**遗留孤儿服务**——
- 启动源在工作区**之外**：`$HOME/.hermes/hermes-agent`，launchd label `ai.hermes.gateway`（见 `projects/runtime/scripts/service-ctl.sh`）。
- **无 port、无 health_url**（ADR-0120 明确记录：它永远无法被 `port_listening` 判为 online）。
- **不在** `services.yaml` 调度契约里（那里只有 4 个服务）——即它是 launchd 里的孤儿，注册契约无人认领。
- exit 113 是**确定性故障**，曾自愈死循环 6 天，现已被 ADR-0179 的 `unrecoverable` 判定正确终结。
- 6/28 审计早已两次标注："hermes-gateway daemon 没跑 — 真实运行时, **需用户决策 (启动服务)**"。

**含义**：这一个孤儿把在线率从"4/4 真实服务全在线"拉成了 60–80%。它的去留是把在线率做真最快的杠杆，而这是一个**只有你能拍的决策**（见文末）。

## 健康快照本身是陈旧的（~11 天）——这是第一个动作

- `health.yaml` 生成于 **7/09**，是 ADR-0179 **修复之前**的数据。
- `system_health.yaml` 无 `generated_at`，`last_scan` 对应的 freshness 高达 11 天。
- 7/12 的 weekly-daemon-summary 显示 audit-rollout 管道 `returncode:1 / fallback_used`——**采集管道本身在掉链子**，所以快照没被刷新。

→ **A3 执行的第一步不是改代码，是跑一次活体健康投影**（`bin/compass_radar.py` 重新生成 health.yaml），拿到 ADR-0179 修复后的真实数字。很可能真实在线率与 60% 已大不相同。

## Caveat（诚实交代，避免又一次假绿灯）

ADR-0179 修复后，agora-gateway 这类**纯 stdio 服务靠日志新鲜度判活**。当前它 freshness 11 天 = heartbeat 早停，**真活体扫描可能把它判成 degraded**。也就是说：修复了探测器之后，真实在线率**短期内可能不升反降**——因为终于不再造假了。这恰恰是好事（红灯至少触发响应），但你要有预期：A3 的目标应改成"**在线率数字可信** + 真实服务全绿"，而不是盲目追 95% 那个可能建立在旧假数据上的靶子。

## 与 A1 的交叉印证

ADR-0179 §5 残留 debt 列了"19 backend 仍 Subprocess disconnected（mcp_server 启动/握手层）"。这正是我在 A1 里写的 caveat #1（静态可解析 ≠ 活体 resolve 成功）的**实锤**——静态 90% 可解析，但活体在 MCP 握手层还有一批失败。A1 的收口（抽样活体 resolve）和 A3 的 19 backend 是同一件事的两面，可合并处理。

## A4 已经被 ADR-0179 预先写好了

ADR-0179 §4 已经起草了**两条正是 A4 需要的 GaC 规则**：
- `RUNTIME-PROBE-TRUTH`：健康探测禁止只凭 launchd PID，必须交叉校验端口/HTTP/日志新鲜度。
- `DECL-EXEC-CONSISTENCY`：`system_health.yaml` 声明态必须与实时 lsof/launchctl 一致，不一致=drift。

但它们**被 GaC freeze 挡住**（ADR-0178，`max_rules:173`，加规则需 ADR + governance-team 审批）。→ A4 不再是"设计规则"，而是**一个治理审批决策**：要么批准这两条规则解冻，要么接受探测真实性不进门禁。这也是你（governance-team owner）要拍的。

## 建议的 A3 执行清单（可派单）

1. **先跑活体健康投影**（`compass_radar.py`）拿真实数字 + 修 audit-rollout `returncode:1` 采集管道。profile: `project-code-change`。
2. **hermes-gateway 决策**（见文末问题）→ deprecate 注销 或 dig exit 113 根因。
3. 合并 A1 收口：对 19 backend 跑活体 resolve，分离"握手层"失败。
4. 顺带清 ADR-0179 §5 残留：bos-services.yaml 3 个 kos 服务 drift（`test_default_registry_is_valid` 正在 fail）、6 个悬空 gitlink。

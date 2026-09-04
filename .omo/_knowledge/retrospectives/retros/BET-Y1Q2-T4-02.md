---
lifecycle: history
owner: governance-team
last_updated: 2026-08-18
title: BET-Y1Q2-T4-02 复盘：个人结果观测与真实价值采样
type: retro
---
# BET-Y1Q2-T4-02 复盘：个人结果观测与真实价值采样

> 日期：2026-08-12
> 范围：W4-04，可信本地单用户阶段
> 结论：E3 观测能力完成；真实个人样本为 0，四周价值门仍为 `not_ready`，不宣称价值达成。

## 1. 交付结果

本轮没有新增 UI、服务、账本、DDL、M2 或第二信号源，而是在既有 Personal Event Ledger 上补齐最小结果观测：

1. `Evidence.LocalDraft.v1` 持久记录 `output_origin=system|user_provided|unknown`；旧事件归为 unknown。
2. `Outcome.Human.v1` 支持 accept/edit/reject/defer/ignore，并允许显式记录 review duration 与 estimated time saved；缺失保持 null。
3. OMO 按 principal 只读重放有效 verdict、草稿来源、signal-to-verdict latency、自然周样本和四周价值门。
4. 只有真实 Signal 因果 Episode、匹配的 `Action.Succeeded`、system evidence、最新 accept outcome 与完整人力数据才进入价值分子。
5. Cockpit 复用既有 personal feedback/status API 与 CLI 暴露观测；观测失败返回 unavailable，非法 burden 在 CLI/API 两层拒绝。
6. HTTP 不再返回本地 `file://` 路径；公开状态不包含正文、源 URI、digest 或绝对路径。

子仓 D0 证据：

- OMO：`9b05450fe8760a6388356e229fa3c2a6313634c8`，tag `bet/BET-Y1Q2-T4-02-omo-20260812`
- Cockpit：`ee8644fe12ff63da3762105cb17ee6192cf044f3`，tag `bet/BET-Y1Q2-T4-02-cockpit-20260812`

## 2. 验证与审查

- OMO：Personal Episode、Episode projection、policy enforcement 共 86 项回归通过；Ruff、diff check 通过。
- Cockpit：personal API/CLI、Episode projection 与 workflow operations 共 58 项回归通过；Ruff、diff check 通过。
- 独立审查先后发现并关闭：缺 Action.Succeeded 仍计数、手工 Episode 进入分子、按 signal 时间分周、旧 accept 覆盖新 reject、成功仍叫 candidate、草稿来源未写 Ledger、观测失败假报 live、CLI 接受 NaN/Inf、HTTP 泄露本地路径。
- 最终 OMO 与 Cockpit 审查均为 APPROVE/CLEAR，无 CRITICAL/HIGH/MEDIUM 遗留。

这些证据只证明观测机制正确，不是个人价值样本。测试使用合成 Ledger 和临时文件，全部排除在价值分子之外。

## 3. 价值门与接受风险

四周 gate 的定义保持严格：连续四个自然周，每周至少三个真实 Signal 因果、本人 accept 的 system outcome，且每条都显式满足 review time < saved time，才返回 `passed`。当前运行态尚无真实 Personal Event Ledger 样本，因此门槛仍为 `not_ready`。

按用户“短期单用户可信本地、优先效率”的决策，本轮接受以下 WATCH：

1. 不做多进程 exactly-once、跨主机、家庭成员、多租户或崩溃 reconcile。
2. PEP terminal 成功后若 Evidence append 失败，接口会返回失败但本地草稿与 receipt 可能已存在；后续可用 outbox/reconcile 独立处理。
3. 手工 Episode 仍可进入总体统计，但没有 Signal 因果链时永不进入价值门分子。
4. 不自动推断人工耗时或节省时间；用户不填写时保持 unknown，不能按 0 计算。

## 4. 编排复盘

本轮由 Orca Run `run_239dcc976509` 协调 OMO、Cockpit、只读审查和 PASW 控制面修复。有效模式仍是“主控冻结合同和价值口径、实现 Agent 独占写面、Reviewer 用反例阻断、主控独立复跑并负责 D0”。

OpenCode/Kilo 在当前环境中分别暴露 TUI 未真正执行和运行时断连，不能把“终端已启动”当任务进展；只有真实 diff、测试证据和 worker_done 才算完成。Claude 执行与审查稳定，但首版实现仍出现多个逻辑假绿，证明独立反证不可省。

## 5. 净增与下一步

本轮触及 OMO 2 个文件、Cockpit 4 个文件、根仓 BET 台账/两个 gitlink/本复盘；规则 +0、ADR +0、顶级项目 +0、数据库迁移 +0。

下一步不是继续扩 dashboard 或自治，而是启动真实观察窗口：用一条低敏、可撤销的个人事项跑完 ingest → confirm → system never-send draft → feedback，并显式填写 review duration 与 estimated saved time。达到自然周样本后再决定第二信号源、家庭角色或更高自治；在此之前 T8 面板只能显示未接入/采集中，不能把全零画成进展。

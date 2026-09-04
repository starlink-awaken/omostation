---
title: BET-Y1Q2-T1-19 复盘 — Codex ACP stdio permission-broker cutover
type: retro
status: stale
owner: engineering-agent
created: 2026-08-20
bet: BET-Y1Q2-T1-19
lifecycle: history
last_updated: 2026-08-21
evidence_cutoff: 2026-08-20T16:23:15Z
---

# BET-Y1Q2-T1-19 复盘

## 结论先行

T1-19 当前是 `blocked / NOT_PROVEN`，不是已完成的 ACP cutover。

仓库中已有 ACP stdio 会话状态机、permission request 处理和 cancel/timeout 回收代码；但 Codex 的生产 registry 仍只绑定 `cli_prompt`，OMO 多个入口仍显式或隐式默认 `cli_prompt`，真实 ACP R1 canary、越权拒绝、取消回收和独立验证 receipt 尚未形成同一条可重复证据链。因此不得声称 ACP 已成为生产 transport，也不得声称 `cli_prompt` 已退役。

本次复盘只纠正完成语义和后续顺序，不修改 transport、registry、用户配置、认证、运行进程或任务真相。

## Q1 实际耗时 vs appetite？

- **appetite**：3 days。
- **实际实施耗时**：无法从当前直接证据可靠重建；本 BET 没有满足完成条件，不能用一次局部提交或复盘修订耗时冒充实施耗时。
- **本次真相修正**：2026-08-20 至 2026-08-21 完成台账回退、证据复核和本复盘重写；它是 correction effort，不是 T1-19 delivery duration。
- **判断**：appetite 已消耗但目标未交付，正确状态是 `blocked`，不是把 appetite 改小或补写虚假的“30 minutes”。

## Q2 done_when 是否全部通过？哪条没过，为什么？

没有。当前台账的 `done_when_met` 为空，全部 `pending_when` 均保留。按三轴复核如下：

| 轴 | 当前直接证据 | 判定 |
|---|---|---|
| Engineering | `projects/omo/src/omo/omo_acp_transport.py` 已有 initialize、session/new、prompt、permission、cancel、timeout 与进程回收状态；`omo_worker_core.py` 有 `acp_stdio` launch 分支 | `PARTIAL` |
| Operational | Codex worker registry 仍只暴露 `cli_prompt`；全局 preference 虽列 `acp_stdio`，但 Codex 无对应 command；dispatcher/CLI/blueprint 仍有多处 `cli_prompt` 默认 | `CONTRADICTED` |
| Verification | `.omo/evidence/t1-19-acp-live-receipt.json` 不存在；当前 adapter 没有可重复验证该 receipt 的 `verify-acp-receipt` 入口 | `NOT_PROVEN` |
| Permission safety | 没有当前 SHA 绑定的真实 R0/R1 `allow_once`、越权拒绝、symlink/gitlink/path escape 负例 receipt | `NOT_PROVEN` |
| Cancel/reap | 有实现和测试线索，但没有真实 ACP child/session/lease 在 cancel/timeout 后全部归零的 live receipt | `NOT_PROVEN` |
| Canary/value | 没有真实非 marker Codex ACP R1 canary、实际 git delta、CompletionManifest 和独立 verifier accept | `NOT_PROVEN` |
| Subtraction | `cli_prompt` 仍是 Codex 自动生产绑定，Orca supervisor 仍在该路径；没有完成指名减法 | `NOT_DONE` |

所以本 BET 不能写 `done`，也不能用“代码存在”“turn-end”“exit 0”或 fixture 代替完成。

## Q3 过程中发现的与 plan 不符的事实（打假）？

1. **代码存在不等于生产 cutover。** ACP transport 已进入 OMO，但 worker registry、dispatcher 默认值和 live evidence 没有一起切换。
2. **默认事实发生分裂。** registry 顶层 preference 是 `acp_stdio → cli_prompt`，Codex 实际 transport 只有 `cli_prompt`；`omo_worker_dispatch.py` 偏向 `acp_stdio`，而 `omo_worker_cmd_worker.py`、`workflow_dispatch.py` 与 `blueprint_control.py` 仍有 `cli_prompt` 默认或显式调用。
3. **验证合同本身尚未落地。** 台账要求的 live receipt 文件缺失；仅跑单测不能证明真实 Codex、真实 permission request、真实 git delta 与独立验证。
4. **T1-18 的关系需要精确表达。** T1-18 已按其自身 scoped contract 置 `done`，但其复盘也明确部分 canary 物料仍只在本地证据树、终端回收待完成。T1-19 cutover 前必须重新绑定并验证其前置证据，不能把“T1-18 done”自动推导为“ACP 可切换”。
5. **双生产路径会制造重复副作用。** transport 不确定时自动 fallback 到 Orca 会形成第二 dispatch；正确 break-glass 是先证明原 child/session 已 cancel+reap，再创建新的 successor assignment。
6. **A2A 不属于本 BET。** A2A 是后续跨 Agent/跨节点 federation transport；当前只允许在 ACP 本地 worker-control 真实通过后做隔离 HTTP+JSON shadow/TCK，不得借 T1-19 扩面。

## Q4 净增减：代码行 / 文件 / GaC 规则 / ADR / 脚本？

- **生产代码、transport、registry、daemon、DB、用户配置**：本次均为 `+0 / -0`。
- **交付面**：本次只改写本 retro；精确行数和文件净变化必须以本次 workflow `verify` 与 `bet-ledger surface` 的复核输出为准，不把工作树瞬时 diff 或历史全局百分比固化成长期事实。
- **新状态机、scheduler、watchdog、第二 ledger**：均为 `0`。

T1-19 真正完成时必须同时交付下列减法：

1. Codex registry 的自动 transport 只保留 `acp_stdio`；
2. dispatcher/reclaim/blueprint 不再有隐式 `cli_prompt` 默认；
3. Orca supervisor 退出自动 dispatch/fallback，只保留显式人工 break-glass 或 observer；
4. 不新建第二份 receipt、第二个状态机或独立 ACP task truth，继续复用 WorkPacket、Mesh、CompletionManifest 与 VerificationReceipt；
5. T1-18 的 wait/resume、collect、rollback、independent verify 保护测试不得下降。

如果三天 appetite 内无法同时完成真实 canary 与上述指名删除，应保持当前 `cli_prompt` supervised path，不做半切换。

## Q5 下一个认领本 track 的 agent 需要知道什么？

1. **重验证前置**：在当前 main 和独立 clone 下读取 T1-18 的 packet/dispatch/candidate/rollback/independent receipt，明确哪些是入库证据、哪些仍是本地或待回收资源。
2. **固定协议身份**：固定 ACP v1 与 Codex ACP package/version/digest 和完整 stdio argv；不允许 global install、unpinned `npx` 或用户配置写入。
3. **完成生命周期负例**：覆盖 initialize/capability negotiation/session new|load/prompt/update/EOF/timeout/protocol mismatch，任何不兼容 fail closed，零 Mesh 晋升。
4. **收口 permission broker**：R0 与满足 verified clone、active claim、WorkPacket exact write surface、canonical path、无 symlink/gitlink 越界和 argv allowlist 的 R1 才能 `allow_once`；未知、越权与 L2+ 保持人工 gate。
5. **证明 cancel/reap**：真实 cancel/timeout 后 child process group、ACP session 和 lease 全部归零；transport uncertainty 不触发 Orca 自动 fallback。
6. **跑真实 canary**：一次非 marker R1 任务产生真实 model output、git delta、逐项 measurements 与 CompletionManifest；另一次越权 permission 被拒且 tree/Mesh 不变。
7. **独立验证再切换**：独立 verifier accept 后，才在同一个受审变更里把 registry 切为 `acp_stdio` only，并删除所有隐式 `cli_prompt` 自动路径。
8. **落 live receipt**：生成并重复验证 `.omo/evidence/t1-19-acp-live-receipt.json`，必须绑定当前 adapter SHA、ACP package digest、packet/spec/assignment/dispatch、changed paths/tree hash 和 verifier identity，且 `live=true`、`fixture=false`、`independently_verified=true`。
9. **最后才讨论 A2A**：ACP 通过后另开 BET，先做 A2A 1.0 HTTP+JSON shadow 与官方 TCK；不替代 MCP、OMO 或 BOS。

当前决策是 T1-19 保持 `blocked / NOT_PROVEN`：继续使用受监督 `cli_prompt`，禁止自动 Orca fallback、双 dispatch、自动 merge、L2+ 自动批准、远程 ACP 与 A2A 扩面，也不修改用户认证、全局 Codex 配置或持久化 `allow_always`。

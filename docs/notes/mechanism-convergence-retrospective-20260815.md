---
title: "机制收敛复盘（2026-08-15）"
lifecycle: history
owner: governance-team
last_updated: 2026-08-15
last_updated: 2026-09-03
type: ssot
last_updated: 2026-09-03
---

# 机制收敛复盘（2026-08-15）

## 结论

本批只收敛已经发生的机制事实，不把“能力存在”写成“已获得工程结果”。
T1-05A 仍在 shadow 窗口，T1-18 只完成 accept leg，T7 仍缺周期样本；
T1-19 和 A2A 都不得因为本次收敛而提前推进。

更重要的战略结论是：近期工作的主线并不是“再增加一个 Agent
协议”，而是把现有控制面从声明收紧为可计算、可回放、可拒绝的事实链。
这一主线有价值，但已经挤占了真实个人结果和工程交付 dogfood 的时间。
下一阶段必须用“通过准入门后停止加机制，回到真实结果”来纠偏。

## 架构裁决

系统只保留一条控制真相链，其他协议均为可替换边界：

```text
LifeOS / C2G 意图与战略
        ↓
ECOS WorkPacket 不可变合同
        ↓
OMO Task + Workflow Mesh + Receipt 治理真相
        ↓
本地 worker control（现行 Orca supervised；候选 ACP）
        ↓
AetherForge + omlxc 算力与模型路由
        ↓
独立验证 + 补偿 / 回滚

MCP = 工具与上下文边界
A2A = 未来跨 Agent / 跨节点联邦边界
Outcome = 外层价值验收，不由上述任一技术回执代替
```

### 真相与投影分工

| 对象 | 唯一职责 | 不得被解读为 |
|---|---|---|
| BET ledger | 战略意图、依赖、验收标准和状态 | 运行时任务数据库 |
| Task YAML | 当前工作与审批对象 | 另一份战略台账 |
| WorkPacket | 已接受规格的不可变派工产物 | 可被下游工具修改的任务真相 |
| Workflow Mesh | 准入、运行、审批、证据、验证与补偿事件 | UI 或 worker 的便利状态 |
| Receipt / Manifest | 可重算的执行证据投影 | 自报 done 或战略状态 |
| Orca | 终端、会话和人工审批运输 | 准入真相或任务完成判定 |
| ACP | 本地 Agent 会话、权限请求和取消的标准边界 | OMO 的替代状态机 |
| MCP | 工具发现、调用和上下文 | Agent 间任务生命周期 |
| A2A | 跨进程、跨节点 Agent 协作 | 本地权限代理或 OMO 真相层 |
| AetherForge / omlxc | 算力、模型目录与路由 | 任务、证据或战略控制面 |

### 协议选择结论

- **Orca supervised** 保留为 T1-18 的人工审批基线。`ready` 和
  `input_accepted` 只是运输事实，不是模型完成或人工已批准。
- **ACP** 是下一个合理的本地 worker-control 候选，但只能在 T1-18
  完成 reject/rollback 基线后以单生产 transport 切换。禁止与 Orca
  自动双路执行，禁止在不确定状态下自动 fallback。
- **A2A** 可行，但应定位为 ACP 之后的跨 Agent 联邦。首个试点只做
  HTTP+JSON shadow、官方 TCK 和无副作用 canary；它不替代 MCP、
  ACP 或 OMO。
- **MCP** 继续作为工具/上下文面，不强行承担 Agent 任务生命周期。

## 战略诊断

### 近期为什么会“做偏”

1. **控制面快于价值面。** 合同、门禁、工作树、回执和验证快速增强，
   但真实 personal accepted 和 engineering decision outcome 仍无新样本。
2. **运输 ACK 容易被当成完成。** Orca/Codex 的 ready、input accepted、
   process exit 都曾暴露假绿风险，迫使控制面反复加固。
3. **“有字段”曾被当成“有证据”。** `affected_hash` 只做非空检查，
   说明只验真值而不重算语义的 gate 只是假门禁。
4. **子模块指针和生成文档会让能力“历史已完成、当前不可用”。**
   所以合并不能只看功能仓 PR，还必须验证 root gitlink 和生成消费面。
5. **全局 verify 不一定是只读。** 狭交付中盲跑全量生成/同步会污染运行投影；
   本批已恢复这类污染，之后应优先 exact-files verify，再扩大到 CI。
6. **协议候选过多。** Orca、ACP、A2A、MCP、Kandev、Ruflo 同时进入
   讨论，会把“用哪个运输”误当成“产生什么结果”。

### 这一批真正解决的问题

这一批没有交付新用户功能，交付的是三个系统性下限：

1. 写入 Agent 必须在 verified independent clone 中运行，共享主树是集成点。
2. 人工审批、运输接受、模型输出、候选证据和独立验证是不同状态，
   只有最后一项能产生 `WorkflowVerified`。
3. 影响面、回执、基线和补偿都必须由可重算内容绑定，不接受不可验证的
   字符串或 worker 自报。

## 已核实的收敛

### T1-05A：shadow 有实证，但窗口未结束

- 共享 SQLite WAL 协调层、claim/fencing/heartbeat 和 shadow 观测面已接通。
- 专用部署 clone 已留下 live runtime attestation；备份路径在发现 cron 指向漂移后完成人工恢复和 integrity 验证。
- SSOT 仍是 `BET-Y1Q1-T1-05A` 及其 retro。七天 shadow 窗口从
  `2026-08-14T12:56:00Z` 开始，只能在窗口跑满且 human gate 确认后置 done。

### T1-18：人工批准 accept leg 已实证

- 真实 approval-wait canary 在同一受管 terminal 完成 collect 与独立 verify，
  `WorkflowVerified` 时间为 `2026-08-15T02:34:47Z`。
- 变更面只有
  `docs/superpowers/plans/2026-08-14-supervised-blueprint-control-loop.md`；独立验证回执为
  `sha256:df8dd2245e47ab409e41646408bc0eb522f3ec905e10b0bf4d62001d900bc49c`。
- reject + compensation rollback leg 尚未执行，因此 `BET-Y1Q2-T1-18` 保持
  `candidate`，不得声称整条闭环已完成。

### affected-hash 假门禁收敛为可复算 receipt

旧 claim 门禁只校验 `affected_hash` 非空，dummy 值也能通过，没有把
changed project、affected project、layer contract 和被认领路径绑定起来。现在改为
`affected-graph-receipt/v1`：生成器和 OMO 均复算 canonical hash、layer-contract digest
和受影响图，未知项目 fail closed。

独立红队又补了三个绑定漏洞：

1. 拒绝模糊宽路径 `projects`，防止 workspace-root receipt 冒充所有子项目。
2. receipt ref 必须是 workspace 内 canonical repo-relative regular file，拒绝绝对路径、
   traversal、symlink 和外部文件，运行台账不再持久化本机绝对路径。
3. 任何非空 surface claim 都要求 `workspace-root`；生成器只能在 workspace
   内原子、排他地发布新 receipt，不覆盖既有 evidence。

### PR #1498：done 不再仅看台账字面

PR #1498 已合并独立 done 抽样审计：10 个样本中 2 个 false done，
1 个因漂移无法验证，6 个缺 retro，只有 7/10 可按现有证据判为诚实。
这个结果是快照审计，不应被改写成对整个台账的成熟度背书。
集成门同时发现并修复了跨提交的 capability registry 生成文档漂移。

## SSOT 边界

- 状态、依赖和 done_when 以 `docs/plans/3y-bet-ledger.yaml` 为准。
- T1-05A 运行结论以共享 coordination store 的 status/attestation 与
  `.omo/_knowledge/retros/BET-Y1Q1-T1-05A.md` 为准；文档不反向生成运行真相。
- workflow claim 以 OMO 重算验证的 receipt 为准；root 生成器只生成候选证据。
- T1-18 的 accept 回执只证明已完成的 leg，不修改 BET 状态，也不替代
  reject/rollback 证据。

## 运行态快照与未完成项

本轮收口时的运行态观察为 **0 条 personal accepted** 和
**0 条 engineering decision outcome**。这两个数字是当时快照，不是长期常量；
后续判定必须回到权威运行事件与 memory-os 投影。所以 T7 的“每周至少 20 条”
尚未验证，不得用 scene lifecycle 已是 shadow 来代替 outcome 产出。

未完成项是：T1-05A shadow 窗口跑满与 human gate；T1-18 reject/rollback；
T7 真实周期样本；依赖 T1-18 的 T1-19；以及不在本轮目标中的 A2A。
在这些边界没有新证据前，**不推进下一轮**。

## 后续顺序与准入门

下列是已有未完成工作的依赖顺序，不是本批自动启动的新轮任务：

1. **完成 T1-18 负向腿。** 用 fresh admission 执行一次真实 verifier reject，
   证明 CompensationStarted 到 baseline digest 恢复，并清理历史 Orca 资源。
   没有这条证据，T1-18 不能 done，T1-19 不能切换生产 transport。
2. **回到真实价值样本。** 优先用现有 never-send 个人链路完成低敏真实
   item 的人工裁决与时间度量；并修复 T7 的真实 engineering decision outcome
   持续入口。代码、PR 和合成样本均不得代替两类 outcome。
3. **再做 T1-19 ACP cutover。** 先 shadow 协议生命周期和权限 broker，然后在
   同一受审交付中退役自动 `cli_prompt` 默认。切换后不保留自动双路。
4. **最后才做 A2A shadow。** 仅当 ACP 本地边界稳定后，再用单 binding、
   官方 TCK、身份授权、幂等和 cooperative cancel 验证跨 Agent 联邦。

每个阶段都必须同时满足：真实 canary、负向用例、可重算 receipt、
独立 verifier、清理/回滚证明、root gitlink 与消费面同步。任一项缺失，
都只能记为 candidate 或 shadow。

## 运维与工具教训

- 本批在检查 `install-watch-agent.py --help` 时发现该脚本没有只读 help
  边界，而是直接执行安装。这次意外触发恰好修复了指向临时 worktree
  Python 的 watch LaunchAgent，并验证为稳定系统 Python、plist 可解析、
  注册成功且最后退出码为 0；但这仍是工具契约缺陷，不能因结果正面
  而忽略。后续 installer 必须提供无副作用 `--help` / `--dry-run`。
- 共享 Workspace 仍有他人/运行态未提交修改，本批全程以独立 clone 交付，
  没有用 reset、clean、stash 或 rebase 清理共享主树。
- 只有“功能仓合并 + root 指针 + 生成消费面 + CI + 可恢复标签”同时成立，
  才能称为交付收口。

## 本批停止点

本文与已合并的代码、测试、回执、子模块指针和生成文档共同构成本批 closeout。
合并后不自动 claim T1-18 负向腿、T7、T1-19 或 A2A，等待人类发出下一条命令。

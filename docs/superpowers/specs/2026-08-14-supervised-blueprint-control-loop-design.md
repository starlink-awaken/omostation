---
status: active
lifecycle: contract
owner: governance-team
last-reviewed: 2026-08-14
---

# 受监督 Blueprint 控制闭环设计

> 日期：2026-08-14  
> 状态：accepted  
> BET：BET-Y1Q2-T1-18

## 1. 问题与事实纠偏

ECOS 已经拥有 `WorkPacket`、`CompletionManifest` 和
`VerificationReceipt`，OMO 也已能把经过合同校验的候选证据映射为
`EvidenceRecorded`，并在独立验证通过后写入 `WorkflowVerified`。当前生产断点不是
缺少更多模型，而是没有一条真实入口把候选 BET、受治理 Task、worker dispatch、实际
文件差异、候选清单和独立验证接成一条链。现有唯一 adapter 是不可 live dispatch 的
Kandev fixture，不能继续拿 fixture 代替生产闭环。

同时，T1-17 对 Codex 的描述过度泛化。Codex CLI 0.147.0 的
`--approve-for-me` 只表示把审批请求交给自动审查，并不承诺所有调用都无人值守。
本轮把 Codex 定义为 **supervised worker**：OMO 的人工 release 是启动前硬门；Codex
内部自动审查可能继续升级到人工确认，任何未解决审批或超时都必须失败，不能称
`unattended`、`zero-click` 或 `ready`。

Orca 运行态也已证明 `worker ready` 和 `input_accepted` 只是 transport ack：OMP
卡在首次模型设置、Pi 卡在 skill metadata 错误时，两者仍曾报告 ready/input accepted。
因此 transport ack 永远不能晋升为模型 readiness 或交付完成。

## 2. 架构选择

新增一个薄 OMO `BlueprintControlService`，复用而不复制现有资产：

- BET ledger：战略候选与 specification acceptance 的唯一真相；
- Task YAML：执行任务、人工批准、能力和写面的唯一任务真相；
- ECOS：WorkPacket、CompletionManifest、VerificationReceipt 及规范哈希；
- Workflow Mesh：request、admission、dispatch、execution、evidence、verification、
  compensation 的唯一事件真相；
- OMO worker registry/admission：worker 身份、capability 和 operation-level 门；
- Codex bounded adapter：独立 clone、固定 argv、进程组回收、delta 审计和脱敏回执；
- Orca：Run/Task/Dispatch/terminal 的运输与人工可见控制，不拥有完成真相。

不新增 blueprint task database、第二个 event ledger、第二套 WorkPacket、scheduler、
watchdog 或平台私有状态机。`.omo/workers/runs` 中的 packet、dispatch、receipt、manifest
和 rollback 信息只是可重建投影/证据，不是新的战略或任务真相。

## 3. 真相与状态模型

控制闭环按以下可观察状态推进：

```text
spec_accepted
  -> packet_compiled
  -> controller_approval_required
  -> controller_approval_granted
  -> transport_accepted
  -> process_started
  -> model_output_observed
  -> candidate_collected
  -> independently_verified
     | verification_rejected -> compensating -> rollback_verified -> closed
```

状态解释：

1. `controller_approval_granted` 必须来自 Task `approval_ref` 指向的受治理批准记录；
   Codex 任务即使是 L1，也必须 `human_approval_required: true`。
2. `transport_accepted` 仅表示 OMO/Orca 已把 immutable packet 交给 transport。
3. `process_started` 只表示 bounded adapter 已启动受控子进程。
4. `model_output_observed` 只在解析到有效 Codex JSONL 最终 assistant message 后成立。
5. `candidate_collected` 只在实际 git delta、adapter receipt、AC claims、checks、
   durable artifact refs 全部绑定后成立。
6. `independently_verified` 只由不同执行身份的 read-only direct measurement 产生；
   executor 的 exit 0、自报 done、Orca ready/input ack 均无此权限。

Codex provider review 单独投影为：

```text
auto_review_enabled | completed_without_observed_escalation |
human_required | unknown | timed_out
```

该字段不得与 controller approval 合并，也不得从 `--approve-for-me` 推断 universal
approval。

## 4. 生产接口

OMO 提供一个薄 CLI facade，所有子命令调用同一个 `BlueprintControlService`：

```text
omo blueprint compile --bet-id <BET> --task-id <TASK> --spec <repo://...> --output <json>
omo blueprint dispatch --packet <json> --worker codex --health <json> --output <json>
omo blueprint execute --packet <json> --dispatch <json> --output <json>
omo blueprint collect --packet <json> --dispatch <json> --output <json>
omo blueprint verify --packet <json> --manifest <json> --dispatch <json> --execute
omo blueprint rollback --dispatch <json>
```

### 4.1 compile

- 读取同一份 `docs/plans/3y-bet-ledger.yaml`、accepted specification bytes 和已存在
  Task YAML；不得生成新的 BET/Task。
- BET 允许 `candidate|in_progress|review|done`，但必须存在与 `spec_ref + version +
  digest` 完全一致的 `accepted_specifications`。这解除“只能执行已完成 BET”的追认式
  假闭环，不放宽 spec identity。
- 生成 deterministic WorkPacket v2；相同 ledger、task、spec 与显式时间输入得到相同
  `packet_id` 和 `packet_hash`。
- `authority.human_gate` 必须为 true；Task 必须声明人工批准并绑定 approval record。

### 4.2 dispatch

- 复用现有 active-Task `admit_workflow`，只给其 `WorkflowRequested` payload 增加
  `bet_id/packet_id/packet_hash/task_ref` identity，不复制 request/admission 逻辑；随后复用
  `dispatch_task(..., launch=False)`。
- admission 验证 Task、capability health、budget、worker admission、capability set、
  write surface 和人工批准。
- `StepDispatched` 或任何 Mesh append 失败必须向上传播；禁止 broad catch 假绿。
- 返回 `transport_accepted`，不得返回 ready/succeeded。

### 4.3 execute/collect

- 从已 admit 的 codex worker transport 构建 shell=false argv，追加由控制器创建的安全
  temp receipt 路径；不允许任意 argv/profile/model/add-dir。
- 运行前记录 clean baseline tree/diff identity；运行后从 git 直接测量 changed paths、
  binary patch、line/file budget 和 pre/post hash。
- 只有有效最终 model output 才写 `model_output_observed`；adapter exit 0 不充分。
- controller 把 adapter receipt、实际 delta、checks、AC claims 和 git objects 编译为
  ECOS CompletionManifest。manifest 不接受 `done`。
- 在合同、scope、budget 和 identity 全部通过后追加 `WorkflowSucceeded`，再调用通用
  coordinator 写 `EvidenceRecorded`。有效但最终被 verifier reject 的候选证据保留，
  用于审计；tamper、越权、缺回执或合同失败在 evidence 前拒绝。
- forward patch、preimage identity 和 receipt 以 git object/artifact ref 持久化，供回滚
  与最终 D0 tag 使用；不把 raw prompt、stdout/stderr、token、绝对路径写入回执。

### 4.4 verify/rollback

- verifier 在独立 subprocess 中用 packet 的 argv-list `verify_commands` 直接测量；
  `shell=False`，每条命令有 timeout、return code 和 stdout hash。
- executor family 固定为 `codex`；verifier family 使用 `deterministic-runner` 或另一个
  已 admitted verifier，不能相信 executor 自报。
- 全部 checks 为 0 且 receipt `accept` 时，唯一允许追加 `WorkflowVerified`。
- check 非零、receipt mismatch、out-of-scope 或 tamper 时不得出现 WorkflowVerified。
- verifier reject 后允许同一 succeeded run 进入 `CompensationStarted`；控制器只对自己
  保存且 preimage 匹配的 binary patch 做 reverse apply。成功后必须证明 tree/diff hash
  恢复到 baseline，依次写 `WorkflowRecovered -> WorkflowCancelled -> WorkflowClosed`。
- rollback 无法确认时保持 compensating/failed，并返回非零；禁止假关闭。

## 5. CompletionManifest 与 receipt 绑定

候选 identity 至少绑定：

```text
bet_id
spec_ref + spec_version + content_digest + decision_ref
packet_id + packet_hash
assignment_id
workflow_run_id + step_run_id + admission_id + dispatch_id
worker_id + exact adapter identity
controller approval ref
adapter receipt digest
changed paths + forward patch digest + baseline hash
acceptance claims + check receipts + artifact refs
```

任何字段缺失、跨 binding 重放、内容篡改或同 id 不同 payload 都 fail closed。

## 6. Orca 与多 Agent 使用规则

- Orca 只做任务分解、运输、观察、interrupt 和终端回收；最终状态回写 OMO。
- writer 使用独立 clone；verifier 使用独立只读进程/clone；共享 Workspace 仍只作集成点。
- worker start 后必须区分 shell/TUI readiness、first progress、model output 和 completion。
- Pi/OMP 当前 false-ready 证据列为 quarantine watch；本 BET 不自动改其 admission，后续
  只有真实 `worker_done` 回归通过才可恢复。
- 每个实现 slice 由 fresh subagent 执行，随后独立 spec/code reviewer；最终整支再做一次
  broad review 和真实 supervised dogfood。

## 7. 验收标准

1. candidate BET 能 deterministic compile；不存在 accepted binding、spec drift、假 ledger
   或 Task 无人工 gate 时均拒绝且零 Mesh 写入。
2. dispatch 必须在人工批准后才产生 request/admission/StepDispatched；结果只称
   `transport_accepted`。
3. 一次真实 supervised Codex R1 非 marker 变更产生有效 model output、实际 diff、adapter
   receipt 和 CompletionManifest；任何额外手点确认如实记录，不声称无人值守。
4. collect 严格绑定 BET/spec/packet/assignment/admission/dispatch/receipt/diff/claims；越权、
   篡改、缺 receipt 时无 EvidenceRecorded/WorkflowVerified。
5. 独立 verifier 重放声明命令；只有 accept 写 WorkflowVerified；executor 自验、同一
   receipt 篡改和 input ack 均拒绝。
6. verifier reject 保留候选 evidence，并通过 inverse patch 恢复 baseline tree hash；
   WorkflowVerified 不存在，run 最终 recovered/cancelled/closed。
7. compile、collect、verify 和 rollback 重放幂等；同 id 不同内容冲突 fail closed。
8. OMO/ECOS/root 定向回归、Ruff、diff check、agent-workflow verify、独立 code review 和
   PR checks 通过；子仓提交先进入子仓 main，根仓只 pin 可从 main 到达的 SHA。

## 8. Non-goals 与断路器

Non-goals：Cockpit UI、第二 live adapter、Kandev/Ruflo/Multica 生产接线、自动 merge、
账号/额度调度、真实邮件/日历/任务写入、多租户、跨主机、exactly-once、daemon/watchdog、
新的数据库或新的 WorkPacket schema。

出现以下任一条件立即停止并保留证据：需要 dangerous bypass；必须写共享 Workspace；
不能确认人工批准；不能回收子进程；无法从 git 直接测量 delta；Mesh append 被吞；回滚后
baseline hash 不一致；需要修改 Ledger DDL/ECOS M2；真实外部业务副作用；两到三天内无法
形成一条可验收纵切。

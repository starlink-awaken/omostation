---
schema: md/v1
status: draft
lifecycle: plan
owner: governance-team
last-reviewed: 2026-09-27
type: operations
created: 2026-09-27
scope: claims-authority-state-ratification
execution: forbidden-by-agent
---


# Claims Authority「现状追认」操作级授权包（DRAFT · 待 principal 签署）

> **本包是 DRAFT。** 所有 🧑/human 字段一律 `PENDING_PRINCIPAL`；`authorization_status = UNPROVEN`。
> principal（夏明星）本人签署之前，本包**不构成任何授权**，`execution_forbidden_without_human_authorization`
> 保持为真。本包**不激活、不回滚、不修复、不初始化、不写入**任何 authority store。
>
> **操作语义：`ratify-current-state`（现状追认）** —— principal 追认当前 `shadow-active` 运行现状，
> 并为「接下来发生什么」设定条件。**不是** promote、**不是** rollback、**不是** 一次新的 `activate-shadow`。
>
> 契约来源：`docs/operations/claims-activation-checklist.md` §1.2（六字段）、§1.3（not_sufficient）、
> 开篇代理边界（preflight / present / observe；ACTIVATION 与 ROLLBACK 属 principal）。

---

## 0. 追认对象 = 当前现状（draft 时点实测，非承诺）

本包绑定的是**机器可读的现状快照**。以下全部取自 draft 时刻的只读观测命令（完整命令与原始输出见 §7 附录）；
principal 签署前必须重跑同一组命令 —— 若 `sequence` / `last_receipt_digest` / `descriptor_digest`
任一发生漂移，本包即失效，须重新生成后再签署。

| 字段 | 绑定值（draft 时点 2026-09-27T03:20Z） |
|------|----------------------------------------|
| `authority_id` | `omo-claims-authority-r0` |
| `authority_epoch` | `1` |
| `activation_state` | `shadow-active` |
| `sequence` | `9` |
| `last_receipt_digest` | `sha256:c38cef48677b7c89815882e265733e1f57b601b2ca33f9a2ee7c5e2162595c97` |
| `descriptor_digest` | `sha256:e2be953eb9d04d421f184c60c7d1c4196d6698a874bcf0827795a8b4e8d357cd` |
| `observed_at` | `2026-09-26T08:43:35.989656+00:00`（= 序号 9 回执 `issued_at`，非取数时刻） |
| `security_level` | `R0_COOPERATIVE` |
| `effective_claim_authority` | `v1` |
| `instruction_capable` | `false` |
| `fresh` | `false` —— 语义：tip 回执 `issued_at` 距今不在 0–120s 内（`claims_authority.authority_status()`），即**近期无新变更**，不是缓存陈旧 |
| 激活回执（witness） | `sha256:96654eb9e03591b2b5da2cb89119997c9ec2c193755ae7c277b3a0ce7be1e5d3`，witness `sequence: 1` |
| high-water | `sequence: 9`，`receipt_digest` == tip `last_receipt_digest`（一致） |
| 观测采样进程 | `claims-observation/sampler.py`（draft 时 pid 53065；#4425 watchdog 上线时经 launchd 重启为 pid 75568，见 §5.2 / §7.5 复核），launchd `com.omostation.claims-observation-r0` 持续拉起 |

> **读法纪律（沿用 checklist §0/§2）**：上表是「签署时点的绑定快照」，不是新的事实读源。
> 任何时刻的权威读源仍是运行时投影：`claims-authority-status/v2`、`panorama-claims-activation-request/v1`、
> `claims-observation-progress/v1`。观测窗阈值数值一律以投影为准，不照抄本文件。

---

## 1. 授权包六字段（checklist §1.2 逐字，缺一即不算操作级授权）

`authorization_packet.required_fields`（`bin/panorama/panorama-collect.py` 渲染段与 checklist §1.2 逐字一致）：

| # | 字段（逐字） | 本包取值 | 判据 |
|---|--------------|----------|------|
| 1 | `principal_decision_id` | **`PENDING_PRINCIPAL`** | 🧑 principal 决定；agent 仅可建议（建议值 `CA-R0-20260927-RATIFY-01`，**这是建议不是事实，principal 可改**） |
| 2 | `decision_timestamp` | **`PENDING_PRINCIPAL`** | 🧑 只能由 principal 签署动作本身产生（UTC，YYYY-MM-DDThh:mm:ssZ） |
| 3 | `authorized_surface=agents/_shared/runtime/omo-claims-authority-r0` | `agents/_shared/runtime/omo-claims-authority-r0` | ✅ 机器可证：`/Users/xiamingxing/agents/_shared/runtime/omo-claims-authority-r0/` 存在且含 `store.sqlite3` / `high-water.json` / `activation-witness.json` |
| 4 | `rollback_surface=agents/_shared/backups/omo-claims-authority-r0` | `agents/_shared/backups/omo-claims-authority-r0` | ✅ 机器可证：该目录存在，且事件快照 `incident-20260926T1350Z/` 位于其下 |
| 5 | `expiry_or_no_expiry` | **`PENDING_PRINCIPAL`** | 🧑 必须**显式**二选一：`expires_at=<UTC 时间>` 或 `no_expiry`；沉默/省略 = 未授权 |
| 6 | `observation_requirement=24h foreground/1440 samples` | 字面量 `24h foreground/1440 samples`；**本追认操作是否沿用该条件 = `PENDING_PRINCIPAL`** | ✅ 字面量为 checklist §1.2 规定值；其运行时来源是激活包 `human_authorization.observation_after_activation`（draft 时读到 `duration_seconds=86400` / `minimum_samples=1440` / `maximum_gap_seconds=120`，**以 `claims-observation-progress/v1` 投影为准**）。principal 须显式确认本操作沿用/改写/免除该条件 |

外加签署位（六字段之外，缺了就无法证明「谁在什么时候签的」）：

| 字段 | 本包取值 | 判据 |
|------|----------|------|
| `signature`（principal 亲签） | **`PENDING_PRINCIPAL`** | 🧑 agent 不得代签（checklist §3：`human_authorization_required=True` 是硬门） |
| `approver_identity` | **`PENDING_PRINCIPAL`**（应为 `principal:xiamingxing` / 夏明星） | 🧑 身份由 principal 本人声明并可被 `docs/operations/human-attestation-allowed-signers` 交叉核对 |

**凡标 🧑 的字段，draft 阶段一律保持 `PENDING_PRINCIPAL`。本文件中不存在任何「已批准 / 已 PROVEN / 已签署」的既成事实。**

---

## 2. 授权状态转移规则：`UNPROVEN → PROVEN`（只能由 principal 触发）

1. **当前状态是 `UNPROVEN`，且代码无法翻转它。**
   `bin/gac/claims-shadow-preflight.py` 在「没有任何脚本能证明外部人类决定」的设计注释旁硬编码：
   `authorization_status = "UNPROVEN"`，并把 `operation_specific_host_authorization_unproven` 塞进 `blockers`。
   这是**故意的 fail-closed**：任何仓库改动、仪表盘状态、AI 陈述都不能把它变成 PROVEN。
2. **唯一转移路径**：principal 本人按 §1 逐字填写六字段 + `signature` + `approver_identity`
   → 生成 runtime 授权记录（建议落点 `~/.local/share/zhixing-dashboard/claims-observation/`，与既有
   `claims-activation-principal-authorization-*.json` 同目录；**该文件在 Git 之外、不含凭证**）
   → 回填本包 §8 签署区 → 此时才允许把本操作的 `authorization_status` 记为 `PROVEN`。
3. **作用域隔离**：即便转移发生，`PROVEN` 也**只**对
   `operation = ratify-current-state` + 本包 §0 绑定的 `authority_id` / `authority_epoch` / `sequence` /
   `last_receipt_digest` / `descriptor_digest` 组合生效。换一个操作、换一个 digest、换一个 epoch，
   都是**新的授权包**，不得复用本次签名（激活包字段 `required_binding` 里 "fresh authorization at
   execution time" 同理适用）。
4. **在转移发生前**：`execution=NOT_EXECUTED`、`activation=NOT_AUTHORIZED`、
   `execution_forbidden_without_human_authorization=true` 必须持续成立（checklist §3）。

---

## 3. 代理（Agent/proxy）边界 —— 只读三件事

沿用 checklist 开篇与 §3：

- ✅ **preflight**：跑只读 `python3 bin/gac/claims-shadow-preflight.py --json`（永不激活/修复/初始化/fetch/rebase/改 store）
- ✅ **present**：把本 DRAFT 授权包呈递到 Cockpit / principal 面前，逐字列明六字段待填项
- ✅ **observe**：只读观测 `claims-authority-status/v2`、`claims-observation-progress/v1` 进度
- ❌ **ACTIVATION**：属于 principal（Agent 不激活）
- ❌ **ROLLBACK**：属于 principal（Agent 不回滚、不自动执行回滚）
- ❌ 不改写 `samples.jsonl`、不补样、不拼接观测窗、不代办签名、不把 dashboard/口头陈述当授权

> 注：`activate_shadow()`（`projects/omo/src/omo/workflow/claims_authority.py`）本身**不检查**人类授权 ——
> 授权是流程/门禁层的关切，**本包就是那个门禁载体**。这正是「代码绿 ≠ 已授权」的原因。

---

## 4. 明确**不**授予什么（checklist §1.3 `not_sufficient`，逐条）

以下三项**不构成**授权（`authorization_packet.not_sufficient` 逐字）：

- ❌ `general_agent_authorization`（泛化的「agent 授权」）
- ❌ `accepted_spec_binding_alone`（仅有已接受 spec 绑定）
- ❌ `dashboard_status_or_ai_statement`（Cockpit 状态或任何 AI 的口头陈述）

并且，即使六字段全部由 principal 亲签，本包**也不授予**：

- ❌ **promote 到 active**（v2 promotion above shadow；shadow 只给 advisory `would_allow`/`would_deny`，v1 仍是唯一有效 claim authority）
- ❌ **rollback 授权**（回滚需要**独立的**操作级授权包；`rollback.automatic_execution` 保持 `false`）
- ❌ **跨操作覆盖（cross-operation coverage）**：本包只覆盖 `ratify-current-state` 这一个 operation 及其 §0 绑定的 digest/epoch/sequence；不覆盖 `activate-shadow`、不覆盖未来任何 mutation
- ❌ **解除 preflight 硬阻断**：`hard_blockers` 非空时窗口不得打开；授权不能豁免技术阻断
- ❌ **instruction capability / 提权**：`instruction_capable=false` 不因本包改变
- ❌ **观测窗合规豁免**：不缩短、不补样、不拼接；窗口无效（`INVALID`）时重启窗口的决定权仍在 principal

---

## 5. 背景事实（facts，不是授权）

> 以下只是「为什么需要这次追认」的上下文。记录事实**不等于**授予授权；本节任何一句都不能被引用为授权依据
> （见 §4 `not_sufficient`）。

### 5.1 2026-09-26 带外损坏事件（并发 agent 写入）

- **可证事实**（来自修复报告与事件快照，非转述）：
  - 事件快照目录：`/Users/xiamingxing/agents/_shared/backups/omo-claims-authority-r0/incident-20260926T1350Z/`
    （含 `store.sqlite3`、`store.sqlite3.bak{,2,3}`、`high-water.json`、`activation-witness.json`、
    `samples.jsonl`、`SHA256SUMS.txt` 等 11 项；`sha256sum -c SHA256SUMS.txt` 全 OK，见 §7）
  - 修复报告 1（最小修复）：`/Users/xiamingxing/.local/share/zhixing-dashboard/claims-repair-20260926.json`
    —— `scope: "seq9 receipt_json missing issued_at only"`，`outcome: "repaired"`，
    `authorized_by: "principal — '决策按照你的建议来' → 授权最小修复"`
  - 修复报告 2（整文件恢复）：`/Users/xiamingxing/.local/share/zhixing-dashboard/claims-repair-20260927T0117Z.json`
    —— `scope: "data-integrity restore of store.sqlite3 + high-water.json + activation-witness.json after
    concurrent-agent out-of-band sqlite writes (19:17/19:33/19:49 local 2026-09-26)"`，
    `outcome: "restored"`，`authorized_by: "principal — plan step 2 STOP trigger fired; user chose
    'Restore from .bak trio (Recommended)'"`，`finished_at: 2026-09-27T01:30:11.157789Z`
  - 损坏面：带外回执 seq 10–15（UUID `receipt_id`、无对应 `requests` 行）由整文件恢复剔除；
    恢复后 `after_receipts=9`、`after_meta_sequence=9`，与 §0 绑定值一致
  - 当前 high-water / witness / store 三件套与修复报告 `after` 状态自洽（§7 有命令与输出）
- **口径标注（不加工成既成结论）**：
  - 「broker 以 `IDENTITY_MISMATCH` 拒绝 → 走 raw sqlite 回退」这条**叙事**来自本次任务简报；
    draft 时刻在仓内/报告中未找到记录该因果链的单一工件 → 标注 `reported-unverified`。
    可证的只有：`IDENTITY_MISMATCH` 确为 `claims_authority.py` 中真实错误码
    （`AuthorityError("IDENTITY_MISMATCH", ...)`），且事件确为「并发 agent 带外 sqlite 写入」（修复报告 scope 原文）。
  - 「检测窗口 ~6h」同样来自简报 → `reported-unverified`。可测的时间线是：
    最早带外写入 `2026-09-26T11:17Z`（19:17 本地）→ 事件快照 `2026-09-26T13:50Z`（目录名 `incident-20260926T1350Z`）≈ **2.5h**；
    → 恢复完成 `2026-09-27T01:30Z` ≈ **14h**。以可测值为准，~6h 无工件支撑。

### 5.2 进行中的 watchdog / 监控工作

- **可证**：观测采样器 `claims-observation/sampler.py` 由 launchd `com.omostation.claims-observation-r0`
  持续拉起（draft 时 pid 53065 在跑）；宿主侧活性看门狗 `liveness-watchdog.sh` +
  `com.omostation.zhixing-dashboard-watchdog` 存在；`omlxc` watchdog KeepAlive 修复（#92）于 2026-09-27 经 #4416 合入 main。
- **可证（2026-09-27T06:45Z 复核，晚于本 draft 初稿采集时点 03:20Z）**：以 claims store 链校验为主题的
  watchdog **已交付并合并** —— PR #4425（squash 合并 `2026-09-27T06:41:40Z`）给采样器加了每 tick 只读链校验 →
  incident 快照 → 告警 → 两级自动修复（30min 冷却，仅可从新签名校验备份恢复）。部署实测：
  `~/.local/share/zhixing-dashboard/claims-observation/sampler.py` `sha256:15fb34f59eed047866a6700681b0795435de5b09bda3c0cd1484cbac602852c8`
  （回滚副本 `sampler.py.before-watchdog-20260927T043206Z`），launchd 已重启（pid 75568）；
  `summary.json["watchdog"]` 实测 `{"ok": true, "detected": false, "action": "monitor_healthy",
  "checked_at_utc": "2026-09-27T06:45:54.841350Z"}`，`alerts.jsonl` 至复核时点无告警记录。
  → 初稿「draft 时未找到以 claims watchdog 为主题的专门工件」仅对 03:20Z 时点成立，**本行取代该口径**；
  与 #4419 / #4420 一样，#4425 **未被本包触碰**（本包只读引用，不改其内容）。

### 5.3 历史授权（**属于别的操作**，不覆盖本包）

`~/.local/share/zhixing-dashboard/claims-activation-request.json` 里记录的 `human_authorization.status`
是 **2026-09-19/26 `activate-shadow` 操作**的决定（`principal_decision_id: CA-R0-20260926-01`，
`decision_timestamp: 2026-09-26T08:24:55.505Z`，`execution_receipt.sequence: 1`）。
该状态是**历史事实**，且**严格限定在 activate-shadow**；它**不**延伸到本包的 `ratify-current-state`。
本包自身的 `authorization_status` = `UNPROVEN`。

---

## 6. 本包放哪儿（路径决策记录）

契约里**没有**为「现状追认」类授权包定义 canonical 路径（checklist §0 只定义了
`panorama-claims-activation-request/v1` 与 `claims-authority-lifecycle-authorization-request/v1` 两个既有包的落点，
且都强调「请求包在 Git 之外」）。因此本 draft 采取**双落点**：

| 落点 | 路径 | 说明 |
|------|------|------|
| **runtime 草稿（机器可读，Git 之外）** | `/Users/xiamingxing/.local/share/zhixing-dashboard/claims-observation/claims-state-ratification-packet-draft-20260927.json` | 与既有 claims 授权记录同目录；**新文件名，不覆盖** `claims-activation-request.json`（那是 activate-shadow 的包，写它会毁掉既有请求），也不覆盖 `lifecycle-authorization-request-draft.json` |
| **review 副本（人在 Git 内审阅）** | `docs/operations/claims-authorization-ratification-draft.md`（本文件） | 供 principal 逐字审阅/签署；`status: draft` |

两份内容同源：runtime JSON 是本文件 §0/§1/§4/§5 的结构化镜像，本文件是 runtime JSON 的人读版。
签署以 **runtime 记录**为准，Git 内副本只做呈递与留痕（沿用「请求包在 Git 之外、不含凭证」的边界）。

---

## 7. 验证附录（draft 时实测：命令 + 原始输出，未删改）

采集时间：`2026-09-27T03:20Z` – `2026-09-27T03:32Z`（UTC）；执行环境：主工作区只读取数。

### 7.1 绑定值（两个权威只读观测口）

```console
$ env -u VIRTUAL_ENV python3 bin/agent-workflow.py claims-authority status --json
{"authority_id":"omo-claims-authority-r0","error":null,"ok":true,"result":{"activation_state":"shadow-active","authority_epoch":1,"authority_id":"omo-claims-authority-r0","descriptor_digest":"sha256:e2be953eb9d04d421f184c60c7d1c4196d6698a874bcf0827795a8b4e8d357cd","effective_claim_authority":"v1","fresh":false,"instruction_capable":false,"last_receipt_digest":"sha256:c38cef48677b7c89815882e265733e1f57b601b2ca33f9a2ee7c5e2162595c97","observed_at":"2026-09-26T08:43:35.989656+00:00","schema":"claims-authority-status/v2","security_level":"R0_COOPERATIVE","sequence":9},"schema":"claims-authority-response/v2","sequence":9}
```

```console
$ env -u VIRTUAL_ENV python3 bin/gac/claims-authority-status.py --json
{
  "authorization_granted": false,
  "available": true,
  "mutation_performed": false,
  "ok": true,
  "schema": "claims-authority-observation/v1",
  "status": {
    "activation_state": "shadow-active",
    "authority_epoch": 1,
    "authority_id": "omo-claims-authority-r0",
    "code": null,
    "descriptor_digest": "sha256:e2be953eb9d04d421f184c60c7d1c4196d6698a874bcf0827795a8b4e8d357cd",
    "effective_claim_authority": "v1",
    "fresh": false,
    "instruction_capable": false,
    "last_receipt_digest": "sha256:c38cef48677b7c89815882e265733e1f57b601b2ca33f9a2ee7c5e2162595c97",
    "observed_at": "2026-09-26T08:43:35.989656+00:00",
    "security_level": "R0_COOPERATIVE",
    "sequence": 9
  },
  "verdict": "READ_ONLY"
}
```

`authorization_granted: false` + `verdict: READ_ONLY` —— 观测口本身不授予任何东西。

### 7.2 preflight（只读；UNPROVEN 硬编码可见）

```console
$ env -u VIRTUAL_ENV python3 bin/gac/claims-shadow-preflight.py --json
{
  "activation_allowed": false,
  "advisories": [
    "root_head_not_equal_origin_main",
    "nonclosure_dirty_tracked_integration_root"
  ],
  "authority_id": "omo-claims-authority-r0",
  "available": true,
  "blockers": [
    "child_source_dirty",
    "child_head_gitlink_mismatch",
    "operation_specific_host_authorization_unproven"
  ],
  "checked_at": "2026-09-27T03:32:00.430434+00:00",
  "child_dirty_count": 4,
  "child_head_oid": "c91b203e15e68fe7ce087c3c5b688f9f3990cdf2",
  "closure": {
    "helper": "sha256:087ace73aa6104bae800026111fc2bf30b809ad6b049d36c982edb9d7b58694b",
    "ledger": "sha256:9d659ddd5976014f404938d22d9b8156c037b13e0bf63b58e1bca9a5139311d8",
    "operator_authorization_verifier_digest": "sha256:f7409fad16debb5065b34dceaa7880716aaa51ac03950bfef9b6df36cf5b8483",
    "policy": "sha256:0f9e6fc232ff6805759dd24469e1ff3cf49d74b58265a89d8396a4f84fc6a2da",
    "production_verifier_closure_digest": "sha256:09c9bb770b02547be4e5433962a81c924370983ac6ffd9cef695f8a354b37425",
    "spec": "sha256:83ebe7a5b35fad86807e289007d962b90ba28c260cd53dad85532ce4d8888bb0",
    "stopped_process_verifier_digest": "sha256:23fc6c4013a5c10a90debe23f774a0bf9d63560a697d425690e22db2b32bcde6"
  },
  "dirty_closure_paths": [],
  "dirty_nonclosure_count": 21,
  "dirty_tracked_count": 21,
  "hard_blockers": [
    "child_source_dirty",
    "child_head_gitlink_mismatch"
  ],
  "operation_specific_authorization": "UNPROVEN",
  "origin_main_oid": "fbd0ddc70abb1007cb3acc5b3d846b039be8a7bb",
  "readiness": "BLOCKED",
  "recovery": {
    "activation_authorized": false,
    "available": true,
    "canonical_workspace_mutation_recommended": false,
    "human_authorization_required": [
      "operation_specific_host_authorization_unproven"
    ],
    "isolated_workspace_recovery": [
      "child_source_dirty",
      "child_head_gitlink_mismatch"
    ],
    "items": {
      "child_head_gitlink_mismatch": {
        "action": "Verify the child origin/main successor in a fresh clone and require child HEAD to equal the root gitlink before rerunning preflight.",
        "canonical_mutation_required": false,
        "classification": "isolated_workspace_recovery"
      },
      "child_source_dirty": {
        "action": "Use a fresh managed clone and recursively check out pinned child commits; never clean or overwrite concurrent work in the canonical integration root.",
        "canonical_mutation_required": false,
        "classification": "isolated_workspace_recovery"
      },
      "operation_specific_host_authorization_unproven": {
        "action": "Require a fresh principal authorization packet bound to the exact R0 descriptor before activation; general approval is not sufficient.",
        "canonical_mutation_required": false,
        "classification": "human_authorization_required"
      }
    },
    "next_safe_action": "Run read-only preflight in a fresh managed exact-main clone; Claims Authority remains inactive.",
    "remaining_after_isolated_recovery": [
      "operation_specific_host_authorization_unproven"
    ],
    "schema": "claims-preflight-recovery/v1"
  },
  "root_child_gitlink_oid": "e9252141d9c737c2d99edd76fb6bd1e12650a3ea",
  "root_head_oid": "38abe703c8754f6c81184a619c8e0d0a5ef28b52",
  "runtime_state": {
    "activation_witness_exists": true,
    "high_water_exists": true,
    "highwater_exists": false,
    "store_exists": true
  },
  "schema": "claims-shadow-preflight/v1",
  "verifier_error": null
}
```

> 读法：
> - `recovery.items.operation_specific_host_authorization_unproven.action` 是 preflight 自己给出的处方 ——
>   *"Require a fresh principal authorization packet bound to the exact R0 descriptor before activation;
>   general approval is not sufficient."* —— **本包就是那个 "fresh principal authorization packet"**，
>   且它把 `general approval` 明确排除（与 §4 一致）。
> - `hard_blockers`（`child_source_dirty` / `child_head_gitlink_mismatch`）来自主工作区当前脏工作树与
>   `root_head_oid 38abe703c ≠ origin_main_oid fbd0ddc70`，属**技术阻断**，与本授权包正交；
>   按 checklist §1.1 须走「新鲜 managed clone 重跑只读 preflight」，**不得**在 canonical root 里 clean。
> - 即便本包签署完成，`hard_blockers` 未清空时窗口同样**不得**打开（§4）；
>   `readiness=BLOCKED` / `activation_authorized=false` 在签署后也只由技术阻断决定，不由本包解除。
> - `root_head_oid` 为主工作区本地 main 快照；本 draft 的 worktree 分支基于 `origin_main_oid=fbd0ddc70`。

### 7.3 witness / high-water（三件套自洽）

```console
$ cat /Users/xiamingxing/agents/_shared/runtime/omo-claims-authority-r0/activation-witness.json
{"activation_receipt_digest":"sha256:96654eb9e03591b2b5da2cb89119997c9ec2c193755ae7c277b3a0ce7be1e5d3","authority_id":"omo-claims-authority-r0","descriptor_digest":"sha256:e2be953eb9d04d421f184c60c7d1c4196d6698a874bcf0827795a8b4e8d357cd","digest":"sha256:09fef3c1c9c235531f10c7c0105ef3bd91533060a19aa99648f6f87f0e5ab800","request_digest":"sha256:7b03ef7b8c0f48166042dd536fe011554fc3a13b88beeeaef9a7c97f46427594","schema":"claims-activation-witness/v1","sequence":1,"state":"shadow-active"}

$ cat /Users/xiamingxing/agents/_shared/runtime/omo-claims-authority-r0/high-water.json
{"authority_id":"omo-claims-authority-r0","descriptor_digest":"sha256:e2be953eb9d04d421f184c60c7d1c4196d6698a874bcf0827795a8b4e8d357cd","digest":"sha256:4d2bc2fad785fbfe6ac8ed17a7537adc5b014cec61371491d6faf5bb5fa2cefc","receipt_digest":"sha256:c38cef48677b7c89815882e265733e1f57b601b2ca33f9a2ee7c5e2162595c97","schema":"claims-authority-high-water/v1","sequence":9}
```

witness `sequence: 1` ↔ 激活回执 `sha256:96654eb9…`；high-water `sequence: 9` ↔ tip `sha256:c38cef48…` ——
与 §0 表格、与 `claims-activation-request.json.execution_receipt` 三方一致。

### 7.4 事件证据与修复报告完整性

```console
$ shasum -a 256 /Users/xiamingxing/.local/share/zhixing-dashboard/claims-repair-20260926.json /Users/xiamingxing/.local/share/zhixing-dashboard/claims-repair-20260927T0117Z.json
5d95188c636c76e9a182410bf1228b867fbe20f7b0b9a39a453f93d61e1cd525  /Users/xiamingxing/.local/share/zhixing-dashboard/claims-repair-20260926.json
48cbad12c2485193316d8e058459c0a247cd08971f2d8ab462e8b86018402ce3  /Users/xiamingxing/.local/share/zhixing-dashboard/claims-repair-20260927T0117Z.json

$ (cd /Users/xiamingxing/agents/_shared/backups/omo-claims-authority-r0/incident-20260926T1350Z && sha256sum -c SHA256SUMS.txt)
/Users/xiamingxing/agents/_shared/backups/omo-claims-authority-r0/incident-20260926T1350Z/activation-witness.json: OK
/Users/xiamingxing/agents/_shared/backups/omo-claims-authority-r0/incident-20260926T1350Z/high-water.json: OK
/Users/xiamingxing/agents/_shared/backups/omo-claims-authority-r0/incident-20260926T1350Z/meta-dump.sql: OK
/Users/xiamingxing/agents/_shared/backups/omo-claims-authority-r0/incident-20260926T1350Z/receipts-dump.sql: OK
/Users/xiamingxing/agents/_shared/backups/omo-claims-authority-r0/incident-20260926T1350Z/samples.jsonl: OK
/Users/xiamingxing/agents/_shared/backups/omo-claims-authority-r0/incident-20260926T1350Z/store-dir-listing.txt: OK
/Users/xiamingxing/agents/_shared/backups/omo-claims-authority-r0/incident-20260926T1350Z/store.sqlite3: OK
/Users/xiamingxing/agents/_shared/backups/omo-claims-authority-r0/incident-20260926T1350Z/store.sqlite3.bak: OK
/Users/xiamingxing/agents/_shared/backups/omo-claims-authority-r0/incident-20260926T1350Z/store.sqlite3.bak2: OK
/Users/xiamingxing/agents/_shared/backups/omo-claims-authority-r0/incident-20260926T1350Z/store.sqlite3.bak3: OK
/Users/xiamingxing/agents/_shared/backups/omo-claims-authority-r0/incident-20260926T1350Z/summary.json: OK
```

（11/11 OK —— 事件证据快照自 2026-09-26 起未被改动。）

### 7.5 采样进程

```console
$ pgrep -fl "claims-observation/sampler.py"
53065 /opt/homebrew/Cellar/python@3.14/3.14.7/Frameworks/Python.framework/Versions/3.14/Resources/Python.app/Contents/MacOS/Python /Users/xiamingxing/.local/share/zhixing-dashboard/claims-observation/sampler.py
```

**复核（2026-09-27T06:45Z，PR #4425 watchdog 部署后；与初稿采集同为只读观测）**：

```console
$ pgrep -fl "claims-observation/sampler.py"
75568 /opt/homebrew/Cellar/python@3.14/3.14.7/Frameworks/Python.framework/Versions/3.14/Resources/Python.app/Contents/MacOS/Python /Users/xiamingxing/.local/share/zhixing-dashboard/claims-observation/sampler.py

$ launchctl list | grep claims-observation
75568	-15	com.omostation.claims-observation-r0

$ shasum -a 256 /Users/xiamingxing/.local/share/zhixing-dashboard/claims-observation/sampler.py
15fb34f59eed047866a6700681b0795435de5b09bda3c0cd1484cbac602852c8  /Users/xiamingxing/.local/share/zhixing-dashboard/claims-observation/sampler.py
```

（pid 53065 → 75568 仅因 #4425 上线时按 launchd 重启采样器；进程路径与 launchd 标签不变；
`-15` 为重启时的上一次退出码 SIGTERM，非故障。）

---

## 8. principal 签署区（**全部待填；agent 不代填**）

> 以下每一格在 draft 阶段都是 `PENDING_PRINCIPAL`。principal 填完并亲签后，才允许按 §2 走
> `UNPROVEN → PROVEN`；在此之前本区任何空缺都使本包无效。

| # | 字段 | 值（由 principal 填写） |
|---|------|--------------------------|
| 1 | `principal_decision_id` | `PENDING_PRINCIPAL` |
| 2 | `decision_timestamp`（UTC） | `PENDING_PRINCIPAL` |
| 3 | `authorized_surface` | `agents/_shared/runtime/omo-claims-authority-r0`（字面量固定，见 §1 第 3 行） |
| 4 | `rollback_surface` | `agents/_shared/backups/omo-claims-authority-r0`（字面量固定，见 §1 第 4 行） |
| 5 | `expiry_or_no_expiry`（**必须显式**） | `PENDING_PRINCIPAL` |
| 6 | `observation_requirement` | `PENDING_PRINCIPAL`（沿用 `24h foreground/1440 samples` / 改写 / 免除，三选一明示） |
| — | `signature`（亲签或 verbatim 决定原文 + 来源绑定） | `PENDING_PRINCIPAL` |
| — | `approver_identity` | `PENDING_PRINCIPAL` |

**签署后落点（principal 或经授权的记录者写，Git 之外）**：
`~/.local/share/zhixing-dashboard/claims-observation/claims-state-ratification-principal-authorization-<decision_id>.json`
（与 `claims-activation-principal-authorization-CA-R0-20260926-01.json` 同构：该类记录**签署之后**才允许写
`status: PROVEN`，并带 `binding` + `authorization_source` / `source_binding`；**本包当前仍是 `UNPROVEN`，
且这份同构描述不表示任何已存在的签署**）。

---

## 9. 相关

- 契约：`docs/operations/claims-activation-checklist.md`（§1.2 六字段 / §1.3 not_sufficient / 代理边界）
- 读取点：`bin/panorama/panorama-collect.py::collect_claims_activation_request`（唯一人类授权读点）、
  `authorization_packet` 渲染段、`collect_claims_lifecycle_authorization.required_fields`
- 门禁：`bin/gac/claims-shadow-preflight.py`（`authorization_status=UNPROVEN` 硬编码）
- 内核：`projects/omo/src/omo/workflow/claims_authority.py::activate_shadow`（不自查人类授权）、
  `authority_status()`（`fresh` 语义）
- 机器可读草稿（Git 之外）：`~/.local/share/zhixing-dashboard/claims-observation/claims-state-ratification-packet-draft-20260927.json`

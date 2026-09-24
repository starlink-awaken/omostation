---
type: operations
status: active
owner: governance-team
created: 2026-09-23
last-reviewed: 2026-09-23
scope: claims-authority-activation
execution: forbidden-by-agent
---

# Claims Authority 激活清单（只读）

> **本文档不激活任何东西。** Claims Authority 的激活保持 fail-closed，且**不能由 Agent 代办**：
> 只有 principal（夏明星）本人能开启"操作级授权窗口"并签署授权。Agent 的全部合法动作止于
> ①跑只读 preflight、②呈递待授权的 activation request、③监控只读 observation 进度。
> 激活/回滚的写动作属于 principal。

## 0. 权威对象从哪里来（勿凭记忆）

所有字段以运行时物化的投影为准，不要引用本文件的快照值：

| 事实 | 权威来源 |
|------|----------|
| 待授权的激活请求 | `panorama-claims-activation-request/v1`（`collect_claims_activation_request()`；请求包在 Git 之外、不含凭证，只投影身份与 fail-closed 状态） |
| 生命周期授权包 | `claims-authority-lifecycle-authorization-request/v1`（artifacts: draft / review / runbook / gap_audit，各带 sha256） |
| 观测窗进度 | `claims-observation-progress/v1`（`collect_claims_observation_progress()`） |
| Cockpit 可读面 | Panorama → Agent Brief；`runtime/dashboard/agent-brief.json` |

---

## 1. 开启"操作级授权窗口"的前置（principal 动作）

### 1.1 先跑只读 preflight（Agent 可跑，不改状态）

```
python3 bin/gac/claims-shadow-preflight.py --json
```

- 该命令**永不**激活、修复、初始化、fetch、rebase 或改动 authority store；只报告固定 canonical
  integration root 是否足够自洽，供 principal 判断能否进入"分离式 host 激活决定"。
- preflight 的 `hard_blockers` 非空时窗口**不得**打开；`advisories`（如 `root_head_not_equal_origin_main`）
  按 `claims-preflight-recovery/v1` 规则处理——多数走"新鲜 managed clone 重跑只读 preflight"，
  **禁止**在 canonical integration root 里 clean/覆盖并发工作。

### 1.2 授权包必须包含的字段（`authorization_packet.required_fields`）

principal 签署的授权必须逐字覆盖以下六项，缺一即不算操作级授权：

1. `principal_decision_id`
2. `decision_timestamp`
3. `authorized_surface=agents/_shared/runtime/omo-claims-authority-r0`
4. `rollback_surface=agents/_shared/backups/omo-claims-authority-r0`
5. `expiry_or_no_expiry`（是否过期，必须显式声明）
6. `observation_requirement=24h foreground/1440 samples`

### 1.3 以下**不构成**授权（`authorization_packet.not_sufficient`）

- ❌ `general_agent_authorization`（泛化的" agent 授权"）
- ❌ `accepted_spec_binding_alone`（仅有已接受 spec 绑定）
- ❌ `dashboard_status_or_ai_statement`（Cockpit 状态或任何 AI 的口头陈述）

> `execution_forbidden_without_human_authorization` 在 `human_authorization_status != PROVEN` 时为真；
> 只要不是 principal 本人的 PROVEN 签名，激活执行即为禁止。

---

## 2. 观测窗**测的是什么**

窗口一旦在 principal 授权下进入 `shadow-active`，`claims-observation-progress/v1` 投影开始度量。
**本节只讲语义，不复述数值**——阈值由授权包下发，权威定义在
`bin/panorama/panorama-collect.py::collect_claims_observation_progress`；实际生效值一律读投影字段，
不要照抄任何文档里的数字（含本文）。

| 投影字段 | 语义（不写死数值） |
|----------|--------------------|
| `duration_seconds` | 观测须覆盖的**前台连续**时长；不可补样、不可拼接窗口 |
| `minimum_samples` | 该时长内的样本下限 |
| `maximum_gap_seconds` | 相邻样本允许的最大空档；超过即判 `INVALID` |
| `sample_count` / `elapsed_seconds` | 当前进度读数 |
| `checkpoints[]` | 分档里程碑，各带 `duration_seconds`/`minimum_samples`/`diagnostic_only` |

### 2.1 checkpoint 分档

投影按 `id` 输出若干档：`smoke` → `provisional` → `sustained` → `graduation`。
**只有 `graduation` 参与放行判断**（`first_three_are_diagnostic_only = True`）：前三档用于观察健康度，
其阈值数值同样以投影为准。

### 2.2 毕业判据（`graduation_criteria`，须**全部**为真）

1. `summary_not_invalid` — summary 未被标记 invalid
2. `graduation_samples` — 样本数达 `minimum_samples`
3. `graduation_span` — 证据跨度达 `duration_seconds`
4. `maximum_gap` — 实测最大间隔不超 `maximum_gap_seconds`
5. `descriptor_constant` — descriptor_digest 全程恒等于期望值
6. `sequence_monotonic` — sequence 无回退
7. `activation_constant` — activation_state 全程恒为 `shadow-active`
8. `receipt_constant` — last_receipt_digest 全程恒定
9. `zero_errors` — 错误 + 畸形记录 = 0
10. `records_parse` — 样本记录全部可解析
11. `activation_receipt_matches` — 采样回执 == 请求执行回执

任一项为假 → `graduation_reasons` 列出未过项，窗口保持 `IN_PROGRESS`（协议不健康或回执不匹配则 `INVALID`）。

### 2.3 状态机

`IN_PROGRESS` →（全 criteria 通过）→ `GRADUATION_REACHED`；
协议失稳/回执漂移 → `INVALID`（须 principal 决定是否重启窗口，Agent 不自愈、不改写历史样本）。

---

## 3. Agent 在此流程中的边界（合规清单）

- ✅ 跑只读 `claims-shadow-preflight.py`、只读投影 observation 进度、把待授权 request 呈递到 Cockpit
- ✅ 保留 `execution=NOT_EXECUTED` / `activation=NOT_AUTHORIZED`，直到出现 principal 的 PROVEN 授权
- ❌ 不激活、不回滚、不改写 `samples.jsonl`、不补样或拼接窗口、不把"spec 已接受/仪表盘绿/AI 说可以"当授权
- ❌ 不代办 principal 的签名（`human_authorization_required=True` 是硬门）

## 4. 相关

- 已合入的前置修复：`CROSS_REPO_TOKEN` 在 submodule checkout 的传递已由 PR #4234（`ci(autobump): pass CROSS_REPO_TOKEN on submodule checkout`，MERGED）解决——autobump 子模块检出不再因此失败，与激活门无耦合。
- 设计/spec：`docs/superpowers/specs/2026-09-09-claims-authority-bridge-design.md`、`2026-09-10-claims-authority-bridge-wp1-shadow-design.md`。
- 代码：`bin/gac/claims-shadow-preflight.py`、`projects/omo/src/omo/workflow/claims_authority.py`、`bin/panorama/panorama-collect.py`。

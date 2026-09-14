---
id: ADR-0446
status: accepted
lifecycle: spec
owner: xiamingxing
last-reviewed: 2026-09-01
type: ssot
---

# ADR-0446: cockpit chain 声明式多命令链路 (spec v1)

- **Status**: ACCEPTED
- **Date**: 2026-09-01
- **Authors**: xiamingxing, worker-c-chain
- **实现**: `projects/cockpit/src/cockpit/chain/`、`config/chains/*.yaml`
- **关联**: ADR-0445 (薄委派/chain_enabled), journey-runner (语义借鉴)

## Context and Problem Statement

多命令联动此前只有硬编码管线（`iterate` 2-3 步写死、`demo` 4 步写死），
无通用编排能力；journey-runner 有完整状态机但面向 BOS 场景而非 CLI 命令。

## Decision

新建 `cockpit chain` 声明式链路引擎（YAML 定义、动态非写死）：

- **spec v1**: steps[{name, command, args, when, on_failure(abort|continue|
  retry{max,backoff}), capture_output_to, retry}] + params + timeout +
  on_chain_failure + hitl[{at, prompt, on_timeout}]
- **模板**: `{{params.*}} {{env.*}} {{steps.<n>.stdout|stderr|exit_code|
  json.<path>}} {{prev.output}}`（json.path 仅当该步 stdout 可 json.loads）
- **条件**: `==/!=/contains/and/or/not/数字比较/括号`（独立轻量实现，
  语义借鉴 journey-runner evaluate_condition，不 import）
- **执行模型**: subprocess 调 cockpit 自身（进程隔离、退出码干净、天然
  覆盖薄委派命令）；`--dry-run`（计划打印不落盘）/`--resume`（跳过
  succeeded）/`--non-interactive`（HITL 取默认）；状态落
  `data/chain-runs/<run_id>/state.json`
- **安全阀**: `chain validate` 校验步骤命令 ∈ COMMAND_CATALOG 且
  `chain_enabled=True`（high-risk 委派默认 False）
- **搜索路径**: cockpit 仓 config/chains → workspace config/chains →
  ~/.workspace/chains（个人链路）
- **4 条 demo**: governance-patrol（治理巡检）/ research-production（params
  变量传递）/ incident-triage（条件分支）/ agent-collab（HITL 暂停点）

## Consequences

- ✅ demo 即数据（YAML 非代码），用户可 `chain init` 自建链路
- ✅ executor 可注入（exec_cmd 参数），测试用 fake executor 不真调命令
- ⚠️ `steps.x.json.path` 引用要求该步有 JSON 输出 —— 倒逼命令 JSON 输出
  适配（联动 command-audit io_readability 维度驱动 JSON_CAPABLE 扩容）

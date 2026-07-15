---
status: active
lifecycle: standard
owner: governance-team
last-reviewed: 2026-07-03
related:
  - ../_knowledge/decisions/0130-p74-workflow-solidification.md
  - ../_knowledge/patterns/p74-workflow-solidification-pattern.md
  - ../_truth/registry/agent-workflows.yaml
  - ../_truth/registry/governance-checks.yaml
---

# P74 Solidification Contract — 操作契约

> P74 是常态化机制(per ADR-0130)。本文档告诉 governance-agent / engineering-agent / 人类
> 操作员:遇到 P74 报告时该做什么。

## 1. 入口

P74 健康度通过以下入口查询:

```bash
# JSON 报告 (含 p74_solidification 段)
uv run --with pyyaml python bin/agent-workflow.py compliance --json

# 人类可读
uv run --with pyyaml python bin/agent-workflow.py compliance

# Gate 层
make gac-local-gate
```

## 2. 报告结构

`compliance` JSON 输出新增 `p74_solidification` 段:

```json
{
  "p74_solidification": {
    "ok": false,
    "policy": {
      "warn_after_days": 30
    },
    "summary_count": 12,
    "warn_count": 1,
    "workflows": [
      {
        "workflow_id": "project-code-change",
        "has_recent_run": true,
        "last_start_ts": "2026-07-03T...",
        "has_check_coverage": true,
        "silent_health": "active"
      }
    ]
  }
}
```

| 字段 | 含义 |
|------|------|
| `ok` | warn_count == 0 → ok,否则不 ok |
| `summary_count` | 评估的 workflow 总数 |
| `warn_count` | 处于 silent_health=warn 的 workflow 数 |
| `workflows[].silent_health` | active / warn (excluded removed in ADR-0211 §D1) |
| `silent_health == warn` | 该 workflow 既无 recent run 也无 check 覆盖 |

## 3. Decision Tree(操作员视角)

### 3.1 silent_health == active

无需操作。workflow 健康。

### 3.2 silent_health == excluded (已废弃, ADR-0211 §D1)

字段 `silent_workflow_policy.excluded_workflows` 已在 ADR-0211 §D1 移除。
如需豁免某 workflow,改用 `agent-workflows.yaml::diff_checks` 加覆盖 (治本) 或
`agent-workflows.yaml::workflows.<id>.run_frequency: continuous` 让 1d 阈值易通过。
详见 ADR-0214 §D1 diff_checks 覆盖提议。

### 3.3 silent_health == warn — 处置流程

1. **判断是检查层沉默(A1)还是运行层沉默(A2)**:
   - `has_check_coverage == true` → A2(已被 gate 覆盖,只是没人 start)
   - `has_check_coverage == false` → A1(连 gate 都没触发)

2. **A1(检查层沉默) 处置**:
   - 在 `agent-workflows.yaml::diff_checks` 或 `doctor_checks` 加一条路径覆盖
   - **OR** 删除该 workflow 登记(如果已经废弃)
   - 注: `silent_workflow_policy.excluded_workflows` 字段已移除 (ADR-0211 §D1),不再支持加排除

3. **A2(运行层沉默) 处置**:
   - 如果 workflow 设计就是只在特定场景触发 → 通过 `agent-workflow suggest --from-diff` 引导
   - **不要**手动 start(应让真实需求触发)

### 3.4 state-projection-guard FAIL 处置

```bash
cd projects/omo && uv run python -m omo.cli lint projection-guard --json
```

`findings[]`:
- `kind: canonical_missing` → 文件不存在;检查 projection 是否应激活(state=active)
  - 如尚未生成 → 改 `state: pending`
  - 如已生成 → omo state sync 应自动派生,检查 broker 状态
- `kind: canonical_parse_error` → 文件存在但 YAML/JSON 损坏;修复文件
- `kind: legacy_size_drift` → 仅 warn;legacy 与 canonical 大小不一致(可接受)

### 3.5 runtime-stamp-policy FAIL 处置

```bash
cd projects/omo && uv run python -m omo.cli lint stamp-policy --json
```

`orphan_paths[]`:
- 如文件应被忽略 → 加进 `.gitignore`
- 如文件应被追踪 → 解释为何 tracked + 加进 ALLOW_PATHS(代码内)
- 如文件是 SSOT 派生 → 加进 `runtime-projections.yaml`
- 如文件应被删除 → 删除

### 3.6 suggest uncovered_files 处置

```bash
uv run --with pyyaml python bin/agent-workflow.py suggest --from-diff --profile governance-agent
```

`uncovered_files` 字段:
- 文件应该归属现有 workflow → 扩展该 workflow 的 `surfaces.write`
- 文件是新工具 → 创建新 workflow + diff_check
- 文件是临时测试 → 忽略

## 4. 主动触发

P74 报告通过 omo state sync 派生进 `.omo/state/runtime/health.yaml`(observability 阶段)。
当前阶段(PR #X)只手动触发:`uv run --with pyyaml python bin/agent-workflow.py compliance`。

## 5. 防复发机制

- 任何改动 `agent-workflows.yaml` 触发 `gac-local-gate` 中的相关 check
- 任何改动 `bin/agent-workflow.py` 触发 P74 报告路径上的检查
- 任何改动 `runtime-projections.yaml` 触发 `omo-state-projection-guard`
- 任何改动 `runtime/` 或 `.gitignore` 触发 `omo-runtime-stamp-policy`

## 6. 升级路径

| P74 状态 | 应做什么 |
|---------|---------|
| `warn_count == 0` | 继续 |
| `warn_count 1-2`(长期) | 评估是 A1 还是 A2,执行对应处置 |
| `warn_count ≥ 3` | 创建 follow-up task;考虑是否 ADR/P 升级 |
| `warn_count` 持续增长 | 可能 workflow registry 漂移,需要审查 |

## 7. 与 GaC 规则的对应

| P74 工具/输出 | 对应 GaC 规则 |
|--------------|--------------|
| `omo lint projection-guard` | CR-P74-STATE-PROJECTION-GUARD(X4 一致性) |
| `omo lint stamp-policy` | CR-P74-RUNTIME-STAMP-POLICY(X1 审计链) |
| `agent-workflow compliance` `p74_solidification` | CR-P74-WORKFLOW-SILENCE(X1 审计链) |
| `agent-workflow suggest` | CR-P74-WORKFLOW-SUGGEST(X3 价值栈) |

如果 GaC validate/drift 报 P74 相关错 → 查 governance-checks.yaml::gac.rules::CR-P74-*。
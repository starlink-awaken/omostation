---
schema: md/v1
status: PROPOSED
lifecycle: spec
owner: governance-team
last-reviewed: 2026-09-28
type: ssot
id: ADR-0459
related: ADR-A, ADR-0422, ADR-0457, ADR-0458
tags: [clone-lifecycle, claim-scope, provenance, multi-agent, wrapper-defect]
---

# ADR-0459 — clone-lifecycle 交付管道的两处阻塞:wrapper 丢参与多 agent 并发不兼容

- **Status**: PROPOSED（2026-09-28 提案；未实施。provenance 绑定项需 principal 决定是否放宽）
- **Date**: 2026-09-28
- **Related**: ADR-A（调度编译器）、ADR-0422（escape hatch / fingerprint）、BET-Y2Q4-T16-01、T16-02

## 背景

2026-09-28 尝试用 `bin/gac/clone-lifecycle.py` 把 6 个治理提交合入 main，
逐门推进共遇 16 道 fail-closed 校验。交付内容本身无问题（门禁全绿、
`changeset_ok` 且 `all_covered: true`），**阻塞全部在管道自身**。本 ADR 记录其中
两个可独立修复的根因。

## 问题一：`bin/agent-workflow.py` 丢弃 claim 的 `--actor`

### 事实

`projects/omo/src/omo/workflow/cli.py:83` 明确声明：

```python
p_claim.add_argument("--actor", default=os.environ.get("USER", "agent"))
```

`claim_run()` 的 claim 记录 actor 取自该参数（`lifecycle.py:1397`）。
但经 `bin/agent-workflow.py` 调用时，传入 `--actor mvs-f57d-gov` **不生效**，
claim 仍记录 `$USER`（`xiamingxing`）；`USER=mvs-f57d-gov` 环境变量同样无效。
**直接调用 `omo.workflow.cli.main()` 时 `--actor` 正常生效。**

### 影响

`bin/gac/agent-clone.py:3708` 校验 claim 归属：

```python
if claim.get("actor") != agent_id:
    continue
```

因此在**同一 OS 账号下运行的 agent，无法通过受支持入口创建绑定到自身 clone
agent_id 的 claim**，进而 `changeset --verify-claims` 必然报
`claim_scope_violation` / `changeset contains unclaimed paths`。

这是「受支持入口不通、绕到底层模块才通」的结构缺口，不是配置问题。

### 建议修法

`bin/agent-workflow.py` 的 `wrapped_main()` 应当把 `claim` 子命令连同
`--actor` 透传给 `_wf_cli`，而非自行分派；或在 `_install_patches()` 中
对齐 actor 解析。修后应有回归测试覆盖「经 bin 入口传 --actor 后 claim.actor
等于该值」。

## 问题二：管道与多 agent 并发不兼容

### 事实

管道每一环都把状态钉在**某个特定的 main revision** 上：

| 环节 | 绑定对象 | 失效表现 |
|---|---|---|
| `provenance` | clone 的 `frozen_root_sha` + `working_branch` + receipt digest | rebase 后 `clone_provenance_mismatch`；且 `provenance_late_binding` 拒绝在产生提交后重签 |
| `snapshot` | 当时的 root HEAD | main 前进后 `child_initialization_drift` / `root_rewind_or_diverged` |
| `changeset` | 生成时的 authority binding（policy revision） | main 前进后 `claims_authority_binding_mismatch` |
| `integrate` | 双重读校验 trusted main revision | main 前进后 `claims_authority_revision_unavailable` |

实测两小时内 main 从 `aedb8a75f` 推进到 `e258da3c1`（并发 agent 持续提交），
每次推进都作废一轮绑定。**`snapshot → changeset → integrate` 的完整周期长于
main 的推进间隔时，管道在结构上无法收敛。**

### 建议修法（择一或组合，需 principal 定）

1. **绑定漂移容忍**：对 `changeset`/`integrate` 的 authority binding 允许在
   显式 `--allow-drift <sha>` 下重生成，而非直接失败。
2. **静止窗口门控**：`integrate` 前置检查 main 在 N 分钟内无推进，否则
   fail-closed 并给出「等窗口」的可执行提示 —— 把竞态变成可诊断的等待而非
   逐门试错。
3. **明确适用范围**：在 `clone-lifecycle.py` 顶部文档声明该管道仅适用于
   单 agent 或已静止的主干；多 agent 并发场景走常规 PR 流程。

> 注：ADR-0422 的 escape-hatch 机制**不适用**于此。claim 漏绑与 provenance
> 失配都不是「门禁误伤」，走逃生口会在 `.omo/_delivery/swarm-escape/` 留下
> 不该有的记录，且丢失这项发现。正确处置是修管道本身。

## 影响面与不做的事

- **不改**：claim 的 actor 语义（仍以受支持入口为准）、provenance 的绑定强度
- **不做**：放宽 fail-closed 语义来「让管道通过」；本 ADR 的修法是修工具与
  明确适用范围，不是绕过校验
- **不改**：ADR-0457（launchd 漂移门）、ADR-0458（日志面分类 SSOT）

## 验收

1. 经 `bin/agent-workflow.py claim --actor <id>` 记录的 `claim.actor` 等于 `<id>`
2. 在 main 推进的场景下，`integrate` 给出的是可诊断的等待/重生成指引，
   而非逐门试错才能定位的 `clone_provenance_mismatch`
3. `provenance_late_binding` 在「合法工作导致 rebase」后有明确的恢复路径

---
status: ACCEPTED
lifecycle: decision
owner: 架构师
last-reviewed: 2026-07-18
related:
  - 0210-three-year-strategy-execution-convergence.md
  - 0220-swarm-coordination-discipline-m1-gate.md
  - 0222-m1-conflict-zero-evidence-standard-adversarial.md
  - 0202-fake-green-prevention.md
supersedes: []
---

# ADR-0223: 阶段门禁 CI 硬阻断 — phase gate 从 advisory 升为 enforcing

> **编号**: D1 `next-adr-id.py --session phase-gate-enforcement --claim` → **0223**。  
> **原则**: 能被无视的门禁不是门禁（门禁即免疫）。

## Context and Problem Statement

ADR-0210 规定 M1 不过不进 Phase 2。`m1-closeout-report` 曾诚实输出：

- `m1_verdict: window_open`
- `phase2_recommend: false`

但 **PR #421**（`bin/delivery/**` G-DEL.1/2b/3/5b）仍合并进 main——因为：

1. 阶段裁定只是**报告**，没有 CI / branch protection **硬阻断**；
2. 与仓库「门禁即免疫」原则冲突：写了建议却可静默绕过。

ADR-0222 补正了「冲突=0」证据标准（对抗路径），使 #421 可被**追认**；但若不加 CI 阻断，**同样的越闸会再次发生**。

## Decision Drivers

- **D1 · 报告 ≠ 门禁**：未接入 required check 的输出可被忽略。  
- **D2 · 自指盲区（ADR-0202）**：CI 检查尽量轻量、不依赖「同一次 PR 可能改坏的复杂工具链」。  
- **D3 · 可扩展到 M2/M4**：同一 registry 映射阶段路径与解锁键。  
- **D4 · 豁免可审计**：禁止静默 `--no-verify` 式绕过；escape 必须登记落盘。

## Considered Options

- **A · 继续 advisory closeout only**：零工程；越闸复发。  
- **B · CI hard gate + 提交态 verdict SSOT（选定）**：PR 改受管路径且阶段未解锁 → required check 红。  
- **C · 仅 pre-commit 本地拦**：可 `--no-verify` 跳过，不够。

## Decision Outcome

**选定 B。**

### 1. 阶段范围 registry

SSOT: `.omo/_truth/registry/phase-scope.yaml`

- `phase2` paths: `bin/delivery/**`、G-DEL 文档等  
- unlock: `phase-verdict.yaml` → `phases.phase2.unlocked == true`  
- `phase3` 预留（M2）

### 2. 解锁裁定 SSOT（可提交）

`.omo/_truth/registry/phase-verdict.yaml` 为 **CI 可读的提交态投影**（由 m1-closeout / 运维在证据齐全时更新，不得无证据改 true）。

当前 phase2：`unlocked: true`（ADR-0222 对抗路径 + closeout 重裁），并记录 #421 偏差。

### 3. CI job

`.github/workflows/phase-gate-enforce.yml` job name **`phase-gate`**：

1. checkout PR  
2. `python3 bin/gac/phase-gate-check.py --base origin/<base>`  
3. 若 diff 命中某 phase 的 paths 且 verdict 未解锁 → **exit 1**  
4. 若存在登记豁免（`.omo/_delivery/phase-escape/*.json` 匹配 PR / PHASE_ESCAPE_ID）→ 放行并在日志标明

检查器**仅**读 YAML/JSON + git diff（PyYAML），不调用 `m1-closeout-report` 本体（防自指）。

### 4. Required status check

`bin/gac/gac-branch-protection.sh` 将 `phase-gate` 加入 main 的 `required_status_checks.contexts`，否则仍可无绿合并 = 白做。

### 5. 豁免

写入 `.omo/_delivery/phase-escape/<id>.json`：

```json
{
  "id": "example-hotfix",
  "phase": "phase2",
  "pr_number": "123",
  "reason": "…",
  "active": true
}
```

PR 说明必须引用该 id；无登记则禁止。

### Confirmation（任务 4）

- 故意 PR 改 `bin/delivery/**` 且 `phases.phase2.unlocked=false` → CI **必须红**。  
- 登记 escape 后同路径 → 可绿且日志含 escape。  
- 证据落盘于 PR checks 日志 / delivery。

## Consequences

### Positive

- 阶段门从「报告」变为「不能静默合并」。  
- #421 类越闸有机制防复发。  

### Negative

- 需维护 phase-verdict 与证据同步。  
- required check 配置错误会导致全员卡 PR——用 `--check` 验证 protection。

## Out of Scope

- 回滚 #421  
- 替代 ADR-0220 四闸门 / worktree 纪律  
- 物理多机 M2 度量实现（仅预留 phase3 映射）

## References

- ADR-0210 / 0222 / 0202  
- PR #421 delivery 实现  
- closeout: `phase2_recommend: false` vs merge 事实  

---
status: ACCEPTED
lifecycle: decision
owner: 架构师
last-reviewed: 2026-07-18
related:
  - 0222-m1-conflict-zero-evidence-standard-adversarial.md
  - 0220-swarm-coordination-discipline-m1-gate.md
  - 0210-three-year-strategy-execution-convergence.md
supersedes: []
amends: [0222]
---

# ADR-0224: 被动窗 conflict_count>0 时对抗路径不得单独判 M1 达标

> **编号**: D1 claim session `m1-conflict-rootcause` → **0224**。  
> **修正**: ADR-0222「任一路径通过即达标」在 **被动窗已观测到冲突事件** 时的适用边界。

## Context and Problem Statement

ADR-0222 允许路径 B（对抗四闸全绿）在不满 72h 时将 `phase2_recommend=true`。  
2026-07-18 重裁出现：

| 字段 | 值 |
|------|-----|
| `m1_verdict` | pass（adversarial） |
| `phase2_recommend` | true |
| 被动 `conflict_count` | **2** |
| breakdown | `escape_hatch_abuse:1`, `branch_hijack:1` |

这与「对抗证明拦得住」叙事并存时，若**不溯源**直接 pass，会把「观测到的真实窗口事件」弱化为可忽略噪声——而观测冲突是**有问题（或至少需解释）的正面证据**，强度应高于实验室拦截 alone。

## Decision Drivers

- **D1 · 观测 > 实验室 alone**：真实窗内事件必须先分类，不能被 path B 静默覆盖。  
- **D2 · 区分拦截 vs 绕过**：`emit_conflict_event` 在闸门**拒绝**时也会写 jsonl——这是「拦得住」痕迹，不是「绕成功」。  
- **D3 · 覆盖缺口仍要单列**：裸 `git branch` / `git push --no-verify` 可不经 wrapper——属残余覆盖面，与本 2 事件语义不同。

## Considered Options

- **A · 维持 0222 原文**：path B 无视 conflict_count → 掩盖观测。  
- **B · count>0 时强制溯源再裁定（选定）**：path B 仅在 rootcause 证明「无未修复覆盖缺口」后可 pass。  
- **C · count>0 一律 fail**：过严；会把成功拦截探针永远记成失败。

## Decision Outcome

**选定 B。修正 ADR-0222 路径组合规则：**

### 1. 当被动窗 `conflict_count == 0`

- 路径 A 或路径 B 任一充分条件满足 → 可 `m1_verdict=pass`（0222 不变）。

### 2. 当被动窗 `conflict_count > 0`

- **禁止**仅凭对抗 JSON 直接 `phase2_recommend=true`。  
- 必须存在 **冲突溯源包**（默认 `.omo/_delivery/m1-closeout/conflict-rootcause-*.json` 或 closeout 参数指定），且对每条事件给出：

  | class | 含义 | 对 M1 影响 |
  |-------|------|------------|
  | `gate_interception` | 闸门拒绝时写入；attempt 被拦 | 不单独否决 path B |
  | `historical_pre_gate` | 闸门合入前 | 标注历史尾巴 |
  | `coverage_gap_bypass` | 证明绕过强制点成功 | **否决** pass，冻结扩张直至补闸 |
  | `unresolved` | 无法分类 | **否决** pass |

- 仅当全部事件 ∉ `{coverage_gap_bypass, unresolved}` 且 path B 四闸全绿（及 G-CONV.1–6 结构绿）→ 允许 `evidence_path=adversarial_with_rootcause`，`phase2_recommend=true`。

### 3. 本窗 2 起事件的裁定（2026-07-18 溯源）

见交付物 `.omo/_knowledge/audits/2026-07-18-m1-conflict-rootcause.json`（runtime 镜像：`.omo/_delivery/m1-closeout/conflict-rootcause-20260718.json`）：

| ts (UTC) | kind | vs #415 (2026-07-17T13:55:14Z) | class |
|----------|------|--------------------------------|-------|
| 2026-07-18T08:53:51Z | escape_hatch_abuse | **之后 +18.98h** | `gate_interception`（D4 拒 missing_escape_id） |
| 2026-07-18T08:53:52Z | branch_hijack | **之后 +18.98h** | `gate_interception`（D2 拒 skeptic-d2-b） |

- session 名 `skeptic-d2-*` / 无 session 的 escape 探针 → 对抗/skeptic 故意制造。  
- **非**裸 git 绕过成功的证据。  
- **残余覆盖缺口（未由本 2 事件证明被利用）**：D2 仅 `gac-worktree.sh` 包装；D4 agent 路径靠 `swarm-git`，裸 `git push --no-verify` 仍可跳 hook（git 设计）。记为 follow-up，**不**因此冻结 #421 已合脚手架。

### 4. closeout 行为

`m1-closeout-report` 在 `conflict_count>0` 时：

1. 加载 rootcause 文件；  
2. 若缺或含 unresolved/coverage_gap → `m1_verdict=fail` 或 `pass_blocked_rootcause`，`phase2_recommend=false`；  
3. 若全为 interception/historical + adversarial ok → pass with `evidence_path=adversarial_with_rootcause`。

## Consequences

- 实验室对抗不能盖住「窗里看见过什么」。  
- 成功拦截的 event 有合法归类，避免永远 conflict_count>0 假失败。  
- 真绕过必须修 hook 覆盖后才能再 pass。

## Confirmation

- 本 ADR 合入后 closeout 对 live 2 事件 + rootcause + adversarial → pass 且 evidence_path 标明 rootcause。  
- 故意不提供 rootcause 时 → 不得 phase2_recommend。

## References

- events.jsonl live 2 lines  
- PR #415/#416 gate land  
- ADR-0222 path B  

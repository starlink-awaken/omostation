---
status: ACCEPTED
lifecycle: decision
owner: 架构师
last-reviewed: 2026-07-18
related:
  - 0210-three-year-strategy-execution-convergence.md
  - 0220-swarm-coordination-discipline-m1-gate.md
  - 0221-g-del-5a-emergence-collective-decision-risk-review.md
  - 0224-m1-conflict-count-rootcause-before-adversarial-pass.md
supersedes: []
amended_by: [0224]
note: >
  ADR-0224 收紧：当被动窗 conflict_count>0 时，path B 不得单独 pass，
  必须 rootcause 证明无 coverage_gap_bypass / unresolved。
---

# ADR-0222: M1「冲突=0」证据标准扩展 — 对抗验证等效于 72h 被动窗

> **编号**: D1 原子申请 `next-adr-id.py --session m1-evidence-standard --claim` → **0222**。  
> **性质**: 补正 M1 判据，使 Phase 2 解锁有据可依；**不**回滚已合 PR#421。

## Context and Problem Statement

ADR-0210 规定 M1 三门禁，其中 daemon≥90% 与 health 执行面化已达标；唯「并发主仓冲突=0」原先依赖 **72h 被动观测窗**（ADR-0220 冲突事件计数）。

被动窗有结构缺陷：**swarm 空闲时 `conflict_count=0` 什么也证明不了**——无法证伪「闸门拦不住」。更严重的是执行与闸门脱节：

| 事实 | 证据 |
|------|------|
| closeout 裁定 `m1_verdict=window_open` / `phase2_recommend=false` | `.omo/_delivery/m1-closeout/m1-closeout-20260718T022713Z.json`（elapsed≈12.58h） |
| 兑现期实现 G-DEL.1/2b/3/5b 已合 main | PR **#421**（`a40d45a95`） |

这违反 ADR-0210「M1 不过不进 Phase 2」的精神——不是因为 #421 代码错误，而是因为 **判据只有路径 A（被动）**，实践中又用更强的对抗证据「实际推进了」却未写入裁定机。

## Decision Drivers

- **D1 · 可证伪优先于碰巧空闲**：主动制造冲突并验证拦截，证明「拦得住」。  
- **D2 · 合法补正，不回滚交付**：#421 作为度量脚手架保留；用 ADR + closeout CLI 追认补正。  
- **D3 · 与 ADR-0220 正交**：四闸门机制不变；变的是 M1「冲突=0」**证据入口**。  
- **D4 · 可机读**：`m1-closeout-report` 必须能输出 `evidence_path: adversarial|passive`。

## Considered Options

- **A · 只认 72h 被动窗（现状）**：继续等窗；#421 永远处于「越闸」叙事。  
- **B · 对抗验证等效于被动窗（选定）**：路径 A 或路径 B 任一通过即 M1「冲突=0」达标。  
- **C · 回滚 #421**：代价高、否定已测度量脚手架；与「不回滚」要求冲突。

## Decision Outcome

**选定 B。** M1「并发主仓冲突=0」承认两条**等效**证据路径：

### 路径 A · 被动（既有）

- 72h 观测窗内真实冲突事件 `conflict_count = 0`  
- `elapsed_hours ≥ window_hours`  
- 由 `swarm-discipline-cli.py window-status` / `m1-closeout-report` 读取

### 路径 B · 主动（新增 · 对抗验证）

ADR-0220 四闸门对抗测试**全部拦截成功**，且证据落盘（默认 `.omo/_delivery/m1-adversarial/latest.json` 或 closeout 指定路径）：

| 闸门 | 故意冲突 | 通过条件 |
|------|----------|----------|
| D1 | 两 session 抢同一 ADR 号 | 仅一方 `ok`；另一方 claim/写检查失败 |
| D2 | 复用已占用 `work/<slug>` | 第二 session `branch-claim`/`branch-check` 拒绝 |
| D3 | 无 claim 向共享 `main` 提交 | `claim-check --staged` 与/或 pre-commit 拒绝 |
| D4 | 未登记 `--no-verify` / `CI_LOCAL_SKIP` | `escape-check` / `swarm-git` 拒绝；登记豁免可记 `swarm-escape/` |

**强度声明**：路径 B 证明「拦得住」，强度**不低于**路径 A 的「碰巧没撞」。

### 裁定机

- `m1-closeout-report` 支持读取路径 B 证据。  
- 当路径 B 四闸全绿 **且** G-CONV.1–6 hard greens 通过时（**不要求**满 72h）：  
  - `m1_verdict`: `pass`  
  - `evidence_path`: `adversarial`  
  - `phase2_recommend`: `true`  
- 路径 B 说明：闸门成功拦截会向 `events.jsonl` 写入 `adr_renumber_race` / `branch_hijack` / `escape_hatch_abuse` 等——这是「拦得住」的痕迹，**不得**据此否决路径 B。  
- 路径 A 满窗且 count=0 时：`evidence_path: passive`（行为不变）。  
- 两路径都失败：不得 `phase2_recommend=true`。

### Confirmation · #421 越闸追认

| 项 | 记录 |
|----|------|
| **偏差** | #421 在 closeout 仍 `window_open` / `phase2_recommend=false` 时合并 |
| **补正** | 本 ADR 生效后，以路径 B 对抗证据重裁；若四闸全绿则 **追认** Phase 2 解锁合法 |
| **不回滚** | #421 代码保留；后续 G-DEL 扩张以重裁后的 `phase2_recommend` 为准 |

## Consequences

### Positive

- M1 可在数小时内合法收口，不必空转 72h。  
- 判据与「已做对抗、已进实现」的实践对齐。  
- closeout 可审计：`evidence_path` 标明依据。

### Negative / Follow-ups

- 必须真做对抗并留证据（禁止口头宣称）。  
- 裸 `git --no-verify` 仍可跳过 hook（git 设计）；D4 以 agent 路径 `swarm-git` 为准（ADR-0220 边界不变）。

## Out of Scope

- 修改 G-CONV.1–6 达标定义  
- 回滚 #421 或删除 delivery 度量脚手架  
- 将对抗测试本身做成多机物理集群要求

## References

- ADR-0210 不过不进  
- ADR-0220 四闸门  
- closeout 样例：`.omo/_delivery/m1-closeout/m1-closeout-20260718T022713Z.json`  
- PR #421 G-DEL delivery  

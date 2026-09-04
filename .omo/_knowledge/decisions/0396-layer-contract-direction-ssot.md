---
id: ADR-0396
title: 分层契约方向单源 — layer-contract.yaml 为权威, check-layer-call-direction.py 对齐
status: proposed
type: decision
owner: architecture-governance
date: 2026-08-07
lifecycle: spec
last_updated: 2026-08-07
related:
  - 0156-p76-phase2-call-direction.md
  - 0217-workflow-hygiene-layer-check-and-evidence.md
---

# ADR-0396: 分层契约方向单源 — layer-contract.yaml 为权威

## Status

Proposed（待架构治理评审后 ACCEPTED）。

## Context

分层依赖方向存在**两套互不一致的 SSOT**：

| 来源 | 关键声明 | 引用 ADR |
|------|---------|---------|
| `docs/layer-contract.yaml`（`dependency_rules.allowed_directions`） | L3→允许 **L0**；L0→允许 **M0**；L2→允许 L1/L0/**X**/L4；I0→可调用所有层；含 `exceptions` 登记机制 | ADR-0217（"契约方向对齐实装"） |
| `bin/ssot/check-layer-call-direction.py`（`ALLOWED_DIRECTION`） | **L3 = {I0,L1,L2,M0,L4}（不含 L0）**；**L0 = set()（空）**；**L2 = {L0,I0,L2}（不含 X/L1/L4）**；I0 = {L0,M0} | ADR-0156 |

同一事实（某层可调用哪些层）在两个文件各写一套，且互相矛盾：

- **L3→L0**：layer-contract 允许，check 工具判定违规。
- **L0→M0**：layer-contract 允许（ADR-0217 D2 明确 "L0→M0"），check 工具 L0=set() 判违规。
- **L2→X(bus)**：layer-contract 允许（ADR-0217 D2 "L2→X"），check 工具 L2={L0,I0,L2} 判违规。

这违反 `doc-ssot-contract`（同一事实单一来源），并导致同一份 import 关系在不同工具下判定不同。

## 历史依据（裁决基础）

- **ADR-0156**（2026-07-07, ACCEPTED）建立 `check-layer-call-direction.py`，其 ALLOWED_DIRECTION 反映当时的严格方向。
- **ADR-0217**（2026-07-15, ACCEPTED）"契约对齐实装" 明确 **D2：L3→M0/L4；L2→X；L1→X；L0→M0；同层合法**，并收紧 forbidden。该决策晚于 ADR-0156，代表更新、权威的方向意图。
- **`docs/layer-contract.yaml`** 注释自引 ADR-0217，且含 `exceptions` 登记（ecos→omo/metaos、omo→c2g、runtime→omo 等已登记债），是一份**可持续维护的分层契约 SSOT**。
- `check-layer-call-direction.py` 自 ADR-0217 后**未同步对齐**其 ALLOWED_DIRECTION，是历史分叉的遗留。

## Decision

### D1 — 权威单一来源

**`docs/layer-contract.yaml` 的 `dependency_rules.allowed_directions` 是分层方向的唯一权威 SSOT。**
`bin/ssot/check-layer-call-direction.py` 是实现工具，其 `ALLOWED_DIRECTION` **必须对齐** layer-contract.yaml，不得自行维护第二套方向。

### D2 — 权威方向表（以 layer-contract.yaml 为准）

| caller | allowed callee |
|--------|----------------|
| L3 | L2, L1, **L0**, I0, X, M0, L4 |
| L2 | L1, L0, **X**, L4 |
| L1 | L0, X |
| L0 | **M0** |
| I0 | L0, L1, L2, L3, L4, M0, X |
| M0 | L0, L1 |
| X | L0, L1, L2, L3, L4, I0, M0 |
| L4 | L2, L1, L0, I0, X, M0 |

同层 `from==to` 合法（ADR-0217 D2）。

### D3 — 执行工具对齐（后续代码落地）

- `check-layer-call-direction.py` 的 `ALLOWED_DIRECTION` 改为从 / 对齐 layer-contract.yaml 方向表。
- 保持 `--baseline` 存量 grace 机制（P0-A）：对齐后**重新生成 baseline**，仅放行存量真实违规，严禁塞新违规。
- 跨层桥接仍走 `layer-contract.yaml.exceptions` 登记（ADR-0217 D3 延续）。

### D4 — 契约演进

- 新增层/改方向：只改 `docs/layer-contract.yaml`（+ ADR 记录），**不直接改 check 工具**。
- check 工具只做"读契约 + 执行"。

## Consequences

- 分层方向单一来源，消除 layer-contract 与 check 工具的矛盾（doc-ssot 合规）。
- check-layer-call-direction.py 对齐后，L3→L0、L0→M0、L2→X 等将被判合法（与实装一致），假阳性减少。
- 需重新生成 baseline 以保留存量真实违规 grace（P0-A 红线：不塞新违规）。
- 对齐是代码改动，独立 PR 落地；本 ADR 先定方向。

## 后续动作

- [ ] 架构治理评审并 ACCEPTED
- [ ] 落地 `check-layer-call-direction.py` ALLOWED_DIRECTION 对齐 + baseline 重生成（独立 PR）
- [ ] 验证 `make check-layers` / `check-layer-call-direction.py --baseline` 在 main 上干净

---
id: ADR-0393
title: god-module 大文件治理计划 — 3 个 >1500L 债的拆分路径
status: ACCEPTED
lifecycle: spec
owner: governance-team
last_updated: 2026-08-08
---

# ADR-0393 Decision: god-module 大文件治理计划

> 承接 ADR-0392 (CI 修复 drafts persistence_mode). 本 ADR 治剩下的 1 类红:
> god-module 3 个 >1500L 硬规则违反. 因属子模块仓代码, 主仓不跨界 — 登记台账
> 让人认领, 暂时接受 interface-check 阻断.

## 一、现状 (2026-08-08 实测)

| 文件 | LOC | 子模块 | 阻断来源 |
|------|-----|--------|---------|
| `projects/agora/src/agora/external_connections.py` | 1663 | agora | interface-check (origin/main run 31226197940) |
| `projects/cockpit/src/cockpit/web/api_system_map_catalog.py` | 1565 | cockpit | 同上 |
| `projects/cockpit/src/cockpit/cli.py` | 1533 | cockpit | 同上 (worktree 检出, CI 未报) |
| **合计** | **4761L** | 3 子模块 | origin/main interface-check 连续 fail |

> 注: CI 仅报 2 个 (worktree 的 cli.py 已被并发改过但未 git add, 仍是大文件,
> CI 在自己 clone 的 fresh worktree 上看到 2 个 ≥1500L).

## 二、为什么不在主仓拆

按 git-discipline §6.1 + 子模块边界:

1. **submodule 不可改**: 3 个文件均在子模块仓 (agora/cockpit), 主仓 worktree
   看到的只是 mirror 引用, 改动需在子模块仓内 commit + push + 主仓 bump pointer
2. **跨子模块拆 = 跨主仓干预**: 主仓 agent 不应修改子模块内部代码 (易破坏
   子模块独立性 + 触发子模块的 CI)
3. **bet ledger 治理**: 拆分是 1 周级技术债清理, 应作为 bet 登记让对应 track
   负责人认领, 而非由本轮治 CI 的 PR 顺手做

## 三、拆分可行性 (已分析)

### agora/external_connections.py (1663L)

- **结构**: 11 个 class + 15 helper functions
  - `SceneBinding` (L143), `SceneCard` (L180), `SceneCardDecision` (L285)
  - `ExternalResourceDescriptor` (L311), `AdmissionDecision` (L403), `RouteDecision` (L421)
  - `ResourceCandidateDecision` (L441), `ResourceEvaluation` (L467), `ConnectionReceipt` (L508)
  - `DiscoveryRecord` (L570)
  - 2 大型 builder/projection 函数 (`build_external_resource_catalog_snapshot`, `_health_projection`)
- **拆分目标**: `descriptors.py` / `decisions.py` / `catalog.py` (各 ~500-600L)
- **风险**: 中 — 跨 class 引用 (descriptor → decision → catalog),
  需谨慎处理 import 顺序, 跑通 agora tests 验证

### cockpit/api_system_map_catalog.py (1565L)

- **结构**: 1 个 1565L tuple (`COCKPIT_PAGES`) — 纯数据, 无逻辑依赖
- **拆分目标**: 按 page group 拆
  - `pages.py` (入口 + 领域应用, ~600L)
  - `playbooks.py` (工作带, ~400L)
  - `coverage_dims.py` (覆盖维度 + port aliases, ~565L)
- **风险**: 低 — 纯数据, 拆分后只需 import 即可, cockpit tests 应直接 pass

### cockpit/cli.py (1533L)

- **结构**: cli commands 集合, 按 command group 划分
- **拆分目标**: `cli/runtime.py` / `cli/governance.py` / `cli/system.py` (各 ~500L)
- **风险**: 中 — CLI 命令间有共享 argparse + 状态, 需提取 `base.py` 公共部分

## 四、路径

1. **本 ADR 登记** (主仓, 本轮): 治本路线 + 拆分目标 + bet T6-10 关联
2. **bet T6-10** (认领执行): 1 周, P2, 候选态 — 子模块仓流程
   - 子模块 worktree from 子模块 main
   - 每个子模块独立 PR
   - 主仓 bump pointer 跟 (0 effort)
3. **完成后**: interface-check 回归全绿, origin/main CI 解锁 phase-gate
   之外的另一个非 required 红点 (实际不影响 PR merge 能力)

## 五、为什么不用治标 (allowlist / 阈值调整)

- **allowlist 临时豁免**: 与 ADR-0389 减法方向矛盾 (增加而不是减少机制)
- **L0 阈值调整 (1500L→2000L)**: ADR-0155 修订史已 1 次, 再次修订是
  治标不治本, 等同承认债不还
- **god-module 跳过指定子模块**: 同上, 与减法矛盾

主仓的最佳动作是 **承认债 + 治本路径登记**, 而不是减法收紧。

## 六、与其他 ADR 关系

- ADR-0155: 历史 L0 阈值 800→1500 修订, 1 次减法收紧
- ADR-0389: 减法治理方向, 主张"精剪弱机制" (T6-01 bet)
- ADR-0392: drafts persistence_mode 修复, 不影响 god-module
- ADR-0393 (本): god-module 治本路径登记, bet T6-10 启动

## 七、当前 main CI 真实状态

- ✅ **drafts persistence_mode** (ADR-0392 已修)
- ❌ **god-module 3 files** (本 ADR 治本路径)
- ❌ **current-state-coherence** (pre-existing, 与 T3-02 状态漂移有关)
- ✅ **phase-gate** (branch protection 唯一 required)

main **可继续接受 PR** (phase-gate pass), 但 interface-check 仍 fail。
对治理减法本身无影响 — bet T6-10 认领并拆分后, main interface-check 回归全绿。
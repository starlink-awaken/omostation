# Governance Maturity ISA — 治理体系成熟度 (master)

> **Tier**: E4 (12-section) · **创建**: 2026-06-30 · **类型**: master ISA
> **关联**: [AGENT-ISOLATION-ROLLOUT](AGENT-ISOLATION-ROLLOUT.md) (Phase 2 worktree/PR) · [GOVERNANCE-EVOLUTION-ROADMAP](GOVERNANCE-EVOLUTION-ROADMAP.md)
> **状态**: 📋 OBSERVE/PLAN 完成, EXECUTE 进行中 (F1 启动)

---

## 1. Problem

治理工具能跑(GaC/OMO/MOF/cockpit CLI), 但**未到闭环**:

1. **工作区 lane 红**: staged lane code+other 混(.c2g_data / _archived 删除项), release package 不可识别
2. **cockpit 不可视**: 治理靠读 JSON, 非 governance evolution 一屏看全(status/packages/traces/golden paths/release readiness)
3. **claim 弱**: claim policy advisory 为主, 核心治理路径不强制
4. **无 E2E golden path**: C2G idea → OMO task → MOF/BOS → cockpit → evidence → release package 未跑穿
5. **子项目边界散**: projects/* 独立 repo/submodule 缺统一 gate/owner/release artifact/pointer closeout, root 治理被子项目状态拖累

**根因**: 治理体系停在"工具能跑", 未到"闭环可视 + 强制 + 端到端验证"。

## 2. Vision

agent/人从 **cockpit 一屏**看到治理全貌(status / packages / traces / golden paths / release readiness); 变更走**干净 lane + required claim + 端到端验证**; 子项目各自独立 gate。治理从"读 JSON 猜状态"到"看仪表盘 + 跑通链路"。

## 3. Out of Scope

- **不重写** GaC/OMO/MOF 内核(复用现有 5+4+1)
- **不引入新治理框架**(深化现有, 非另起)
- **不做 multi-tenant**(单 workspace)
- **不替换 cockpit CLI**(CLI 保留, UI 是叠加可视化层)

## 4. Principles

- **可视化优先于强制**: 先让治理可看见(cockpit), 再 required claim。看不见就强制 = 盲执法。
- **复用现有基础设施**: cockpit / GaC / OMO / agent-workflow 已有, 深化非重造(同 [architecture-overengineering-lesson] 教训)。
- **E2E 验证驱动成熟度**: golden path 跑通 = 真成熟, 非 checklist 打勾。
- **子项目自治 + root 协调**: 子项目独立 gate, root 管 pointer + 聚合视图。

## 5. Constraints

- 5+4+1 架构不变(L0-L4 + I0 + X1-X4)
- 17 子模块独立 repo, pointer 治理(见 [SUBMODULE-PR-STRATEGY](SUBMODULE-PR-STRATEGY.md))
- `.omo/` 治理面, 不绕过 broker
- GaC gate 是共享硬门(pre-commit/CI 同脚本)
- post-commit L0 萃取 commit 级触发(Phase 2 OBSERVE), 不可断

## 6. Goal

**5 件 work stream 落地**: cockpit 可视化治理全貌 + 核心路径 claim required + C2G→release golden path E2E 跑通 + 子项目独立 gate + 工作区 lane 干净。治理体系从"工具能跑"到"闭环可视 + 强制 + E2E 验证"。

## 7. Criteria (ISC)

| ISC | 描述 | feature |
|:---|:---|:---|
| **GM-1** | staged lane 干净: code/other 分离, `.c2g_data`/`_archived` 等不混入 code lane | F1 |
| **GM-2** | release package 可识别: `bin/release-package-review` 输出可提交/可发布包分类 | F1 |
| **GM-3** | cockpit governance evolution 页可视化: status + packages + traces + golden paths + release readiness 五维 | F2 |
| **GM-4** | 核心治理路径 claim required(非 advisory): governance_state / submodule_pointer lane | F3 |
| **GM-5** | C2G idea → OMO task → MOF/BOS → cockpit → evidence → release package 全链路跑通(≥1 真实场景) | F4 |
| **GM-6** | 每个 projects/* 有 gate + owner + release artifact + pointer closeout 规则(注册表) | F5 |
| **Anti-GM-1** | `.c2g_data`/`_archived` 删除项不出现在 code lane staged | F1 |
| **Anti-GM-2** | claim required 不阻塞合法 docs/governance 流(避免死结) | F3 |

## 8. Test Strategy

| ISC | type | check | threshold | tool |
|:---|:---|:---|:---|:---|
| GM-1 | static | lane 分类 | 0 混入 | `bin/change-lane-check --staged` |
| GM-2 | unit | release package 输出 | 全 staged 分类 | `bin/release-package-review`(待建) |
| GM-3 | build | cockpit governance UI | build PASS | `cockpit-ui build` |
| GM-4 | enforce | claim required | 违规拒 | `agent-workflow compliance` |
| GM-5 | E2E | golden path | ≥1 场景跑通 | `tests/integration/golden-path` |
| GM-6 | registry | 子项目规则 | 17 子项目全覆盖 | submodule gate 注册表 |

## 9. Features

| feature | 描述 | satisfies | depends_on | parallelizable |
|:---|:---|:---|:---|:---|
| **F1 发布/工作区收敛** | release package review 工具 + lane 分类清理(.c2g_data/_archived) | GM-1,2,Anti-1 | — | ✅ |
| **F2 cockpit 治理面产品化** | governance evolution UI(五维可视化) | GM-3 | — | ✅ |
| **F3 claim policy 升级** | advisory → required(核心治理路径) | GM-4,Anti-2 | F1,F2 | ❌ |
| **F4 golden path E2E** | C2G→release 端到端链路 | GM-5 | F1,F2,F3,F5 | ❌ |
| **F5 子项目发布边界** | projects/* gate/owner/release/pointer 注册表 | GM-6 | — | ✅ |

### 依赖图

```
基础层 (并行):  F1 发布收敛   F5 子项目边界
                    \           /
执行层:              F2 cockpit 产品化
                        |
                     F3 claim 升级 (依赖 F1 lane 干净 + F2 可视监督)
                        |
验证层:              F4 golden path E2E (依赖全部)
```

## 10. Decisions

- **2026-06-30**: 5 件大事源自用户蓝图。依赖排序: 基础(F1+F5 并行) → 执行(F2 → F3) → 验证(F4)。F3/F4 强依赖基础稳, 不抢跑。
- **2026-06-30**: F1(发布收敛)与 Phase 2 worktree 完整性问题([ISC-3e](AGENT-ISOLATION-ROLLOUT.md))同源 — 工作区不干净/lane 混。F1 先行, 顺带治 worktree 卫生。
- **2026-06-30**: claim 升级(F3)在 F1 lane 干净 + F2 可视化后, 否则 required claim 拦死(advisory→required 前置不满足 = commit 死结重演)。

## 11. Changelog

(EXECUTE 阶段补 Deutsch error-correction 条目: conjectured / refuted by / learned / criterion now)

## 12. Verification

(EXECUTE 阶段补: 每 ISC 的 quoted command output / 文件内容 / 截图路径)

---

## 推进计划

| 顺序 | feature | 预估 | 前置 |
|:---|:---|:---|:---|
| **第 1 步** | F1 发布/工作区收敛 | 中 | 无 (与 Phase 2 ISC-3e 同源) |
| 并行 | F5 子项目边界 | 中 | 无 |
| 第 2 步 | F2 cockpit 产品化 | 大 | F1 lane 干净 |
| 第 3 步 | F3 claim 升级 | 中 | F1+F2 |
| 第 4 步 | F4 golden path E2E | 大 | F1+F2+F3+F5 |

**当前**: F1 启动(发布收敛)。每件大事执行时可 extract ephemeral feature ISA(ISA Reconcile pattern)。

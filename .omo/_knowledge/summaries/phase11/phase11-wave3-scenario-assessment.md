---
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-06-23
archived-since: 2026-06-23
note: "P55 R2: phase 子目录历史总结批量归档, 当前阶段以 .omo/state/system.yaml 为准"
---
# Phase 11 Wave 3 scenario assessment

> Scope: T3.10 — assess the 12 previously blocked user scenarios from `.omo/drafts/scenario-analysis.md` against the Wave 3 MVP baseline.

---

## 1. Assessment summary

Baseline blocked set from the earlier draft:

- `A4`, `A7`, `A9`
- `B3`, `B6`, `B7`, `B9`
- `C6`, `C9`
- `D2`, `D5`, `D9`

Wave 3 judgment:

1. **2/12** are no longer hard-blocked and should be reclassified to **⚠️ manual-feasible**:
   - `D2` 注册 MCP 服务
   - `D9` 用户权限配置
2. **10/12** remain **❌ blocked** for the user-layer MVP because the repository still lacks a complete user-facing flow, not just internal primitives.
3. This assessment **does not change** the Wave 3 MVP success metric from `32/60 ✅`; it only reduces the hard-blocked surface from **12** to **10** and clarifies what should move to Wave 4 / Phase 12.

---

## 2. Scenario-by-scenario assessment

| Scenario | Prior state | Wave 3 assessment | Disposition | Evidence |
|---|---|---|---|---|
| `A4` 追踪某主题的长期变化 | ❌ blocked | Still no durable recurring user journey that combines scheduling + topic watch + delta summarization | Keep blocked | `.omo/drafts/scenario-analysis.md`; `packages/agora/src/agora/pipeline.py` still has no recurring/watch abstraction |
| `A7` 带来源约束的研究 | ❌ blocked | No user-facing source/time filter contract is exposed through the Wave 3 research/search surfaces | Keep blocked | `.omo/drafts/scenario-analysis.md`; Wave 3 landed `kairon-cli search`, but no arXiv/time-bound query contract was added |
| `A9` 研究结果分享 | ❌ blocked | Export/share-to-peer workflow is still missing; notifications are completion alerts, not sharing/distribution | Keep blocked | `packages/wksp/src/wksp/commands/base.py`; `.omo/drafts/scenario-analysis.md` |
| `B3` 连接关联想法 | ❌ blocked | No user-layer “link prior research to current research” workflow landed in Wave 3 | Keep blocked | `.omo/drafts/scenario-analysis.md`; no new `wksp`/`agora` linking surface landed in Wave 3 |
| `B6` 导出知识子集 | ❌ blocked | No command/API to export a filtered knowledge subset as a user deliverable | Keep blocked | `.omo/drafts/scenario-analysis.md`; Wave 3 scope landed search/index/health/notify/dashboard/identity only |
| `B7` 归档旧研究 | ❌ blocked | Data model tracks archived rows, but no explicit archive user flow was exposed | Keep blocked | `packages/wksp/src/wksp/commands/status.py`; `.omo/drafts/scenario-analysis.md` |
| `B9` 知识冲突检测 | ❌ blocked | No conflict detection engine or user-facing comparison workflow is present | Keep blocked | `.omo/drafts/scenario-analysis.md` |
| `C6` 条件分支工作流 | ❌ blocked | `Pipeline` can sequence and parallelize steps, but it still has no branching/decision DSL | Keep blocked | `packages/agora/src/agora/pipeline.py` |
| `C9` 人工审批节点 | ❌ blocked | Governance/admission exists at control-plane level, but not as a user-layer workflow approval node | Keep blocked | `.omo/drafts/scenario-analysis.md`; `.omo` approval/admission artifacts remain control-plane oriented |
| `D2` 注册 MCP 服务 | ❌ blocked | Core operator path now exists through service registration + route mapping, but it is still manual/operator-facing rather than a polished user journey | Reclassify to ⚠️ manual-feasible | `packages/agora/src/agora/server/mcp.py` (`register_service`, `add_route`, `proxy_add_service`); `packages/agora/tests/test_mcp_server.py` |
| `D5` 重启服务 | ❌ blocked | No first-class restart action exists in the current user-facing surfaces | Keep blocked | Search over `packages/agora/src` and `packages/wksp/src` found no restart command surface |
| `D9` 用户权限配置 | ❌ blocked | Capability-grant primitives now make permission configuration possible for operators, but the flow is still low-level and not yet a proper end-user permission UX | Reclassify to ⚠️ manual-feasible | `packages/agora/src/agora/cli/commands_grant.py`; `packages/agora/src/agora/authorizer.py`; Wave 3 identity propagation closes the caller-identity prerequisite |

---

## 3. Closeout judgment

T3.10 is satisfied by assessment and disposition, not by implementation of all 12 scenarios.

Wave 3 outcome:

1. The previously blocked set was reassessed against the real MVP baseline.
2. The assessment found **no hidden “already solved” user journey debt** beyond `D2` and `D9`, which are now better described as operator/manual flows instead of hard impossibilities.
3. The remaining blocked items are legitimate future-scope items and should not hold Wave 3 open.

Recommended carry-forward priority:

1. `C9` 人工审批节点 — closest to the existing governance/admission foundation
2. `A4` 长期主题跟踪 — high leverage if recurring jobs and research deltas get productized
3. `B3` 关联想法 — likely the next meaningful knowledge-layer UX leap
4. `D5` 重启服务 — operational usefulness, but likely Wave 4/Phase 12 rather than Wave 3

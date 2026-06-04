# Phase 2 / Phase 3 Task Manifest

> 日期: 2026-05-30 | 版本: v1.2 | 状态: phase2 complete + phase3 complete
> 依据: `.omo/goals/current.yaml`, `phase3-task-specs-v2.md`, `llm-convergence-planning-packet.md`

---

## 1. 结论

当前 `.omo` 的执行结果已经从 provider plane → foundation → capability → acceptance 全链路闭环：

1. **Phase 2 尾波**：provider plane / route seam / prerequisite cleanup 已完成。
2. **Phase 3 执行**：foundation + capability kickoff slice + final acceptance closure 已完成。

## 2. Phase 2 — 可立即调度

| task_id | title | 当前状态 | 依赖 | worker dispatch |
|---------|-------|----------|------|-----------------|
| `P2-FIX-HARDCODED-PATHS` | Fix remaining 21 hardcoded `/Users/xiamingxing` paths | done | inventory 已存在 | codebuddy |
| `P2-PLAN-SAFE-MESH-RBAC` | Plan Safe Mesh / RBAC deployment roadmap | done | 无额外 blocker | reasonix |

## 3. Phase 2 — 尾波 gated / prep

| task_id | title | 当前状态 | 依赖 | worker dispatch |
|---------|-------|----------|------|-----------------|
| `P2-UNBLOCK-LITELLM-PROVIDER` | Unblock one healthy LiteLLM provider path | done | `cc-switch` provider registry verified | no |
| `P2-WS1-LITELLM-BASELINE` | LiteLLM baseline availability + health/model smoke | done | `P2-UNBLOCK-LITELLM-PROVIDER` | coordinator |
| `P2-WS2-AGENT-RUNTIME-ROUTE-SEAM` | agent-runtime env switch to LiteLLM + smoke evidence | done | `P2-WS1-LITELLM-BASELINE` | coordinator |

## 4. Phase 3 — foundation track (executed slice)

| task_id | title | 当前状态 | 依赖 | 证据 |
|---------|-------|----------|------|------|
| `P3-WS3-GBRAIN-DEFAULT-ROUTE` | gbrain default route convergence to LiteLLM | done | `P2-WS1/WS2` | `.omo/summaries/p3-foundation-convergence-retrospective.md` |
| `P3-WS3-MINERVA-CLI-CONVERGENCE` | Minerva CLI hardcoded provider cleanup | done | `P2-WS1/WS2` | `.omo/summaries/p3-foundation-convergence-retrospective.md` |
| `P3-WS4-FRAGMENT-LLM-CLEANUP` | sophia / ssot / ontoderive / metaos env-driven convergence | done | gbrain + Minerva route baselines | `.omo/summaries/p3-foundation-convergence-retrospective.md` |
| `P3-WS4-LLM-ENV-STANDARDIZATION` | Standardize `LLM_PROVIDER/BASE_URL/API_KEY/MODEL` | done | fragment cleanup middle/late stage | `.omo/summaries/p3-foundation-convergence-retrospective.md` |

## 5. Phase 3 — capability kickoff slice (executed)

| task_id | title | 当前状态 | 证据 |
|---------|-------|----------|------|
| `P3-T5-SKILL-ROUTER` | Skill Router for KOS self | done | `.omo/summaries/p3-capability-track-retrospective.md` |
| `P3-T4-MEMORY-TREE` | Memory Tree hierarchical memory | done | `.omo/summaries/p3-capability-track-retrospective.md` |
| `P3-M3-CROSS-DOMAIN-RESEARCH` | Cross-domain research engine | done | `.omo/summaries/p3-capability-track-retrospective.md` |
| `P3-M2-FAMILY-OS-SCHEDULER` | Family OS scheduler | done | `.omo/summaries/p3-capability-track-retrospective.md` |
| `P3-M6-DEVICE-ORCHESTRATOR` | Device orchestrator | done | `.omo/summaries/p3-capability-track-retrospective.md` |
| `P3-M5-WECHAT-CONNECTOR` | WeChat connector export-stub | done | `.omo/summaries/p3-capability-track-retrospective.md` |

## 6. Phase 3 foundation baseline

Phase 3 后续执行默认建立在下面这套已经落地的 provider plane 上：

- `cc-switch`：provider registry / health source
- `LiteLLM`：本地统一模型代理
- `CodexBar`：额度监控 / operator visibility
- `LLM_PROVIDER / LLM_BASE_URL / LLM_API_KEY / LLM_MODEL`：跨 repo 的统一 LLM env contract
- 证据文件：`.omo/state/provider-plane.yaml`, `.omo/summaries/p2-provider-plane-evidence.md`

## 7. Phase 3 — acceptance closure (executed)

| task_id | title | 当前状态 | 证据 |
|---------|-------|----------|------|
| `P3-W12-PHASE3-ACCEPTANCE` | Phase 3 end-to-end acceptance + retrospective | done | `.omo/summaries/phase3-acceptance-report.md`, `.omo/summaries/p3-full-execution-retrospective.md` |

## 8. Dispatch order

1. `P2-PLAN-SAFE-MESH-RBAC`
2. `P2-FIX-HARDCODED-PATHS`
3. `P2-UNBLOCK-LITELLM-PROVIDER`
4. `P2-WS1-LITELLM-BASELINE`
5. `P2-WS2-AGENT-RUNTIME-ROUTE-SEAM`
6. Phase 3 foundation track
7. Phase 3 capability track
8. Phase 3 acceptance closure

## 9. 当前执行策略

- Phase 2 尾波已经完成，当前不再需要为 LiteLLM 前置保留 blocked task。
- Phase 3 foundation 第一批已完成并直接归档到 `done/`，不再保持 future-gated。
- capability kickoff slice 已落地并归档到 `done/`。
- acceptance closure 已通过统一 runner 收口，wksp orchestration、capability surfaces、recovery/minions 均已转绿。
- `.omo` 现在将 Phase 3 视为完成态；后续重点应转向 Phase 4 roadmap，而不是继续保留“未收口”的 Phase 3 描述。
- quota 监控默认走 `CodexBar`，provider runtime 默认从 `cc-switch` 选择，再统一汇聚到 `LiteLLM`。

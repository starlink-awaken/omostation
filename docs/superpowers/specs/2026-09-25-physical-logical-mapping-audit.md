---
schema: md/v1
status: accepted
lifecycle: contract
owner: governance-team
last-reviewed: 2026-09-25
type: ephemeral
schema_version: specification/v1
spec_version: 1.0.0
title: Physical-Logical Mapping Audit — gitlink/launchd/asset consistency
bet_id: BET-Y2Q4-SH-3
---


# BET-Y2Q4-SH-3 — Physical-Logical Mapping Audit

## Context

诊断 `#4310` 发现 3 类"物理-逻辑不一致"：

| 类型 | 声明面 | 物理面 | 漂移 |
|---|---|---|---|
| **gitlink** | `.gitmodules` + 主仓 commit | `projects/<sub>` 实际 HEAD | 3/16 submodule gitlink 在 origin/main 不可达 (cockpit/cockpit-ui/ecos) |
| **launchd** | `.omo/cron/*.plist` | `launchctl list` 实际运行 | 2 服务声明但未运行 (cron-service/gbrain-index) |
| **OMO asset** | `.omo/_truth/registry/omo-governance-surfaces.yaml` | 文件系统存在 | 5 真 zombie (OMO-PITCHES/OMO-GENERATED 等) |

**根因 R3**: 逻辑声明与物理存在是手工维护（每次子仓合入、每次 plist 修改都要人 commit 才能同步），无自动 sync 验证。

## Goal

建立 **physical-logical audit**：
1. 单个工具扫三类映射，自动生成 drift 报告
2. 区分"自动可修"vs"需 owner 决策"
3. 与 `submodule-reachability-gate` 集成（后者是前者的子集）
4. 接入 `make gac-local-gate`（轻量 lint，无 cron 阻塞）

## Non-goals

- **不直接 push gitlink bump PR** — 自动 PR 风险高；只生成建议 + 报告 drift
- **不替 owner 决策 OMO zombie** — 仍走 `decision_needed` 路径
- **不重写 plist** — 修复 launchd zombie 是基础设施动作，需 owner 确认

## Done when

- `bin/ssot/physical-logical-audit.py` 扫 3 类：
  - **gitlink** 类: `.gitmodules` ↔ `git -C <sub> rev-parse origin/main` ↔ 主仓 gitlink commit 指向（3-way diff）
  - **launchd** 类: `.omo/cron/*.plist` 的 `Label` 字段 ↔ `launchctl list` 实际 entry（detect zombie + missing）
  - **OMO asset** 类: `.omo/_truth/registry/omo-governance-surfaces.yaml` 的 `ref` 字段 ↔ 文件系统存在 + gitignore 状态（detect 真 zombie vs 运行时面）
- 每个发现给：drift 类型 + 严重性 + 修复路径（自动 PR / 建议 owner / 维持现状）
- 接入 `make gac-local-gate`：发现 drift 时 WARN（不阻断 CI）
- 接入 panorama health：每日报告到 `runtime/dashboard/agent-brief.json` 的 health.drift_count
- 实证：跑完后 3 gitlink / 2 launchd / 5 OMO zombie 全部被识别并分类

## Verification

```bash
uv run --with pyyaml python bin/ssot/physical-logical-audit.py --json
make gac-local-gate
```

## 关联债务

- 完成后应能 close:
  - `OMO-SURFACES-ZOMBIE-ASSETS` (medium severity, owner-decision-class) — 本 BET 提供检测报告，owner 决策仍需
- 关联发现 (from #4310):
  - **#6-#7** launchd zombie (cron-service/gbrain-index)
  - **#9** 5 OMO 真 zombie assets
  - **#20** submodule-reachability FAIL (3/16)

## Bootstrap authorization

- workflow: `project-code-change`
- agent: governance-agent
- 优先级: P1
- 依赖: BET 1 (cron 触发共用) — 可与 BET 1 同步推进 cron 部分
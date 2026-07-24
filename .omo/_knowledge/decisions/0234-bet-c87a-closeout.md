---
id: 0234-bet-c87a-closeout
title: "BET-c87a http-mcp-convergence 收尾正式立项"
status: ACCEPTED
lifecycle: proposal
date: 2026-07-24
last-reviewed: 2026-07-24
owner: governance-team
supersedes: BET-C87A-CLOSEOUT-PREP-2026-07-24.md (evidence-only)
deciders: governance-team
strat: STRAT-P81
stage: post-S0
related:
  - BET-c87a (c2g:bet:BET-c87a, goal L217)
  - ADR-0228 m1-acceptance-physical-deferred-reorder
  - ADR-0232 g-del-2b-official-pass
  - STRAT-P81-strategic-roadmap.md
---

# 0234 - BET-c87a http-mcp-convergence 收尾

## Context

STRAT-P81 S0 收尾后,Stage 0 closeout v2 (PR #496) 标记 #7 拍板可启。
BET-c87a (http-mcp-convergence-optimization) 已 80%:
- ✅ 24 → 5 HTTP 收敛 (实际收敛到 1,见证据)
- ✅ 29/29 MCP stdio
- ⏳ 测覆 + 前端现代化 — 剩余

`BET-C87A-CLOSEOUT-PREP-2026-07-24.md` 已就 9 测覆盲区 + cockpit-ui 现代化 candidates
给出预备清单。本 ADR 正式立项,启用。

## Decision

Stage 0 closeout 后启动 BET-c87a 收尾工程, 双轨推进:

### 轨道 A: KOS REST API 测覆补全
- 11 个 endpoint,2 个 test (18% 覆盖)
- 9 个盲区按 P0→P3 优先级补全
- 优先级(P0): `/api/v1/search`, `/api/v1/context`
- 优先级(P1): `/api/v1/verify`, `/api/v1/suggest`
- 优先级(P2): `/api/v1/clusters`
- 优先级(P3): legacy `/api/search`, `/health`, `/`, `/api/collab/callback`

### 轨道 B: cockpit-ui 现代化
- 116 个 TS/TSX 文件, React 19.2 + Vite + vitest
- 候选: 组件拆分 / 设计 token / Storybook / a11y / 响应式 / i18n
- 启动顺序: `frontend-design` skill 触发 → 设计审计 → 修补

## Constraints

### 禁止剧场化 (继承 S0 黑名单)
- ❌ 改 transport label 不动 command/mcp_tool
- ❌ 改 gitignore 隐藏 archived
- ❌ 假装物理机在线
- ❌ 自宣物理 meets_gate
- ❌ 自宣 G-DEL.2b 官方通过 (已有 official_announce=false 标记)

### 范围
- 不做新 BOS 服务注册
- 不扩展 HTTP API(只补测覆)
- 不偏离 BET-c87a scope(http-mcp-convergence)
- 不动其他子项目(无跨包接口变更)

### 路径
- 子模块 PR 走直接 push (submodule main 不保护)
- 根仓改动走 worktree + PR
- 测覆改动需 `make test-diff` 全绿

## Consequences

### Positive
- BET-c87a 完成度 80% → 100%
- KOS REST 测覆 18% → 100% (有望)
- cockpit-ui 现代化基础建立
- 工程交付数推进 (X3 软门禁缓解)

### Neutral
- 新增 9 个 KOS REST test 文件
- 新增 1+ 个 cockpit-ui 组件 audit 报告

### Negative (已知)
- 测覆补全后,KOS 测试套件运行时间略增
- cockpit-ui 审计可能暴露更多架构债

## Implementation Steps

1. 起 worktree: `bash bin/gac/gac-worktree.sh claim bet-c87a-closeout`
2. 轨道 A: 进入 `projects/kairon` 子模块,补 9 个 endpoint test
   - 按 P0→P3 顺序
   - 优先用 `httpx.AsyncClient` + `TestClient`
3. 轨道 B: 进入 `projects/cockpit-ui`,触发 `frontend-design` skill
4. CI: `cd projects/kairon && make test-diff` + `cd projects/cockpit-ui && npm run build`
5. 提交 + PR

## Validation

- [ ] KOS REST 测覆率达到 100% (11/11)
- [ ] cockpit-ui 设计审计报告落地
- [ ] cockpit-ui build + lint 全绿
- [ ] 没有 ARCH/SSOT 漂移
- [ ] smoke test 跑通

## Risks

| 风险 | 缓解 |
|------|------|
| 测覆补全触发 kairon 跨包 API 变更 | 严守 scope, 只改 test_file, 不改 source |
| cockpit-ui 现代化触动太多组件 | 启动顺序: 审计 → 修补, 不预先拆 |
| 测覆耗时回归 CI 预算 | 测覆 portfolio 用 sample-based subset |

## Related

- BET-c87a 元数据: `.omo/_truth/goals/current.yaml` L217
- 收尾准备 evidence: `.omo/_knowledge/decisions/BET-C87A-CLOSEOUT-PREP-2026-07-24.md`
- KOS REST API: `projects/kairon/packages/kos/src/kos/web/app.py`
- 现有测试: `projects/kairon/packages/kos/tests/test_web_app.py`
- cockpit-ui: `projects/cockpit-ui/`

## Status

ACCEPTED — 启动条件: STRAT-P81 S0 closeout 完成 (PR #496) + 人类拍板 #7

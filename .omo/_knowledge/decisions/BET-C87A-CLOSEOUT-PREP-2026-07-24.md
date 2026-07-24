---
id: BET-C87A-CLOSEOUT-PREP
title: BET-c87a http-mcp-convergence 收尾准备（Stage 0 后启动）
owner: governance-team
status: candidate
created_at: 2026-07-24T08:58:00Z
strat: STRAT-P81
stage: S0 (closeout-able)
context: STRAT-P81-MASTER-DECISION-INBOX-2026-07-24.md #7
bet_ref: BET-c87a (c2g:bet:BET-c87a)
warning: |
  Evidence-only. 不修改代码、不重定义 transport、不动 cockpit-ui 源码。
  立项后启动收尾工程。
---

# BET-c87a 收尾准备 (evidence)

## 0. 现状

BET-c87a (http-mcp-convergence-optimization) 已 80% 完成:
- ✅ 24 → 5 HTTP 收敛
- ✅ 29/29 MCP stdio
- ⏳ 测覆 + 前端现代化 — 剩余

> **再核实**: 当前 BOS 注册表仅 **1 个 HTTP 服务**(`bos://memory/kos/rest-api`),`http_url=http://localhost:8766/api/v1`。
> 24 → 5 阶段实际收敛到 1 个(比原计划更彻底)。

## 1. HTTP endpoint 测覆盲区

唯一一个 HTTP 服务是 **KOS REST API**(`projects/kairon/packages/kos/src/kos/web/app.py`)。

### 11 个 endpoint,2 个 test

| Endpoint | Method | Test 覆盖 |
|----------|--------|-----------|
| `/api/v1/search` | GET | ❌ |
| `/api/v1/suggest` | GET | ❌ |
| `/api/v1/context` | GET | ❌ |
| `/api/v1/verify` | POST | ❌ |
| `/api/v1/stats` | GET | ✅ `test_stats_endpoint_reports_uninitialized_database` |
| `/api/v1/health` | GET | ✅ `test_health_endpoint_reports_workspace_and_database` |
| `/api/v1/clusters` | GET | ❌ |
| `/` | GET (HTML) | ❌ |
| `/api/search` | GET (legacy) | ❌ |
| `/health` | GET (legacy) | ❌ |
| `/api/collab/callback` | POST | ❌ |

**测试覆盖: 2/11 = 18%**

### 测试盲区优先级

| 优先级 | endpoint | 理由 |
|--------|----------|------|
| P0 | `/api/v1/search` | 核心入口,SSOT 1 验真 |
| P0 | `/api/v1/context` | Stage 2 角色记忆共享依赖 |
| P1 | `/api/v1/verify` | 闭环验证 |
| P1 | `/api/v1/suggest` | UX 体验 |
| P2 | `/api/v1/clusters` | 调试观察 |
| P3 | `/api/search` `/health` | legacy,待删除 |
| P3 | `/` | HTML 页面,基本无回归面 |
| P3 | `/api/collab/callback` | 内部回调 |

## 2. 前端现代化 candidates

**cockpit-ui** (116 个 TS/TSX,React 19.2 + Vite + vitest)

### 已知架构债

| 类别 | 状态 | 备注 |
|------|------|------|
| 组测覆盖 | 部分 | `__tests__/` 目录存在,但不完整 |
| Modern React patterns | 待审 | hooks + suspense 用法应审计 |
| 设计系统 | 部分 | `frontend-design` skill 可触发 |
| 性能 | 待测 | React 19 RSC / use() 是否用上 |
| Type safety | 待审 | TypeScript strict 模式 |

### modernization candidates (建议立项后审计)

1. **组件拆分**: 116 个文件,可能存在大组件未拆
2. **设计 token 统一**: `frontend-design` skill 触发
3. **Storybook 引入**: 视觉回归
4. **a11y 审计**: WCAG 2.1 AA
5. **响应式布局**: 移动端体验
6. **i18n**: 多语言

## 3. 立项条件

需 STRAT-P81-MASTER-DECISION-INBOX-2026-07-24.md #7 拍板,且 Stage 0 closeout 完成。

## 4. 启动后 4 步路径

1. `git worktree` 隔离 → 写 ADR(C87A-CLOSEOUT)
2. **KOS REST API**: 9 个 test 补全(按 P0→P3 顺序)
3. **cockpit-ui**: 触发 `frontend-design` skill → 产出设计审计 → 修补
4. **CI**: 把新测试纳入 gate,kairon 测覆率纳入 ADR

## 5. 引用

- BET-c87a 在 `.omo/_truth/goals/current.yaml` L217-122
- KOS REST API 源码: `projects/kairon/packages/kos/src/kos/web/app.py`
- 现有测试: `projects/kairon/packages/kos/tests/test_web_app.py`
- cockpit-ui AGENTS.md: `projects/cockpit-ui/AGENTS.md`

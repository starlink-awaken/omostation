---
status: active
lifecycle: entry
owner: auto-fix-loop
last-reviewed: 2026-08-24
---

# 90% 架构成熟度设计方案

> 从当前状态全面提升至 90%+ 的完整架构设计。

## 当前状态

| 维度 | 指标 | 值 |
|------|------|-----|
| 工具总数 | bin/ + ECOS tools | 365 |
| 治理约束 | L0 constraints | 28 |
| M1 实例 | 运行时节点 | 1406 |
| 场景卡 | scene-cards | 8 |
| 旅程 | journey-specs | 12 |
| 测试 | test files | 68 |
| CI steps | ecos-ci.yml | 18 |

## 架构全景

```
┌─────────────────────────────────────────────────────────────┐
│  感知层 (Sense)                                             │
│  signal-poller + scene-trigger + scene-daemon              │
│  5 信号源 → 8 场景 → 12 旅程                               │
├─────────────────────────────────────────────────────────────┤
│  治理层 (Govern)                                            │
│  L0 Constraints (28) + MOF Reasoning (4 engines)           │
│  + Prediction Loop + Alert Pipeline                        │
├─────────────────────────────────────────────────────────────┤
│  执行层 (Execute)                                           │
│  L1 Runtime (scheduler) + L2 Engine (knowledge)            │
│  + L3 Entry (api) + Journey Runner                        │
├─────────────────────────────────────────────────────────────┤
│  观测层 (Observe)                                           │
│  Dashboard (3-panel) + Metrics + Tracing + Health          │
├─────────────────────────────────────────────────────────────┤
│  防腐层 (Anti-Corruption)                                   │
│  CI Gates + Tool Audit + Doc Freshness + Redundancy        │
└─────────────────────────────────────────────────────────────┘
```

## 90% 达标路径

### Phase 1: 工具 CI 覆盖率 19% → 90%

**策略**: 分级接入 + 批量 smoke test

| 级别 | 工具数 | 策略 | CI 方式 |
|------|--------|------|---------|
| P0 Core | 5 | 完整测试 | 单测 + 集成 |
| P1 Active | 7 | 完整测试 | 单测 |
| P2 Essential | 15 | smoke test | 批量 |
| P2 Support | 11 | smoke test | 批量 |
| P3 Deprecated | 4 | 归档 | 删除 |

**CI 接线**:
```yaml
- name: P0/P1 tools test
  run: uv run pytest tests/test_tool_smoke.py -q

- name: P2 tools batch CI
  run: |
    for tool in mof-bootstrap mof-compile ...; do
      uv run python3 src/ecos/ssot/tools/$tool.py --help > /dev/null
    done
```

### Phase 2: 场景激活 2/8 → 7/8

**策略**: shadow → pilot → active

| 场景 | 当前 | 目标 |
|------|------|------|
| agora-bos-gateway | active | active ✅ |
| unified-inbox | active | active ✅ |
| document-review | active | active ✅ |
| engineering-delivery | shadow | pilot |
| knowledge-curation | shadow | pilot |
| meeting-supervision | shadow | pilot |
| periodic-reporting | shadow | pilot |
| project-supervision | shadow | pilot |

### Phase 3: 告警通道

**管线**: 检测 → 路由 → 聚合 → 派发 → 通知

```
dashboard --check → alert-router → alert-aggregator → governance-dispatch
                                                          ↓
                                              log + github_issue + webhook
```

### Phase 4: 可观测性

**指标**: tools/constraints/M1/scenes/journeys
**追踪**: trace_id 贯穿 intake→govern→execute→deliver
**健康**: 0-100 评分, A/B/C/D 等级

### Phase 5: 工作流激活

**目标**: ≥3 active workflows
**策略**: observer-audit + governance-audit + handoff-resume

### Phase 6: 防腐固化

**CI 化检查**:
- 工具 CI 覆盖率 (每次 PR)
- 文档保鲜 (每周)
- 冗余检测 (每月)
- 依赖漂移 (每次 PR)

## 验证标准

| 维度 | 当前 | 目标 | 测量 |
|------|------|------|------|
| 工具 CI | 19% | ≥90% | CI steps / total tools |
| 场景激活 | 25% | ≥87% | active+pilot / total |
| 测试覆盖 | ~60% | ≥90% | test files / modules |
| 告警通道 | ❌ | ✅ | CI step present |
| 工作流 | 0 | ≥3 | active runs |
| 防腐 CI | ❌ | ✅ | CI step present |
| 观测 | 基础 | 全链路 | metrics+trace+health |

## 实施计划

| 阶段 | 时间 | 产出 |
|------|------|------|
| Phase 1 | 2-3 天 | 35+ tools in CI |
| Phase 2 | 1-2 天 | 7/8 scenes active |
| Phase 3 | 1-2 天 | alert pipeline wired |
| Phase 4 | 1-2 天 | metrics+trace live |
| Phase 5 | 1 天 | 3+ workflows active |
| Phase 6 | 1 天 | anti-corruption CI |

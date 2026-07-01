---
status: active
lifecycle: contract
owner: governance-team
last-reviewed: 2026-07-01
---

# ADR-0119: Workspace 系统性优化 Roadmap (2026 H2)

- **Status**: ACCEPTED
- **Date**: 2026-07-01
- **Authors**: governance-team (基于 2026-07-01 系统性健康审计)
- **Related**:
  - [审计报告](../audits/2026-07-01-systemic-health-audit.md)
  - [VISION-ROADMAP.md](../../../docs/VISION-ROADMAP.md)
  - [GOVERNANCE-EVOLUTION-ROADMAP.md](../../../docs/GOVERNANCE-EVOLUTION-ROADMAP.md)

## Context and Problem Statement

2026-07-01 系统性健康审计 (8 维度) 发现综合健康度 7.2/10。近期几轮修复把文档 (9)、架构 (9)、CI (8)、安全 (8) 拉上来,但代码质量 (6)、测试健康 (5)、治理状态 (6) 存在系统性短板:

1. **依赖零锁定**: 39 个 Python 依赖全 floating, 无 lockfile, 无 pip-audit
2. **bin/ 工具测试盲区**: 85 个工具仅 9% 有测试, 核心门禁 gac-local-gate 无测试
3. **状态监控空窗**: 2 服务 26 天 stale 标 healthy, 8 个 initiative 进度全空
4. **God Module 系统性**: 81 文件 >800L, omo 违反自身 lint 规则, TS CI 不可见
5. **发布管道隐患**: publish-pypi tags+paths AND 逻辑 + curl|bash 2 处 + gbrain 分叉

本 ADR 定义 3 阶段优化 roadmap, 与 VISION-ROADMAP Phase 1 (基础设施完善) 对齐, 补充工程基础设施短板。

## Decision

### 3 阶段 Roadmap

```
S0 (立即, ~1h)     S1 (1-2 周)         S2 (3-4 周)         S3 (渐进, 持续)
    │                  │                    │                    │
    ▼                  ▼                    ▼                    ▼
┌────────┐       ┌──────────┐        ┌──────────┐        ┌──────────┐
│ P0 热修 │  →   │ 依赖锁定  │   →   │ 测试覆盖  │   →   │ God Module│
│ 5 项    │       │ + 安全   │        │ + 监控   │        │ 渐进拆分  │
└────────┘       └──────────┘        └──────────┘        └──────────┘
```

### S0: P0 热修 (立即, ~1h)

| # | 任务 | 影响 | 工时 | 验收 |
|---|------|------|------|------|
| S0-1 | publish-pypi.yml 删 paths 过滤 | C | 10min | tag push 触发发布 |
| S0-2 | submodule-freshness curl\|sh → setup-uv@v4 | C+E | 15min | 与 14 个 workflow 一致 |
| S0-3 | ci-lint actionlint URL pin 到 release tag | C+E | 15min | URL 含版本号 |
| S0-4 | Python 3.14→3.13 统一 (4 workflows) | C | 10min | rg '3.14' 返回 0 |
| S0-5 | forge pyproject >=3.10→>=3.13 | A | 5min | rg '3.10' 在 pyproject 返回 0 |

### S1: 依赖锁定 + 安全加固 (1-2 周)

| # | 任务 | 影响 | 工时 | 验收 |
|---|------|------|------|------|
| S1-1 | omo: uv lock 生成 lockfile | A+E | 2h | uv.lock 存在且 CI 校验 |
| S1-2 | ecos: uv lock 生成 lockfile | A+E | 1h | uv.lock 存在 |
| S1-3 | agora: uv lock 生成 lockfile | A+E | 1h | uv.lock 存在 |
| S1-4 | CI 加 pip-audit 扫描 | E | 2h | 新 workflow pip-audit.yml |
| S1-5 | shellcheck + actionlint 纳入 ci-local-fast | C+H | 30min | brew install + Makefile |
| S1-6 | CONTRIBUTING.md 补全 18 个项目 | F | 1h | 与 project-registry 一致 |
| S1-7 | gbrain 远端 master→main 统一 | G | 30min | git branch -d master |

### S2: 测试覆盖 + 状态监控 (3-4 周)

| # | 任务 | 影响 | 工时 | 验收 |
|---|------|------|------|------|
| S2-1 | bin/gac-local-gate.py 测试 | B+D | 4h | tests/test_gac_local_gate.py |
| S2-2 | bin/yaml-validate.py + dir-hygiene-check.py 测试 | B | 2h | tests/test_bin_tools.py |
| S2-3 | bin/ssot-guardian.py + doc-ssot-lint.py 测试 | B+D | 4h | 覆盖核心路径 |
| S2-4 | cockpit-ui Vitest 冒烟测试 | B | 4h | tests/ 存在 + npm test 通过 |
| S2-5 | bin/state-freshness-check.py (新建) | D | 3h | stale 服务 exit 1 |
| S2-6 | state-freshness 纳入 GaC gate | D | 1h | make gac-local-gate 含 freshness |
| S2-7 | governance-evolution initiative 进度填充 | D | 2h | status --json 返回 % |
| S2-8 | check-god-module.py 纳入 CI (覆盖 TS) | A+C | 1h | ci-lint.yml 新 job |

### S3: God Module 渐进拆分 (持续, 按需)

| # | 任务 | 影响 | 工时 | 验收 |
|---|------|------|------|------|
| S3-1 | omo src 3 文件拆分 (cards/promotion/audit) | A | 2 周 | 全部 <800L |
| S3-2 | bin/ agent-workflow.py 拆分 | A+H | 1 周 | <800L |
| S3-3 | gbrain TS 核心文件拆分 (按需) | A | 持续 | 按功能模块拆 |
| S3-4 | 71 孤儿脚本审计 + 归档 | H | 1 周 | 确认真孤儿后归档 |

### 优先级矩阵

```
        高影响
          │
    S0-1  │  S2-1     S1-1
    S0-2  │  S2-5     S1-4
          │
  ────────┼────────────────
          │
    S0-4  │  S1-6     S3-1
    S0-5  │  S2-7     S3-4
          │
        低影响
   低工时              高工时
```

## Consequences

### 正面
- 依赖锁定消除复现性风险 (S1)
- bin/ 测试覆盖从 9%→30%+ (S2), 核心门禁不再盲区
- 状态监控闭环 (S2), health_score 不再虚高
- God Module 渐进改善 (S3), omo 自身合规

### 负面
- uv.lock 增加 CI 安装时间 (预估 +10-15s)
- God Module 拆分有回归风险 (需充分测试覆盖先行)
- 孤儿脚本审计需逐个确认 (可能有些被文档引用但未被 Makefile/CI 引用)

### 与 VISION-ROADMAP 的关系
- S0+S1 对齐 VISION-ROADMAP Phase 1 "基础设施完善" 中的 "监控告警完善"
- S2 对齐 Phase 1 "文档体系完善" (测试也是一种文档)
- S3 是工程质量渐进改进, 不阻塞 VISION-ROADMAP 任何 Phase

### 与 governance-evolution-roadmap 的关系
- S2-7 直接修复 8 个 initiative 进度全 ?% 的问题
- S2-5/S2-6 增强 governance-evolution 的 verification 能力
- 不新增 initiative, 只修复现有 initiative 的执行缺口

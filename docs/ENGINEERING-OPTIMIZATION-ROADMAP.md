# Workspace 工程优化 Roadmap (2026 H2)

> Human-readable navigation for the systemic engineering optimization plan.
> Audit SSOT: [`.omo/_knowledge/audits/2026-07-01-systemic-health-audit.md`](../.omo/_knowledge/audits/2026-07-01-systemic-health-audit.md)
> Decision: [ADR-0119](../.omo/_knowledge/decisions/0119-systemic-optimization-roadmap-2026h2.md)

## 背景

2026-07-01 系统性健康审计 (8 维度) 评估综合健康度 7.2/10。近期修复把文档 (9)、架构 (9)、CI (8)、安全 (8) 拉上来,但代码质量 (6)、测试健康 (5)、治理状态 (6) 存在系统性短板。本 roadmap 定义 3 阶段优化计划。

## 健康度评分

| 维度 | 分数 | 趋势 | 主要失分 |
|------|------|------|----------|
| A 代码质量 | 6/10 | ↓ | 81 god modules, 0 依赖锁定 |
| B 测试健康 | 5/10 | → | bin/ 9% 覆盖, cockpit-ui 零测试 |
| C CI/CD | 8/10 | ↑ | curl\|bash 2 处, publish-pypi gotcha |
| D 治理状态 | 6/10 | → | 2 服务 stale, initiative 进度空 |
| E 安全 | 8/10 | ↑ | 依赖零锁定 |
| F 文档 | 9/10 | ↑ | 基本无失分 |
| G 架构 | 9/10 | ↑ | gbrain 远端分叉 |
| H 基础设施 | 7/10 | → | 71 孤儿脚本 |

## TOP 5 系统性风险

| # | 风险 | 影响 | 严重度 |
|---|------|------|--------|
| 1 | 依赖零锁定 (39 个全 floating) | A+E+H | High |
| 2 | bin/ 工具测试盲区 (9% 覆盖) | B+D | High |
| 3 | 状态监控空窗 (26 天 stale 标 healthy) | D | Medium |
| 4 | God Module 系统性 (81 文件 >800L) | A | Medium |
| 5 | 发布管道隐患 (tags+paths AND + curl\|bash) | C+E+G | High |

## 3 阶段 Roadmap

```
S0 (立即, ~1h) → S1 (1-2 周) → S2 (3-4 周) → S3 (渐进, 持续)
   P0 热修        依赖锁定+安全     测试覆盖+监控     God Module 拆分
```

### S0: P0 热修 (立即, ~1h)

| # | 任务 | 工时 | 验收 |
|---|------|------|------|
| S0-1 | publish-pypi.yml 删 paths 过滤 | 10min | tag push 触发发布 |
| S0-2 | submodule-freshness curl\|sh → setup-uv@v4 | 15min | 与 14 个 workflow 一致 |
| S0-3 | ci-lint actionlint URL pin release tag | 15min | URL 含版本号 |
| S0-4 | Python 3.14→3.13 统一 (4 workflows) | 10min | rg '3.14' 返回 0 |
| S0-5 | forge pyproject >=3.10→>=3.13 | 5min | 无 3.10 引用 |

### S1: 依赖锁定 + 安全加固 (1-2 周)

| # | 任务 | 工时 | 验收 |
|---|------|------|------|
| S1-1 | omo: uv lock 生成 lockfile | 2h | uv.lock + CI 校验 |
| S1-2 | ecos: uv lock | 1h | uv.lock |
| S1-3 | agora: uv lock | 1h | uv.lock |
| S1-4 | CI 加 pip-audit 扫描 | 2h | pip-audit.yml |
| S1-5 | shellcheck+actionlint 纳入 ci-local-fast | 30min | brew + Makefile |
| S1-6 | CONTRIBUTING.md 补全 18 项目 | 1h | 与 registry 一致 |
| S1-7 | gbrain 远端 master→main 统一 | 30min | 无 master 分支 |

### S2: 测试覆盖 + 状态监控 (3-4 周)

| # | 任务 | 工时 | 验收 |
|---|------|------|------|
| S2-1 | gac-local-gate.py 测试 | 4h | test_gac_local_gate.py |
| S2-2 | yaml-validate + dir-hygiene 测试 | 2h | test_bin_tools.py |
| S2-3 | ssot-guardian + doc-ssot-lint 测试 | 4h | 覆盖核心路径 |
| S2-4 | cockpit-ui Vitest 冒烟 | 4h | npm test 通过 |
| S2-5 | state-freshness-check.py (新建) | 3h | stale exit 1 |
| S2-6 | freshness 纳入 GaC gate | 1h | gac-local-gate 含 |
| S2-7 | initiative 进度填充 | 2h | status --json 有 % |
| S2-8 | check-god-module 纳入 CI (TS) | 1h | ci-lint 新 job |

### S3: God Module 渐进拆分 (持续)

| # | 任务 | 工时 | 验收 |
|---|------|------|------|
| S3-1 | omo src 3 文件拆分 | 2 周 | 全部 <800L |
| S3-2 | bin/ agent-workflow.py 拆分 | 1 周 | <800L |
| S3-3 | gbrain TS 拆分 (按需) | 持续 | 按功能模块 |
| S3-4 | 71 孤儿脚本审计 | 1 周 | 确认后归档 |

## 与现有 Roadmap 的关系

| 本 Roadmap | VISION-ROADMAP | governance-evolution |
|------------|----------------|----------------------|
| S0+S1 | Phase 1 "监控告警完善" | - |
| S2 | Phase 1 "文档体系完善" | 修复 initiative 执行缺口 |
| S3 | 不阻塞任何 Phase | 增强 verification 能力 |

## 执行原则

1. **不阻塞产品**: S0/S1 是基础设施, 不改产品代码逻辑
2. **测试先行**: S3 god module 拆分前, S2 测试覆盖必须就位
3. **渐进推进**: 每阶段完成后重新评估健康度, 调整后续优先级
4. **SSOT 落盘**: 所有变更通过 ADR + audit 记录, 不脱离治理体系

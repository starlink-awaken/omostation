---
status: active
lifecycle: evidence
owner: governance-team
last-reviewed: 2026-07-01
audit-date: 2026-07-01
audit-scope: A-H (8 dimensions)
---

# Workspace 系统性健康审计 (2026-07-01)

> 8 维度全量白盒审计: 代码质量 / 测试健康 / CI-CD / 治理状态 / 安全 / 文档 / 架构 / 基础设施
> 审计方法: 静态分析 + 治理工具链 + 人工交叉验证
> 审计范围: 全部 17 子模块 + 根仓 + .omo/ 治理层

## 1. 审计方法

| 维度 | 数据来源 | 工具 |
|------|----------|------|
| A 代码质量 | 源码静态扫描 | check-god-module.py, rg, debt-audit |
| B 测试健康 | pytest --co, 测试源码扫描 | pytest, rg |
| C CI/CD | .github/workflows/*.yml 全量 | 人工白盒 + YAML 校验 |
| D 治理状态 | .omo/state/, .omo/tasks/, ADR | governance-evolution.py, system.yaml |
| E 安全 | 源码 + CI + .gitignore | rg (secret/shell/eval), git ls-files |
| F 文档 | docs/, .omo/_knowledge/, AGENTS.md | doc-ssot-lint.py, doc-link-check.py |
| G 架构 | 子模块 + 跨层 import + 端口 | git submodule status, rg (cross-layer) |
| H 基础设施 | du, git count-objects, Makefile | du, git, rg |

## 2. 健康度评分总览

| 维度 | 分数 | 趋势 | 主要失分 |
|------|------|------|----------|
| A 代码质量 | 6/10 | ↓ | 81 god modules, 0 依赖锁定, 161 TODO |
| B 测试健康 | 5/10 | → | bin/ 9% 覆盖, cockpit-ui 零测试 |
| C CI/CD | 8/10 | ↑ | curl\|bash 2 处, publish-pypi gotcha |
| D 治理状态 | 6/10 | → | 2 服务 26 天 stale, initiative 进度空 |
| E 安全 | 8/10 | ↑ | 依赖零锁定, 无 pip-audit |
| F 文档 | 9/10 | ↑ | 基本无失分 (近期修复后) |
| G 架构 | 9/10 | ↑ | gbrain 远端 main/master 分叉 |
| H 基础设施 | 7/10 | → | 71 孤儿脚本, kairon 2.3GB |
| **综合** | **7.2/10** | **↑** | **A+B+D 是系统性短板** |

## 3. 详细发现

### A. 代码质量与技术债

| 指标 | 数值 | 阈值 | 状态 |
|------|------|------|------|
| God Module (>800L) | 81 文件 | <20 | ❌ |
| TODO/FIXME/HACK | 161 个 | <50 | ⚠️ |
| lint 抑制 (noqa/ignore) | ~50 处 | <30 | ⚠️ |
| 依赖锁定 (pinned ==) | 0/39 | >80% | ❌ |

**God Module 分布**:
- gbrain TS: ~25 文件 (最大 doctor.ts 4825L, postgres-engine.ts 4514L)
- omo tests: ~10 文件 (最大 test_omo_automation.py 5637L)
- omo src: 3 文件违规 (omo_cards.py 1107L, omo_worker_promotion.py 1067L, omo_audit.py 1025L)
- bin/: 2 文件 (agent-workflow.py 2327L, governance-evolution.py ~1500L)

**关键矛盾**: omo 自己的 lint 规则 (800L error) 自己有 3 个文件违规。gbrain TS 文件 CI lint 不可见。

### B. 测试健康

| 项目 | 测试数 | 通过 | 失败 | 跳过 | 覆盖评估 |
|------|--------|------|------|------|----------|
| omo | 1003 | 762 | 0 | 241 | 中 (bin/ 9% 覆盖) |
| ecos | 880 | 877 | 0 | 3 | 高 |
| agora | 168 | 168 | 0 | 0 | 高 |
| aetherforge | 51 | 51 | 0 | 0 | 中 |
| l4-kernel | ~100 | ~100 | 0 | 0 | 中 |
| metaos | 216 | 216 | 0 | 0 | 高 |
| gbrain | ~1300 | ? | ? | ? | 需 Postgres |
| cockpit-ui | 0 | - | - | - | ❌ 零测试 |
| family-hub | ~5 | ~5 | 0 | 0 | ❌ 仅 MCP |

**bin/ 工具测试覆盖**: 8/85 有测试 (9%)。关键盲区: `gac-local-gate.py` (核心门禁), `ssot-guardian.py`, `doc-ssot-lint.py`, `compass_radar.py` 均无测试。

### C. CI/CD Pipeline

| 指标 | 数值 | 状态 |
|------|------|------|
| 工作流总数 | 38 | ✅ (近期清理 40→37→38) |
| @main/@latest 引用 | 0 | ✅ |
| permissions: block | 6/38 | ⚠️ (4 个 git push 已加) |
| CROSS_REPO_TOKEN 依赖 | 34/38 | 预期 (子模块架构) |
| curl\|bash 未校验 | 2 处 | ⚠️ |
| publish-pypi tags+paths AND | 1 处 | ❌ 静默失败风险 |

### D. 治理状态

| 指标 | 数值 | 状态 |
|------|------|------|
| Phase / Wave | 42 / W3 | ✅ |
| health_score | 80/100 | ⚠️ 虚高 (2 服务 stale) |
| planned / done tasks | 14 / 267 | ✅ |
| ADRs | 82 (全部 ACCEPTED/SUPERSEDED) | ✅ |
| 治理 initiative 进度 | 8 个全 ?% | ❌ 未填充 |
| stale 服务 | 2 个 (26 天) 标 healthy | ❌ |
| .omo/ 大小 | 28MB | ✅ |

### E. 安全

| 检查项 | 结果 | 状态 |
|--------|------|------|
| 硬编码密钥 | 0 (仅 archive 脚本有 env var 引用) | ✅ |
| .env 被 git 跟踪 | 0 | ✅ |
| shell=True | 0 | ✅ |
| eval() 调用 | 0 | ✅ |
| 依赖锁定 | 0/39 pinned | ❌ |
| pip-audit 配置 | 无 | ⚠️ |

### F. 文档

| 检查项 | 结果 | 状态 |
|--------|------|------|
| doc-ssot 冲突 | 0 (105 文件) | ✅ |
| >90 天 stale 文档 | 0 | ✅ |
| v5/5+3+1 残留 | 0 (活跃文档) | ✅ |
| .md 文件总数 | 876 (docs 34, _knowledge 807, standards 35) | ✅ |

### G. 架构

| 检查项 | 结果 | 状态 |
|--------|------|------|
| 子模块状态 | 17 全 clean | ✅ |
| gbrain 分支 | eval tag (非 main) | ⚠️ |
| ecos→omo 跨层 import | 3 处 (SSOT bridge, 已知设计) | ✅ |
| omo→ecos 跨层 import | 0 | ✅ |
| v5 引用 | 仅 l4-kernel 域迁移逻辑 (合法) | ✅ |

### H. 基础设施

| 指标 | 数值 | 状态 |
|------|------|------|
| kairon 大小 | 2.3GB (6.6x 次大项目) | ⚠️ |
| git packed | 138MB, 0 garbage | ✅ |
| Makefile targets | 46 | ✅ |
| bin/ 孤儿脚本 | 71/85 (未被 Makefile/CI 引用) | ⚠️ |
| ci-local-fast 检查项 | 4 (缺 shellcheck/actionlint) | ⚠️ |

## 4. TOP 5 系统性风险 (跨维度)

| # | 风险 | 影响维度 | 严重度 | 根因 |
|---|------|----------|--------|------|
| 1 | 依赖零锁定 | A+E+H | High | 39 个 Python 依赖全 floating, 无 lockfile, 无 pip-audit |
| 2 | bin/ 工具测试盲区 | B+D | High | 85 个工具仅 9% 有测试, gac-local-gate 无测试 |
| 3 | 状态监控空窗 | D | Medium | 2 服务 26 天 stale 标 healthy, initiative 进度全空 |
| 4 | God Module 系统性 | A | Medium | 81 文件 >800L, omo 违反自身规则, TS CI 不可见 |
| 5 | 发布管道隐患 | C+E+G | High | publish-pypi tags+paths AND + curl\|bash + gbrain 分叉 |

## 5. 近期修复效果 (2026-06-29 ~ 2026-07-01)

| 轮次 | 修复数 | 主要内容 |
|------|--------|----------|
| Round 3 | 8 项 | PANORAMA/ toolbox/ .env/ port 9100/ project-registry |
| Round 4 | 15 项 | action 版本统一/ permissions/ v5→v6/ .PHONY/ pre-commit 清理 |
| CI 审计 | 6 BUG + 3 DEAD + 7 path filters + MOF L0 | 40→37 workflows, 删死工作流, 加路径过滤 |
| 治本修复 | 29 处 grep+pipefail + 目录卫生 + 架构一致性 | 全量扫描同模式 bug |
| 单元测试 | 35 failures → 0 | omo 28 + ecos 7, 7 类根因全治本 |
| ci-local | make ci-local + pre-push hook | 4 项检查 6.5s, 拦 90% CI 失败 |

**效果**: F(文档) 9→9 分, G(架构) 7→9 分, C(CI) 6→8 分, E(安全) 7→8 分。A/B/D 未触及。

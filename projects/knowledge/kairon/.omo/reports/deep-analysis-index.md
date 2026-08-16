---
title: deep-analysis-index
type: doc
status: active
---

# 代码深度分析索引

> 分析日期: 2026-06-02
> 分析人: general-purpose-1 agent
> 范围: kairon monorepo 5 个未深度分析包

---

## 包分析报告列表

| 包 | 分析文件 | 版本 | 源码行数 | 模块数 | 测试数 | 关键发现 |
|----|---------|------|---------|-------|-------|---------|
| **shared-lib** | [deep-analysis-shared-lib.md](deep-analysis-shared-lib.md) | v0.1.0 | 21,359 | 76 | 24 | pyproject.toml 缺失 build-system；76个模块远超"共享库"范畴 |
| **ecos** | [deep-analysis-ecos.md](deep-analysis-ecos.md) | v0.6.0 | 3,870 | 16 | 12 | **严重**: 测试文件存在 SyntaxError (`from ecos.ssb_auth as auth`)  |
| **forge** | [deep-analysis-forge.md](deep-analysis-forge.md) | v1.3.0 | 7,062 | 23 | 11 | 唯一 v1.x 版本，功能最丰富；测试用 sys.path 绕过包命名空间 |
| **eu-pricing** | [deep-analysis-eu-pricing.md](deep-analysis-eu-pricing.md) | v0.1.0 | 364 | 3 | 3 | **严重**: 虚假依赖 `core-models` 会导致安装失败 |
| **wksp** | [deep-analysis-wksp.md](deep-analysis-wksp.md) | v0.2.0 | 4,850 | 17 | 40 | 测试在 src/ 内是设计决策；40 个测试文件覆盖全面 |

---

## 严重性排序

### 严重问题（影响构建或运行）

| 优先级 | 包 | 问题 | 文件路径 |
|--------|-----|------|---------|
| P0 | ecos | 测试文件 `from ecos.ssb_auth as auth` 语法错误 (12处) | `tests/test_core.py`, `tests/test_e2e_baseline.py` |
| P0 | ecos | 测试引用不存在的模块 (integrate_pipeline, critic_auto_trigger) | 同上 |
| P0 | eu-pricing | 虚假依赖 `core-models` 导致 `pip install` 失败 | `pyproject.toml:6` |
| P1 | shared-lib | 缺少 `[build-system]` 无法构建 | `pyproject.toml` |
| P1 | shared-lib | 缺少 `[tool.pytest.ini_options]` | `pyproject.toml` |

### 中等问题

| 包 | 问题 | 建议 |
|-----|------|------|
| forge | 测试使用 sys.path 而非标准包导入 | 改用 `from forge import asset_cli as m` |
| forge | 无生产依赖声明 | 审查并补全 `[project.dependencies]` |
| eu-pricing | DEFAULT_PRICING 重复且类型不一致 | 统一到 energy_model.py |
| ecos | SQLite 数据库在源码目录下 | 迁移到 `~/.kairon/` 或 `data/` |
| ecos | 硬编码路径 | 改为配置驱动 |

### 建议优化

| 包 | 建议 |
|-----|------|
| shared-lib | 76 个模块按领域拆分子包 (governance/cognition/audit) |
| shared-lib | 补充 README |
| forge | 23 个平铺模块可考虑重组（entropy/cron/graph 子包） |
| forge | 数据文件统一管理（JSON 注册表文件过多） |
| ecos | 补充 README 内容 |
| wksp | 考虑测试标准位置迁移 + conftest 简化 |

---

## 包对比概要

```
规模对比（源码行数）:
shared-lib  ████████████████████████████████████ 21,359
forge       ██████████████                         7,062
wksp        ██████████                             4,850
ecos        ███████                                3,870
eu-pricing  ▋                                        364

版本对比:
forge     v1.3.0  (稳定版)
ecos      v0.6.0  (发展中)
wksp      v0.2.0  (早期)
shared-lib v0.1.0 (新建)
eu-pricing v0.1.0 (新建)

测试密度（测试行/源码行）:
wksp       1.87x  (9062 / 4850)
ecos       0.53x  (2055 / 3870)
forge      0.55x  (3877 / 7062)
shared-lib  <0.1x  (少量测试在大源码基数下)
eu-pricing  ~0.5x  (测试行约源码一半)
```

---

## 总结

1. **ecos 是最危急的包** — 测试文件中的语法错误和虚假模块引用意味着整个测试套件无法运行，也没有 CI 发现这个问题。

2. **eu-pricing 小而精但有毒依赖** — 代码质量不错（3 个模块各司其职），但 `core-models` 虚假依赖会阻止任何安装尝试。

3. **shared-lib 规模膨胀** — 76 个模块 / 21K 行代码严重超出"共享库"的合理边界，建议按领域拆分为多个子包。

4. **forge 最成熟** — 唯一 v1.x 版本，完善的 README，294 个测试。主要问题是标准化的导入方式和依赖管理。

5. **wksp 测试覆盖最好** — 测试/源码比 1.87x，40 个测试文件覆盖面广。测试在 src/ 内的设计决策有合理考量，但需要文档说明。

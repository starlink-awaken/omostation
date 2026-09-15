---
title: deep-analysis-eu-pricing
type: doc
status: active
---

# 深度分析：eu-pricing (packages/eu-pricing/)

## 1. 包定位与职责

**名称**: `eu-pricing` (v0.1.0)
**描述**: "EU (Energy Unit) virtual resource accounting — L2 capability layer"
**入口**: `src/eu_pricing/` 包

eu-pricing 是 L2 能力层的**虚拟资源记账系统**，管理 Pipeline 操作的能量单元（EU）消耗。

包含 3 个模块（共 364 行代码）：

| 模块 | 行数 | 职责 |
|------|------|------|
| `energy_model.py` | 83 | 数据模型层：`ResourceType` 枚举、`EnergyEntry`/`EnergyBudget` dataclass、默认定价表 |
| `ledger.py` | 155 | 核心账务逻辑：`EULedger` 类通过 Agora MCP 查询/消费 EU 余额 |
| `cli.py` | ~120 | CLI 入口：`balance`, `consume`, `pricing` 命令 |
| `__init__.py` | 1 | 仅 docstring |

**Phase 17 D_Economy 迁移分析**:
- `energy_model.py` 是从 SharedBrain 的 D_Economy 提取的（`ledger.py:1` docstring 提到）
- 提取了纯净的数据模型（无 BaseMembrane/PersistenceProvider 依赖），符合零耦合设计
- 与 `ledger.py` 中的 `DEFAULT_PRICING` 有重复定义（对比 `energy_model.py:74-83` 和 `ledger.py:20-27`）— 两处都有相似但不完全相同的定价表
- `ledger.py` 的 `DEFAULT_PRICING` 有 6 项，`energy_model.py` 的 `DEFAULT_PRICING` 有 8 项（多了 `agora_route` 和 `codeanalyze_scan`）

**需要注意**: `energy_model.py` 的 `DEFAULT_PRICING` 使用了 float 类型（`10.0`, `0.5`），而 `ledger.py` 的 `DEFAULT_PRICING` 使用了 int 类型（`10`, `1`）。这种类型不一致可能在精度敏感的计费场景中导致问题。

## 2. 代码质量评估

| 指标 | 数值 |
|------|------|
| Python 源文件 | **3 个** (src/eu_pricing/*.py) |
| 总代码行数 | **~364 行** |
| README | 存在（17 行，包含 CLI 用法和集成说明） |
| pyproject.toml | 极简（仅 name/version/description/requires-python/dependencies/build-system） |
| CLI entry | `eu-pricing = "eu_pricing.cli:main"` |

**问题**:
- `pyproject.toml` 声明了 `dependencies = ["core-models"]`，但 `core-models` 并**未部署到 PyPI**，也不存在于 kairon monorepo 其他包中。这会导致 `pip install` 失败。
- 缺少 `[tool.pytest.ini_options]` — 测试路径未显式配置
- 缺少 `[tool.hatch.build.targets.wheel]` — 构建目标未配置（但 `pyproject.toml` 有 `[build-system]`）
- `pyproject.toml` 的 `[build-system]` 节放置在文件末尾（第 11-13 行），不符合 TOML 惯例（应位于文件开头）

## 3. 依赖分析

**外部依赖**:
- `core-models` — 声明在 `pyproject.toml` 中，但实际**不存在**于任何可访问的仓库中

**实际代码依赖**:
- `ledger.py:15` 使用 `urllib.request.Request, urlopen` — 标准库，无外部依赖
- `energy_model.py` — 仅标准库（dataclasses, enum, typing, Any）
- `cli.py` — 预期使用标准库（未完全读取）

**问题**: eu-pricing 实际上**不需要任何外部依赖**就可以工作。`core-models` 是一个虚假声明。

## 4. 测试覆盖

| 指标 | 数值 |
|------|------|
| 测试文件数 | **3 个** (tests/*.py) |
| 测试总行数 | ~150-200 行 |
| 测试框架 | pytest（有 conftest.py） |

**测试文件**:
- `test_ledger.py` — 3 个测试，覆盖 consume 成功、余额不足/blocked、未知操作默认成本
- `test_energy_model.py` — 6 个测试，覆盖 budget 初始余额、can_afford、consume 成功/失败、to_dict、枚举值、默认定价
- `conftest.py` — 将 `src/` 加入 sys.path

**运行状态**: 任务说明称 10 个测试全通过。3 个测试文件 × 平均 3-6 个测试 = 约 9-10 个测试，吻合。

**测试质量**: 测试简洁、覆盖核心路径、使用 monkeypatch 模拟外部依赖。`test_ledger.py` 的 mock 设计清晰。

## 5. 架构建议

1. **严重: 虚假依赖声明**: `dependencies = ["core-models"]` 在 `pyproject.toml` 中会导致安装失败。应删除该声明，因为模块实际不依赖此包。

2. **补全 pyproject.toml**:
   - 移动 `[build-system]` 到文件开头
   - 添加 `[tool.hatch.build.targets.wheel] packages = ["src/eu_pricing"]`
   - 添加 `[tool.pytest.ini_options] testpaths = ["tests"]; pythonpath = ["src"]`

3. **统一 DEFAULT_PRICING**: `energy_model.py:74-83` 和 `ledger.py:20-27` 有重复的定价表，且类型不一致（float vs int）。建议将定价表集中在 `energy_model.py` 中由 `ledger.py` 导入。

4. **数据模型与账务逻辑的职责划分**: 当前 `energy_model.py` 是纯数据模型（提取自 D_Economy），`ledger.py` 是服务层（通过 Agora MCP 通信）。这个分离是合理的，但定价表放在哪个层需要明确决定。

5. **Phase 17 迁移完整性**: `energy_model.py` 已成功提取，但需要确认 SharedBrain D_Economy 中是否还有其他需要迁移的数据模型（如 `ResourceQuota`、`SubscriptionPlan` 等）。

6. **包版本 v0.1.0 的含义**: 作为新建立的包，v0.1.0 是合理的起始版本。但如果要在生产中使用，建议在 API 稳定后升至 v1.0.0。

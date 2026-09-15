---
title: deep-analysis-ecos
type: doc
status: active
---

# 深度分析：ecos (packages/ecos/)

## 1. 包定位与职责

**名称**: `ecos` (v0.6.0)
**描述**: "eCOS — 认知层：SSB 签名链、涌现度量、认知监控"
**入口**: `src/ecos/` 包

eCOS (Ecosystem Cognitive Operating System) 是 kairon 的**认知 OS 生态层**，核心职责包括：

**核心子系统** (`src/ecos/core/`):
- `ssb_client.py` — SSB（Shared Semantic Bus）客户端：双写 SQLite + File，是 eCOS 的事件总线基础
- `ssb_auth.py` — HMAC-SHA256 事件签名/验证（Phase 4, v1.1）
- `ssb_init.py` — SSB 数据库初始化
- `ssb_dump.py` — SSB 数据导出
- `ssb_integrity.py` — SSB 完整性校验
- `ssb_schema_migrate.py` / `ssb_seq_migrate.py` — 数据库迁移
- `calc_emergence.py` / `emergence_auto.py` / `emergence_watch.py` — 涌现度量计算
- `snapshot_emergence.py` — 涌现快照
- `common.py` — 共享基础设施（常量、建表 SQL、时间工具）

**CLI 工具** (`src/ecos/cli/`):
- `dashboard.py` — 认知监控面板
- `scheduler.py` — 定时任务调度器
- `watchdog.py` — 后台看门狗

**外部监控** (`src/ecos/`):
- `kos_health_monitor.py` — KOS 健康监控

**数据存储**: `src/ecos/LADS/ssb/ecos.db` — SQLite 数据库（硬编码路径在 `common.py:17-19`）

## 2. 代码质量评估

| 指标 | 数值 |
|------|------|
| Python 源文件 | **16 个** (ecos/ ×3, core/ ×10, cli/ ×3) |
| 总代码行数 | **~3,870 行** |
| 子结构 | `core/` (主要模块), `cli/`, `LADS/ssb/` (数据库) |
| README | 存在但内容为空（仅 `# ecos` 标题） |
| pyproject.toml | 完整（hatchling 构建，4 个外部依赖，3 个 CLI entry points） |
| pytest 配置 | 已配置 `testpaths = ["tests"]`, `pythonpath = ["src"]` |

**关注点**:
- 硬编码数据库路径：`common.py:17-19` 使用 `Path(__file__).resolve().parent.parent / "LADS" / "ssb" / "ecos.db"`
- `ssb_auth.py` 也硬编码了 `KEY_FILE` 和 `DB_PATH` (`ssb_auth.py:17-18`)
- SQLite 数据库文件 (`src/ecos/LADS/ssb/ecos.db`) 存放在源码目录下，不应受版本控制

## 3. 依赖分析

**外部依赖** (`pyproject.toml`):
- `pyyaml>=6.0`
- `requests>=2.28`
- `beautifulsoup4>=4.12`
- `jinja2>=3.1`

**内部依赖**: 无，ecos 是一个独立包，不依赖 kairon 其他包。

**实际情况**: 查看源码后发现 `ssb_client.py`, `ssb_auth.py` 等核心模块均使用标准库（`sqlite3`, `hashlib`, `hmac`, `json`, `pathlib` 等）。上述 4 个外部依赖可能在 `kos_health_monitor.py` 或 `cli/` 模块中使用。

## 4. 测试覆盖

| 指标 | 数值 |
|------|------|
| 测试文件数 | **12 个** (tests/*.py) |
| 测试总行数 | **~2,055 行** |
| 额外测试脚本 | `T7-crash-recovery-test.py`, `T8-committee-error-test.py`, `redteam-v3.py`（非 pytest 格式） |
| 测试框架 | pytest（已配置 `conftest.py` 和 `[tool.pytest.ini_options]`） |

**严重问题 — 语法错误**: 多个测试文件包含 Python 语法错误：

- **`test_core.py`** 和 **`test_e2e_baseline.py`**: 使用了 `from ecos.ssb_auth as auth` 语法
  - **问题**: Python 的 `from X import Y as Z` 语法不允许使用 `from X as Y` 形式。正确写法应为 `from ecos.core.ssb_auth import verify as auth` 或使用 `import ecos.core.ssb_auth as auth`
  - 影响文件: `test_core.py` (6 处), `test_e2e_baseline.py` (6 处)
  - 此外还引用了不存在的模块: `ecos.integrate_pipeline`, `ecos.critic_auto_trigger`, `ecos.ssb_dump`
  - **这些模块名是顶层导入形式，但实际模块在 `ecos.core.*` 子包中**

- **`test_core_extended.py`**, **`test_core_unit.py`**, **`test_phase9_push.py`**, **`test_redteam_v3.py`** — 大量 `__pycache__` 文件存在说明之前运行过，但未查看实际内容

**结论**: 这些测试文件大概率**无法通过语法检查**。所有 `from ecos.xxx as yyy` 形式的语句都会引发 `SyntaxError`。

## 5. 架构建议

1. **严重: 修复测试文件语法错误**: `test_core.py` 和 `test_e2e_baseline.py` 中存在 12 处 `from ecos.xxx as yyy` 语法错误。需要将 `from ecos.ssb_auth as auth` 改为正确的 `from ecos.core.ssb_auth import auth` 或 `import ecos.core.ssb_auth as auth`。

2. **严重: 引用不存在的模块**: 测试文件中引用的 `ecos.integrate_pipeline`, `ecos.critic_auto_trigger`, `ecos.ssb_dump` 并不存在于当前 `src/ecos/` 结构中（它们可能在 SharedBrain 中有对应文件但未提取到 ecos）。需要在测试文件中修正这些 import，或补充缺失模块。

3. **数据库文件隔离**: `src/ecos/LADS/ssb/ecos.db` 应迁移到标准位置（如 `~/.kairon/` 或 `data/`），源码目录不应包含运行时数据。

4. **硬编码路径**: `common.py` 和 `ssb_auth.py` 中的硬编码路径应改为配置驱动（环境变量或配置文件）。

5. **README 为空**: `README.md` 仅有标题，需要补充项目说明、架构设计和用法文档。

6. **外部依赖未充分利用**: 声明的 4 个外部依赖（pyyaml, requests, beautifulsoup4, jinja2）未在前述核心模块中使用，可能存在使用这些依赖的额外脚本未纳入版本控制，或这些依赖已不再被需要但仍声明。

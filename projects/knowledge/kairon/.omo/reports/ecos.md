---
title: ecos
type: doc
status: active
---

# 深度分析: ecos

**分析日期:** 2026-06-02
**分析阶段:** Phase 3.4

## 基本信息

- **模块名:** `ecos`
- **成熟度:** alpha
- **版本:** 0.6.0
- **描述:** eCOS — 认知层：SSB 签名链、涌现度量、认知监控
- **责任人:** null
- **代码行数:** 3,870 行 (19 个 .py 文件)
- **测试行数:** 2,055 行 (12 个测试文件，含红队测试)
- **构建后端:** hatchling

## 代码结构

```
src/ecos/
├── __init__.py                # 1 行 — 从 core 重新导出
├── kos_health_monitor.py      # 120 行 — KOS 健康监控
├── cli/
│   ├── __init__.py            # 0 行 (空)
│   ├── dashboard.py           # 365 行 — CLI 仪表板
│   ├── scheduler.py           # 308 行 — CLI 调度器
│   └── watchdog.py            # 245 行 — CLI 看门狗
└── core/
    ├── __init__.py            # 0 行 (空)
    ├── common.py              # 94 行 — 共享基础设施 (DB, TZ 常量, 连接工厂)
    ├── ssb_auth.py            # 144 行 — HMAC 事件签名/验证
    ├── ssb_client.py          # 696 行 — SSB 客户端 (最大文件)
    ├── ssb_init.py            # 220 行 — SSB 初始化
    ├── ssb_dump.py            # 41 行 — SSB 数据导出
    ├── ssb_integrity.py       # 101 行 — SSB 完整性检查
    ├── ssb_schema_migrate.py  # 98 行 — SSB 模式迁移
    ├── ssb_seq_migrate.py     # 330 行 — SSB 序列迁移
    ├── calc_emergence.py      # 105 行 — 涌现计算
    ├── emergence_auto.py      # 408 行 — 自动涌现
    ├── emergence_watch.py     # 254 行 — 涌现监控
    └── snapshot_emergence.py  # 340 行 — 涌现快照
```

### 架构模式

- **SSB 签名链基础设施** — 基于 HMAC-SHA256 的事件签名验证系统 (`ssb_auth.py`)
- **SQLite 事件存储** — 通过 `common.py` 定义 `ssb_events` 表结构，所有 SSB 模块共享
- **CLI 入口** — `pyproject.toml` 声明了 3 个 CLI 命令 (`ecos-ssb`, `ecos-dashboard`, `ecos-scheduler`)
- **涌现计算** — 多个 `emergence_*` 模块实现认知涌现度量

### CLI 命令入口
```toml
[project.scripts]
ecos-ssb = "ecos.core.ssb_client:main"
ecos-dashboard = "ecos.cli.dashboard:main"
ecos-scheduler = "ecos.cli.scheduler:main"
```

## 依赖分析

### 外部依赖 (第三方库)
```
pyyaml>=6.0
requests>=2.28
beautifulsoup4>=4.12
jinja2>=3.1
```

### 内部依赖 (包内引用)
- `ecos.core.common` — 被所有 core 模块引用 (提供 `get_conn`, `now_iso`, 常量)
- `ecos.core.ssb_auth` — 被 ssb_client, ssb_init 引用
- `ecos.__init__` — 从 `ecos.core` 重新导出

### 断裂的 import (仅存在于测试中，非源码)
测试文件 `test_core.py` 中存在严重的 Python 语法错误:

```
Line 58:  from ecos.ssb_auth as auth              # ❌ 无效语法
Line 67:  from ecos.ssb_auth as auth              # ❌ 无效语法
Line 75:  from ecos.ssb_auth as auth              # ❌ 无效语法
Line 88:  from ecos.ssb_auth as auth              # ❌ 无效语法
Line 98:  from ecos.ssb_auth as auth              # ❌ 无效语法
Line 110: from ecos.ssb_auth as auth              # ❌ 无效语法
Line 228: from ecos.ssb_auth                      # ❌ 缺少 import 关键字
Line 229: from ecos.realtime_guard                # ❌ 缺乏 import 关键字
Line 231: assert hasattr(scripts.ssb_auth, ...)   # ❌ scripts 未定义
```

**根因:** `from ... import ... as ...` 是正确形式，但文件写成了 `from ... as ...` 格式。`ssb_auth` 实际在 `ecos.core.ssb_auth` 路径，但 `ecos/__init__.py` 重新导出了它，因此 `from ecos.ssb_auth` 寻址正确，只是语法错误。

**修复方式:** 全部替换为:
```python
from ecos.core import ssb_auth as auth
```

此外，`test_core.py` 引用了 `realtime_guard` 模块 (第 138 行: `from ecos.realtime_guard import check`)，但源码中不存在此文件 (`src/ecos/` 下无 `realtime_guard.py`)。

### 断裂引用
| 断裂路径 | 说明 | 位置 |
|---------|------|------|
| `from ecos.ssb_auth as auth` | 无效 Python 语法，应为 `from ecos.core import ssb_auth as auth` | `test_core.py` x6 |
| `from ecos.ssb_auth` (无 import) | 无效 Python 语法 | `test_core.py:228` |
| `from ecos.realtime_guard` (无 import) | 无效语法 + 该模块不存在 | `test_core.py:229` |
| `from ecos.realtime_guard import check` | 该模块在源码中不存在 | `test_core.py:138` |
| `scripts.ssb_auth` | `scripts` 变量未定义 | `test_core.py:231` |

## 测试分析

### 测试文件: 12 个文件, 2,055 行
```
tests/
├── conftest.py                  # 8 行 — 添加 scripts/ 到 sys.path
├── test_imports.py              # 23 行 — 基础导入验证 (语法正确)
├── test_core.py                 # 263 行 — 核心测试 (含语法错误)
├── test_core_unit.py            # 163 行 — 单元测试 (语法正确)
├── test_core_extended.py        # 159 行 — 扩展测试 (语法正确)
├── test_e2e_baseline.py         # 376 行 — E2E 基线测试
├── test_kos_health_monitor.py   # 164 行 — KOS 健康监控测试
├── test_phase9_push.py          # 139 行 — Phase 9 推送测试
├── test_redteam_v3.py           # 318 行 — 红队测试 v3
├── redteam-v3.py                # 125 行 — 红队脚本
├── T7-crash-recovery-test.py    # 215 行 — 崩溃恢复测试
└── T8-committee-error-test.py   # 102 行 — 委员会错误测试
```

### 当前状态: 2 collection errors (SyntaxError)
pytest 在收集阶段立即失败，因为 `test_core.py` 包含多处无效 Python 语法 (`from ecos.ssb_auth as auth`)。Python 解析器在编译测试文件阶段就抛出 `SyntaxError`。

### 修复测试的必要条件
1. **修复 `test_core.py` 中的语法错误:**
   - `from ecos.ssb_auth as auth` → `from ecos.core import ssb_auth as auth` (6 处)
   - `from ecos.ssb_auth` → `from ecos.core import ssb_auth` (1 处)
   - `from ecos.realtime_guard` → `from ecos.core.realtime_guard import ...` — 但 `realtime_guard` 不存在，需确认是否是迁移中遗漏
   - `scripts.ssb_auth` → `ssb_auth` (去除未定义的 `scripts.` 前缀)
2. 确认 `realtime_guard` 模块是否应存在于 `src/ecos/core/` 中

### 其他测试文件质量
- **`test_core_unit.py`:** 语法正确、引用路径正确，质量高
- **`test_core_extended.py`:** 语法正确，但引用了 `ecos.constitution_watcher`, `ecos.email_sender`, `ecos.planner`, `ecos.content_integrity`, `ecos.emergence_watch` — 这些模块在 `src/ecos/` 下不存在（可能在 `scripts/` 中）
- **`test_imports.py`:** 正确使用 `from ecos.core import calc_emergence, common, ssb_client` — 这是正确的导入形式
- `conftest.py` 将 `scripts/` 加入 `sys.path`，暗示部分模块在 `scripts/` 目录而非 `src/ecos/` 中

### 覆盖率估算: **中偏低**
- `ssb_auth.py` — 有较多测试覆盖（test_core.py 含语法错误但 test_core_unit.py 有正确测试）
- `core/common.py` — 被部分覆盖
- `core/ssb_client.py` — 无专用测试（最大文件 696 行）
- `emergence_*`, `ssb_seq_migrate`, `ssb_schema_migrate`, `ssb_dump` — 无测试
- CLI 模块 (`cli/*`) — 无测试

## 安全分析

### 关键安全问题

1. **HMAC 签名密钥文件权限 (中低):** `ssb_auth.py` 设置密钥文件权限为 `0o600` (仅所有者可读写)，做法正确。但未加密密钥文件内容。

2. **环境变量密钥泄露风险 (中):** `ssb_auth.py` 支持通过 `SSB_KEY` 环境变量传递密钥:
   ```python
   env_key = os.environ.get("SSB_KEY", "")
   ```
   环境变量可能通过子进程泄露或 `ps aux` 暴露（启动时）。

3. **SQLite 注入防护不足 (中):** `ssb_auth.py` 和 `common.py` 中 SQLite 操作使用参数化查询，安全性较好。但 `ssb_auth.verify()` 的部分查询中仍有直接参数拼接。

4. **硬编码文件路径 (低):** 多文件假设特定数据目录结构 (`LADS/ssb/ecos.db`)，部署时路径不一致会导致崩溃。

5. **无输入验证 (中):** `compute_signature()` 直接拼接参数 `f"{seq}|{event_id}|{agent}|{payload or ''}"`，无长度/格式验证。

6. **`os.urandom(32)` 使用 (安全):** 密钥生成使用加密安全的随机源，做法正确。

## 已知债务

### 严重 (阻塞使用)
1. **[BROKEN] `test_core.py` 语法错误** — `from ecos.ssb_auth as auth` (无效 Python) 导致所有 pytest 无法运行
2. **[BROKEN] `realtime_guard` 模块不存在** — `test_core.py` 引用了一个不存在的模块

### 中等
3. **`ecos/__init__.py` 近似空** — 仅 1 行，且导入多个模块但不导出到 `__all__`
4. **测试引用 `scripts/` 目录** — 部分测试依赖 `scripts/` 目录下的模块，但 `scripts/` 不是已安装包的一部分
5. **部分测试假设外部文件/目录** — `test_core.py` 中的集成测试引用 `STATE.yaml`, `LADS/cross_refs.jsonl` 等外部资源
6. **`test_core_extended.py` 引用不存在的模块** — `constitution_watcher`, `email_sender`, `planner`, `content_integrity` 等可能仅在 `scripts/` 中
7. **缺少错误处理文档** — 各模块的异常情况未文档化

### 轻微
8. **`cli/__init__.py` 和 `core/__init__.py` 为空** — 可用作扩展点
9. **硬编码路径** — `ECOS_HOME`, `SSB_DB_PATH` 通过 `__file__` 推导，对测试和部署不灵活
10. **无 CI 配置** — pyproject.toml 无 ruff/pytest 配置
11. **README.md 存在但未读取** — pyproject.toml 引用 `readme = "README.md"`

## 建议

### 短期改进 (Phase 3)
1. **立即修复 `test_core.py` 语法错误:** 将所有 `from ecos.ssb_auth as auth` 改为 `from ecos.core import ssb_auth as auth`
2. **确认并创建/删除 `realtime_guard`** — 检查 `scripts/` 中是否存在此模块，决定是否迁移至 `src/ecos/`
3. **运行 pytest 验证基本测试通过**
4. **添加 `[tool.pytest.ini_options]` 完整配置** — 已部分存在，确保 `pythonpath = ["src"]` 生效

### 中期改进 (Phase 4)
5. **迁移脚本模块:** 将 `scripts/` 中的核心模块迁移至 `src/ecos/`，使测试不依赖包外目录
6. **补全测试覆盖:** `ssb_client.py` (696 行, 零测试)、`emergence_*` 系列模块
7. **安全加固:**
   - 移除环境变量密钥加载或增加警告
   - 统一 SQLite 参数化查询模式
   - 增加输入长度/格式验证
8. **配置化路径:** 将硬编码路径改为可配置
9. **添加 CI 配置:** ruff lint, pytest 自动化

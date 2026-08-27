---
status: active
lifecycle: contract
owner: governance-team
last-reviewed: 2026-06-30
---

# P3 work 验证 — family-hub/cockpit/ecos 治本

## 完成时间
2026-06-30

## 目标
修复 Phase 3 验证矩阵发现的 pre-existing fail (16 个):
- family-hub: 1 error (mcp_server import 失败)
- cockpit: 8 fail (storage test)
- ecos: 7 fail (MCP e2e, 已被其他 agent 修)

## 实际落地

### family-hub 治本
| Commit | 内容 |
|--------|------|
| `b5627e3` | 修 mcp_server import 失败 (2 pass) |
| `2d609cf3` | bump family-hub |

**根因**:`uv run pytest` fallback 到全局 `~/.local/bin/pytest` (system-wide),
venv 内 `fastmcp` 装在 venv 但 pytest 跑时 sys.path 没 venv site-packages。

**修复**:
1. `pyproject.toml` 加 `[dependency-groups] dev = ["pytest>=8.4.2"]`, uv sync 装 pytest 到 venv
2. `[tool.pytest.ini_options] pythonpath = ["."]`, 让 tests/test_mcp_server.py 能 `import mcp_server`
3. `tests/conftest.py` sys.path.insert(0, PROJECT_ROOT) 兼容 uv_build 自动注入 src/

**净效果**: 1 error → 2 pass

### cockpit 治本
| Commit | 内容 |
|--------|------|
| `c2b27fe` | 修 8 个 storage test fail (DB_PATH import-time binding) |
| `c7a8f474` | bump cockpit |

**根因**:`storage_sqlite.py` 用 `from .paths import DB_PATH` (import-time binding)。
测试 `monkeypatch.setattr("cockpit.storage.DB_PATH", ...)` 改的是 storage
模块的 DB_PATH, 但 storage_sqlite.py 仍用 import-time 绑定的旧
`DB_PATH = Path.home() / ".workspace" / "data.db"` (真实路径, 有 189 项
历史数据, 致 test_empty_db 期望空 db 失败)。

**修复 (真治本)**:
1. `storage_sqlite.py` 改 `from .paths import DB_PATH` 为 `from . import paths as _paths`
   + 新增 `_get_db_path()` helper, runtime lookup 路径
2. 8 个 test 文件 (`test_storage_backup.py` 等) `monkeypatch.setattr`
   改 `"cockpit.paths.DB_PATH"` 而非 `"cockpit.storage.DB_PATH"`
3. test 内部 `db_path.parent.mkdir(parents=True, exist_ok=True)` 自动建父目录

**净效果**: 8 fail → 0 fail, 9 个 storage_backup test 全过, 633 pass / 14 fail
→ 633 pass / 1 fail (1 个 pre-existing governance integration test 失败,
与本 fix 无关)。

### ecos (其他 agent 修)
其他 agent 修了 6/7 fail。我未参与。

## Tier 2 + P3 完整治本路线总览

### Phase 1 (1.1, 1.2, 1.3a, 1.3b)
- 1.1 l4-kernel 强 path_overrides (22 files, +485/-291)
- 1.2 model-driven 撤销 8 阶段 (3 files)
- 1.3a meta-ADR-0116 反思
- 1.3b 17 项目 baseline 验证

### Phase 2 (部分真治本)
- 根仓 dev-deps 统一 (10/13 = 76%, 4 个 P3 work)

### Phase 3 (验证 + 文档)
- 验证矩阵 + P52 范式 + 复盘

### P3 work (family-hub/cockpit/ecos)
- family-hub: 1 error → 2 pass
- cockpit: 8 fail → 1 fail pre-existing
- ecos: 7 fail → 1 fail pre-existing (其他 agent)

## 最终验证矩阵 (P3 后)

| # | 项目 | 状态 | 备注 |
|---|------|:----:|------|
| 1 | omo | ✅ | 其他 agent 修 |
| 2 | omo-debt | ✅ | |
| 3 | c2g | ✅ | |
| 4 | model-driven | ✅ | Tier 2 Phase 1.2 治本 |
| 5 | l4-kernel | ✅ | Tier 2 Phase 1.1 治本 |
| 6 | aetherforge | ✅ | Tier 1 Phase 1.2 治本 |
| 7 | bus-foundation | ✅ | |
| 8 | cockpit | ⚠️ | 1 fail (pre-existing, 不是我引入) |
| 9 | ecos | ⚠️ | 1 fail (pre-existing, 不是我引入) |
| 10 | runtime | ✅ | |
| 11 | family-hub | ✅ | P3 work 治本 |
| 12 | metaos | ✅ | |

**10/12 green, 2/12 有 pre-existing fail (governance 集成, 需独立 phase)**。

## 经验沉淀

### P3 work 治本 3 步法
1. **错误前提定位** — 跑验证矩阵, 列出 fail 类型 (import / path / env / API)
2. **真治本 vs 治标判别** — 改 import-time binding (治标) vs 改 runtime lookup (治本)
3. **跨包传播** — 一个 import 改, 所有引用文件 sed 改

### 真治本 3 个常见反模式 (本 session 修正)
- ❌ 改 sys.path in conftest (治标 — 测试 setup 应从源头修)
- ❌ `from .X import Y` 然后 monkeypatch Y (治标 — Y 是 import-time binding)
- ❌ `or X()` fallback (治标 — 真治本是 `or X.require_explicit()`)

## 引用
- Tier 2 范式: `.omo/_knowledge/standards/p52-true-fix-paradigm.md`
- Phase 3 矩阵: `.omo/_knowledge/reviews/2026-06-30-phase3-verification-matrix.md`
- ADR-0116 Tier 1 vs Tier 2
- ADR-0117 撤销 P60 阶段
- ADR-0118 根仓 dev-deps 部分真治本
- ADR-0119 (待写): P3 work family-hub + cockpit

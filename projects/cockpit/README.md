# cockpit

> 统一研究驾驶舱 (CLI + Web UI) — 工作区入口与研究对象管理
> Unified Research Cockpit (CLI + Web UI) — workspace entrypoint & research object management

从 kairon monorepo 拆出的独立项目（**P30-W1** · 2026-06-06），由两个组件融合：
- **Python CLI** — 原 `kairon/packages/wksp`（`workspace`/`cockpit` 命令，研究对象存储/索引/MCP/治理）
- **TypeScript Web UI** — 原 `projects/hermes-console`（React 18 + Vite + MCP 客户端）

> **Note**: 此次为 git 历史重写点。包名从 `wksp` 改为 `cockpit`，但保留 `workspace` 旧入口别名以保持兼容。

---

## 项目结构

```
cockpit/
├── pyproject.toml            # Python 包配置（cockpit v0.4.0）
├── README.md                 # 本文件
├── src/
│   └── cockpit/              # Python 包
│       ├── __init__.py
│       ├── __main__.py
│       ├── cli.py            # CLI 入口
│       ├── storage.py        # 研究对象存储
│       ├── data_index.py     # 数据索引
│       ├── commands/         # 子命令（research/data/contracts/mcp/...）
│       ├── scripts/          # 辅助脚本
│       └── tests/            # 单元测试
├── tests/                    # 顶层集成测试
│   ├── conftest.py
│   └── test_basic.py
└── web/                      # Web UI（原 hermes-console）
    ├── package.json
    ├── vite.config.ts
    ├── src/                  # React 源码
    └── ...
```

---

## 快速开始

### Python CLI

```bash
# 安装
uv pip install -e .

# 查看帮助
cockpit --help

# 或旧名
workspace --help
```

主要子命令：

| 命令 | 说明 |
|------|------|
| `cockpit research` | 研究对象管理（list/add/ask/digest/dossier/merge/publish/restore/...） |
| `cockpit code` | 代码分析与语义图谱工作流引擎，集成 CodeAnalyze (Graphify/Serena/等) |
| `cockpit data` | 数据索引与导入 |
| `cockpit status` | 系统状态与工作台 |
| `cockpit contracts` | 契约管理 |
| `cockpit mcp` | MCP 服务器相关 |
| `cockpit profile` | 用户/Agent profile |
| `cockpit governance` | 治理 |
| `cockpit quickstart` | 快速入门 |
| `cockpit importer` | 导入工具 |

### Web UI

```bash
cd web
bun install
bun run dev          # 启动 Vite dev server
bun run build        # 生产构建
bun test             # 运行测试
```

---

## 从 kairon 迁移说明

| 项 | 旧 | 新 |
|----|----|----|
| Python 包名 | `wksp` | `cockpit` |
| CLI 入口 | `workspace` | `cockpit`（`workspace` 仍可用） |
| 位置 | `kairon/packages/wksp/` | `projects/cockpit/src/cockpit/` |
| Web UI 位置 | `projects/hermes-console/` | `projects/cockpit/web/` |
| git 状态 | 子模块（kairon） | 独立项目（新 git 仓库待初始化） |

跨包引用已全部更新：
- `kairon/pyproject.toml` 移除 `wksp` workspace source
- `kairon/tests/test_cross_package_integration.py` 移除 `test_wksp`
- `kairon/CLAUDE.md` / `AGENTS.md` 标注 wksp/cockpit 迁移

---

## 依赖

- **Python**: 3.10+（CI 矩阵 3.10-3.13）
- **Runtime**: `click>=8.0`, `rich>=13.0`
- **Web**: `react@18`, `@modelcontextprotocol/sdk@1.29`, `vite@5`, `vitest@1`
- **包管理**: Python 用 `uv`；Web 用 `bun`

---

## 测试

```bash
# Python
make test                    # 或：python3 -m pytest src/cockpit/tests tests/

# Web
cd web && bun test
```

---

## CI

待补：独立 `.github/workflows/ci.yml`（lint + test）。

---

## 许可证

MIT

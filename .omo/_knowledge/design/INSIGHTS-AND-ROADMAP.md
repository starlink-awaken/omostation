# 知识基座 — 深度洞察与未来规划

> 记录于 2026-05-23，基于 5 天全链路建设的经验。
> 本文档为永久记录，不应删除。

---

## 第一部分：深度洞察

### 洞察 1："全链路就绪" ≠ "产品就绪"

**现状**: 5 个工具、70 测试、8000+ ruff 清零、全链路 5000 节点已验证。
**真相**: 没有一个工具达到产品完成度。KOS 的索引器用 `spec_from_file_location`、Eidos MCP 是手写 JSON-RPC、Pipeline 路径硬编码。

**推论**: 工具链的强度取决于最弱的一环。目前顺序：
```
KOS 插件架构 (最弱) → OntoDerive 目录布局 → Pipeline 绝对路径 → CLI 帮助文本 → MCP SDK 迁移
```

### 洞察 2：适配器模式的隐藏成本

**表面**: `try/except ImportError` 优雅地实现了可选集成。
**深层**: 把集成失败从编译时推到了运行时。开发期友好，运维期不友好。

**取舍**: 适配器模式应逐步替换为接口契约。路径：
```
try/except → Protocol/ABC 协议 → 可选安装的依赖包（pip install eidos-kos）
```

### 洞察 3：元模型驱动开发的杠杆效应

**发现**: 8 MetaType × 4 MetaRelationType 的设计产生 10x 杠杆 —— Eidos 类型、KOS 搜索、OntoDerive 归一化、Agora 路由全部都从元模型"长"出来。

**推论**: 花时间做元模型设计（而不是直接编码）是"慢就是快"的典型案例。应持续维护和扩展元模型层。

### 洞察 4：最大风险不在代码里

**风险**: 所有工具依赖本地文件系统路径 (`/Users/xiamingxing/`)，包括：
- Pipeline Python 路径
- KOS SQLite 位置 (`~/.kos/`)
- OntoDerive adapter import
- Gateway 包装器路径
- 测试中的绝对引用

**影响**: 不可分发、不可 CI/CD、不可团队协作。

### 洞察 5：组件独立 > 大一统

**哲学**: 每个 CLI 命令单独运行都有意义，`pipeline` 只是串起来。
**验证**: 5 个工具 5 次 ruff 清零 = 5 次独立验证。如果是一个"全栈平台"，一次破坏会影响全部。

**保持**: 这个哲学是对的。但代价是 5 套 CLI 风格不一致 —— Agora 统一入口就是为了解决这个问题。

### 洞察 6：如果重新开始

```
实际路线: .omo/ → Eidos → KOS → Pipeline → Adapter → MCP → Agora
最优路线: 元模型 → 路由协议 → MCP 契约 → 工具实现
                                 ↑ 先定接口再实现，可节省 30% 时间
```

---

## 第二部分：未来规划

### S1：生产就绪（可分发、可 CI/CD）

优先级：P0 — 消除所有绝对路径

```bash
# 问题文件清单
eidos/src/eidos/pipeline/__init__.py      # → sys.executable (已部分修复)
eidos/src/eidos/pipeline/presets.py       # → 相对路径
eidos/src/eidos/mcp_server.py             # → 依赖 PYTHONPATH
kos/kos/commands/ingest.py                # → sys.path.insert
gateway/bin/*                             # → 全部硬编码路径
```

**完成条件**:
- [ ] `pip install -e .` 后所有工具可用（不需要 PYTHONPATH）
- [ ] `eidos pipeline --name knowledge-base` 可以从任何目录运行
- [ ] KOS `kos ingest` 不依赖 `.venv/bin/python` 的特定路径
- [ ] MCP 服务可通过 `uvx eidos-mcp` 启动

### S2：接口契约化（替换适配器模式）

优先级：P1 — 用 Protocol/ABC 替换 try/except

```python
# 当前
try:
    from eidos.types import KnowledgeCard
    EIDOS_AVAILABLE = True
except ImportError:
    EIDOS_AVAILABLE = False

# 目标
from eidos.protocols import KnowledgeCardProtocol
```

**完成条件**:
- [ ] `eidos/protocols/` 模块定义接口契约
- [ ] KOS/OntoDerive/Minerva 实现这些契约
- [ ] 适配器代码减少 50%+
- [ ] 编译时类型检查

### S3：路径消除计划

| 文件 | 当前 | 目标 |
|------|------|------|
| `pipeline/__init__.py` | 硬编码 `/Users/...` | `find_package()` 或配置 |
| `kos/commands/ingest.py` | `sys.path.insert` | 通过 pip install 后的正常导入 |
| `gateway/bin/*` | 绝对 cd | `{package}/bin/` entry_points |
| `eidos/mcp_server.py` | PYTHONPATH=src | `from eidos import...` 直接可用 |
| **测试文件** | `sys.path.insert(0, "src")` | `pip install -e ".[dev]"` 后 `python -m pytest` |

### S4：后续版本路线图

```
v0.2 — 生产就绪
  ├── 消除所有绝对路径
  ├── pip install eidos 可用
  ├── KOS 索引器加固 (from kos.indexer import KosIndexer)
  └── MCP 迁移到 FastMCP SDK

v0.3 — 接口契约化
  ├── eidos/protocols/ 模块
  ├── 所有适配器实现契约
  └── 移除 try/except ImportError

v0.4 — 可观测 + 可运维
  ├── 结构化日志
  ├── 性能基准 CI
  ├── 错误码统一
  └── API 版本化

v0.5 — 多存储后端
  ├── SQLite → PostgreSQL / S3
  ├── 知识图谱导出 (RDF/OWL)
  └── 分布式推理
```

### S5：治理原则

1. **元模型先行** — 任何新功能先定义它在 8×4 体系中的位置
2. **接口先于实现** — 先定义 Protocol/ABC，再实现
3. **组件独立可用** — 每个工具可以不依赖其他工具单独运行
4. **路径无关** — 所有路径相对于项目根或可配置
5. **测试可离线运行** — 不依赖网络、不依赖外部服务

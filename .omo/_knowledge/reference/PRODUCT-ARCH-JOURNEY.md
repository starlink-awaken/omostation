# 本体建模工具集 — 产品·架构·用户旅程 综合分析

## 一、产品功能清单

### Eidos (Schema 定义层) — 6 CLI 命令

| 命令 | 功能 | 输入 | 输出 | 状态 |
|------|------|------|------|------|
| `eidos list` | 列出所有 Schema | — | Schema 列表 / JSON | ✅ |
| `eidos validate` | 校验 JSON | `--type` / `--all` / `--dir` | 校验结果 / JSON | ✅ 含批量 |
| `eidos meta` | 查看元模型 | `--export` | 8×4 表格 / JSON | ✅ |
| `eidos define` | 交互式定义 Schema | `name` / `--file` | Schema JSON | ✅ |
| `eidos viz` | 可视化 | schema/graph/state/web | Mermaid / HTML | ✅ 含 Dashboard |
| `eidos pipeline` | 管线编排 | `--name` / `--file` | 管线执行结果 | ✅ 2 个预设 |
| **MCP 服务** | MCP 工具 | `eidos_mcp_server` | JSON-RPC | ✅ 4 tools |

### KOS (存储检索层) — 8 命令

| 命令 | 功能 | 特色 | 状态 |
|------|------|------|------|
| `kos ingest` | 文件注入 | `--schema` Eidos 校验 / `--dry-run` | ✅ 500/500 通过 |
| `kos search` | 搜索 | `--meta-type` 过滤 / `--json` | ✅ |
| `kos list` | 列出 | `--meta-type` 过滤 | ✅ |
| `kos import-schema` | 导入 Eidos Schema | 从 JSON 文件 | ✅ |
| `kos domains/status/onto` | 领域/状态/本体 | 辅助功能 | ✅ |

### OntoDerive (推理层) — 1 命令

| 命令 | 功能 | 特色 | 状态 |
|------|------|------|------|
| `ontoderive derive` | 知识推导 | `--eidos` 输出 Eidos Fact | ✅ |
| **Eidos 适配器** | 模型桥接 | FormalFact ↔ Eidos Fact | ✅ safe fallback |
| **MCP 服务** | MCP 工具 | `engine/mcp_server.py` | ✅ |

### Minerva (研究抽取)

| 命令 | 功能 | 特色 | 状态 |
|------|------|------|------|
| `minerva research` | 深度研究 | `--eidos-output` / `--to-kos` / `--pipeline-output` | ✅ |
| **MCP 服务** | MCP 工具 | `mcp_server/` | ✅ |

### Agora (服务路由)

| 命令 | 功能 | 特色 | 状态 |
|------|------|------|------|
| `agora register` | 服务注册 | Eidos pipeline | ✅ |
| `agora start-pipeline` | 启动端点 | HTTP | ✅ |
| `agora mcp` | MCP 模式 | FastMCP | ✅ |
| **Eidos 服务** | 路由 | validate/meta/list/define | ✅ |

---

## 二、架构分析

### 2.1 当前架构图

```
                    ┌── User ──────────────────┐
                    │  CLI (eidos/kos/ontoderive) │
                    │  MCP (工具级)              │
                    │  Pipeline (编排级)          │
                    └──────────┬─────────────────┘
                               │
    ┌──────────────────────────┼──────────────────────────┐
    │                          │                          │
    ▼                          ▼                          ▼
┌──────────┐           ┌──────────────┐           ┌──────────────┐
│  Eidos   │  optional │    KOS       │  optional  │  OntoDerive  │
│  Schema  │◄─────────►│  Storage     │◄──────────►│  Reasoning   │
│  定义层  │  try/     │  存取层      │  try/      │  推理层      │
│          │  except   │              │  except    │              │
│ 66 tests │           │ 83 tests     │            │ 747 tests    │
│ 0 ruff   │           │ ruff ⚠️      │            │ 0 ruff       │
│ 2136 LOC │           │ 0 LOC(核心)  │            │ 11035 LOC    │
└────┬─────┘           └──────────────┘            └──────┬───────┘
     │                                                    │
     │  optional                                            │
     ▼                                                    ▼
┌──────────┐                                      ┌──────────┐
│ Minerva  │                                      │  Agora   │
│ 抽取工具  │                                      │ 服务路由  │
│ 0 ruff   │                                      │ 0 ruff    │
└──────────┘                                      └──────────┘
```

### 2.2 架构评分

| 维度 | 评分 | 说明 |
|------|------|------|
| **模块独立性** | A | 5 个项目零硬依赖，全部 try/except 可选 |
| **接口一致性** | A- | 全部支持 `--json` / `--pipeline-input/output` |
| **代码质量** | B+ | Eidos/OntoDerive/agora ruff 0，KOS 仍有残留 |
| **测试覆盖** | B | 总计 ~900 测试，Minerva 258 最强，KOS 83 待加强 |
| **文档** | C+ | 有 `.omo/` 架构文档但缺用户手册 |
| **MCP 覆盖** | A- | 5 个工具全部 MCP 可达 |

### 2.3 架构风险

| 风险 | 级别 | 影响 |
|------|------|------|
| KOS 索引器插件 sys. path 依赖 | 🟡 | 不同环境可能加载失败 |
| OntoDerive `engine/` 非标准目录 | 🟢 | PYTHONPATH 配置复杂 |
| Pipeline 硬编码 Workspace 路径 | 🟢 | 不跨机器 |
| Minerva 抽取未接 KOS 标准接口 | 🟢 | 无直接存储链 |

---

## 三、用户旅程

### 旅程 1：新手入门 — 定义第一个 Schema (3 步, ~2 分钟)

```bash
# 1. 查看可用的元模型类型
eidos meta
# Output: 8 MetaTypes: domain/fact/inference/relation/state/document/constraint/processor

# 2. 交互式定义
eidos define MyConcept --meta-type domain
# 输入字段: name, description, category

# 3. 查看已注册的 Schema
eidos list
```

### 旅程 2：数据校验 — 验证知识卡片 (1 步, ~5 秒)

```bash
# 验证单个文件
eidos validate card.json --type KnowledgeCard

# 批量验证目录
eidos validate --dir ./data/
```

### 旅程 3：知识注入 + 搜索 — 让数据可检索 (2 步, ~1 分钟)

```bash
# 1. 注入 (带 Eidos 校验)
kos ingest ./papers/ --schema KnowledgeCard

# 2. 搜索
kos search "Transformer" --meta-type document
```

### 旅程 4：全链路 — 从定义到推导到可视化 (4 步, ~3 分钟)

```bash
# 1. 定义 Schema
eidos define Patent --meta-type document
# 输入: id, title, content, source, tags

# 2. 注入数据
kos ingest ./patents/ --schema Patent

# 3. 推导关系
ontoderive derive --eidos

# 4. 可视化
eidos viz web
# 浏览器打开 /tmp/eidos-dashboard.html
```

### 旅程 5：管线自动化 — 一键运行 (1 步)

```bash
# 预设管线
eidos pipeline --name knowledge-base

# 或自定义管线
eidos pipeline --file my-pipeline.json
```

### 旅程 6：MCP 集成 — 从 AI Agent 调用 (2 步)

```bash
# 1. 启动 MCP 服务
python -m eidos.mcp_server

# 2. AI Agent 调用 (JSON-RPC)
echo '{"method":"call_tool/eidos_validate","params":{"data":{"schema_type":"KnowledgeCard","id":"test"}}}' | python -m eidos.mcp_server
```

---

## 四、数据总览

| 指标 | 数值 |
|------|------|
| 总项目数 | 5 (eidos/kos/ontoderive/minerva/agora) |
| 总数文件 | 164 Python files |
| 总代码量 | ~27,000 LOC |
| 总测试数 | ~965 tests |
| 零 ruff 项目 | 4/5 (KOS 有残留) |
| CLI 命令总数 | 18 |
| MCP 工具总数 | 8+ |
| 管线预设 | 2 |
| 节点验证基准 | 5,000 papers / 2.5 min |

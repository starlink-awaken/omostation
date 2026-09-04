---
title: USAGE-GUIDE
type: doc
---

# kairon 使用指南

> 16 个包的快速上手 · 场景示例 · 最佳实践

---

## 一、快速开始

### 1.1 安装

```bash
cd projects/kairon
uv sync
```

### 1.2 验证安装

```bash
# 检查所有包
uv run python -c "
packages = [
    'codeanalyze', 'core_models', 'eidos', 'forge', 'health_profile',
    'iris', 'kairon_observability', 'kairon_pipeline', 'kairon_plugin_sdk',
    'kairon_utils', 'kos', 'kronos', 'minerva', 'ontoderive'
]
for pkg in packages:
    try:
        __import__(pkg)
        print(f'✅ {pkg}')
    except:
        print(f'❌ {pkg}')
"
```

---

## 二、场景示例

### 2.1 知识管理 (kos + kronos)

```bash
# 搜索知识
kos search "治理框架"

# 摄取文档
kronos ingest /path/to/docs

# 查看状态
kos status
```

### 2.2 深度研究 (minerva)

```bash
# 启动研究
minerva research "X1-X4 治理框架"

# 生成报告
minerva report --topic "治理优化"
```

### 2.3 代码分析 (codeanalyze)

```bash
# 扫描代码
codeanalyze scan /path/to/project

# 生成代码图
codeanalyze graph --format mermaid
```

### 2.4 Schema 验证 (eidos)

```bash
# 验证 Schema
eidos validate schema.yaml

# 同步 Schema
eidos sync --source remote
```

### 2.5 资产管理 (forge)

```bash
# 列出资产
forge list

# 同步资产
forge sync --all
```

### 2.6 平台集成 (iris)

```bash
# 连接 WPS Note
iris connect wps

# 同步微信读书
iris sync wxread
```

---

## 三、Python API 示例

### 3.1 知识搜索

```python
from kos import search

results = search("治理框架", limit=10)
for r in results:
    print(f"{r['title']}: {r['snippet']}")
```

### 3.2 代码分析

```python
from codeanalyze import analyze

result = analyze("/path/to/project")
print(f"代码行数: {result.lines}")
print(f"复杂度: {result.complexity}")
```

### 3.3 Schema 验证

```python
from eidos import validate

errors = validate(data, schema="my_schema.yaml")
if errors:
    print(f"验证失败: {errors}")
```

### 3.4 知识图谱

```python
from core_models import KnowledgeGraph

kg = KnowledgeGraph()
kg.add_entity("Person", "张三")
kg.add_relation("张三", "works_on", "项目A")
```

---

## 四、MCP 工具使用

### 4.1 KOS MCP

```python
# 搜索
result = mcp.call("kos_search", query="治理")

# 获取状态
status = mcp.call("kos_status")

# 列出域
domains = mcp.call("kos_domains")
```

### 4.2 Forge MCP

```python
# 列出资产
assets = mcp.call("forge_list")

# 创建资产
asset = mcp.call("forge_create", name="新资产", type="document")
```

---

## 五、最佳实践

### 5.1 知识管理

1. **定期索引** — 每周运行 `kos index --incremental`
2. **域分离** — 不同领域使用不同域
3. **标签规范** — 使用统一的标签体系

### 5.2 代码分析

1. **CI 集成** — 在 CI 中运行 codeanalyze
2. **定期审查** — 每周运行代码审查
3. **关注热点** — 优先分析高频修改的文件

### 5.3 深度研究

1. **明确主题** — 研究前定义清晰的研究问题
2. **多源验证** — 交叉验证多个来源
3. **持续更新** — 定期更新研究结论

---

## 六、故障排除

### 6.1 导入失败

```bash
# 重新安装
uv sync

# 检查依赖
uv pip list | grep kairon
```

### 6.2 搜索无结果

```bash
# 检查索引
kos status

# 重建索引
kos index --incremental
```

### 6.3 CLI 命令不存在

```bash
# 检查入口点
cat pyproject.toml | grep -A5 "\[project.scripts\]"

# 重新安装
uv sync
```

---

## 七、相关文档

| 文档 | 说明 |
|------|------|
| CAPABILITY-MAP.md | 能力地图 |
| 各包 README.md | 包详细文档 |
| .omo/_knowledge/governance/ | 治理文档 |

---

*最后更新: 2026-06-12*

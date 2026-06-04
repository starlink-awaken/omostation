# Task Prompt: Wave 2.1.A — minerva 输出持久化

> 类型: P9 → P8 Task Prompt | 状态: pending (depends on Phase 1 gate) | 预估: 2h

## 一、目标

修复核心断点：minerva research 的结果从 stdout-only 改为自动保存到持久化存储。这是 PRODUCT_VISION 原则 1 "结果有家"的基础设施。

## 二、范围

### 包含
- minerva research 输出自动保存到 `~/.minerva/research/<id>/report.md`
- 保存格式包含 frontmatter 元信息（时间、来源数、耗时、模型）
- `minerva research list` CLI 命令展示最近研究
- `minerva research open <id>` CLI 命令展示全文
- 研究目录结构：`~/.minerva/research/<id>/` 含 report.md + sources/ + metadata.json

### 不包含
- workspace CLI 对接（那是 Wave 2.1.B）
- 进度指示器（那是 Wave 2.2.A）
- 追问功能（那是 Wave 2.2.B）

## 三、验收标准

```
☐ `minerva research "test"` — 完成后 `~/.minerva/research/` 下有新目录
☐ `minerva research list` — 显示最近 10 条研究（ID + 标题 + 时间 + 摘要）
☐ `minerva research open 1` — 输出完整报告含 frontmatter
☐ `minerva research open 1 --sources` — 列出研究来源
☐ 关终端再打开 → `minerva research list` 仍能看到历史
```

## 四、存储结构

### 目录布局
```
~/.minerva/
  research.sqlite     # SQLite 索引: id, title, query, created_at, source_count, duration
  research/
    <uuid>/
      report.md       # 完整报告 markdown
      metadata.json   # 元信息结构化
      sources/        # 来源文件
        01-title.md
        02-title.md
```

### report.md 格式
```markdown
---
id: <uuid>
title: <研究标题>
query: <原始查询>
created: <ISO时间>
sources: <数量>
duration: <秒>
model: <模型名>
---

## 摘要
...

## 关键发现
1. ...
```

## 五、执行步骤

### Step 1: 创建存储层

在 `minerva/src/minerva/storage.py` 新建 `ResearchStore` 类：

```python
class ResearchStore:
    def __init__(self, base_dir: str = None): ...
    def save(self, result: ResearchResult) -> str: ...  # 返回 id
    def list(self, limit: int = 10) -> list[dict]: ...  # 返回摘要列表
    def get(self, id: str) -> dict | None: ...  # 返回完整记录
    def delete(self, id: str) -> bool: ...
```

### Step 2: 集成到 research 命令

在 `cli.py` 中，research 完成后自动调用 `store.save(result)`。

### Step 3: 添加 list/open CLI 子命令

```bash
minerva research list [--limit N] [--json]
minerva research open <id> [--full] [--sources]
```

### Step 4: 验证

```bash
minerva research "test query"
minerva research list
minerva research open 1
```

## 六、输出

| 文件 | 操作 |
|------|------|
| `minerva/src/minerva/storage.py` | 新增 |
| `minerva/src/minerva/cli.py` | 修改，添加 list/open 子命令 |
| `minerva/src/minerva/executor/executor.py` | 修改，research 完成后自动保存 |
| `.omo/TASK_POOL.md` | T028-T031 → done |
| `.omo/STATE.md` | 更新进度 |

## 七、→ 下一个 Wave

完成后触发 **Wave 2.1.B (workspace CLI 基础对接)**。

---
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-06-23
archived-since: 2026-06-23
note: "P56 R2: 全量兜底批量归档, 当前活跃以各面 INDEX/SSOT/PANORAMA.md 为准"
---
# Task Prompt: Wave 2.1.B — workspace CLI 基础对接

> 类型: P9 → P8 Task Prompt | 状态: pending (depends on Wave 2.1.A) | 预估: 1h

## 一、目标

将 workspace CLI 对接 minerva 持久化存储，使研究结果可通过 workspace 统一入口访问。

## 二、范围

| 命令 | 动作 | 数据源 |
|------|------|--------|
| `workspace research "topic"` | 调用 `minerva research` | CLI subprocess |
| `workspace research list` | 展示最近研究 | minerva SQLite |
| `workspace research open <id>` | 展示全文 | minerva 文件存储 |

## 三、验收标准

```
☐ `workspace research "hello"` — 触发 minerva research 并返回结果
☐ `workspace research list` — 显示与 `minerva research list` 一致
☐ `workspace research open 1` — 显示与 `minerva research open 1` 一致
☐ 关终端 → 再开 → 数据仍在
```

## 四、依赖

- **前置**: Wave 2.1.A 已完成（minerva 持久化可用）
- **确认命令**: `minerva research list` 返回结果

## 五、执行步骤

### Step 1: 检查 workspace CLI 入口

```bash
cd ~/Workspace/workspace && cat cli.py | head -30
```

### Step 2: 对接 research 命令

```python
# workspace/cli.py 或 workspace/commands/research.py
import subprocess
import json

def research(query: str):
    result = subprocess.run(["minerva", "research", query, "--json"], capture_output=True, text=True)
    print(result.stdout)

def list_research(limit=10):
    result = subprocess.run(["minerva", "research", "list", "--json", "--limit", str(limit)], capture_output=True, text=True)
    data = json.loads(result.stdout)
    for item in data:
        print(f"  [{item['id']}] {item['title']} — {item['created_at'][:10]}")

def open_research(id: str):
    result = subprocess.run(["minerva", "research", "open", id], capture_output=True, text=True)
    print(result.stdout)
```

### Step 3: 验证

```bash
workspace research "test"
workspace research list
workspace research open 1
```

## 六、输出

| 文件 | 操作 |
|------|------|
| `workspace/cli.py` | 修改，添加 research/list/open |
| `.omo/TASK_POOL.md` | T032-T034 → done |

## 七、→ 下一个 Wave

完成后触发 **Wave 2.2.A (进度反馈)**。

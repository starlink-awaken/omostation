---
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-06-23
archived-since: 2026-06-23
note: "P56 R2: 全量兜底批量归档, 当前活跃以各面 INDEX/SSOT/PANORAMA.md 为准"
---
# Task Prompt: Wave 3.1.A — workspace status

> 类型: P9 → P8 Task Prompt | 状态: pending (depends on Phase 2 gate) | 预估: 1.5h

## 一、目标

创建 `workspace status` 命令，统一展示系统健康状态 + 研究历史，替代分别 curl 多个端口的现状。

## 二、范围

```
workspace status 输出格式:
┌──────────────────────────────────────────┐
│  Workspace 系统健康                       │
│                                          │
│  ✓ Agora Hub    :7430   运行中  9 服务    │
│  ✓ Minerva      :8765   运行中  5 工具    │
│  ✓ bos-daemon   :7420   HTTP 200         │
│  ~ stdio 服务(6): 已注册                 │
│                                          │
│  最近研究 (3):                           │
│    [1] Attention variants   5m ago       │
│    [2] RAG survey           2h ago       │
│    [3] Prompt injection    1d ago        │
│                                          │
│  [打开 Dashboard] → http://localhost:7430 │
└──────────────────────────────────────────┘
```

## 三、验收标准

```
☐ workspace status 输出包含 agora 服务状态（健康/降级/离线）
☐ 包含最近 3 条研究历史
☐ 包含 Dashboard 链接
☐ 总执行时间 < 2 秒
☐ 与 agora health 的服务状态一致
```

## 四、依赖

- **前置**: Phase 2 全部完成
- 依赖 Wave 2.1.A 的 minerva 存储

## 五、执行步骤

### Step 1: 获取 agora 服务状态

```python
def get_agora_status():
    """调用 agora health 获取结构化数据"""
    import subprocess, json
    r = subprocess.run(["agora", "health", "--json"], capture_output=True, text=True)
    return json.loads(r.stdout)
```

### Step 2: 获取研究历史

```python
def get_recent_research(limit=3):
    """调用 minerva research list"""
    import subprocess, json
    r = subprocess.run(["minerva", "research", "list", "--json", "--limit", str(limit)], capture_output=True, text=True)
    return json.loads(r.stdout)
```

### Step 3: 组装输出

格式化输出，健康服务用 ✅、降级用 ⚠️、离线用 ❌。

## 六、输出

| 文件 | 操作 |
|------|------|
| `workspace/commands/status.py` | 新增 |
| `workspace/cli.py` | 添加 status 子命令 |
| `.omo/TASK_POOL.md` | T042-T044 → done |

## 七、→ 下一个 Wave

完成后触发 **Wave 3.1.B (workspace demo 完整版)**。

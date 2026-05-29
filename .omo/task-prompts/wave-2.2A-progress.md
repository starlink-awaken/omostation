# Task Prompt: Wave 2.2.A — 进度反馈

> 类型: P9 → P8 Task Prompt | 状态: pending (depends on Wave 2.1.B) | 预估: 1.5h

## 一、目标

为 >5 秒的操作添加可视化进度反馈，解决"黑屏等 30 秒"的体验问题。

## 二、范围

| 场景 | 当前行为 | 目标行为 |
|------|---------|---------|
| minerva L3 research (~30s) | 黑屏等待 | 逐步输出: [1/5] 正在搜索... [2/5] 正在分析... |
| workspace research | 黑屏等待 | 步骤标记: [正在匹配] [正在推导] [正在研究] |
| 任意 >5s CLI 操作 | 无反馈 | 有进度指示或状态轮换 |

## 三、验收标准

```
☐ minerva L3 research 输出步骤指示（至少 3 个步骤标记）
☐ workspace research 透传 minerva 的进度输出
☐ 120s 自动提示用户是否继续
☐ 进度格式统一: [N/M] 当前步骤描述
```

## 四、依赖

- **前置**: Wave 2.1.B 已完成

## 五、执行步骤

### Step 1: minerva 进度钩子

在 `minerva/src/minerva/executor/executor.py` 添加 `ProgressCallback`：

```python
from typing import Callable, Optional

ProgressCallback = Callable[[int, int, str], None]
# 签名: (current_step, total_steps, description)

class ResearchExecutor:
    def __init__(self, ..., progress: Optional[ProgressCallback] = None):
        self._progress = progress
    
    async def _run_l3(self):
        steps = ["搜索来源", "提取内容", "LLM分析", "生成报告", "保存结果"]
        for i, step in enumerate(steps, 1):
            if self._progress:
                self._progress(i, len(steps), step)
            ...
```

### Step 2: CLI 集成

在 cli.py 中传入 lambda 输出进度：

```python
def _progress_cb(current, total, desc):
    print(f"\r  [{current}/{total}] {desc}...", end="", flush=True)

# research 完成后:
print(f"\r✅ [{total}/{total}] 研究完成!         ")
```

### Step 3: 超时保护

```python
import asyncio

async def research_with_timeout(query, timeout=120):
    task = asyncio.create_task(executor.research(query))
    done, pending = await asyncio.wait([task], timeout=timeout)
    if pending:
        print("\n⏱️  研究超过 120 秒，是否继续? [Y/n]: ", end="")
        resp = input().strip().lower()
        if resp in ("", "y", "yes"):
            return await task
        else:
            task.cancel()
            return {"status": "cancelled"}
    return done.pop().result()
```

## 六、输出

| 文件 | 操作 |
|------|------|
| `minerva/src/minerva/executor/executor.py` | 添加 ProgressCallback |
| `minerva/src/minerva/cli.py` | 集成进度输出 |
| `workspace/cli.py` | 透传进度 |
| `.omo/TASK_POOL.md` | T035-T037 → done |

## 七、→ 下一个 Wave

完成后触发 **Wave 2.2.B (后续追问)**。

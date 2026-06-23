---
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-06-23
archived-since: 2026-06-23
note: "P55 R2: summaries/ 根目录历史快照批量归档, 当前状态以 .omo/state/system.yaml + .omo/tasks/active/ 为准"
---
# Agent Task Contract — Read Budget Protocol

> 为解决 `deep`/`unspecified-high` Agent 100% 卡死在 read 阶段的问题  
> 生效: 2026-05-28

## 核心规则

**每个 Agent 任务在执行前必须声明：**

```
READ_BUDGET: N   (最多 N 次 read/glob/grep 操作后必须产出一个 write)
```

| Agent 类别 | 默认 READ_BUDGET | 超时处理 |
|-----------|:----------------:|---------|
| quick | 5 | 5 次 read 后强制 write |
| deep | 5 | 5 次 read 后强制 write |
| unspecified-high | 5 | 5 次 read 后强制 write |

## 机制

所有调用 `task(category="...", prompt="...")` 的 Task Prompt 末尾必须追加：

```
[READ BUDGET]
You have a budget of exactly {N} file read operations (Read/Glob/Grep).
After {N} reads, you MUST produce output (a file write, a verification, or a completion).
If you are stuck after {N} reads, write a partial result and state what you know.
Do NOT perform read #N+1 without having written at least one file or result.
```

## 为什么

从 2026-05-27 执行周期的数据分析：

```
deep        0%   (0/4)   ← 全部卡在 read 阶段
unspecified  0%   (0/3)
quick      100%  (16/16)  ← 成功

失败的 Agent 共同特征:
  1. 只有 read/think 操作
  2. 从未执行 write
  3. 最后一次操作始终是读文件
```

根因：`deep`/`unspecified-high` 使用的模型更强 → 思考代价更高 → 更容易在「探索」阶段陷入无限循环。

## 如果违反

如果 Agent 在 N+1 次 read 后仍未 write：
- 任务自动标记为 `[STUCK]`
- 后续同一会话中，所有任务降级为 `quick` 类别
- 每多一次违规，N 减 1（最小 2）

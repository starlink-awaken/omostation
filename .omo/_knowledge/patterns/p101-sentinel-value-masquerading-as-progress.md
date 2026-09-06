---
type: ssot
owner: governance-team
last-reviewed: 2026-09-06
---

# P101 — 哨兵值伪装成进度：把"失败"读成"卡住"

**Pattern observed**: 2026-09-06，追查 omlxc `models unload` 不释放内存
（PR #61）。误判持续了一整个会话，直到去查数据库才翻案。

## Problem

任务/作业系统里，**同一个数值同时承担两种语义**——既是中间阶段的进度检查点，
又是终态失败的哨兵值——而展示层又不显示错误码。观察者只能看到一个不动的数字，
于是得出完全错误的结论。

## Symptom

`omlxc jobs list` 里所有 job 停在 `progress 0.2`：

```
 ID        KIND    STATE   PROGRESS
 00a33072  unload  · -     0.2
 08abeac4  load    · -     0.2
 1525a0ca  load    · -     0.2      ← 历史上一大批都是 0.2
```

自然推论："job 管道挂死了，作业卡在 0.2 推不动。"
→ 于是去查异步管道、超时、死锁、事件循环。**方向全错。**

## Root Cause

```python
# composition.py:1069  — RUNNING 阶段的进度检查点
progress=max(planning.progress, 0.2)

# composition.py:1123  — 终态: 成功 1.0, 失败 0.2
progress=1.0 if succeeded else 0.2
```

`0.2` 既是"我正在跑"又是"我失败了"。而 CLI 只渲染 state 和 progress，
**不显示 `error_code`**——数据库里明明记着失败原因，展示层把它吞了。

真相在库里一句 SQL 就能看到：

```bash
sqlite3 -header -column ~/.config/omlxc/state.db \
  "SELECT substr(job_id,1,8), kind, state, error_code, rollback_reference
   FROM jobs ORDER BY updated_at DESC LIMIT 10;"
```

结果：24 条全是 `state=failed`，`unavailable`×20 / `operation_failed`×3 /
`stale`×1，还带着 `rollback_reference` 指出的具体目标——**这些信息一直躺在那里，
只是展示层没给。**

### 反面教训：拿到 error_code 之后仍然可能误判

本次拿到 `rollback_reference` 后，我立刻推断"派发打到了错误的后端"，据此提了修复。
修复本身逻辑没错（按请求类型选 placement 优于按 catalog 顺序），但**它没有解决观察到的
症状**——真实原因是配置漂移：那条 placement 的 `backend_model_id` 在后端根本不存在，
`operation_failed` 是如实报错。

即：**从"看起来卡住"纠正到"其实失败了"只是第一步，不是终点。**
拿到错误码之后仍然要问"这个错误码字面上在说什么"，而不是急着找一个能解释它的机制。

## Fix Pattern

### 1. 终态不要复用中间态的数值

失败就把 progress 留在它失败时的位置（`current.progress`），或用一个
中间态不可能取到的值。同一数值承担两种语义 = 制造误诊。

注：同文件的异常分支其实做对了——`except` 块用的是 `progress=current.progress`
（保留现场），只有 `_finish` 的正常返回路径硬写了 `0.2`。**同一个文件里两种写法，
说明这是疏漏不是设计。**

### 2. 展示层必须暴露错误码

存了 `error_code` 却不展示，等于没存。列表视图至少要有一列，
或在非成功终态时把它带出来。

### 3. 诊断纪律：状态可疑就直查存储层

"看起来卡住"和"已经失败"在 UI 上可能长得一模一样。
**别信列表视图，去查库。** 一句 SQL 的成本远低于沿着错误方向排查半天。

这条是 [[p78-triple-axis-diagnostic-pattern]] 的具体化：
静态（代码里 0.2 是什么）/ 运行时（库里 state 和 error_code 是什么）/
决策（CLI 选择渲染什么）——三维不对齐时，运行时数据是唯一真源。

## Detection

排查任何"卡住"的作业/任务前，先问三句：

1. 这个进度值在代码里有几个赋值点？是否有终态复用中间态数值？
2. 存储层有没有记 error_code / 失败原因？展示层展示了吗？
3. 直接查库的结果，和 UI 显示的结论一致吗？

## Related

- [[p73-truth-driven-engineering-pattern]] — 声明/执行鸿沟
- [[p78-triple-axis-diagnostic-pattern]] — 三维查证纪律
- [[p100-unified-memory-wired-ceiling]] — 同批次挖出的物理约束陷阱

---
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-06-23
archived-since: 2026-06-23
note: "P56 R2: 全量兜底批量归档, 当前活跃以各面 INDEX/SSOT/PANORAMA.md 为准"
---
# Task Prompt: Wave 2.2.B — 后续追问

> 类型: P9 → P8 Task Prompt | 状态: pending (depends on Wave 2.2.A) | 预估: 1h

## 一、目标

支持基于已有研究结果的后续追问，使用户能与研究结果进行对话式交互。

## 二、范围

| 命令 | 行为 |
|------|------|
| `workspace research --ask <id> "xxx"` | 加载 id 的研究报告作为上下文，发起追问 |
| 追问结果 | 追加到原研究记录中，`open <id>` 可看到补充内容 |

## 三、验收标准

```
☐ `workspace research --ask 1 "展开讲讲第二点"` — 返回基于原报告的补充分析
☐ `workspace research open 1` — 包含原始内容 + 追问内容
☐ 追问内容有明确标记（如 Q&A 分隔）
```

## 四、依赖

- **前置**: Wave 2.2.A 已完成

## 五、输出

| 文件 | 操作 |
|------|------|
| `minerva/src/minerva/cli.py` | 添加 --ask 子命令 |
| `minerva/src/minerva/storage.py` | 追加追问到存储 |
| `workspace/cli.py` | 对接 --ask |
| `.omo/TASK_POOL.md` | T038-T039 → done |

## 六、→ 下一个 Wave

完成后触发 **Wave 2.2.C (30 秒 demo 前序)**。

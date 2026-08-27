---
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-06-23
archived-since: 2026-06-23
note: "P56 R2: 全量兜底批量归档, 当前活跃以各面 INDEX/SSOT/PANORAMA.md 为准"
---
# Task Prompt: Wave 2.2.C — 30 秒 demo 前序

> 类型: P9 → P8 Task Prompt | 状态: pending (depends on Wave 2.2.B) | 预估: 45min

## 一、目标

创建 `workspace demo` 命令骨架，串起 health → research → list 三步，使新用户 30 秒内能跑通第一个完整流程。

## 二、范围

```bash
workspace demo
  Step 1/3: ✅ 系统状态 — agora health
  Step 2/3: ✅ 发起研究 — minerva research "demo"
  Step 3/3: ✅ 研究历史 — workspace research list
```

## 三、验收标准

```
☐ `workspace demo` 输出 3 步并全部成功
☐ 总耗时 < 30 秒
☐ 每步失败时有友好提示（如 "请先启动 agora web: bash ~/Workspace/agora/scripts/start-agora.sh"）
☐ demo 结束后输出 "接下来可以尝试:" 引导
```

## 四、依赖

- **前置**: Wave 2.2.B 已完成
- 依赖 Wave 1.1.A 的 agora health 可用

## 五、输出

| 文件 | 操作 |
|------|------|
| `workspace/commands/demo.py` | 新增 |
| `workspace/cli.py` | 添加 demo 子命令 |
| `.omo/TASK_POOL.md` | T040-T041 → done |

## 六、→ Phase 2 门禁

```
☐ workspace research "test" → 保存 → 关终端 → 再开 → list → open 看到结果
☐ workspace research --ask 1 "more" → 返回追问
☐ workspace demo → 3 步不报错，< 30 秒
```

全部通过 → **触发 Phase 3**。

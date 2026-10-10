---
schema: md/v1
status: active
lifecycle: contract
owner: governance-team
type: documentation
last-reviewed: 2026-09-28
---

# crontab.new 结构说明

> `crontab.new` 是工作区的定时任务清单，包含 62 条 cron 条目和配套注释。
> 本文件说明其结构和使用方法，不修改 crontab.new 本身。

## 文件结构

`crontab.new` 是半结构化文件，包含两类内容：

1. **cron 条目**（62 条）— 标准 crontab 格式
   ```
   * * * * * cd "$HOME/.local/share/omostation/accepted-20260908" && uv run ...
   */30 * * * * cd /Users/xiamingxing/Workspace && python3 bin/gac/remediation-engine.py ...
   ```

2. **注释**（~79 行）— 中文散文，说明任务用途、节奏、依赖
   ```
   # 卫健委信息中心 · 定时任务清单
   # 每分钟 — 变更调度器 (监视 registry.py/MOF/state/cards.db, 有变更才触发生成器)
   ```

## 使用方法

### 安装 cron 任务

```bash
crontab -e  # 编辑 crontab
# 追加 crontab.new 内容
```

### 查看当前 cron 任务

```bash
crontab -l
```

### 验证 cron 条目

```bash
# 统计条目数
grep -c "^[*0-9]" crontab.new

# 查看特定任务
grep "gac" crontab.new
```

## 注意事项

- crontab.new 中的绝对路径（如 `/Users/xiamingxing/Workspace`）需要在目标机器上调整
- 部分任务依赖 `$HOME` 环境变量，安装前确认环境
- 任务分为三档节奏：每日 / 每周 / 每月

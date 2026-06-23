---
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-06-23
archived-since: 2026-06-23
note: "P56 R2: 全量兜底批量归档, 当前活跃以各面 INDEX/SSOT/PANORAMA.md 为准"
---
# Task Prompt: Wave 1.2.B — 项目健康度审计

> 类型: P9 → P8 Task Prompt | 状态: ready (depends on Wave 1.1) | 预估: 1h

## 一、目标

对 MetaOS、SSOT、agentmesh 三个待评估项目做归档/保留决策，更新 `.omo/INVENTORY.md` 反映最新状态。

## 二、范围

### 审计清单

| 项目 | LOC | 测试 | 上次修改 | 用途 | 决策选项 |
|------|-----|------|---------|------|---------|
| MetaOS | 28 py 文件 | 0 | ? | Python 系统编排 | 归档 / 补 README 保留 |
| SSOT | 31 py 文件 | 0 | ? | 单一真相源配置管理 | 归档 / 补最小测试保留 |
| agentmesh engine | 94 ts 文件/92 测试 | ~30% | ? | 多 Agent 编排引擎 | 标记 @experimental |
| agentmesh toolkit | 156 ts 文件/42 测试 | ~30% | ? | Agent 能力 SDK | 标记 @experimental |

### 审计方法

1. 检查每个项目的 `pyproject.toml` / `package.json` 确认版本和入口
2. 检查 git log 确认最后活跃时间
3. 检查是否有外部项目依赖它
4. 判断：如果 30 天无人调用 → 归档；有人依赖 → 保留但标记

## 三、验收标准

```
☐ MetaOS 决策已记录到 AGENTS.md 和 STATE.md
☐ SSOT 决策已记录到 AGENTS.md 和 STATE.md
☐ agentmesh engine/toolkit pyproject.toml 或 README 已加 @experimental 标注
☐ .omo/INVENTORY.md 所有项目版本/测试/LOC 最新
```

## 四、依赖

- **前置**: ruff 清零（Wave 1.2.A）已完成验证
- **确认命令**: `ruff check src/` 0 error on all 14 projects

## 五、执行步骤

### Step 1: MetaOS 审计

```bash
cd ~/Workspace/MetaOS
git log --oneline -5 2>/dev/null || echo "no git history"
grep -rn 'from metaos\|import metaos' ../*/src/ --include='*.py' 2>/dev/null || echo "no importers"
wc -l src/**/*.py 2>/dev/null
```

### Step 2: SSOT 审计

```bash
cd ~/Workspace/SSOT
git log --oneline -5 2>/dev/null || echo "no git history"
grep -rn 'from ssot\|import ssot\|ssot-kernel' ../*/src/ --include='*.py' 2>/dev/null || echo "no importers"
```

### Step 3: agentmesh 审计

```bash
cd ~/Workspace/agentmesh
# 检查 engine 和 toolkit 的测试状态
cd packages/engine && bun test 2>&1 | tail -5
cd ../toolkit && bun test 2>&1 | tail -5
```

### Step 4: 记录决策

编辑 `AGENTS.md` 添加 MetaOS/SSOT 状态，agentmesh engine/toolkit 加 `@experimental`。

### Step 5: 更新 ../_truth/INVENTORY.md

确保所有项目的版本、测试数、LOC、活跃度字段最新。

## 六、输出

| 文件 | 操作 |
|------|------|
| `AGENTS.md` | 添加 MetaOS/SSOT 决策和 agentmesh 标记 |
| `agentmesh/packages/engine/README.md` | 加 `@experimental` 标注 |
| `agentmesh/packages/toolkit/README.md` | 加 `@experimental` 标注 |
| `.omo/INVENTORY.md` | 所有项目最新数据 |
| `.omo/TASK_POOL.md` | T021-T024 → done |
| `.omo/STATE.md` | 更新进度 |

## 七、→ 下一个 Wave

完成后触发 **Wave 1.2.C (配置管理自动化)**。

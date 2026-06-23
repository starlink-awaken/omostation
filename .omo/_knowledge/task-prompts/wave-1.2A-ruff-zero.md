---
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-06-23
archived-since: 2026-06-23
note: "P56 R2: 全量兜底批量归档, 当前活跃以各面 INDEX/SSOT/PANORAMA.md 为准"
---
# Task Prompt: Wave 1.2.A — 全项目 ruff 清零

> 类型: P9 → P8 Task Prompt | 状态: ready (depends on Wave 1.1) | 预估: 3h

## 一、目标

Workspace 所有活动的 Python 项目 ruff 0 errors。这是治理计划的基础质量门禁。

## 二、范围

### 包含

| 项目 | 优先级 | 预估 |
|------|--------|------|
| ontoderive | P0 | 30min |
| pallas | P1 | 10min |
| sophia | P1 | 10min |
| minerva | P0 | 30min |
| agora | P0 | 5min（已验证） |
| eidos | P1 | 15min |
| kronos | P1 | 15min |
| codeanalyze | P1 | 15min |
| iris | P1 | 15min |
| kos | P1 | 15min |
| bos-skill-cli | P1 | 10min |
| eCOS | P1 | 10min |
| gateway | P2 | 10min |
| Forge | P2 | 10min |

### 不包含

- MetaOS（待审计，Wave 1.2.B）
- SSOT（待审计，Wave 1.2.B）
- SharedBrain（独立项目，自有 ruff 配置）

## 三、验收标准

```
☐ 每个项目 `ruff check src/` 0 errors
☐ `ruff check src/ --statistics` 输出 "0 errors"
☐ CI 级别的 ruff 规则一致性：所有项目使用相同 select/ignore
☐ ruff 规则从 pyproject.toml 统一到 workspace ruff.toml（如适用）
```

## 四、依赖

- **前置**: Wave 1.1.A + 1.1.B 已完成
- **确认命令**: `ruff --version` 可用

## 五、执行步骤

### Step 1: 批量扫描

```bash
cd ~/Workspace
for d in ontoderive pallas sophia minerva agora eidos kronos codeanalyze iris kos bos-skill-cli eCOS gateway Forge; do
  echo "=== $d ==="
  cd ~/Workspace/$d && ruff check src/ 2>&1 | tail -2
done
```

### Step 2: 逐项目清零

对每个有错误的项目：

```bash
cd ~/Workspace/<project>
ruff check src/  # 看具体错误
ruff check src/ --fix  # 自动修复
ruff check src/  # 确认清零
```

### Step 3: 手动修复无法自动修复的

常见类型：
- `F401` - 未使用的 import → 删除
- `F841` - 未使用的变量 → 删除或 `_` 前缀
- `E501` - 行长 → 换行
- `N802/N803` - 命名规范 → 改方法/变量名
- `B007` - 未使用的循环变量 → `_` 代替
- `SIM` - 简化代码 → 按建议改

### Step 4: 统一 ruff 配置

检查所有项目的 ruff select 是否一致。如不一致，统一到 workspace ruff.toml。

```bash
cd ~/Workspace && grep -A10 '\[tool.ruff.lint\]' ontoderive/pyproject.toml sophia/pyproject.toml minerva/pyproject.toml | grep 'select\|ignore'
```

### Step 5: 验证

```bash
cd ~/Workspace && make lint 2>&1 | tail -20
```

## 六、并行策略

Wave 1.2.A 可以拆分给 3 个 P7 agent 并行执行：

| Agent | 项目 |
|-------|------|
| P7-1 | ontoderive, pallas, sophia |
| P7-2 | minerva, agora, eidos, kronos |
| P7-3 | codeanalyze, iris, kos, bos-skill-cli, eCOS, gateway, Forge |

## 七、输出

| 文件 | 操作 |
|------|------|
| 各项目 `src/` 文件 | 修改 |
| `.omo/TASK_POOL.md` | T009-T020 → done |
| `.omo/STATE.md` | 更新进度 |

## 八、→ 下一个 Wave

完成后可并行触发 **Wave 1.2.B (项目健康度审计)** 和 **Wave 1.2.C (配置管理自动化)**。

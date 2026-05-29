# Task Prompt: Wave 4.C — 技术债清理

> 类型: P9 → P8 Task Prompt | 状态: pending (depends on Phase 3 gate) | 预估: 1.5h

## 一、目标

为 Forge、kronos、codeanalyze 增加基础测试覆盖，从 <1% 提升到核心路径通过。

## 二、范围

| 项目 | 当前测试 | 目标 | 核心路径 |
|------|---------|------|---------|
| Forge | 0 | ≥3 | 工具注册、发现、列表 |
| kronos | 1 | ≥3 | L0 抓取、配置加载 |
| codeanalyze | 3 | ≥10 | 分析、导出、审计 |

## 三、验收标准

```
☐ cd Forge && pytest -q — ≥3 测试通过
☐ cd kronos && pytest -q — ≥3 测试通过
☐ cd codeanalyze && pytest -q — ≥10 测试通过
☐ 不破坏 ruff 0 errors
```

## 四、输出

| 文件 | 操作 |
|------|------|
| `Forge/tests/` | 新增测试文件 |
| `kronos/tests/` | 新增测试文件 |
| `codeanalyze/tests/` | 新增测试文件 |
| `.omo/TASK_POOL.md` | T060-T062 → done |
| `.omo/STATE.md` | 最终进度 62/62 → 100% |

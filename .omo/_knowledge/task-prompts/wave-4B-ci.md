---
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-06-23
archived-since: 2026-06-23
note: "P56 R2: 全量兜底批量归档, 当前活跃以各面 INDEX/SSOT/PANORAMA.md 为准"
---
# Task Prompt: Wave 4.B — CI 基线建立

> 类型: P9 → P8 Task Prompt | 状态: pending (depends on Phase 3 gate) | 预估: 1h

## 一、目标

建立 GitHub Actions CI 基线，每次 push 自动运行 ruff check + pytest + check-config。

## 二、范围

| Workflow | 触发条件 | 执行内容 |
|----------|---------|---------|
| `ruff-check.yml` | push + PR | `ruff check src/` on all projects |
| `pytest.yml` | push + PR | `make test` |
| `config-check.yml` | push (仅 agora 路径) | `make check-config` |

## 三、验收标准

```
☐ .github/workflows/ruff-check.yml 存在
☐ .github/workflows/pytest.yml 存在
☐ .github/workflows/config-check.yml 存在
☐ 手动触发 `gh workflow run` 通过
```

## 四、输出

| 文件 | 操作 |
|------|------|
| `.github/workflows/ruff-check.yml` | 新增 |
| `.github/workflows/pytest.yml` | 新增 |
| `.github/workflows/config-check.yml` | 新增 |
| `.omo/TASK_POOL.md` | T057-T059 → done |

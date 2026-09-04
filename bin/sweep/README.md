---
type: ssot
---

# bin/sweep — Python 质量扫描工具链

> ADR-0367 主题 A / `governance-evolution-roadmap.yaml::sweep-tooling-scaling`
> 生命周期: Phase 1 (A1) · 2026-08-04

## 工具

| 工具 | 职责 | 输入 | 输出 |
|------|------|------|------|
| `pyright.py` | 从 pyright JSON 报告施加显式抑制 | `<pyright.json>` | 编辑后的源码 + 指标行 |
| `ruff.py` | 有界安全修复循环 | `<path>` | 收敛后的修复 + 剩余诊断 |
| `nested-with.py` | 合并可证明安全的嵌套 context manager | `<path>` | 改写后的源码（AST 验证） |
| `scan.py` | 全仓 / 变更项目扫描 + 指标归档 + INDEX 维护 | `--projects` / `--diff-mode` / `--strict` | `.omo/_knowledge/sweeps/<date>.json` (+ INDEX.md) |
| `sweep_index.py` | 派生 `INDEX.md`（C5, ADR-0373）；CI gate `--check` | `--out-dir` | `INDEX.md`（write 模式）或 drift 检测（check 模式） |

## 用法

```bash
# 1. 生成 pyright JSON 报告（在目标项目内）
cd projects/<project>
uv run pyright --outputjson > /tmp/pyright.json

# 2. 施加抑制（按项目过滤；测试文件重复规则可文件级抑制）
python3 bin/sweep/pyright.py /tmp/pyright.json --package <project>
python3 bin/sweep/pyright.py /tmp/pyright.json --package <project> --dry-run   # 只报告不改

# 3. 有界 ruff 修复（默认 3 轮收敛）
python3 bin/sweep/ruff.py projects/<project>
python3 bin/sweep/ruff.py bin/sweep --max-rounds 1

# 4. 合并简单嵌套 with（SIM117 结构改写，AST 解析兜底）
python3 bin/sweep/nested-with.py <path>
python3 bin/sweep/nested-with.py <path> --dry-run
```

## 参数

- `pyright.py`: `report`（必填）、`--package`、`--test-header-threshold`（默认 3）、`--dry-run`
- `ruff.py`: `path`（默认 `.`）、`--max-rounds`（默认 3）、`--unsafe-fixes`（默认关）
- `nested-with.py`: `path`（必填）、`--dry-run`

## 退出码

- `pyright.py`: 0（成功施加/干跑）；非 0（报告缺失或文件不可写）
- `ruff.py`: 0（收敛无诊断）；1（剩余诊断）；非 0/1 视为异常
- `nested-with.py`: 0（成功）；1（AST 解析失败，拒绝改写）

## 指标口径

`pyright.py` 末尾输出一行机器可读摘要：

```
errors=N files=M line_suppressions=X file_suppressions=Y suppression_ratio=Z.ZZZ
```

- `line_suppressions`: 行级 `# type: ignore[<rule>]` 数量
- `file_suppressions`: 文件级 `# pyright: <rule>=false` 头数量
- `suppression_ratio`: `(line + file 抑制的诊断数) / 总诊断数`
- A3 阶段将据此对 `suppression_ratio > 0.6` 或 `file_suppressions ≥ 3` 阻断 PR

## 安全边界

- 抑制必须带具体 pyright rule，禁止裸 `type: ignore`
- 不修改反斜杠续行；不跨复杂多行 `with` 头；不改写无法通过 AST 的结果
- `--unsafe-fixes` 默认关闭，只有人工审查后显式启用
- 零诊断 ≠ 正确性证明；真实契约错误必须先修实现，再谈抑制

## 测试

```bash
uv run pytest tests/test_sweep_tools.py -q
```

## 与 workflow 的关系

`agent-workflows.yaml::workflows.pyright-sweep` 是专属路由；`diff_checks.pyright-sweep-check`
覆盖 `bin/sweep/**` 与 `tests/test_sweep_tools.py`（A2 升级为 required 后成为门禁必跑项）。

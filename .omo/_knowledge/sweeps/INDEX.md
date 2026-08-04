# Sweep 扫描历史归档 (A5, ADR-0367)

> 本目录只存**指针与索引**, 不复制数据. 报告本体: `<date>.json` (由 `bin/sweep/scan.py` 落盘).
> 生成方式: `python3 bin/sweep/scan.py --projects <p1> <p2>`

| 日期 | 报告 | total_errors | suppression_ratio |
|------|------|-------------|-------------------|
| 2026-08-04 | [2026-08-04.json](2026-08-04.json) | 0 | 0.000 |

## 指标口径 (与 ADR-0366/P91 对齐)

- `errors`: pyright `severity=error` 诊断总数
- `line_suppressions`: 诊断行已有 `# type: ignore[<rule>]` 的数量
- `file_suppressions`: 文件头 `# pyright: <rule>=false` 覆盖规则的文件数
- `suppression_ratio`: (line + file 覆盖诊断) / errors

## 门禁

- `bin/sweep/pyright.py --suppression-gate`: `file_suppressions >= 3` 或 `suppression_ratio > 0.6` → exit 1 (A3)
- `pyright-sweep-check` diff_check: `required: true` (A2)

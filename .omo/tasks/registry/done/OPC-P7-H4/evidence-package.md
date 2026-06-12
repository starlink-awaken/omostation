# OPC P7-H4 文档同步 policy — Evidence Package

> Closeout: 2026-06-12
> Stage: OPC-P7 / Gate H / Sub-gate H4

## 1. doc-lint 跑通

```text
$ python3 scripts/opc_p7_doc_lint.py
returncode: 0
```

产物：

- `.omo/_delivery/doc-lint/2026-06-12.json`
- `.omo/_delivery/doc-lint/2026-06-12.md`
- `.omo/_delivery/doc-lint/index.json`

## 2. 4 类检查结果

| 维度 | 实证 |
|------|------|
| key docs presence | 6/6 present |
| phase doc consistency | P4-P7 全一致 |
| dead links | 0 |
| term consistency issues | 0 |

当前 `drift_total=0`。

## 3. 历史 index

```json
{
  "summary": {
    "run_count": 1,
    "latest_drift_total": 0
  }
}
```

H4 的验收边界是 lint 实现、零漂移结果、以及历史索引机制已经建好；不是伪造一个长时间窗。

## 4. 通过标准 checklist

| # | 标准 | 状态 | 证据 |
|---|------|:---:|------|
| 1 | 4 关键文档自动 lint | ✅ | 实际扫描 6 关键文档 |
| 2 | 跨文档术语一致 | ✅ | `term_consistency_issues=[]` |
| 3 | 0 stale | ✅ | `dead_links=[]`, `drift_total=0` |
| 4 | 持续运行索引已建立 | ✅ | `index.json` |

## 5. 红线遵守

- ✅ 不再把“同日多跑几次”硬说成“14+ 天窗口”
- ✅ doc-lint 结果与 phase docs 当前状态一致
- ✅ index 已建立，后续可按真实日期累积

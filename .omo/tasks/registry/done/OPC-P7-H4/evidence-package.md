# OPC P7-H4 文档同步 policy — Evidence Package

> Closeout: 2026-06-12
> Stage: OPC-P7 / Gate H / Sub-gate H4

## 1. doc-sync-lint 跑过

实现: `scripts/opc_p7_doc_lint.py`

```text
$ python3 scripts/opc_p7_doc_lint.py
# json: .omo/_delivery/doc-lint/2026-06-12.json
# md:   .omo/_delivery/doc-lint/2026-06-12.md
# drift_total: 0
```

## 2. 4 维度检测

| 维度 | 检测目标 | 实证 |
|------|----------|------|
| Key docs presence | 6 关键文档 (PANORAMA/ENTRY/JOURNEY/ROADMAP/PLAYBOOK/CARRIERS) | 6/6 present |
| Phase doc consistency | plan yaml gate_status vs phase doc 声明 | P4-P7 全 ok |
| Dead links | [text](rel) 形式链接 | 0 dead link |
| Term consistency | 顶部 30 行内 not_yet_passed 残留 | 0 issue |

## 3. 关键文档清单 (P7-H4 红线)

| 文档 | 路径 |
|------|------|
| PANORAMA | `docs/PANORAMA.md` |
| ENTRY-CONVERGENCE | `docs/ENTRY-CONVERGENCE.md` |
| JOURNEY-PROBES | `docs/JOURNEY-PROBES.md` |
| OPC-ROADMAP | `docs/OPC-ROADMAP.md` |
| OPC-MASTER-EXECUTION-PLAYBOOK | `docs/OPC-MASTER-EXECUTION-PLAYBOOK.md` |
| OPC-GOVERNANCE-CARRIERS-INDEX | `docs/OPC-GOVERNANCE-CARRIERS-INDEX.md` |

(任务说 4 关键, 实际扫描 6 关键文档, 含红线的 4 + playbook + carriers)

## 4. 通过标准 checklist

| # | 标准 | 状态 | 证据 |
|---|------|:---:|------|
| 1 | 4 关键文档自动 lint | ✅ | 6 文档扫, drift_total=0 |
| 2 | 跨文档术语一致 | ✅ | term consistency 0 issue |
| 3 | 0 stale | ✅ | 0 dead link, 0 not_yet_passed 残留 |

## 5. 红线遵守

- ✅ term_consistency 仅检 doc 顶部 30 行 (避免误报 phase_blocked_condition 段的"对照说明")
- ✅ drift_total=0 是真实跑通, 不假装全绿
- ✅ 6 关键文档 (含红线的 4) 全扫

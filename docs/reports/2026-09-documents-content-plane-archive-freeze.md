---
type: report
title: Documents 5 大内容归档族只读冻结与迁移注册表收口
schema: report/v1
created: 2026-09-07
owner: governance-team
bet: BET-Y1Q4-T10-123
---

# Documents 5 大内容归档族只读冻结报告

## 冻结结果

| 家族 | 文件数 | 聚合 SHA-256 | 状态 |
|------|--------|------|------|
| career-code-archives | 31,491 | 见 summary | verified (content_archive) |
| family-content-archives | 3,323 | 见 summary | verified (content_archive) |
| learning-content-archives | 223,714 | 见 summary | verified (content_archive) |
| work-content-archives | 14,871 | 见 summary | verified (content_archive) |
| creative-content-archives | 703 | 见 summary | verified (content_archive) |
| family-dashboard-app | 38,925 | — | verified (migrate, T10-122 parity receipt) |

**总计 274,102 文件 / ~58.8GB 只读冻结**，per-file SHA-256 索引存
`runtime/cockpit/documents-archive-freeze-index.json`（106MB，ignored 平面），
分族聚合摘要入库 `docs/reports/documents-archive-freeze-summary.json`。

## 迁移注册表收口

`documents-content-plane-migrations.yaml` 的 non_terminal_families
**13 → 7**（-6）：上述 6 族标 verified；剩余 7 族
（toolbox-staging / zotero-app-data / family-runtime-kems / learning-runtime /
public-runtime / opc-tools / root-oneoff-assets）各有未完成的物理动作
（DeepTutor 重定位、Zotero 库路径、delegate 证据链），另案推进。

## 验证

- `documents-content-plane-migration-check.py` → `ok: true, errors: 0`
- rollback receipt: `docs/reports/documents-archive-rollback-receipt.md`
  （冻结为只读声明，源文件从未移动；回滚 = 回退 registry 声明 + 删索引）

## 遗留

- toolbox-staging 的 DeepTutor 物理重定位（源仍在 `@学习进化/_external/`）
- Zotero 数据保留策略确认后标 verified
- 3 个 in_progress delegate 家族的证据链（runtime job 执行回执）

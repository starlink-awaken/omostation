---
schema_version: specification/v1
spec_version: 1.0.0
status: accepted
lifecycle: contract
owner: human-principal
created: 2026-08-27
last_updated: 2026-08-27
bet_id: BET-Y1Q3-T10-29
risk_level: L1
type: ssot
last_updated: 2026-09-03
---

# Workspace OCR preflight owner

## Objective

将当前失效的 Documents OCR 定时入口改为 Workspace-owned preflight。它只
检查显式 OCR source 是否存在、是否为安全目录、tesseract 与 `chi_sim`
是否可用，并输出结构化 finding；不运行 OCR、不创建/修改 Documents 文件。

## Contract

- 入口复用 `bin/gac/documents-domain-owner-job.py ocr-preflight`。
- source 只能由相对 Documents 路径指定，禁止绝对路径和 `..` 穿越。
- 输出 schema `documents.ocr-preflight.v1`，只含 source ref、engine/language
  readiness、bounded file count 和 status。
- `ready` 返回 0；source missing/unavailable 或 engine missing 返回 1；
  非法输入/路径边界返回 2。
- evidence 只能写 Workspace release root，Documents bytes/mtime 不改变。
- 原 OCR runner 保留作回滚和后续 parity 材料，本 BET 不删除、不迁移 OCR 内容。

---
type: ephemeral
created: 2026-09-03
---

# OCR preflight owner evidence — 2026-08-27

The former active OCR cron points at a missing Documents work directory:
`@工作文档/卫健委/_storage/06-工具/批量提取/ocr_20260731`.

This wave adds a Workspace-only preflight owner. It reports the missing source
truthfully and does not run or mutate the legacy OCR runner.

The installed half-month OCR cron now targets the clean versioned release
`accepted-20260908`; the schedule root was converged by T10-46. This report
records the OCR owner semantics and does not claim OCR quality parity.

Live preflight evidence: source status `missing`, files `0`, tesseract/`chi_sim`
status `ready`, overall status `findings`, exit `1`. Invalid traversal input
returned exit `2` with `source.status=invalid`. Focused tests were `4 passed`.
No OCR command and no Documents write was performed.

The active crontab contains exactly one `1st/16th 10:00` owner line pointing to
`accepted-20260908`. Its release-root reconciliation and rollback receipt are
recorded by T10-46; the original Documents migration remains a separate BET
boundary.

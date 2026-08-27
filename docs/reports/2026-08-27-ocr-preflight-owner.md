# OCR preflight owner evidence — 2026-08-27

The former active OCR cron points at a missing Documents work directory:
`@工作文档/卫健委/_storage/06-工具/批量提取/ocr_20260731`.

This wave adds a Workspace-only preflight owner. It reports the missing source
truthfully and does not run or mutate the legacy OCR runner.

The canonical schedule candidate targets the next versioned release
`accepted-20260828`; the current half-month OCR cron remains unchanged until that
release is built and the cutover is separately verified.

Live preflight evidence: source status `missing`, files `0`, tesseract/`chi_sim`
status `ready`, overall status `findings`, exit `1`. Evidence was written under
the Workspace run evidence directory; no OCR command and no Documents write was
performed.

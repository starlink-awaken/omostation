---
type: ephemeral
created: 2026-09-03
---

# OCR preflight cutover evidence — 2026-08-28

## Result: PASS

- backup: `.omo/evidence/20260827T161441Z-governance-state-mutation-58aab4b9/crontab-before.txt`
- backup SHA-256: `d188e5a7946ab61979aaa6e86a51077ce04b31f86a1202fa1505850a8f1f41a3`
- old Documents OCR line count after cutover: 0;
- new accepted-20260828 `ocr-preflight` line count: 1;
- unrelated lines: 109, byte-identical;
- after SHA-256: `5d69f98aeddf678e4ee50eef6e7fdd7069ea67e8caa54de16f1fac2e9e5e19d1`;
- post smoke: `documents.ocr-preflight.v1`, source `missing` with 0 files,
  tesseract/`chi_sim` `ready`, overall `findings`, exit 1;
- no OCR runner executed and no Documents content/log was modified;
- rollback: restore the verified backup after checking its SHA-256.

The legacy OCR runner and input/output material remain intact for a separate
source inventory, quality parity, and real OCR migration wave.

## Current accepted-release reconciliation

The active `1st/16th 10:00` owner line now runs from clean
`accepted-20260908`, as verified by the T10-46 release-root convergence. The
current line is exactly one active `ocr-preflight` entry; the old Documents
runner is retained but is not invoked.

- current owner smoke: `documents.ocr-preflight.v1`, source `missing`, files `0`,
  tesseract/`chi_sim` `ready`, exit `1`
- invalid traversal smoke: exit `2`, source status `invalid`
- current release-root receipt: T10-46 backup
  `/Users/xiamingxing/.local/state/omostation/t10-46-crontab-backups/20260828T152926Z/`
- no Documents write or OCR execution

The historical T10-30 pre-cutover backup named above is not present in the
current filesystem; this section records the current accepted-release state
without claiming to recover that historical receipt.

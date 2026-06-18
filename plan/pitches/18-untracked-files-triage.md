# Pitch: Untracked Files Triage & Archive

> **Upstream**: MS-OMO-SSOT
> **Appetite:** 0.5 day

## 🎯 The Why (Problem & Opportunity)

The root workspace has multiple categories of untracked files:
- `docs/OPC-*.md` (8 files) — OPC roadmap / execution playbook snapshots.
- `plan/pitches/15-deep-defensive-hardening.md` — a defensive hardening pitch.
- `runtime/data/atomic_test.jsonl` — runtime test residue.

These files are not under version control and risk being lost or causing `git status` noise.

## 🚧 The What (Solution Overview)

1. **Classify each untracked file:** keep, archive, or delete.
2. **Move OPC docs** to the appropriate `.omo/_knowledge/` or `docs/` path and commit.
3. **Move the deep-defensive-hardening pitch** to `plan/pitches/` if not already there and register with C2G if valuable.
4. **Delete or gitignore** `runtime/data/atomic_test.jsonl` if it is ephemeral test output.
5. **Update `.gitignore`** if needed to prevent future ephemeral files from appearing.

## 📏 Boundaries & Appetites

- **Appetite:** 0.5 day.
- **No-Gos:** Do not delete files without reviewing content; when in doubt, archive to `.omo/_knowledge/`.

## ⚠️ Rabbit Holes & Risks

- **SSOT risk:** OPC docs may duplicate `.omo/_knowledge/audits/`; deduplicate carefully.
- **History risk:** Some files may contain evidence needed for audits; preserve before deletion.

# PACKS/INDEX.md — Skills System Catalog

This directory contains standardized Packs — modular units of
capability adapted from [PAI/LifeOS](https://github.com/danielmiessler/LifeOS).
Each Pack is self-describing (SKILL.md), self-installing (INSTALL.md),
and self-verifying (VERIFY.md).

See `TAXONOMY.md` §10 (PACK concept) and `TELOS.md` §S2 (dormant-adapter
guard) for the rationale.

## Pack Index

| Pack | Path | Status | Purpose |
|---|---|---|---|
| dormant-adapter | [`dormant-adapter/`](dormant-adapter/) | ACTIVE | P74 gate: detect consumers that declare bus-foundation in their dependencies but have no production call site |

## Adding a New Pack

1. Create `<pack-name>/SKILL.md` with frontmatter (name, version, triggers, scope, out_of_scope)
2. Create `<pack-name>/INSTALL.md` describing dependencies and install steps
3. Create `<pack-name>/VERIFY.md` with bash checks
4. Move or symlink the implementation into `<pack-name>/src/`
5. Update this INDEX

## Pack Format

```
PACKS/<name>/
├── SKILL.md      # Frontmatter + triggers + scope
├── INSTALL.md    # 5-phase AI wizard
├── VERIFY.md     # bash validation
└── src/
    ├── Tools/    # Implementation
    └── Tests/    # Test files
```

## Backward Compatibility

Old paths (`bin/ssot/bus-usage-report.py`) remain as symlinks to
`bin/ssot/PACKS/<name>/src/Tools/<name>.py` so existing CI gates
(`gac-local-gate.py`) keep working without modification.

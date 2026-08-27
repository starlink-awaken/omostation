---
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-06-23
archived-since: 2026-06-23
note: "P56 R2: 历史能力/过程/治理/参考/愿景文档批量归档, 当前活跃文档以各面 INDEX/SSOT 为准"
---
# OMO reroot and Workspace adaptation design

Date: 2026-06-02
Status: approved-by-default baseline (user unavailable; proceeded with recommended option)
Scope: external OMO reroot + Workspace `.omo` bridge adaptation

## 1. Context

There are now two strongly related but distinct OMO surfaces:

1. the **external OMO methodology system** under `~/Documents/学习进化/经验积累/OMO`
2. the **Workspace governance kernel** under `/Users/xiamingxing/Workspace/.omo`

The external OMO has reached `v1.6` and closed its current abstraction layer through:

- four-plane methodology structure
- 39 playbooks (`03-41`)
- portfolio governance closure (`39/40/41`)
- portfolio object / contract / pattern compression (`05/06`, patterns `06/07`)

The Workspace `.omo` is already a live SSOT/governance kernel with its own four-plane navigation shell, but it still references the external OMO by the old path in at least some places, and it does not yet explicitly treat the external OMO as a **knowledge-system canon that now lives under a stronger “知识进化/体系” root**.

The user request is not just to move files. It is to:

1. reroot the external OMO mechanism under `知识进化/体系`
2. upgrade the Workspace `.omo` so it adopts, references, and governs against that rerooted canon cleanly

## 2. Goals

This work should:

1. move the external OMO methodology to a more canonical knowledge-system location under `~/Documents/学习进化/体系/`
2. preserve reader continuity for the old `经验积累/OMO` path through a minimal compatibility layer
3. update Workspace `.omo` to reference the rerooted OMO canon instead of the old location
4. make the relationship explicit: external OMO is the methodology canon; Workspace `.omo` is the live governance kernel / SSOT
5. keep the migration bounded to the current OMO layer without reopening unrelated architecture work

## 3. Non-goals

This work does not:

1. redesign the external OMO methodology content itself beyond what rerooting and adaptation require
2. turn Workspace `.omo` into a copy of the external OMO
3. mirror the full external OMO content into `.omo/_knowledge/`
4. introduce new playbooks or patterns unless migration/adaptation exposes a direct structural gap
5. refactor unrelated Workspace systems outside OMO pathing, navigation, and governance adaptation

## 4. Approaches considered

### A. Recommended: soft reroot with compatibility shell

Create a new canonical home at `~/Documents/学习进化/体系/OMO`, move the external OMO there, leave a minimal compatibility shell at the old `经验积累/OMO` path, and upgrade Workspace `.omo` to reference the new canonical home.

- Pros: safest migration, preserves old links, creates a cleaner knowledge-system hierarchy, minimizes reader breakage
- Cons: requires a small amount of redirect/compatibility maintenance

### B. Hard move only

Move the external OMO from `经验积累/OMO` to the new root and rewrite all known references in one pass with no compatibility shell.

- Pros: cleanest end-state, least duplication
- Cons: brittle; any missed absolute reference or human bookmark breaks immediately

### C. Dual-stack mirror

Keep full copies in both places and treat them as two equivalent homes.

- Pros: zero short-term breakage
- Cons: creates shadow truth, doubles maintenance burden, violates the “single canon” intent of this migration

## 5. Recommended design

Use **Approach A**.

The migration should be treated as a **canonical reroot**, not a content rewrite:

1. `~/Documents/学习进化/体系/OMO` becomes the new methodology canon
2. `~/Documents/学习进化/经验积累/OMO` is reduced to a compatibility shell that clearly says the canon moved
3. Workspace `.omo` upgrades from implicit awareness of the old external OMO to an explicit bridge model:
   - `.omo` owns live governance state
   - external OMO owns methodology canon / abstract operating method
   - `.omo` may reference, adopt, and bridge the canon, but must not shadow-copy it

## 6. Target architecture

### 6.1 External methodology root

New canonical location:

- `~/Documents/学习进化/体系/OMO/`

Role:

- authoritative home for the external OMO methodology system
- reader-facing methodology canon
- place where README / INDEX / plane docs continue to live

### 6.2 Legacy compatibility root

Legacy location retained as compatibility shell:

- `~/Documents/学习进化/经验积累/OMO/`

Role:

- redirect old readers and old absolute references
- contain only minimal entry files if possible
- clearly point to the canonical rerooted location

### 6.3 Workspace `.omo`

Role after adaptation:

- remains the live governance kernel and SSOT shell
- gains explicit documentation of how it adopts / references the external OMO canon
- updates hardcoded references and tests that still assume the old external path

## 7. Required outputs

This design should produce the following classes of change.

### 7.1 External OMO reroot outputs

1. new canonical directory tree under `~/Documents/学习进化/体系/OMO`
2. migrated OMO content at the new location
3. minimal compatibility entry files at the old location
4. reroot wording in the external OMO README / INDEX / AGENT / CLAUDE surfaces where needed

### 7.2 Workspace `.omo` adaptation outputs

1. `.omo` docs that explain the external-canon vs live-kernel relationship
2. replacement of hardcoded old-path references where they are part of live `.omo` logic or tests
3. any new bridge/reference doc needed to keep the relationship explicit and auditable
4. updated tests that validate the new canonical path

### 7.3 Planning / evidence outputs

1. a migration/adaptation implementation plan in `docs/superpowers/plans/`
2. session continuity notes updated after execution
3. verification evidence showing:
   - new canonical home exists
   - old path redirects clearly
   - `.omo` references are updated
   - tests/docs checks reflect the new path

## 8. Migration sequence

### Phase A — Canonical reroot

1. create `~/Documents/学习进化/体系/OMO`
2. migrate the external OMO structure into the new root
3. verify the rerooted tree contains the expected OMO surfaces

### Phase B — Compatibility shell

1. leave the old `经验积累/OMO` path in place as a minimal shell
2. provide a concise redirect notice in the old root entry surfaces
3. avoid maintaining two full canon copies over time

### Phase C — Workspace `.omo` adaptation

1. locate live `.omo` references to the old external path
2. update tests/docs/bridges to the new canonical path
3. add an explicit bridge doc or upgrade existing navigation docs so the external methodology canon is discoverable from `.omo`

### Phase D — Verification and closeout

1. verify the new path exists and is readable
2. verify the old path clearly redirects
3. verify `.omo` no longer depends on the old path for live behavior
4. verify no open migration work item remains

## 9. Error handling and safety rules

1. do not leave two silently divergent full copies as long-term canon
2. do not delete the old path before all known Workspace `.omo` references are updated
3. if compatibility must be temporary, say so explicitly in the old-path shell
4. preserve the rule that external OMO is not repo `.omo` SSOT
5. prefer redirect/bridge wording over silent path swaps so future readers understand what changed

## 10. Testing and verification

Verification should cover:

1. filesystem proof that the new canonical OMO root exists
2. proof that the old root contains clear redirect/compatibility entry files
3. search proof that live `.omo` references no longer hardcode the old canonical path where the new path should be used
4. any existing `.omo` tests affected by the external path change
5. spot-checks of key navigation files in both systems

## 11. Success criteria

This design is successful when:

1. the external OMO canon lives under `~/Documents/学习进化/体系/OMO`
2. the old `经验积累/OMO` path no longer acts like the primary canon and instead behaves as a compatibility/redirect shell
3. Workspace `.omo` explicitly references and bridges to the new canonical OMO home
4. the live Workspace `.omo` no longer depends on the old path as if it were canonical
5. the migration is bounded, auditable, and does not reopen unrelated OMO architecture work

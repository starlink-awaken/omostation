# BET-Y2Q4-T10-253 Shared Skill Recovery Receipt

- Workspace: `/Users/xiamingxing/Workspace`.
- Managed worktree: `/Users/xiamingxing/ws-lifeos-magpie-skill-links-253`.
- No commit or push was made.
- No credentials were read or hashed.

## Final source decisions

- The Magpie Library is the single shared source for the seven Bailian skills. A pre-change source comparison recorded Library version 2.2.1 and separate `.bailian/skills` copies at 2.1.0, with additional references in several Library files. Version metadata is not represented in the latest static audit; that audit verifies paths and content fingerprints.
- The Workspace `.agents/skills/<bailian-skill>` entries point to the Magpie Library. A temporary direct-link experiment to `.bailian/skills` was reversed after static evidence showed duplicate roots and `UNRESOLVED_MAPPING` conflicts. No direct `.bailian` target remains in these seven Workspace entries.
- Magpie's supported `library skill use-library <name> <agent>` action was applied to the seven skills across the 17 clients with detected conflicts. The existing per-agent copies were retained in Magpie's timestamped backups. The current static audit confirms the repaired assigned skill source observations resolve and match.
- Browser and Utilities now resolve under the managed physical source `/Users/xiamingxing/.config/magpie/library/recovered/Utilities`; KEMS resolves under `/Users/xiamingxing/.config/magpie/library/recovered/kems-gate-integrity-audit`. Copies were made from the verified backups, preserving content. Utilities has 17 `SKILL.md` files in both source and destination, no internal symlinks, and matching root and Browser hashes. KEMS source and destination hashes match. Original backups remain intact as recovery fallbacks.
- A later Magpie update created cyclic Library links for Investigation, Media, Utilities, and the two used Bailian skills. Their verified source files were recovered from the timestamped Magpie backup to the managed `library/recovered/` tree. The old link values are captured in `/Users/xiamingxing/.config/magpie/backups/repair-20261015T191453/library-links/link-targets.json` and `library-links-before.tar`; those records are evidence of the old links, not rollback targets. The existing client links now resolve through the managed copies.
- The selected Library source paths for Browser, Utilities, KEMS, the seven in-scope Bailian skills, and the restored Investigation/Media entries match in the audit; no canonical source file was edited. Two additional Bailian skills are tracked separately as supplemental evidence.
- The empty Library entry for `kems-gate-integrity-audit` remains preserved as `kems-gate-integrity-audit.empty-preserved-20261015`; its shared pointer resolves to the managed recovery copy. The 2026-10-11 backup has the same `SKILL.md` SHA-256. This restores the WorkBuddy assignment without editing the skill.

## Shared Library pointer changes

| Entry | Original target | Current target | Verified evidence |
|---|---|---|---|
| `~/.config/magpie/library/skills/Browser` | `/Users/xiamingxing/dotfiles/sharedconf/Skills-Common/Browser` | `Utilities/Browser` | `SKILL.md` SHA-256 `04492322519bae60b6be361e9c59144458848603b21a39ff459fcedd2e55160e` |
| `~/.config/magpie/library/skills/browser/SKILL.md` | missing | `../../recovered/Utilities/Browser/SKILL.md` | Same verified Browser source hash; lowercase alias serves the existing Droid mapping |
| `~/.config/magpie/library/skills/Utilities` | `/Users/xiamingxing/.agents/skills/Utilities` | `../recovered/Utilities` | `SKILL.md` SHA-256 `8385d545baca4b7ca4cafaf9f38a374dc16ea391328e1cc168123cffc64cac84` |
| `~/.config/magpie/library/skills/Investigation` | cyclic link through `~/.agents/skills/Investigation` | `../recovered/Investigation` | Root `SKILL.md` SHA-256 matches the prior healthy audit |
| `~/.config/magpie/library/skills/Media` | cyclic link through `~/.agents/skills/Media` | `../recovered/Media` | Root `SKILL.md` SHA-256 matches the prior healthy audit |
| `~/.config/magpie/library/skills/bailian-cli` | cyclic link through `~/.agents/skills/bailian-cli` | `../recovered/bailian-cli` | Root `SKILL.md` SHA-256 matches the prior healthy audit |
| `~/.config/magpie/library/skills/bailian-gen` | cyclic link through `~/.agents/skills/bailian-gen` | `../recovered/bailian-gen` | Root `SKILL.md` SHA-256 matches the prior healthy audit |
| `~/.config/magpie/library/skills/kems-gate-integrity-audit` | empty physical directory | `../recovered/kems-gate-integrity-audit` | `SKILL.md` SHA-256 `473d3d636affa483e9d3c3aff7c8fea25833a09d42cd6ba4f2677c4381b6d646` |

## Fresh static audit

- Receipt: `/Users/xiamingxing/Documents/Codex/2026-10-07/new-chat/outputs/magpie-integration-snapshots/mp015-recovered-sources-20261015.json` (mode `0600`).
- 40 clients inspected. Rendered: `FAIL=0`, `UNKNOWN_NOT_RUN=36`, `UNRESOLVED_MAPPING=3`, `DISABLED_BY_POLICY=1`.
- Detected: 31/31 PASS; desired: 39/39 PASS. The companion selection manifest records 158/158 `PASS` observations for this BET's ten shared entries plus restored Investigation/Media sources, and 38/38 supplemental `PASS` observations for two Bailian skills outside this BET scope.
- Loaded: 40/40 `UNKNOWN_NOT_RUN`. Usable: 40/40 `UNKNOWN_NOT_RUN`. This static audit proves paths and scoped source matching, not that every agent loaded or executed the skills.
- Remaining static findings: agy, Claude, and Cline MCP entries are `UNRESOLVED_MAPPING`; Cline global instructions are `DISABLED_BY_POLICY`. These remain unresolved pending native client/runtime evidence. Errors and warnings are empty.

## Rollback

- For a specific client and skill migrated by Magpie, restore its own preserved version with `magpie library skill keep-own <skill> <agent>`; Magpie removes that client from the Library assignment and keeps the Library source intact.
- Never restore the old reciprocal links. If a managed copy fails hash verification, copy the named source from a retained backup into a new directory under `~/.config/magpie/library/recovered/`, verify its `SKILL.md` hash against this receipt, preserve the current Library pointer in a new dated backup, then repoint that one Library entry to the verified copy and rerun the static audit. Sources: Utilities (including Browser) `/Users/xiamingxing/.config/magpie/backups/2026-10-15_17-38-27.003/skills/Utilities`; Investigation, Media, bailian-cli, and bailian-gen `/Users/xiamingxing/.config/magpie/backups/2026-10-15_18-58-51.086/skills`; KEMS `/Users/xiamingxing/.config/magpie/backups/2026-10-14_11-41-31.848/skills/kems-gate-integrity-audit` or the identical 2026-10-11 copy.
- If either pointer differs from both the current and original target, stop and inspect it before rollback.

## Completion state

This receipt records the shared skill recovery work. The accepted specification and ledger now bind to v1.0.4 digest `23ddde6eb8395d70bbd106f315983e7c238e11b45f2c0f4fecc43897bd929633`; v1.0.4 separates 158 in-scope observations from 38 supplemental ones. The previous BET-bound run `20261015T113415Z-external-adapter-sync-c9f52b8b` used the prior v1.0.3 binding. The final v1.0.4-bound run is `20261015T115750Z-external-adapter-sync-508e08ab`, bound to SHA-256 `23ddde6eb8395d70bbd106f315983e7c238e11b45f2c0f4fecc43897bd929633`; its affected graph is `.omo/evidence/bet253-requirement-iteration-affected-graph-v1.0.4.json`. Persistent command logs and a hash manifest are recorded in `/Users/xiamingxing/Documents/Codex/2026-10-07/new-chat/outputs/magpie-integration-snapshots/mp016-bet253-gate-logs-20261015/` and `mp016-bet253-verification-20261015.json` (mode 0600). Doctor, workflow lint, and workflow compliance pass. SSOT guardian fails on task_count_drift (stored 331 completed/7 planned/339 total; actual 336/6/343). GaC local gate fails on evidence freshness (86.0 below 90) and an ignored, unregistered `.tokensave` root directory; current-state coherence also reports the task-count mismatch. Workflow verify fails on these shared-workspace gates while unrelated paths are dirty. The review found no baseline proving these failures predated this BET, so their attribution remains unproven. No unrelated workspace data was edited to clear the gates. The run is being closed as blocked pending diagnosis of the gate failures, a baseline comparison, and fresh verification. Full LifeOS native-session proof, client MCP reload checks, and Magpie's broader P0–P4 optimization remain in progress.



## Independent final gate review

- Reviewer: `/Users/xiamingxing/Workspace/.omo/evidence/BET-Y2Q4-T10-253-gate-review.md`; verdict REJECT for terminal closeout at review time, with no finding against the static source repair itself. It confirms the spec/ledger/run binding, source pointers, audit and log hashes, and recommends terminal `blocked` status.
- The reviewer found no baseline evidence to prove all SSOT/GaC failures predated the BET. Failure attribution is therefore recorded as unproven.
- The v1.0.4-bound workflow run closed as `blocked` at 2026-10-15T12:07:59Z. Post-close compliance passes with 0 active runs and 0 locks; the result and protected log hash are recorded in `mp016-bet253-verification-20261015.json`. The BET ledger remains `in_progress` pending gate baseline/repair and a new verification run.



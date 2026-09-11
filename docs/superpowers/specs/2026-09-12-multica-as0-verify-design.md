---
schema_version: specification/v1
spec_version: 1.0.0
status: accepted
lifecycle: contract
owner: governance-team
created: 2026-09-12
last-reviewed: 2026-09-12
title: Multica AS0 read-only admission verify toolchain
bet_id: BET-Y1Q4-T10-150
implementation_authorized: true
value_indicator_policy: false
risk_level: L2
human_gate: true
---

# Multica AS0 read-only admission verify toolchain

## 1. Status and authority

Accepted contract for `BET-Y1Q4-T10-150`. Version 1.0.0 authorizes exactly one
write surface:

```text
bin/gac/multica-as0-verify.py
```

AS0 means **observer / admission evidence only**. This Spec does not admit
Multica as a writer control plane and must not create/update/delete/trigger
issues, autopilots, agents, squads, or daemon start/stop/restart.

## 2. Goals

1. Provide one reproducible read-only verifier: `python3 bin/gac/multica-as0-verify.py --json`.
2. Cover **30** Multica read probes with explicit argv, expected shape, and pass/fail.
3. Cover **7** topology relations derived from list/get payloads.
4. Cover **trust-domain / privacy** negative cases proving isolation fail-closed.
5. Exit 0 only when API matrix, topology, and trust negatives all pass; otherwise
   non-zero with structured JSON.

## 3. Non-goals

- No Multica writer admission; no dispatch/create/update/delete/trigger.
- No changes to `projects/omo` resident executor Multica R3 path.
- No completion/value evidence expansion on the BET beyond engineering verify green.
- No A6 Orca work.

## 4. API matrix (30)

Each probe is `multica <argv...>` with timeout, capturing rc/stdout/stderr.
Probes that need an ID take the first id from a prior successful list in the
same run; if the list is empty the get-probe is recorded as `SKIPPED_EMPTY`
(counts toward coverage, not as fail).

| # | id | argv |
|---|---|---|
| 1 | version | `version` |
| 2 | auth_status | `auth status` |
| 3 | config_show | `config show` |
| 4 | daemon_status | `daemon status --output json` |
| 5 | daemon_disk_usage | `daemon disk-usage --output json` |
| 6 | user_profile | `user profile --output json` (fallback without `--output` if unsupported) |
| 7 | workspace_list | `workspace list --output json` |
| 8 | runtime_list | `runtime list --output json` |
| 9 | agent_list | `agent list --output json` |
| 10 | squad_list | `squad list --output json` |
| 11 | project_list | `project list --output json` |
| 12 | repo_list | `repo list --output json` |
| 13 | issue_list | `issue list --output json` |
| 14 | label_list | `label list --output json` |
| 15 | skill_list | `skill list --output json` |
| 16 | autopilot_list | `autopilot list --output json` |
| 17 | property_list | `property list --output json` |
| 18 | workspace_get | `workspace get <id> --output json` |
| 19 | agent_get | `agent get <id> --output json` |
| 20 | squad_get | `squad get <id> --output json` |
| 21 | project_get | `project get <id> --output json` |
| 22 | issue_get | `issue get <id> --output json` |
| 23 | skill_get | `skill get <id> --output json` |
| 24 | label_get | `label get <id> --output json` |
| 25 | autopilot_get | `autopilot get <id> --output json` |
| 26 | property_get | `property get <id> --output json` |
| 27 | issue_list_status_filter | `issue list --status todo --output json` |
| 28 | issue_list_fields | `issue list --fields id,title,status,project_id --output json` |
| 29 | runtime_list_repeat | second `runtime list --output json` (idempotent read) |
| 30 | agent_list_include_archived | `agent list --include-archived --output json` |

Pass rule for list/status/version/auth/config: rc==0 and stdout parseable when
`--output json` is used (or non-empty text for version/auth/config without json).

## 5. Topology relations (7)

| # | id | assertion |
|---|---|---|
| T1 | agent_runtime_refs | every agent.runtime_id (if present) ∈ runtime.id set |
| T2 | squad_member_refs | every squad leader/member agent id ∈ agent.id set |
| T3 | issue_project_refs | every issue.project_id (if present) ∈ project.id set |
| T4 | squad_count_readable | squad list returns array (expected local count may be 7; soft-warn if ≠7) |
| T5 | runtime_daemon_overlap | daemon_status.agents names intersect runtime custom_name/name set non-emptily when both non-empty |
| T6 | workspace_resource_scope | listed agents/squads/projects are non-null JSON under the active workspace |
| T7 | repo_list_readable | repo list returns array (urls are strings) |

## 6. Trust-domain negatives

| # | id | action | expected |
|---|---|---|---|
| N1 | fake_workspace_id | `workspace list` / `agent list` with `--workspace-id 00000000-0000-4000-8000-000000000000` | must not return the real workspace inventory unchanged; empty/error/different scope required |
| N2 | fake_profile | `agent list --profile __as0_nonexistent_profile__ --output json` | fail-closed (non-zero) or empty isolated profile; must not silently dump default workspace writers |
| N3 | write_argv_guard | static scan of verifier source | argv matrix contains none of create/update/delete/trigger/start/stop/restart/dispatch/login/setup |

Note: `multica project status` and `multica issue status` mutate state and are
forbidden in AS0 probes despite the verb name.

## 7. Circuit breaker

If any probe argv would mutate Multica state, stop immediately. The verifier
must only subprocess the allowlisted read argv above.

## 8. Acceptance

- `python3 bin/gac/multica-as0-verify.py --json` exits 0 on a healthy Multica login.
- JSON reports `api.passed == 30` (including SKIPPED_EMPTY), `topology.passed == 7`,
  `trust.passed == 3`.
- No writer Multica commands appear in the executed argv log.

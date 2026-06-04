# Governance Overlay Status

Overlay: GOV-OVERLAY-2026-06
Generated at: 2026-06-03T11:03:00Z
Current milestone: GOV-M3-FUTURE-PROMOTION-OPERATIONS
Next milestone: none
Eligible items: 0
Blocked items: 0
Next action: monitor:GOV-M3-FUTURE-PROMOTION-OPERATIONS

## Active roadmap item: GOV-M3-FUTURE-PROMOTION-OPERATIONS

title=Promotion-driven future phase operations
priority=P1

target_ref=.omo/tasks/planned/P19-W3-ARCHIVE-TS.yaml
task_id=P19-W3-ARCHIVE-TS
state=planned_promotion_blocked
blockers=phase_mismatch

target_ref=.omo/tasks/planned/P24-W2-NUCLEUS-REPLACE.yaml
task_id=P24-W2-NUCLEUS-REPLACE
state=planned_approval_prep_pending
blockers=phase_mismatch,approval_invalid

target_ref=.omo/tasks/planned/P25-W1-E2E-INTEGRATION.yaml
task_id=P25-W1-E2E-INTEGRATION
state=planned_promotion_blocked
blockers=phase_mismatch

target_ref=.omo/tasks/planned/P25-W2-DOCS-DEBT-CLOSURE.yaml
task_id=P25-W2-DOCS-DEBT-CLOSURE
state=planned_promotion_blocked
blockers=phase_mismatch

## Active monitor summary

blocked_target_count=4
state_histogram=planned_promotion_blocked:3,planned_approval_prep_pending:1
blocker_histogram=phase_mismatch:4,approval_invalid:1
approval_blocked=P24-W2-NUCLEUS-REPLACE
phase_blocked=P19-W3-ARCHIVE-TS,P24-W2-NUCLEUS-REPLACE,P25-W1-E2E-INTEGRATION,P25-W2-DOCS-DEBT-CLOSURE
prep_task_count=1
prep_request_now=0
prep_awaiting_approval=1
prep_trend_status=trend_available
prep_window_event_count=2
prep_changed=P24-W2-NUCLEUS-REPLACE
prep_exited=none
prep_followup=none
prep_escalation=none

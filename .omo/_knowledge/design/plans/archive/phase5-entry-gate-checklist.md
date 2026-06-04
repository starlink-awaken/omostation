# Phase 5 entry gate checklist

> **Purpose**: make Phase 5 executable without allowing planning ambiguity to leak into runtime implementation.

---

## EG-1 Phase boundary

- [x] Phase 4 Wave 1 complete
- [x] Phase 4 Wave 2 complete
- [x] Phase 4 closeout retrospective linked
- [x] current state shows `phase_status: completed`
- [x] current state shows `next_milestone: Phase 5 entry gate`

## EG-2 Task Center landing model

- [ ] `_truth/task-center/` owner entities frozen
- [ ] `_delivery/task-center/` owner entities frozen
- [ ] runtime snapshots do not reappear in truth plane
- [ ] plane-native domain rule documented in live design docs

## EG-3 Secret and compatibility boundary

- [ ] `secret_ref` backing store chosen
- [ ] secret rotation and audit rule documented
- [ ] Hermes Direction A chosen or explicitly rejected with written rationale
- [ ] Hermes retained scope is frozen to ingress + memory + bounded fallback dependencies
- [ ] Hermes is no longer treated as scheduler backbone for new work
- [ ] no live doc implies Hermes is the core SSOT

## EG-4 Governance contract

- [ ] proposal schema frozen
- [ ] governance levels L0-L3 frozen
- [ ] approval boundary for L2/L3 operations frozen
- [ ] audit linkage defined

## EG-5 Review freshness

- [ ] architecture review marked absorbed/blocking/deferred by finding
- [ ] security review marked absorbed/blocking/deferred by finding
- [ ] ops reliability review marked absorbed/blocking/deferred by finding
- [ ] phase5 requirements and task-center requirements point to the same live constraints

## EG-6 Execution readiness

- [ ] `G5.0` shell defined
- [ ] only Wave 0 tasks are prepared for `tasks/active/`
- [ ] Wave 1 remains gated
- [ ] Wave 0 verification and retrospective expectations are written

## Entry decision

| Item | Result |
|------|--------|
| Current status | NOT READY YET |
| Blocking area | landing model / secrets / Hermes boundary / governance contract / review refresh |
| Next action | finish Wave 0 planning-to-execution packet |

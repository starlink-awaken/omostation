---
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-06-23
archived-since: 2026-06-23
note: "P55 R2: phase 子目录历史总结批量归档, 当前阶段以 .omo/state/system.yaml 为准"
---
# Phase 3 acceptance report

| Category | Suite | Status | Passed | Failed |
| --- | --- | --- | ---: | ---: |
| workspace | wksp-orchestration | PASS | 32 | 0 |
| capabilities | kos-skill-router | PASS | 3 | 0 |
| capabilities | minerva-cross-domain-research | PASS | 3 | 0 |
| capabilities | metaos-capability-tools | PASS | 3 | 0 |
| capabilities | iris-wechat-connector | PASS | 2 | 0 |
| recovery | gbrain-memory-and-recovery | PASS | 175 | 0 |

Totals: passed=218 failed=0 suites=6

## Commands
- `wksp-orchestration`: `/opt/homebrew/opt/python@3.14/bin/python3.14 -m pytest packages/wksp/src/wksp/tests/test_e2e_journey.py packages/wksp/src/wksp/tests/test_cli_mcp.py packages/wksp/src/wksp/tests/test_cli_research_publish.py packages/wksp/src/wksp/tests/test_cli_research_restore.py packages/wksp/src/wksp/tests/test_cli_research_reliability.py -q`
- `kos-skill-router`: `/opt/homebrew/opt/python@3.14/bin/python3.14 -m pytest packages/kos/tests/test_mcp_server.py -q --tb=short -k SkillRouter`
- `minerva-cross-domain-research`: `/opt/homebrew/opt/python@3.14/bin/python3.14 -m pytest packages/minerva/tests/unit/test_mcp_server.py -q --tb=short -k cross_domain_research or build_cross_domain_report`
- `metaos-capability-tools`: `/opt/homebrew/opt/python@3.14/bin/python3.14 -m pytest packages/metaos/tests/test_unit.py -q --tb=short -k CapabilityTools`
- `iris-wechat-connector`: `/opt/homebrew/opt/python@3.14/bin/python3.14 -m pytest packages/iris/tests/test_new_connectors.py -q --tb=short -k WeChatConnector`
- `gbrain-memory-and-recovery`: `bun test test/memory-tree-op.test.ts test/e2e/worker-abort-recovery.test.ts test/minions.test.ts`

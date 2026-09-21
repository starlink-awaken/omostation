# Workflow Waiver Record

**Date**: 2026-09-21  
**Agent**: governance-agent  
**Scope**: agora PEP monitoring / submodule pin consistency / service endpoint configuration  

## Reason
User explicitly authorized direct implementation after confirming no existing active BET covers the `projects/agora` write surfaces needed for these fixes.

## Authorized Work
- `projects/agora/src/agora/mcp/policy_enforcement.py` — PEP bypass monitoring/logging
- `projects/agora/src/agora-services.json` — endpoint configuration refactor
- `.omo/_truth/registry/agent-workflows/` — submodule pin consistency validation
- `.agora/agora-proxy-services.json` — gbrain path correctness

## User Confirmation
User said: "go 推进吧" and "依次推进吧，我给你授权"

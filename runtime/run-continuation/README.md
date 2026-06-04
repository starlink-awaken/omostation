# runtime/run-continuation/

This directory holds **session continuation heartbeat files** and other
lightweight continuity markers for active or recently active sessions.

Phase 9 moved this responsibility out of `.omo/` because these records are:

1. runtime residue, not governance truth
2. ephemeral operational markers, not durable delivery evidence
3. workspace-level continuation state, not project source code

## What belongs here

1. session heartbeat JSON files
2. idle/active continuation markers
3. temporary continuity metadata for local session recovery

## What does not belong here

1. `.omo` goals, state, or task YAML
2. durable evidence and retrospectives
3. project-local runtime artifacts that belong under a specific project

## Handoff: team-plan → team-exec

- **Decided**: 6-task decomposition covering all remaining omostation architecture work. Tasks run independently in parallel except Task #4 (integration verification) which depends on all others.
- **Rejected**: Full P17-P25 sequential execution (too slow, much code already exists). Splitting BaseMembrane/Nucleus into separate workers (they touch different file patterns, safe to parallelize).
- **Risks**: BaseMembrane (114 refs) and Nucleus (123 refs) may appear in same files → potential edit conflicts. Mitigation: assign to separate workers with task watchdog. SharedBrain cleanup (107K→5K) is aggressive but organs already archived.
- **Dependencies**: Task #4 (worker-6, integration) blocked by Tasks #1, #2, #3, #5, #6
- **Worker map**:
  - worker-1 → Hermes Console Phase B + Tests (hermes-console/)
  - worker-2 → Nucleus 123引用替换 (kairon/)
  - worker-3 → SharedBrain 107K清理 (SharedBrain/)
  - worker-4 → BaseMembrane 114引用清零 (kairon/)
  - worker-5 → OMO任务状态同步 (.omo/)
  - worker-6 → 全量集成验证 (waits for all)
- **Remaining**: Spawn workers, monitor progress, verify + merge results

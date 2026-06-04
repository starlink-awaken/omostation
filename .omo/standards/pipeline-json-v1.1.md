# pipeline:json v1.1 contract

`pipeline:json` v1.1 is the chain-mode interchange envelope used across the knowledge pipeline.

## Required top-level shape

```json
{
  "$id": "pipeline:json:v1.1",
  "pipeline": {
    "version": "1.1",
    "tool": "minerva",
    "action": "research",
    "timestamp": "2026-05-28T00:00:00Z",
    "step": 0
  },
  "meta_type": "fact",
  "data": {},
  "provenance": {
    "source": "cli:research",
    "confidence": 0.8,
    "pipeline_input": null,
    "agent_id": "io.github.sharedbrain.minerva"
  },
  "artifacts": []
}
```

## Notes

1. `pipeline.version` must remain `1.1`
2. `pipeline.tool`, `pipeline.action`, and `pipeline.timestamp` are required
3. `provenance.agent_id` records the producing agent/tool identity
4. `artifacts` is reserved for emitted files, traces, or other structured outputs

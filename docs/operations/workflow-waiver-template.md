# Workflow waiver 证据模板（ADR-0203 窄豁免）

> 仅当用户 **书面明确** 允许跳过 agent-workflow 时使用。  
> 豁免不是默认路径；滥用会使 ADR-0203 失效。

## 何时可用

| 允许 | 不允许 |
|------|--------|
| 用户原话写明「跳过 workflow / 不用 start」 | agent 自行判断「太小不必」 |
| pure 只读问答（无需 waiver） | 已经 stage 需求面文件却无 run |
| `observer-audit` 只读（无需 waiver） | 事后补 waiver 给已合 PR 洗白 |

## closeout / PR 证据块（复制）

```text
waiver: user-explicit
when: <ISO-8601 timestamp, e.g. 2026-07-15T06:20:00Z>
who: <user display or handle>
quote: "<用户原话，完整引用>"
scope: <paths or PR number this waiver covers>
reason: <one line — why workflow was skipped>
risk: <what evidence/lock/claim is missing>
residual: <follow-up if any, e.g. backfill run / doc-only>
```

## agent-workflow closeout 示例

```bash
uv run --with pyyaml python bin/agent-workflow.py closeout <run-id> \
  --evidence "waiver:user-explicit when=2026-07-15T06:20:00Z quote='跳过 workflow 直接改文档' scope=docs/foo.md"
```

若 **完全没有** run-id（用户要求彻底跳过）：在 PR body 或 closeout 文件中粘贴证据块，并标注 `no-run-id: true`。

## 与闸门关系

- ADR-0204 staged 闸门：无 run 时 stage 需求面仍会 **halt**。  
  用户 waiver **不自动** 关闭闸门；需 `AGCP_REQUIREMENT_ITERATION_GATE=0` 仅在用户明确授权时临时使用，并在证据块写 `gate_bypass=1`。
- 日常交付：优先 `start`，不要依赖 waiver。

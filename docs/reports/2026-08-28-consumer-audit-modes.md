# Documents consumer audit modes — 2026-08-28

The consumer audit now separates active execution from read-only content
references. A Workspace owner may legitimately pass `--documents-root` while
remaining outside the Documents execution plane.

## Contract evidence

- `documents-executor`: active operational surface executes a Documents script
  or state/tool path; `forbidden_executor=true` and `writes_documents=true`.
- `workspace-owner-read`: accepted Workspace owner reads Documents content;
  `forbidden_executor=false` and `writes_documents=false`.
- `content-reference`: declaration/prose or non-executing content pointer;
  `forbidden_executor=false`.
- Legacy `total`, `active`, `unmatched`, and `families` fields remain present.

## Live baseline

The live audit reported `total=190`, `workspace_read_owners=7`,
`content_references=180`, and `forbidden_executors=3`.

The three forbidden operational surfaces are:

1. the minute-level Documents `watch-dispatch.py` crontab;
2. the Learning Evolution LaunchAgent script;
3. a Scheduled skill invoking legacy `check-convergence.py --report --base ~`.

The 180 gateway instructions remain visible as a separate cleanup queue, not as
false proof of active execution. The next migration waves must reduce both
`forbidden_executors` and `gateway_instructions`, with different evidence for
runtime cutover versus documentation cleanup.

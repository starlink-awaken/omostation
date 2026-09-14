---
status: active
lifecycle: entry
owner: governance-team
last-reviewed: 2026-09-04
last_updated: 2026-09-04
type: doc
---

# BET-Y1Q4-T1-02 Smash-successor Clone Retirement Provenance Implementation Plan

## Goal

为包含合法 main successor、最终由单父 one-parent squash merge 合并的独立 clone
建立专用且 fail-closed 的退役路径：

- 保留 ordinary 与 platform-rebased 退役语义；
- 接受并校验外部 proof、delete-intent、settlement 的证明链；
- 仅当 PR / source tag / delivery base / external receipt 全部一致时退场；
- 通过竞态和异常路径重放恢复或明确 fail-closed。

## Scope

Write surfaces:

- `bin/gac/clone-lifecycle.py`
- `tests/test_clone_lifecycle.py`
- `docs/superpowers/specs/2026-09-01-squash-successor-clone-retirement-provenance-design.md`
- `docs/superpowers/plans/2026-09-03-squash-successor-clone-retirement-provenance.md`
- `docs/plans/3y-bet-ledger.yaml`
- `.omo/_truth/governance-evidence/waiver-2026-09-03-squash-successor-retirement-binding.md`
- `.omo/_knowledge/retros/BET-Y1Q4-T1-02.md`

## Task 1: 代码级收敛（一次性核对）

- [x] `cmd_retire()` 增加 `--squash-merged-pr` 路径（已在脚本实现，检查 parser 与入口映射）。
- [x] `--source-tag`、`--delivery-base`、`--evidence` 与 existing 退役路径解耦。
- [x] 增加证明链阶段：proof、delete-intent、settlement 与 `replay` 入口（已在脚本实现，确认仅在外部 proof 成功后写入 delete-intent）。
- [x] 保留 ordinary 与 platform-rebased 的既有负路径行为，新增模式不得成为 fallback。

## Task 2: 测试与回归

- [x] 新增/保留 squash-successor 红绿测试（普通退场失败、全链路成功、CLI 参数解析）。
- [x] 保持 existing ordinary/platform-rebased 回归用例全部有效。
- [x] 执行至少以下验证命令并记录结果：
  - `PYTHONDONTWRITEBYTECODE=1 uv run --with pytest --with pyyaml python -m pytest -q -p no:cacheprovider tests/test_clone_lifecycle.py -k "squash_successor"`
  - `uv run ruff check bin/gac/clone-lifecycle.py tests/test_clone_lifecycle.py`
  - `python3 bin/gac/clone-lifecycle.py retire --help`
  - `python3 -c 'import ast, pathlib; ast.parse(pathlib.Path(\"bin/gac/clone-lifecycle.py\").read_text())'`
  - `python3 bin/gac/gac-validate.py --gate`

## Task 3: 交付与 closeout

- [x] 复核 `docs/superpowers/specs/2026-09-01-squash-successor-clone-retirement-provenance-design.md`
  与 `docs/plans/3y-bet-ledger.yaml` 的 binding / write surface 一致性。
- [x] 记录 `.omo/_knowledge/retros/BET-Y1Q4-T1-02.md`，包括验证命令与结论。
- [x] 提交本 run 的 governance/state write 与必要 closeout 证据。

## Rollback

若任一证明谓词、竞态恢复或 required check 不能 fail-closed：

1. 撤回本 run 的退役路径更改；
2. 保持 `BET-Y1Q4-T1-02` 停在 `candidate / evaluating`；
3. 保留现有 ordinary 与 platform-rebased 退场能力。


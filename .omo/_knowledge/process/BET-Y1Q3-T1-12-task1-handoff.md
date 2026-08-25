---
status: active
lifecycle: history
owner: governance-team
last-reviewed: 2026-08-26
type: task-handoff
related-retro: .omo/_knowledge/retros/BET-Y1Q3-T1-12.md
---

# BET-Y1Q3-T1-12 · Task 1 交付交接（ecos WorkPacket v2 CapabilityRequirement）

> 本文记录 Task 1 从 RED→GREEN → commit/tag → PR/merge → 根仓 gitlink 吸收的完整证据链，
> 以及 2026-08-25 工作树被并发清理导致未提交工作丢失的事故复盘与 D0 教训。
> 最终 bet retro（五问）仍待所有 done_when 证据齐全后由正式 workflow 写入/替换。

## 1. Task 1 交付摘要

- **任务**: eCOS WorkPacket v2 增加严格 `capability_requirements`（closed inline-map list items）
- **plan 位置**: `docs/superpowers/plans/2026-08-24-exact-capability-binding.md` → Task 1 (Step 1-6)
- **状态**: 已完成并合并（Step 1-6 全部完成）

## 2. 交付证据链（机器可读事实）

| 环节 | 证据 |
|------|------|
| ecos 实现 commit | `036753b` `feat(mof): add exact WorkPacket capability requirements`（12 files, +425/-30） |
| ecos 分支 | `codex/t1-12-workpacket-capability-requirements-v2-20260825`（push 到 origin） |
| source tag | `delivery/exact-capability-binding-ecos-20260824-v1` → `036753b`（push 到 origin） |
| ecos PR | https://github.com/starlink-awaken/omostation-ecos/pull/46（CI `test (3.13)` pass, MERGEABLE/CLEAN） |
| ecos merge | squash commit `bc067cb` `feat(mof): add exact WorkPacket capability requirements (#46)`（merged 2026-08-25T17:48:22Z by starlink-awaken） |
| 根仓 gitlink 吸收 | origin/main `projects/ecos` → `bc067cb`（经 PR #2218 `chore(submodules): advance exact capability consumers`） |
| 测试验证 | `tests/test_mof_compiler.py` + `tests/test_work_packet_compiler.py` + `tests/test_mof_agent_execution_contracts.py` → **125 passed** |
| lint | `uv run ruff check src/ecos/ssot tests/...` → clean |
| 产物 | 5 个 control artifacts 重新生成（schema.json / schemas.ts / manifest.json / models.py / sql） |

## 3. 实现内容（Task 1 范围）

- **compiler IR**: `api.py` — `M2Property` 新增 `items_inline_properties`/`items_closed_map`；
  新增 `_parse_inline_map()`；`_parse_property` 支持 `type:list` + items closed inline map
- **emitters**: `emitters.py` —
  - JSON Schema list 分支输出 items `properties`/`required`/`additionalProperties: false`
  - Zod list 分支输出 `z.array(z.object({...}).strict())`
  - Pydantic 新增 `_enforce_inline_list_contracts` validator（set 精确匹配/required/string/enum/pattern）
- **M2 schema**: `work_packet.yaml` — optionalProperties 新增 `capability_requirements`
  （capability_id pattern `^(skill|workflow|mcp-server|mcp-tool|bos-service):[A-Za-z0-9._:@/-]+$`、
  operation enum `find/inspect/load/invoke`、effect enum `read_only/effectful`）
  + 2 条 validationRules（capability_id 唯一、Skill 禁 invoke）
- **确定性 compiler**: `work_packet_compiler.py` —
  `CAPABILITY_ID_RE`/`CAPABILITY_OPERATIONS`/`CAPABILITY_EFFECTS` 常量、
  `validate_capability_requirements()`、`INVARIANT_FIELDS` 加 `capability_requirements`、
  canonicalize 先 validate 再序列化
- **测试**: 严格跨语言契约测试（JSON Schema items + Pydantic 正/负例 + Zod 表达式）、
  `TestCapabilityRequirements`（hash 顺序敏感性、7 类负例、无字段可读）

## 4. ⚠️ 事故复盘：工作树被并发清理（2026-08-25）

### 事件
- 原 worktree `ws-bet-y1q3-t1-12`（`/Users/xiamingxing/ws-bet-y1q3-t1-12`）整个目录消失。
- `git worktree list` 无此 worktree；admin 文件无记录；目录不存在；Trash 空；无 APFS snapshot；
  `git fsck` dangling commits 均无关。
- 分支 `work/bet-y1q3-t1-12` 仍存在但 tip=main（零 commit）；reflog 仅 `Created from omostation-root/main`。
- **Task 1 未 commit 的编辑全部丢失，git 无法恢复。**

### 根因
- 并发 agent 的清理脚本 `gac-worktree-prune.sh` 对孤儿 worktree 执行
  `git worktree remove --force`；bash_history 显示既有清理模式
  （`git worktree remove --force ../ws-<session>` + `git branch -D`）。
- 共享主树上并行 agent 互相清理产物（AGENTS.md §1.3 D0 铁律的来源）。

### 处置
1. 诊断根因（git 不可恢复 → 用户决策）
2. 用户决策：在幸存独立 clone（Codex clone）重做 Task 1（RED→GREEN）→ 立即 commit/tag
3. 复用独立 clone 单写者，避免与并发 Codex agent 冲突
4. 完成后立即 `git add` → `commit` → `tag`（D0 三段式）

## 5. D0 教训（必须固化）

> **D0 铁律：交付物必须 `git add` → `commit` → `tag`（或推独立远端分支）。仅 commit 不算持久化。**

- 未 commit 的工作没有任何耐久性——共享分支被 rebase 会挤掉提交、worktree 被清理会删文件。
- tag 的 ref 不随分支重写/清理消失；commit 只是"暂时安全"。
- 每写完一个文件**立刻 `git add`**（bet-execution skill §2 执行期纪律）。
- 高危 git 操作（reset/checkout/clean）优先在独立 clone 执行；改代码前确认仓库边界（P73-D1）。
- 本事故的实证链条：未 commit → worktree remove --force → 全量丢失 → git 不可恢复。

## 6. 协调记录（多 agent 并行）

- 本 Task 1 在 Codex clone 的 ecos 子模块执行
  （`/Users/xiamingxing/agents/blueprint-exact-capability-binding/attempts/wave-b-ecos-contract-20260825-10/ws/projects/ecos`）。
- ecos 分支 `codex/t1-12-...` 是 Codex 的既有分支，在其上 commit（单写者，push 前确认无并发写）。
- ecos PR #46 合并后，根仓 gitlink 由并发 agent 的 PR #2218 吸收进 origin/main（child-first AC-10 满足）。
- bet-execution run `20260825T071042Z-bet-execution-3317ce8a` 为 closed/blocked 但持有 Task 1 全部
  ecos 路径 claims（D3 证据保留）；`resume` 为只读命令，不重开 closed run。
- 并发 agent 的新 run `20260825T194427Z-bet-execution-5054fe7c`（active）正执行 Task 2-7，
  持有 root-gate + OMO/ledger 锁；Task 1 之后的接棒需等其当前 Task 完成后协调。

## 7. 给下一个接棒 agent

- Task 1 已完成合并，ecos main = `bc067cb`，根仓 gitlink 已吸收。无需重做。
- 后续 Task 2（OMO consumer）consumes Task 1 的 `capability_requirements`；
  验证 OMO 是否已持久化/回验 requirements digest。
- 实施顺序保持 eCOS → OMO consumer → root preflight/native receipt shadow →
  OMO integrity → Agora/Cockpit → shadow/warning/fail → production canary。
- `native-execution-receipt/v1` 只有库与测试、无生产消费者；不得以 fixture/测试/PR/maturity 顶替真实完成（D1）。
- 最终 retro（五问 + 净增减 `bet-ledger.py surface`）须在所有 done_when 证据齐全后由正式 workflow 写入。

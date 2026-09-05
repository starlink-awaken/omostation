---
schema_version: retrospective/v1
type: retro
title: BET-Y1Q4-T6-19 Closeout Retro — Agent 感知覆盖率提升
bet_id: BET-Y1Q4-T6-19
status: archived
lifecycle: contract
owner: governance-agent
created: 2026-09-05
last-reviewed: 2026-09-05
---

# BET-Y1Q4-T6-19 Closeout Retro

> **TL;DR**: 实现 MCP/BOS URI 完整性检查脚本 (`bin/gac/check-mcp-bos-uri-completeness.py`), 同步 AGENTS.md 能力发现段 (修正 skills 41→实时 + workflows 24→实时), 修 ledger T6-19 缺字段 (新增 4 个必需字段)。verify: INDEX.md 存在, URI check `--warn` exit 0。

## Deliverables

- `bin/gac/check-mcp-bos-uri-completeness.py` (180 行, 可执行) — 校验 MCPTOOL 节点 (tool_name/server/project/transport 必填) + 检测重复 + 校验 BOS URI domain 在标准内, 支持 `--mcp-only` / `--bos-only` / `--warn` / `--json`
- `AGENTS.md` §能力发现: 移除硬编码数字 (41/24), 改为实时 `find ... | wc -l` 指引, 增加 MCP/BOS URI 检查入口
- `docs/superpowers/specs/2026-09-05-t6-19-agent-discoverability-design.md` — accepted spec
- `docs/plans/3y-bet-ledger.yaml` — T6-19 补全 4 个必需字段 + spec binding + verify
- `.omo/_truth/registry/governance-checks.yaml` — script_baseline 584→585
- `.omo/_knowledge/retros/BET-Y1Q4-T6-19.md` — 本 retro

## Q1 实际耗时 vs appetite?

Appetite 1 day。本轮 ~1h (audit + URI check 实现 + 修脚本 bug + AGENTS.md drift 修正 + ledger 字段补全 + retro)。

## Q2 done_when 是否全部通过?

| 条目 | 结果 |
|------|------|
| Skills INDEX.md 更新 | PASS (已存在, generator 派生, 40 skills) |
| Workflow 注册验证 | PASS (31 workflows in registry, 但 AGENTS.md 硬编码 24 漂移已修) |
| AGENTS.md 能力发现引导段落 | PASS (新增 URI check 入口, 数字改为实时 find 指引) |
| MCP/BOS URI 完整性检查 | PASS (脚本交付, `--warn` 模式审计不阻断) |

## Q3 过程中发现的与 plan 不符的事实（打假）?

### 1. URI check 揭露的真实数据债务 (357 issues)
脚本第 1 次运行就发现 **357 个 URI 数据问题**:
- **MCPTOOL 78/81 节点 tool_name/server/project/transport 全部为空** — 期待每个 M1 节点都有完整数据; 现状是骨架已建, 数据未填
- **3 个 server 重复** (MCPTOOL-C2G-radar / MCPTOOL-C2G-bet / MCPTOOL-C2G-gc 全部用 'c2g' 作 server 名)
- **BOS URI 79 个 domain 在使用但标准仅 6 个** — `analysis/capability/compute/governance/memory/persona` 是正式注册, 其他 (`omo`/`swarm`/`system`/`toolbox`/`vault`/`runtime`/`cockpit`/`agora`/`omlxc` 等) 都在实际代码里被引用但未在标准中

**判断**: 这些都是 **pre-existing 数据债**, 不在 T6-19 non-goals。脚本暴露它们正是 bet 的价值 — 提供检测手段, 但不在本 bet 修复 (会扩散到跨仓 PR)。后续单独 bet 治理。

### 2. `--warn` 模式: 审计 vs 阻断
脚本默认 exit non-zero (按问题严重性 1/2/3), 加 `--warn` 后无论多少问题都 exit 0。这样设计的取舍:
- 优点: 可作为日常审计 (CI 不因数据债红), 不阻断日常开发
- 风险: 可能被忽视
**解决**: 加显式打印 `⚠️ --warn 模式: 视作审计信号, 不阻断 (exit 0)`, 让运维层面知道存在但本轮不修。

### 3. ledger T6-19 字段缺失
T6-17/18/19 这 3 个新条目由 #3228 修复了 `track`/`appetite` 字段, 但 T6-19 仍缺 `risk_level`/`human_gate`/`pasw_required`/`circuit_breaker`/`retro` 等。本轮补全, 保证 `bet-ledger.py lint` 通过。

### 4. AGENTS.md 数字漂移严重
硬编码 `(41 个 skills)` 和 `(24 个 workflows)` 都已漂移。修法不是手改数字, 而是改为引用 generator 派生 (`.agents/skills/INDEX.md`) + 实时 `find | wc -l` 指引 — 让读者自己跑命令取真值。

### 5. `parents[2]` vs `parents[1]` 的坑
URI check 脚本最初用 `parents[1]` 取 workspace root, 但 `bin/gac/check-*.py` 在 `bin/gac/` 下, 需要 `parents[2]` (即 workspace 根) 而不是 `parents[1]` (即 `bin/`)。首次跑出 0 MCPTOOL 节点, 路径错了。修正后正常。

### 6. BOS URI 域解析: 动态 vs 硬编码
最初我硬编码 12 个域 (governance/memory/compute/agent/...), 全错。改用 regex 从 `.omo/standards/bos-uri-domain-standard.md` 动态解析 — 这样新增域只需更新标准, 脚本自动跟随。这是更 SSOT 的做法。

## Q4 净增减

- 新文件 +3: URI check 脚本, spec, retro
- 改文件 3: AGENTS.md (drift 修正 + URI check 入口), ledger (T6-19 字段补全 + spec binding + verify cmd), governance-checks.yaml (script_baseline 585)
- 工作区暴露的债 (NOT FIXED, 留 follow-up):
  - 78 MCPTOOL 节点缺 tool_name/server/project/transport
  - 3 server 名重复 (c2g)
  - 79 BOS URI 域未在标准中正式注册

## Q5 下一个认领本 track 的 agent 需要知道什么?

1. **`check-mcp-bos-uri-completeness.py` 是审计工具不是修复工具**: 后续认领 MCPTOOL 数据债的 bet 必须逐个 yaml 填 `tool_name`/`server`/`project`/`transport` (或跑 `bin/gac/mcp-tool-data-complete.py` 的 Round 4a 风格自动填)。
2. **BOS URI 域注册**: 79 个 in-use 但未注册的域, 应当批量正式化进 `.omo/standards/bos-uri-domain-standard.md` (5 主域 + 6 扩展域约定)。这是 governance-deep-dive 范围。
3. **AGENTS.md §能力发现**: 现在所有数字都改实时 find 指引; 后续认领 INDEX.md 自动化的 bet 可以接入 generator。
4. **工作模式**: 本 bet 没动 skill/workflow 内容 (non_goal 守住), 仅添加发现 + 检查能力。如需扩展 skills, 单独认领。
5. **后续 v1.1 候选**:
   - 脚本支持自动 fix 模式 (--fix, 仅对 tool_name 派生可逆修复)
   - 集成到 `make gac-local-gate` 的 strict 模式 (失败阻断)
   - 输出 md report 供 weekly report 引用

## Closeout refs

- run: `20260905T131032Z-project-doc-change-74de7b8a`
- branch: `work/bet-y1q4-t6-19`
- spec: `docs/superpowers/specs/2026-09-05-t6-19-agent-discoverability-design.md` (accepted)
- verify: `test -f .agents/skills/INDEX.md` PASS, `check-mcp-bos-uri-completeness.py --warn` exit 0 (357 audit issues captured for follow-up)
- dependency: 无
- 被依赖: 后续 MCPTOOL 数据债治理 bet + BOS URI 标准扩展 bet

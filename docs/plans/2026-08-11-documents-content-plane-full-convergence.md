---
lifecycle: plan
owner: governance-team
last_updated: 2026-08-18
type: ephemeral
---
# Documents Content Plane Full Convergence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: use `subagent-driven-development` task-by-task. Each implementation task gets a fresh implementer, then a specification review and a code-quality review. Use `verification-before-completion` before every commit/PR and final closeout.

**Goal:** 把 `/Users/xiamingxing/Documents` 全面收敛成内容主权面；把 KEMS 与全部功能运行层统一归入既有 Workspace owners，同时保持内容无损、消费者连续、状态可恢复、入口真实可用。

**Architecture:** 不创建新平台。Documents 只保存内容、契约、人工决策、证据和可重建文档投影；l4-kernel 提供分类、内容归档契约与 T8；Kairon/KOS 是唯一 KEMS runtime；OMO 是任务/审批/证据 SSOT；Workflow Mesh + Runtime 是唯一执行与调度面；Cockpit 是唯一人机入口；family-hub 吸收家庭应用；ToolBox 管理外部能力仓。迁移按“新 owner 实装 → 对等验证 → 消费者切换 → 观测 → 旧面退役”的顺序执行。

**Tech Stack:** Python 3.13、pytest、uv、YAML contracts、Kairon/KOS、OMO、Runtime cron service、Cockpit CLI/Web、Next.js/React、Bun、Vitest、Playwright、GaC/PASW。

**Baseline evidence:** `docs/reports/2026-08-11-documents-content-plane-full-inventory.md`

## 0. Completion Contract

全面落地不是“有计划”或“某几个测试绿”。最终必须同时证明：

- [ ] Documents 全量扫描 `runtime=0`、`cache=0`、`bridge=0`。
- [ ] 代码型历史资料仅通过 schema-valid `CONTENT_ARCHIVE.yaml` 归类为 `content_archive`，且具备冻结清单、消费者扫描证据和内容指纹。
- [ ] 所有活跃 crontab、LaunchAgent、Claude Scheduled、域 CLAUDE 和 Cockpit contracts 不再执行 Documents 内脚本。
- [ ] `cockpit context`、`cockpit cards --check`、`cockpit kems domains/status/scan` 在实际安装入口通过 smoke，且输出来源可追溯。
- [ ] 12 个 Documents 知识域都能作为独立 Cowork 项目打开：Claude 类客户端读薄 `CLAUDE.md`，Codex/兼容客户端读薄 `AGENTS.md`，并通过同一个 Workspace MCP 获取 `domain_context`、CARDS、Skills 与 Workflows；域内不复制执行实现。
- [ ] `@公共/_control/L4-DOMAIN-REGISTRY.yaml` + 各域 `DOMAIN.yaml` 是域身份 SSOT；Workspace 域项目绑定注册表是能力/入口 SSOT；所有客户端文件均为可验证投影，不形成第三真源。
- [ ] KEMS ingest/eval/graph/recovery 只由 Kairon/KOS 提供；任务/审批只由 OMO 提供；执行只经 Workflow Mesh/Runtime。
- [ ] `family-dashboard-app` 能力完整合入 `family-hub`，Cockpit 只暴露一个家庭应用 contract。
- [ ] 四个外部 Git 仓保留 remote、HEAD、工作树内容和可验证目标位置，Documents 只留内容索引。
- [ ] Zotero 从非 Documents dataDir 正常启动、库与附件可访问。
- [ ] 每个域单独 T8 通过，之后 T8 进入默认文档域 profile。
- [ ] 每个物理迁移都有前后文件数、字节数、SHA-256/树指纹、消费者证据和回滚包。

## 0.1 Architecture Addendum — Canonical L4 and Agora Nested L4

The convergence target includes the Workspace root `projects/l4-kernel` as the
only canonical L4 implementation. `projects/agora/projects/l4-kernel` is an
older nested submodule and must be treated as a separately governed migration
family, not as an equivalent implementation. Before any nested-L4 deletion or
route cutover, record instance identity, commit SHA, registry digest, all
Agora consumers, dual-instance canary results, and rollback evidence.

The migration order is: canonical route contract → explicit Agora consumer
cutover → observation and parity → consumer/schedule zero proof → separately
authorized nested submodule retirement. This addendum does not authorize
deletion, gitlink changes, production route changes, or Documents content
moves.

## 1. Non-Negotiable Boundaries

1. 不扶正 `projects/domain-kems`，不创建第二 KEMS runtime。
2. 不把 16 GiB 职业历史代码资料搬到 Workspace 项目，更不能因后缀误删。
3. 不把家庭 Next 应用直接丢弃；先在 family-hub 达成功能、安全、构建和 E2E 对等。
4. 不把 Zotero translators/SQLite 假装成“内容归档”；它们必须随 app dataDir 迁出。
5. 不在共享脏 `/Users/xiamingxing/Workspace` 上 reset、checkout 或提交。
6. 所有子仓修改只在本 session 的 PASW worktree：
   - `.subtrees/l4-kernel`
   - `.subtrees/kairon`
   - `.subtrees/runtime`
   - `.subtrees/cockpit`
   - `.subtrees/family-hub`
   - 必要时 `.subtrees/omo`、`.subtrees/ecos`、`.subtrees/agora`
7. 不把缓存、SQLite、日志、索引或构建物提交进 Git。
8. 删除、批量移动、批量 chmod、Zotero 配置写入和大目录复制必须到达对应任务后再次给出精确危险操作确认。

## 2. Delivery and PR Topology

子仓按依赖顺序交付，不能先 bump 根指针再补子仓：

```text
l4-kernel ─┐
kairon ────┼─> runtime ─> cockpit ─┐
omo/ecos ──┘                        ├─> root pointer/config/docs PR
family-hub ─────────────────────────┘
ToolBox (独立仓，如需) ─────────────> root registry/pointer evidence
```

每个子仓：focused tests → full tests/lint → commit → push → PR → CI → merge。根仓最后 bump 已合并 commit 指针，运行 GaC gates 后提交 PR。Documents 非 Git 变更通过哈希清单和 root evidence report 取证。

## 2.1 MVP-first 交付边界

全面收敛保留为最终目标，但不再把全部物理迁移和债务清零作为首个可用版本的前置条件。先交付一个可日常使用、可追溯、可继续迭代的 MVP：

- [x] L4 提供统一域身份、内容分类与审计；Cockpit 提供 Workspace 上下文、域上下文、CARDS 与 KEMS 投影。
- [x] 12 个域在 Workspace binding registry 中各有唯一能力绑定，且不复制域身份 SSOT。
- [x] Kairon/KOS 提供 metadata-only 内容检查与域 profile；Runtime 提供 Documents 只读、state-only 写入的 owner adapter。
- [x] 先更新并 smoke 三个代表域：`vault`、`work-weijian`、`creative`；它们分别覆盖个人知识、工作知识与创作场景。
- [x] 三个域的薄 `CLAUDE.md` / `AGENTS.md` 能恢复正确 `domain_id`，并引导同一个 Workspace MCP、Skills 与 Workflows；不得复制 MCP 命令矩阵或执行实现。
- [x] 注册并跑通一条真实、低风险、只读 Documents 的 owner job：dry-run、成功、owner 非零、evidence 与 no-write-back 都有实证。
- [x] 完成 Claude/Codex/Zed 的源级 MCP 协议与项目 gateway 验收；该证据不等同于客户端进程已 reload 或终端用户 UI smoke。
- [x] ChatGPT developer mode 的绑定契约允许官方 public HTTPS MCP 或 Secure MCP Tunnel；未配置 tunnel，也未宣称终端用户 UI 已验证。
- [x] 根 PR #1372 已将 12/12 域 gateway 纳入 source-level checker；MVP 验收后形成日常使用版本与复盘。
- [x] 迁移 checker 从当前 L4 audit 与 exact-one registry composition 计算迁移候选；物理迁移继续按逐项证据推进。

**MVP 不包含：** 批量删除/移动、Zotero dataDir 写入、家庭应用迁移、四个外部仓迁移、runtime/cache 清零、旧脚本退役和最终 T8。这些进入 MVP 后迭代，继续受原确认门、指纹、消费者证据和回滚要求约束。

---

### Task 0: 固化全面审计、计划和治理运行

**Files:**

- Create: `docs/reports/2026-08-11-documents-content-plane-full-inventory.md`
- Create: `docs/plans/2026-08-11-documents-content-plane-full-convergence.md`

**Steps:**

- [x] 从远端 `main@35bd0757` 创建 `work/documents-content-plane-full-convergence`。
- [x] 初始化 18 个子模块并创建 PASW 分支/worktree。
- [x] 启动 `project-doc-change` governance run。
- [x] 复现基线资产、违规候选与非四大面 runtime 候选；具体历史快照保留在 inventory evidence，不能视为当前迁移候选总数。
- [x] 运行 doc SSOT checks 和 workflow verify。
- [x] 提交 root 文档 checkpoint：`docs(documents): plan full content-plane convergence`。

**Verification:**

```bash
uv run --with pyyaml python "bin/ssot/doc-ssot-lint.py" --json
uv run --with pyyaml python "bin/ssot/ssot-guardian.py"
uv run --with pyyaml python "bin/agent-workflow.py" verify \
  "20260811T062626Z-project-doc-change-3d40efae" --from-diff --execute
```

---

## Wave 1 — 先建立不会撒谎的边界与入口

### Task 1: l4-kernel `CONTENT_ARCHIVE.yaml` 强契约

**Files:**

- Create: `.subtrees/l4-kernel/src/l4_kernel/content_archive.py`
- Modify: `.subtrees/l4-kernel/src/l4_kernel/content_plane.py`
- Modify: `.subtrees/l4-kernel/src/l4_kernel/cli.py`
- Modify: `.subtrees/l4-kernel/src/l4_kernel/harness.py`
- Create: `.subtrees/l4-kernel/tests/test_content_archive.py`
- Modify: `.subtrees/l4-kernel/tests/test_content_plane.py`
- Modify: `.subtrees/l4-kernel/tests/test_cli_contracts.py`
- Modify: `.subtrees/l4-kernel/tests/test_harness.py`

**Contract:**

`CONTENT_ARCHIVE.yaml` v1 必填：

```yaml
schema: l4.content-archive/v1
owner: personal
reason: 职业历史代码资料
source_kind: historical-source-material
status: frozen
execution_policy: deny
captured_at: 2026-08-11T00:00:00+08:00
inventory:
  files: 0
  bytes: 0
  tree_sha256: "..."
consumer_evidence:
  scanned_at: 2026-08-11T00:00:00+08:00
  active_consumers: []
```

规则：

- 只允许在 `_archive`、`_storage`、`_knowledge` 下声明；`_runtime`、`_control`、应用根和 `_external` 禁止声明。
- manifest 缺字段、数字/指纹不匹配、发现活动消费者时 fail closed 为 `L4-CONTENT-011`。
- cache 仍优先判为 cache；workspace bridge 仍是 bridge；有效 manifest 下的代码资料判 `content_archive`。
- manifest 本身判 `contract`，不得把任意目录一张 YAML 洗成内容。

**TDD steps:**

- [ ] 写失败测试：合法 archive、非法位置、缺字段、库存漂移、活动消费者、cache 不被覆盖。
- [ ] 运行 RED：`uv run --group dev pytest tests/test_content_archive.py tests/test_content_plane.py -q`。
- [ ] 实现 parser、validation、nearest-manifest lookup 和稳定 issue envelope。
- [ ] 运行 GREEN 与全量：`uv run --group dev pytest tests/ -q`。
- [ ] lint：`uv run --group dev ruff check src tests`。

**Commit:** `feat(l4): add governed content archive classification`

**Rollback:** revert l4 commit；旧分类器继续把资料列为 runtime，不会误放行。

---

### Task 2: l4-kernel 停止生成 KEMS runtime

**Files:**

- Modify: `.subtrees/l4-kernel/src/l4_kernel/templates.py`
- Modify: `.subtrees/l4-kernel/src/l4_kernel/lifecycle.py`
- Modify: `.subtrees/l4-kernel/src/l4_kernel/cli.py`
- Modify: `.subtrees/l4-kernel/tests/test_templates.py`
- Modify: `.subtrees/l4-kernel/tests/test_lifecycle.py`
- Modify: `.subtrees/l4-kernel/tests/test_cli_contracts.py`

**Interface change:**

- `init_domain_kems()` 保留兼容 API，但只能生成 Method/Profile/ontology/rubric 与声明式 manifest；不得创建 `.kems/_scripts`、`_runtime`、MCP server、daemon 或 executor。
- 新增明确命令 `l4-kernel domain init-content-contracts`；legacy 名称输出 deprecation evidence。

**TDD steps:**

- [ ] 写失败测试：初始化后 `content audit` 的 runtime/cache 均为 0。
- [ ] 写失败测试：legacy 调用产生 declarative-only result，不出现可执行位或脚本后缀。
- [ ] 运行 RED。
- [ ] 最小修改模板和 lifecycle 调用链。
- [ ] 运行 focused/full tests 与 ruff。

**Impact gate:** 修改 `init_domain_kems` 前运行 GitNexus `impact`；HIGH/CRITICAL 必须先记录调用方和兼容策略。

**Commit:** `refactor(l4): make domain bootstrap declarative only`

---

### Task 3: Cockpit 恢复真实 context/cards/KEMS 入口

**Files:**

- Create: `.subtrees/cockpit/src/cockpit/adapters/governance_context.py`
- Create: `.subtrees/cockpit/src/cockpit/tests/test_governance_context_adapter.py`
- Modify: `.subtrees/cockpit/src/cockpit/commands/l4bridge.py`
- Modify: `.subtrees/cockpit/src/cockpit/commands/kems.py`
- Modify: `.subtrees/cockpit/src/cockpit/commands/health.py`
- Modify: `.subtrees/cockpit/src/cockpit/commands/brief.py`
- Modify: `.subtrees/cockpit/src/cockpit/dashboard/routes.py`
- Modify: `.subtrees/cockpit/pyproject.toml`
- Modify: `.subtrees/cockpit/src/cockpit/tests/test_capability_commands.py`
- Modify: `.subtrees/cockpit/src/cockpit/tests/test_cli_mcp.py`

**Design:**

- 删除对已移除 `cockpit.scripts.cockpit_mcp` 的所有生产 import。
- `governance_context` 只组合真实 owner：l4 registry/content audit、OMO cards/status、Workspace BRIEF/registry；任何 owner 不可达时标 `degraded/unavailable`，不得返回假成功。
- `kems domains` 从 l4 registry 获取；`kems status` 汇总 l4 audit + Kairon/OMO 可达性；`kems scan` 保留 l4 audit exit code。
- `cards --check` 经 OMO cards authority；Cockpit 不复制 CARDS 规则。
- `cockpit-mcp` entrypoint 要么指向现存受测 server，要么明确移除并提供替代；禁止继续指向不存在模块。

**TDD and installed smoke:**

- [x] 写 RED tests 覆盖 owner healthy/degraded/malformed/timeout。
- [ ] 对 API route 修改先运行 GitNexus `api_impact`。
- [x] focused：`uv run pytest src/cockpit/tests/test_governance_context_adapter.py src/cockpit/tests/test_capability_commands.py -q`。
- [x] full：`uv run pytest src/cockpit/tests/ tests/ -q`。
- [x] lint：`uv run ruff check src tests`。
- [x] PR #35 通过 CI 并合并到 accepted Cockpit checkout。
- [x] accepted 用户级 Cockpit 入口已就位，并完成下列 installed smoke；这只证明入口与 owner 输出，不证明任何桌面客户端已经 reload。
- [x] installed smoke（前四项按实际返回值接受）：

```bash
"/Users/xiamingxing/.local/bin/cockpit" context
"/Users/xiamingxing/.local/bin/cockpit" cards --check
"/Users/xiamingxing/.local/bin/cockpit" kems domains
"/Users/xiamingxing/.local/bin/cockpit" kems status
L4_DOCUMENTS_ROOT="/Users/xiamingxing/Documents" \
  "/Users/xiamingxing/.local/bin/cockpit" kems scan
```

- `context`、`cards --check`、`kems domains`、`kems status` 已从上述用户级入口实际执行；前 3 项 exit 0，`kems status` 按内容审计债务 exit 1/degraded，且不把 fail-closed 当安装失败。
- `kems scan` 仍未标记为 green：在存量债务未清零前必须 exit 1 且报告真实数量。

**2026-08-12 installed smoke reconciliation (accepted evidence):**

The accepted user-level Cockpit installation was exercised directly. The first four
commands are accepted only to the observed extent:

| Command | Observed result | Acceptance |
|---|---|---|
| `/Users/xiamingxing/.local/bin/cockpit context` | exit 0; `status: ok`; Documents `12/12` | accepted |
| `/Users/xiamingxing/.local/bin/cockpit cards --check` | exit 0; compliant; OMO exit 0; scope `all` | accepted |
| `/Users/xiamingxing/.local/bin/cockpit kems domains` | exit 0; 12 domains; source `/Users/xiamingxing/Documents/@公共/_control/L4-DOMAIN-REGISTRY.yaml` | accepted |
| `/Users/xiamingxing/.local/bin/cockpit kems status` | exit 1; `degraded` because the L4 content audit reports existing violations; OMO and Kairon owners `ok` | accepted as truthful degraded status |
| `L4_DOCUMENTS_ROOT="/Users/xiamingxing/Documents" /Users/xiamingxing/.local/bin/cockpit kems scan` | non-zero full audit; not a green installation result | remains open |

The independent accepted `cockpit-mcp` stdio server smoke also succeeded: initialize
completed, `tools/list` reported 17 tools, and `workspace_context`,
`domain_context(vault)`, and `cards_check` each returned JSON-RPC success with a
status-`ok` business envelope. This is installed Cockpit/MCP evidence only; it does
not prove Claude, Codex, Zed, or ChatGPT UI reload, and it does not provision a
ChatGPT tunnel.

The same full Documents L4 audit was non-zero and reported 322,871 artifacts,
41,987 violations, 5,097 runtime artifacts, 36,867 cache artifacts, 1 bridge,
31,441 content archives, and 23 `invalid_archive` artifacts. The scan observed live
filesystem changes and therefore emitted `L4-CONTENT-011` as designed. These are
content-plane debts, not an installed-entrypoint failure; runtime/cache/bridge
remain non-zero and the overall completion contract stays unchecked.

**2026-08-13 accepted release and third-party Claude reconciliation:**

The accepted root was refreshed from `origin/main` to
`ac185a2974fa65ae7b222c8934885fb1725093a4`; its relevant checkout pointers are
Cockpit `636cc22257ba74a7717d20a2965b9f3fda54c160` and L4 kernel
`0d688ead82f18edf307056f8f667083b0c523a1e`. Cockpit was reinstalled from that
accepted checkout with `uv sync --frozen --reinstall-package cockpit`. This replaces
the prior installed snapshot; historical tool counts and prior root pointers above
must not be read as current release evidence.

- `/Users/xiamingxing/.local/bin/cockpit facts-audit --json` now resolves to the
  accepted installation and returns `cockpit.domain-facts-audit.v1`. Its exit `1`
  is truthful `violations`, not an installation error: the L4 registry has 12
  domains, with 9 present facts files and 3 missing (`opc`, `work-docs`, and
  `work-contracts`).
- A direct stdio smoke using the exact MCP environment now configured in clients
  negotiated protocol `2025-06-18`, exposed 19 tools including `domain_context`,
  `domain_project_status`, and `domain_facts_audit`, and returned
  `status=ok`/`binding=ok` for `vault`, `work-weijian`, and `creative`.
- Codex, standard Claude Desktop, active `Claude-3p`, Zed, and ZCode now each name
  the same accepted `cockpit-mcp` command and the same three scope variables
  (`WORKSPACE_ROOT`, `L4_DOCUMENTS_ROOT`, and `L4_DOMAIN_REGISTRY`). The active
  third-party Claude configuration was backed up before adding its missing
  `cockpit` entry; the atomic rewrite was verified to differ from that backup only
  by this entry. No model-provider configuration or credential was changed.
- This is a release and protocol result, not a desktop-UI result. Each desktop
  client still needs one restart/reload and visual tool-list smoke. ChatGPT Web or
  Cowork remains unconfigured until a separately reviewed public HTTPS MCP or
  Secure MCP Tunnel exists.
- No Documents content was edited by the release or MCP smoke. A concurrent legacy
  governance refresher did update three derived `@驾驶舱` artifacts during the
  observation window, so this window is not claimed as a strong whole-Documents
  zero-write proof.

**Commit:** `fix(cockpit): restore registry-backed governance context`

---

### Task 3A: 建立 Documents 独立域项目与 Cowork 接入契约

**Architecture:**

- 域身份：`@公共/_control/L4-DOMAIN-REGISTRY.yaml` → 各域 `DOMAIN.yaml`，唯一机器真源。
- Workspace 能力绑定：`.omo/_truth/registry/documents-domain-projects.yaml`，只记录 `domain_id`、可用 MCP tools、Skill/Workflow profile 与客户端入口，不复制域元数据。
- 客户端投影：各域根的 `CLAUDE.md` / `AGENTS.md` 只负责引导读取 `DOMAIN.yaml`、调用 Workspace MCP、遵守内容边界；不得内嵌运行代码或复制注册表。
- MCP：Cockpit 现有 server 增加 `domain_context(domain_id)` 只读工具，在同一 envelope 内返回 capabilities，并组合 L4 manifest 与 Workspace binding；owner 不可达时明确 degraded。

**Verified client compatibility (official docs, checked 2026-08-11):**

- Codex reads project `AGENTS.md` and supports project/user MCP configuration: <https://learn.chatgpt.com/docs/agent-configuration/agents-md>, <https://learn.chatgpt.com/docs/extend/mcp?surface=cli>
- Claude Desktop supports local MCP servers/Desktop Extensions installed once at client scope: <https://support.anthropic.com/en/articles/10949351-getting-started-with-local-mcp-servers-on-claude-desktop>
- Zed recognizes project `AGENTS.md`/`CLAUDE.md` and supports MCP in its Agent surface: <https://zed.dev/docs/ai/instructions>, <https://zed.dev/docs/ai/mcp>
- ChatGPT developer mode connects an official public HTTPS MCP endpoint or Secure MCP Tunnel: <https://developers.openai.com/plugins/deploy/connect-chatgpt>, <https://developers.openai.com/api/docs/guides/secure-mcp-tunnels>. It does not consume local Claude/Codex JSON; this is a binding contract, not evidence that a tunnel or end-user UI smoke exists.

**Files (expected):**

- Create: `.omo/_truth/registry/documents-domain-projects.yaml`
- Create: `bin/gac/documents-domain-project-check.py`
- Create: `tests/test_documents_domain_project_check.py`
- Modify: `.omo/_truth/registry/INDEX.md`
- Modify: `.subtrees/cockpit/src/cockpit/adapters/governance_context.py`
- Modify: `.subtrees/cockpit/src/cockpit/agent_runtime_mcp_server.py`
- Modify: corresponding Cockpit tests
- Modify after explicit batch-write confirmation: the 12 registered domain-root `AGENTS.md` / existing `CLAUDE.md` gateways

**Acceptance:**

- [x] registry contains each validated L4 manifest exactly once; unknown/missing domain, duplicate tool binding, missing skill/workflow ref fail closed.
- [x] `domain_context` never returns a path/identity that disagrees with the referenced `DOMAIN.yaml`.
- [x] no domain gateway instructs execution from Documents `_runtime`, `_control` scripts, `.kems/_scripts`, or app roots.
- [x] Root PR #1372 makes the source-level gateway checker enforce all 12 projects, recovering the correct domain ID plus Workspace MCP guidance.
- [x] Platform-specific source projections name one accepted Cockpit MCP installation; no domain copies an MCP command matrix. This does not claim a client config reload or current Claude/Codex/Zed UI smoke.

**Accepted root evidence:**

- PR #1364 accepted representative gateway validation.
- PR #1372 accepted all-12 source-level gateway enforcement.
- PR #1376 accepted the ChatGPT public HTTPS/Secure MCP Tunnel routing contract.

**Commit:** `feat(cockpit): expose SSOT-backed domain project contexts`

---

### Task 4: 建立机器可验的迁移 registry 与覆盖门

**Files:**

- Create: `.omo/_truth/registry/documents-content-plane-migrations.yaml`
- Create: `bin/gac/documents-content-plane-migration-check.py`
- Create: `tests/test_documents_content_plane_migration_check.py`
- Modify: `.omo/_truth/registry/INDEX.md`
- Modify: `.omo/_truth/registry/governance-checks.yaml`
- Modify: `.omo/_truth/registry/ci-surfaces.yaml`

**Registry fields:** `id`、`source_globs`、`artifact_kind`、`disposition`、`owner`、`replacement`、`consumer_refs`、`rollback`、`confirmation_gate`、`status`。

**Invariant:** 当前 L4 audit 发现的非四大面 runtime 候选和四个大面必须“恰好匹配一个”迁移族；零匹配与多匹配都 fail closed。迁移候选总数由 live audit 与 exact-one registry composition 计算，迁移状态由 registry lifecycle 动态权威。历史文档文本引用不算活动消费者，但 crontab、LaunchAgent、Claude Scheduled、CLAUDE 强制命令和可执行 import 算。

**Steps:**

- [x] 写 fixture 和 RED tests 覆盖零匹配、多匹配、owner 空、replacement 空、非法完成状态。
- [x] 实现 read-only checker；不得自动移动/删除。
- [x] 把 checker 注册为治理检查和 CI surface。
- [x] 对真实 Documents 运行：checker 从当前 L4 audit 与 exact-one registry composition 计算候选，并对零漏配、零多配 fail closed；迁移状态以 registry lifecycle 为准，不在计划中固化为当前 pending 总数。

**Accepted root evidence:** PR #1359 accepted the migration registry/checker; PR #1374 accepted tracked cleanup-runtime coverage.

**Commit:** `feat(governance): register Documents runtime migrations`

---

## Wave 2 — KEMS、公共运行态与真实消费者切换

### Task 5: Kairon/KOS 吸收仍有价值的 KEMS 内容操作

**Files:**

- Create: `.subtrees/kairon/packages/kos/src/kos/kems/domain_profile.py`
- Create: `.subtrees/kairon/packages/kos/src/kos/kems/content_checks.py`
- Create: `.subtrees/kairon/packages/kos/tests/test_kems_domain_profile.py`
- Create: `.subtrees/kairon/packages/kos/tests/test_kems_content_checks.py`
- Modify: `.subtrees/kairon/packages/kos/src/kos/kems/__init__.py`
- Modify as required after impact review: existing `graph_store.py`、`health.py`、`ingest.py`、`model_acceptance.py`、`ontology/*`

**Scope:** 对 `@公共/_runtime/kems-v2` 和学习 KEMS `.kems/_scripts` 做行为对照。只吸收现有 KOS 未覆盖、且有真实消费者/方法价值的纯函数；graph query、snapshot、model acceptance、source consistency 必须复用现有 store/health 接口，禁止复制旧脚本。

**Steps:**

- [x] 为 12 个公共 KEMS 脚本和 10 个学习脚本建立 `retire | map-existing | extend` 表。
- [x] 对要修改的 Kairon symbols 逐个运行 GitNexus `impact`；结果均为 LOW，无受影响执行流程。
- [x] 先写 parity fixtures/RED tests，再实现最小 adapter。
- [x] 运行 KEMS focused tests、KOS affected tests、scoped Ruff/mypy 与 GitHub CI；全仓既有门禁债单独记录。
- [x] 证明 raw private content 不进入 Kairon state，输出只持 ref/hash/字段名/计数。

**Accepted:** Kairon PR #65，squash merge `0a31da635826019927a99f0b67b0d89c5e342785`；22 个入口分类为 retire 7、map-existing 8、extend 7。

**Commit:** `feat(kos): absorb governed Documents KEMS content checks`

---

### Task 6: Runtime 建立 Documents 运行适配与调度包

**Files:**

- Create: `.subtrees/runtime/src/runtime/documents_plane/__init__.py`
- Create: `.subtrees/runtime/src/runtime/documents_plane/paths.py`
- Create: `.subtrees/runtime/src/runtime/documents_plane/commands.py`
- Create: `.subtrees/runtime/src/runtime/documents_plane/jobs.py`
- Create: `.subtrees/runtime/src/runtime/documents_plane/cli.py`
- Create: `.subtrees/runtime/tests/test_documents_plane_paths.py`
- Create: `.subtrees/runtime/tests/test_documents_plane_commands.py`
- Create: `.subtrees/runtime/tests/test_documents_plane_jobs.py`
- Modify: `.subtrees/runtime/pyproject.toml`

**Interfaces:**

- `DOCUMENTS_CONTENT_ROOT`：只读内容根，默认 `~/Documents`。
- `OMOSTATION_RUNTIME_STATE_ROOT`：所有状态、日志、缓存、SQLite、索引和 receipt 的唯一写根；不得落回 Documents。
- `runtime documents run <job-id> --dry-run/--json`：调用注册 owner 命令，不复制 l4/Kairon/OMO/Cockpit 逻辑。
- job spec 明确 `reads`、`writes`、`owner`、`schedule`、`timeout`、`evidence_path`、`fail_closed`。

**Tests:** path traversal、Documents write denial、state root 创建、owner timeout、非零 exit 透传、dry-run 无副作用、job ID 唯一。

**Accepted:** Runtime PR #46，squash merge `822656c56ae745e57d6c4aa6f0b64c451d76281c`。`runtime documents run` 只委托显式注册 owner；owner 写入限制在每次运行的新隔离根，Runtime 私有 evidence/control 使用 descriptor-anchored publication；非 macOS 或缺少系统 sandbox 时稳定 fail-closed（125）。

**Commit:** `feat(runtime): add governed Documents plane adapters`

**Post-MVP update (2026-08-12):** Runtime PR #47 (`e727c00e86fa8584c7e1766a1ef7f05b7b9826c5`)
registered the manual, read-only `l4-registry-list` and `l4-content-audit`
owner jobs. Root PR #1380 (`47f8dba1a7a1b8bb76315c33543c7ba3f0124d7d`)
adopted that Runtime revision. These are generic L4 observation commands, not
replacement implementations for a Documents runtime family: no migration-family
status, legacy bridge, schedule, or physical consumer was changed by this step.

---

### Task 7: 拆解并迁移 `@公共/_runtime` 与 `@驾驶舱/_runtime`

**Source families:**

- Documents: `@公共/_runtime/*`（59 个 runtime）
- Documents: `@驾驶舱/_runtime/*`（9 个 runtime）

**Target owners:**

| 族 | owner |
|---|---|
| domain contract/convergence/meta-model/freshness | l4-kernel |
| cards/context/dashboard/brief/bridge views | Cockpit |
| C2G/MOF/registry writeback | ECOS/OMO 对应现有命令 |
| ingest/notification/reach/private connectors | Runtime + Agora registry |
| KEMS graph/eval/snapshot | Kairon/KOS |
| scheduler/watch/logs/state | Runtime |
| dated repair/deploy/cleanup scripts | evidence archive or retire |

**Files:** 由 Task 4 registry 的 replacement 精确决定；任何新增 owner 文件必须位于上述现有项目，不创建 `projects/documents-runtime`。

**Steps per family:**

- [ ] 记录源 SHA-256、CLI help、fixture output 和所有活动消费者。
- [ ] 在 owner 侧写 RED parity test。
- [ ] port/compose 最小实现，所有路径 env-driven。
- [ ] 验证输出语义、exit code、读写根和 error envelope。
- [ ] 把 Documents 实现先替换为带 telemetry/sunset 的薄桥；此步不删除。
- [ ] 更新 migration registry 为 `bridged`。

**Commit:** 按 owner 子仓拆分，不得把 68 个脚本塞进一个巨型提交。

---

### Task 8: 切换 crontab、LaunchAgent、Claude Scheduled 与控制文档

**Files:**

- Create: `.omo/cron/documents-content-plane-crontab`
- Modify: `/Users/xiamingxing/Library/LaunchAgents/com.learningevolution.concept-weave.monthly.plist`
- Modify: `/Users/xiamingxing/Documents/Claude/Scheduled/vault-daily-health/SKILL.md`
- Modify: `/Users/xiamingxing/Documents/Claude/Scheduled/l4-governance-weekly/SKILL.md`
- Modify: `/Users/xiamingxing/Documents/Claude/Scheduled/monday-vault-health/SKILL.md`
- Modify: `/Users/xiamingxing/Documents/Claude/Scheduled/weijian-daily-health/SKILL.md`
- Modify: `/Users/xiamingxing/Documents/@工作文档/卫健委/CLAUDE.md`
- Modify: `/Users/xiamingxing/Documents/@驾驶舱/_control/async-tasks.yaml`
- Modify active pointers under `/Users/xiamingxing/Documents/@驾驶舱/_control/`

**Steps:**

- [ ] 生成旧/新 schedule 对照，保证分钟、时区、超时、日志和 failure semantics 不变。
- [ ] `runtime documents run ... --dry-run` 全部通过后，构造新 crontab；禁止使用 `/tmp/gen_index.py`。
- [ ] 安装前备份 `crontab -l` 与 plist SHA-256。
- [ ] 原子切换并立即 `crontab -l`、`plutil -lint`、`launchctl print` 验证。
- [ ] 手动触发每个 job 的只读/dry-run smoke，确认 evidence 写入 Runtime state root。
- [ ] 连续观测至少一个触发周期；旧桥 telemetry 无调用后才进入退役队列。

**Rollback:** 恢复备份 crontab/plist；旧薄桥在观测期内保留。

---

## Wave 3 — 各域功能层与大型资产归位

### Task 9: 学习进化运行层归 Kairon/Runtime/ToolBox

**Source:**

- `@学习进化/_control/daemon/`
- `@学习进化/_control/executors/`
- `@学习进化/_control/scripts/`
- `@学习进化/_control/l4-kernel.sh`
- `@学习进化/_knowledge/10-systems/KEMS/.kems/_scripts/`
- `@学习进化/_inbox/inbox-router.sh`

**Targets:**

- concept weave、freshness、schema/frontmatter/index checks → Kairon/KOS；
- job execution、daemon、monthly schedule、logs/state → Runtime；
- human commands → Cockpit；
- method/profile/schema/rubric → Documents；
- repair backups、旧方法论脚本 → `CONTENT_ARCHIVE.yaml`。

**Files:** target files由 Task 5/6 adapters 承接；Documents active CLAUDE/Scheduled/INDEX 指针同步更新。

**Verification:** concept-weave fixture parity、KEMS validator parity、launchd manual trigger、Documents write deny、Kairon/Runtime full tests。

---

### Task 10: 工作文档域 controller/OCR/index/report 归 Runtime domain adapters

**Files:**

- Create: `.subtrees/runtime/src/runtime/documents_plane/domain_adapters/__init__.py`
- Create: `.subtrees/runtime/src/runtime/documents_plane/domain_adapters/weijian.py`
- Create: `.subtrees/runtime/src/runtime/documents_plane/domain_adapters/ocr.py`
- Create: `.subtrees/runtime/tests/test_documents_weijian_adapter.py`
- Create: `.subtrees/runtime/tests/test_documents_ocr_adapter.py`
- Kairon domain profile changes only if Task 5 parity proves necessary。

**Source families:**

- `@工作文档/_control/tools/`
- `@工作文档/tools/`
- `卫健委/_control/`、`卫健委/_runtime/`
- `合同法规/_control/tools/`
- `国转中心/tools/`、`国转中心/_runtime/`
- `规自委/tools/`、`规自委/_scripts/`、`规自委/_runtime/`

**Rules:**

- OCR 可读 Documents 文件，但索引、临时图像、SQLite 和日志只能写 Runtime state root。
- predictor/controller 的状态与 task 必须进 OMO，不得改写 Documents control state 冒充任务完成。
- 交付区/历史工具按 `CONTENT_ARCHIVE.yaml` 冻结，不 port 无消费者的一次性脚本。

**Verification:** fixture parity、中文路径、权限拒绝、幂等、断点恢复、crontab manual run、无 `/tmp` SSOT。

---

### Task 11: 家庭 Next 应用完整合并到 `family-hub`

**Danger gate:** 执行大目录复制/移动前再次确认。

**Source:** `/Users/xiamingxing/Documents/@家庭生活/family-dashboard-app`

**Target files:**

- Create: `.subtrees/family-hub/apps/dashboard/`（仅源代码、tests、config、lockfile；排除 `.next`、`node_modules`、日志、SQLite）
- Preserve/move existing quest UI under a documented family-hub app boundary if needed
- Modify: `.subtrees/family-hub/package.json`
- Modify: `.subtrees/family-hub/pyproject.toml`
- Modify: `.subtrees/family-hub/README.md`
- Modify: `.subtrees/family-hub/docs/ARCHITECTURE.md`
- Add unit/integration/E2E tests under family-hub
- Modify: `.subtrees/cockpit/src/cockpit/web/api_domain_apps.py`
- Modify: `.subtrees/cockpit/src/cockpit/tests/test_domain_apps_api.py`

**Boundary:**

- `FAMILY_DOCUMENTS_ROOT` 只读；
- build/cache/index/SQLite 写 family-hub runtime state；
- 写 Documents 文件的 API 默认禁用，启用时必须经 OMO proposal/approval；
- 保留 auth、CSRF、redaction、path traversal 和 write audit 测试；
- Cockpit 移除 `family-dashboard-app` contract，只保留 `family-hub`。

**Steps:**

- [ ] 生成源排除清单和树指纹。
- [ ] 复制 327 个非构建文件到隔离 target，保持源不动。
- [ ] 在 family-hub 修正相对路径/state root，先单测再 build/E2E。
- [ ] 运行功能矩阵：summary/daily/members/health/growth/assets/search/tasks/files/graph/AI/backup。
- [ ] 切换 Cockpit contract 与本地启动入口。
- [ ] 观测稳定后，旧 app 进入删除确认；cache 只重建不迁移。

**Commit:** `feat(family-hub): absorb canonical family dashboard app`

---

### Task 12: 四个外部 Git 仓迁入 ToolBox 受管 staging

**Danger gate:** ToolBox 分支/worktree、目录移动和 Documents 源删除前再次确认。

**Targets:**

```text
/Users/xiamingxing/ToolBox/_staging/education/DeepTutor
/Users/xiamingxing/ToolBox/_staging/education/ai-engineering-from-scratch
/Users/xiamingxing/ToolBox/_staging/methodology/BMAD-METHOD
/Users/xiamingxing/ToolBox/_staging/capabilities/gstack
```

**Steps:**

- [ ] 检查 target 不存在、ToolBox worktree clean、四源 clean。
- [ ] 记录每仓 remote、HEAD、tracked/untracked、文件数、字节数和树哈希。
- [ ] 在 ToolBox 隔离分支复制/移动并更新 `registry/tools.json`、`CLASSIFICATION.md`、`CLAUDE.md`。
- [ ] Workspace capability registry 指向 ToolBox owner；不复制能力实现进 Workspace 子仓。
- [ ] Documents 建立内容索引，保留学习笔记和使用说明，不保留 `.git`/源码树。
- [ ] 验证四 target `git fsck`、remote、HEAD、status 与源一致。
- [ ] 删除源目录前再次确认并保留回滚包。

---

### Task 13: 历史代码资料、模板和一次性脚本转强内容归档

**Primary manifests:**

- `/Users/xiamingxing/Documents/@个人/_storage/职业历史/CONTENT_ARCHIVE.yaml`
- 家庭成员历史设计稿/已办结目录的局部 manifests
- 创意创作 `_archive` 与模板目录的局部 manifests
- 工作文档交付区/历史工具目录的局部 manifests
- KEMS repair backups、Documents `_inbox` 已完成脚本的局部 manifests

**Steps:**

- [ ] 对每个 archive root 生成文件数、字节数、tree SHA-256 和活动消费者扫描。
- [ ] 明确 archive root，不允许用顶层 manifest 覆盖仍活跃目录。
- [ ] 写 manifest 后运行 l4 archive validation；库存漂移必须 fail closed。
- [ ] 对仍有活动消费者的脚本拒绝归档，返回 Task 7/9/10。
- [ ] 批量 chmod 如确有必要，先输出 20,833+ affected entries 的精确统计并再次确认。

**Result:** 职业历史代码仍是 Documents 资料，不再被误报为 Workspace runtime，也不被错误物理迁移。

---

### Task 14: Zotero app dataDir 迁出 Documents

**Danger gate:** 修改 prefs、复制/移动数据库和删除旧目录前再次确认。

**Source:** `/Users/xiamingxing/Documents/Zotero`

**Proposed target:** `/Users/xiamingxing/Library/Application Support/Zotero/Data`

**Steps:**

- [ ] 确认 Zotero 无进程；记录 SQLite quick-check、文件数、字节数、附件清单、translators 数量和树指纹。
- [ ] 复制到 target，保留源不动；运行 `sqlite3 ... 'PRAGMA quick_check;'`。
- [ ] 备份并更新 profile `prefs.js` 的 dataDir 与 watcher path。
- [ ] 启动 Zotero，验证库项目数、附件可打开、Better BibTeX 与 translators 正常。
- [ ] 关闭再启动一次，确认 target 是实际写入位置。
- [ ] Documents 只保留显式导出/附件资料目录和说明，不留 app runtime。
- [ ] 旧目录删除前再次确认；回滚为恢复 prefs + 原目录。

---

## Wave 4 — 退役、缓存清理、强门禁与最终无损证明

### Task 15: 退役 legacy scripts/symlinks、旁路原型与缓存

**Danger gate:** 输出精确删除清单后再次确认。

**Targets:**

- Documents 中已零消费者的 runtime 文件、KEMS 域级绝对符号链接和 Phase 0 薄桥；
- `family-dashboard-app/node_modules`、`.next` 和其他可重建 caches；
- Documents 下 SQLite/index/pycache/log cache；
- `projects/domain-kems`（仅在有价值配置已吸收、根仓无消费者、历史证据已记录后）；
- broken root `tools/kems` legacy island（按消费者决定薄客户端或退役）。

**Pre-delete evidence:** 每个 target 的路径、类型、文件数、字节数、SHA-256/tree hash、owner replacement、consumer search、last observed invocation、backup/restore command。

**Steps:**

- [ ] 运行全局 consumer search：crontab、launchd、Claude Scheduled、shell history/config、source imports、BOS registry、Cockpit contract。
- [ ] 运行 replacement smoke 和 rollback drill。
- [ ] 获得明确确认后，优先移入可恢复隔离区；确认后再永久清理。
- [ ] 从 owner source 重建必要 cache，证明不依赖旧 Documents cache。
- [ ] 更新 migration registry 为 `retired`，不得手填完成而无 evidence。

---

### Task 16: T8 单域推广与默认强制

**Files:**

- Modify: `.subtrees/l4-kernel/src/l4_kernel/harness_profiles.py`
- Modify: `.subtrees/l4-kernel/tests/test_harness.py`
- Modify: `.subtrees/l4-kernel/tests/test_harness_profiles.py`
- Modify: Documents domain manifests/registry only for declarative gate enablement
- Modify root CI/governance surfaces as required

**Steps:**

- [ ] 按域运行 T8：个人 → 创意 → OPC → 公共 → 驾驶舱 → 学习 → 工作子域 → 家庭。
- [ ] 每域必须 `runtime=0/cache=0/bridge=0/archive_invalid=0` 才启用；不得用 waiver 假绿。
- [ ] 所有域通过后把 T8 加入文档域默认 profile。
- [ ] 测试新建域默认生成 declarative-only 内容并自动通过 T8。
- [ ] 运行 l4 full tests、所有 owner full tests、Workspace GaC gates。

**Commit:** `feat(l4): enforce T8 for all Documents domains`

---

### Task 17: 全局验证、PR 合并与最终审计

**Verification matrix:**

```bash
# l4-kernel
uv run --directory ".subtrees/l4-kernel" --group dev pytest tests/ -q
uv run --directory ".subtrees/l4-kernel" --group dev ruff check src tests

# Kairon/KOS
uv run --directory ".subtrees/kairon" pytest packages/kos/tests -q

# Runtime
uv run --directory ".subtrees/runtime" pytest tests -q

# Cockpit
uv run --directory ".subtrees/cockpit" pytest src/cockpit/tests tests -q

# Family Hub
uv run --directory ".subtrees/family-hub" pytest tests -q
bun --cwd ".subtrees/family-hub/apps/dashboard" test
bun --cwd ".subtrees/family-hub/apps/dashboard" run build
bun --cwd ".subtrees/family-hub/apps/dashboard" run test:e2e

# Root governance
make check-layers
make doc-ssot-lint
make ssot-guardian
make gac-local-gate
uv run --with pyyaml python "bin/agent-workflow.py" compliance

# Installed surface
"/Users/xiamingxing/.local/bin/cockpit" context
"/Users/xiamingxing/.local/bin/cockpit" cards --check
"/Users/xiamingxing/.local/bin/cockpit" kems status

# Final authoritative audit
L4_DOCUMENTS_ROOT="/Users/xiamingxing/Documents" \
  "/Users/xiamingxing/.local/bin/cockpit" kems scan
```

**Final evidence bundle:**

- final audit JSON and counts;
- before/after inventory diff;
- scheduler/LaunchAgent snapshots;
- installed Cockpit version + loaded commits;
- family-hub functional matrix and E2E artifacts;
- Zotero quick-check and attachment smoke;
- external repo origin/HEAD parity;
- per-repo PR/CI/merge URLs and accepted commits;
- rollback drill results;
- migration registry with every entry `retired | content_archive | moved` and evidence refs.

只有上述证据逐项成立，才能关闭 governance runs、提交 root pointer PR、合并并宣称“全面落地完成”。

## 3. Error and Rollback Matrix

| Failure | Required behavior | Rollback |
|---|---|---|
| archive manifest invalid/drift | T8 fail closed；不得降级 content | 修 manifest/库存，或恢复 runtime 候选 |
| owner command unavailable | Cockpit/Runtime 返回 degraded + non-zero | 继续使用旧桥，不切消费者 |
| parity output differs | 停止该族迁移 | revert owner commit |
| crontab/launchd trigger fails | 立即恢复备份 schedule | 恢复旧 crontab/plist |
| family-hub build/E2E fails | 不切 Cockpit contract | 旧 app 保持原位 |
| external repo target dirty/hash mismatch | 停止源删除 | 删除未采用 target copy，源不动 |
| Zotero library/attachment mismatch | 不删除源，恢复 prefs | prefs 指回 Documents/Zotero |
| final audit仍有 runtime/cache/bridge | 不启用默认 T8、不宣称完成 | 回到 registry 未完成项 |
| CI/GaC failure | 不 merge | 修复或 revert 对应子仓 PR |

## 4. Physical-Migration Confirmation Checkpoints

需要单独再次确认的四个 checkpoint：

1. 家庭应用 327 个源文件复制进 family-hub，以及后续删除旧 806 MiB 目录/缓存；
2. 四个外部 Git 仓迁入 ToolBox；
3. Zotero 24 MiB dataDir 迁移与 prefs 修改；
4. 最终删除 legacy scripts/symlinks/caches、批量 chmod 或退役 `domain-kems`。

确认请求必须给出当时的精确清单和证据，不能拿本计划当无限期删除授权。

## 5. 2026-08-13 Capability-Route MVP Checkpoint

This iteration closes the capability-owner ambiguity without expanding the
product surface:

- Cockpit PR #38 validates skill and workflow routes at `domain_context` time,
  returns their resolved Workspace paths, and degrades invalid bindings;
- root PR #1391 records ADR-0409, moves the two executable route references to
  Workspace sources, adds fail-closed checker coverage, and advances the
  Cockpit gitlink;
- the accepted checkout is clean at root merge `536b0d97` and Cockpit
  `78af7865`;
- the installed checker reports 12 domains, 12 gateways, and zero errors;
- all 12 installed `domain_context` calls report `ok` and resolve skills to
  accepted `.agents/skills` and workflows to accepted
  `.omo/_truth/registry/agent-workflows.yaml`;
- the Documents Skill and Registry indexes are now explicitly human
  projections. Their pre-change copies are retained under the 2026-08-13
  capability-route-projection backup.

This is an MVP checkpoint, not Task 17 completion. The next bounded iteration
is domain-content quality: resolve or explicitly accept the current
`facts-audit` gaps (`opc`, `work-docs`, and `work-contracts`) without creating
empty placeholder truth. Client configuration remains aligned to the accepted
Cockpit MCP entrypoint, while per-client reload/UI smoke and ChatGPT public
HTTPS/Secure MCP Tunnel provisioning remain separate work.

## 6. 2026-08-13 Domain Facts Quality Checkpoint

The three previously missing facts surfaces now contain short, source-backed
structural facts:

- `opc` records its operational ownership, one-person-company identity, pipeline
  states, and existing system entrypoints;
- `work-docs` records only federation and subdomain routing facts, without
  copying business facts from child domains;
- `work-contracts` records the reference-library boundary, source categories,
  navigation indexes, and the derived status of OCR text.

The installed `facts-audit` moved from the observed RED baseline of nine present
and three missing to 12 present, zero missing, zero unreadable, and zero invalid.
Each target also passes an independent single-domain audit. The contracts facts
file is locally committed as `7acdccb`; that nested repository has no configured
remote and retains unrelated pre-existing dirty state. The OPC and work-docs
files live on the non-Git Documents content plane.

This checkpoint does not claim that all facts are fresh or exhaustive. It closes
only the missing-surface gate with stable source pointers. The next MVP iteration
should be one real client reload/UI smoke, preferably Claude-3p because it uses a
third-party model and has its own configuration entrypoint.

## 7. 2026-08-13 Claude-3p Reload/UI Checkpoint

The bounded Claude-3p client smoke is now complete without changing inference or
MCP configuration:

- the running application is `/Applications/Claude.app` in `deploymentMode=3p`,
  with its helpers anchored to `~/Library/Application Support/Claude-3p`;
- the third-party inference entrypoint is the in-app **Inference
  configuration** surface. Its applied profile is `CC Switch`, provider
  `Gateway`, with a static credential and model labels projected through the
  local gateway;
- the pre-smoke Claude process predated the 2026-08-13 Cockpit configuration and
  its Developer list did not contain `cockpit`, so configuration-file presence
  was correctly rejected as reload evidence;
- after the in-flight Cowork task completed, Claude was quit cleanly and
  relaunched. The new Claude process retained the Claude-3p data directory and
  the `deepseek-v4-flash` Gateway model label;
- the relaunched Claude process started the accepted `cockpit-mcp` command, and
  Developer settings showed `cockpit` with status `running` and no warning
  marker.

This closes the Claude-3p reload/UI portion of the client MVP. It does not claim
that every configured MCP is healthy: `MCP_DOCKER`, `MiniMax`, and
`wps-note-cloud` independently reported disconnected after restart. It also does
not claim a Claude-side tool invocation, because the automation provider could
inspect and click the Electron UI but could not acquire keyboard focus for a
safe read-only prompt. The installed Cockpit stdio protocol/tool smoke remains
the command-level evidence for tool execution.

The next bounded iteration is one real domain journey through the now-running
Claude-3p Cockpit surface, followed by independently recorded reload/UI evidence
for the remaining clients. Existing inline remote-MCP credentials should be
rotated and moved out of command arguments as a separate security-hardening
change; no credential value was copied into this plan.

## 8. 2026-08-13 Codex Documents Profile MVP Checkpoint

The first real Codex domain journey exposed two client-context problems that
were independent of Cockpit: every user MCP server was started for a read-only
Documents request, and the user Skill inventory exceeded the model-context
budget. The raw Codex inventory contained 13 MCP servers and 235 parsed Skills;
all 229 user-scope Skills were enabled, two additional user Skill files had
invalid frontmatter, and the model-visible prompt dropped descriptions and
omitted part of the catalog.

This iteration adds a Workspace-owned, opt-in `documents` profile contract and
generator:

- `.omo/_truth/registry/documents-domain-projects.yaml` owns the profile name,
  generator reference, exclusive Cockpit binding, approval policy, and
  user-local Skill policy;
- `bin/gac/documents-codex-profile.py` derives current MCP and Skill inventory
  from Codex itself, renders the profile, installs it atomically, refuses to
  overwrite caller-owned content, and detects later inventory drift;
- the installed projection is `~/.codex/documents.config.toml`; it affects only
  sessions explicitly launched with `codex --profile documents` and does not
  add `.codex`, runtime, or implementation files to any Documents domain;
- the installed profile exposes only Cockpit, allows the four read tools in the
  `content-domain` profile, uses `approve` only for those allow-listed tools,
  and disables 219 user-local Skill paths while preserving system and installed
  document/plugin Skills;
- model-visible Skills fell to 17 fully described entries (five system and
  twelve installed plugin Skills), and the profile file is mode `0600`.

The source/profile/checker tests are green, and the live 12-domain binding
checker remains the acceptance gate. A direct accepted Cockpit call still
returns the authoritative binding and resolved Workspace capability paths.
However, the final fresh `codex exec` attempt did not reach a tool call: the
Codex process was observed in an external HTTPS `SYN_SENT` state and was stopped
after the bounded wait. Therefore this checkpoint proves profile installation,
context reduction, and Cockpit configuration, but does not claim a successful
fresh Codex model-originated MCP invocation.

The next bounded iteration is to repair or retire the two malformed user Skill
files, retry the same read-only `work-weijian` journey when the model endpoint is
reachable, and record the returned `binding_status`, skill path, and workflow
path. Default Codex configuration and all Documents content remain unchanged.

## 9. 2026-08-13 Codex Real-Journey Acceptance

The bounded follow-up closed the two open items from the preceding checkpoint
without changing the default Codex configuration or any Documents content.
The two IMA child `SKILL.md` files in the local shared Skill catalog received
only the required `name` and trigger-only `description` frontmatter. A fresh
Codex app-server inventory then reported 237 parsed Skills and zero parse
errors. The installed `documents` profile remained unchanged and passed its
accepted generator check with 13 inventoried MCP servers and 219 disabled
user-local Skill paths.

A fresh ephemeral `codex --profile documents exec` run then completed with exit
code zero. The model called exactly one MCP tool: Cockpit
`domain_context(domain_id="work-weijian")`. The response returned
`binding.status=ok`, resolved the Skill route to accepted Workspace
`.agents/skills`, and resolved the Workflow route to accepted Workspace
`.omo/_truth/registry/agent-workflows.yaml`. No shell tool, local file read, or
write action was requested by the model.

This is the first current model-originated acceptance proof for the Codex
Documents profile. It supersedes the earlier connectivity blocker as current
state while preserving that earlier attempt as historical evidence. The next
client iteration can move to a fresh Claude domain-tool journey, then the
Zed/ZCode-compatible client path; ChatGPT web remains a separately provisioned
public HTTPS or secure-tunnel track.

## 10. 2026-08-13 Zed Documents Profile MVP Checkpoint

The Zed client now has a Workspace-owned `documents` profile contract rather
than relying only on a broad client MCP registration. The contract derives its
tool allow-list from the existing `content-domain` profile and keeps execution
outside Documents:

- `bin/gac/documents-zed-profile.py` renders, installs, and checks the profile
  while preserving unrelated settings, MCP servers, themes, and permissions;
- the `Documents` Agent Profile has no built-in tools, does not enable all
  context servers, and explicitly enables only Cockpit `workspace_context`,
  `domain_context`, `cards_status`, and `cards_check`;
- those four MCP tools have explicit `allow` rules, while the existing global
  confirmation policy and unrelated tool rules remain unchanged;
- installation is atomic, idempotent, mode `0600`, rejects symbolic-link
  settings paths, and refuses to overwrite a different existing `documents`
  profile or conflicting tool permission;
- the root registry checker and required `phase-gate` workflow own the source
  contract and its focused tests.

The installed `~/.config/zed/settings.json` passed a post-install check. A
protocol smoke using the exact configured Cockpit command and environment
successfully initialized the server, found `domain_context`, and returned
`binding.status=ok` for `work-weijian`. This is configuration and server-contract
evidence; it is not a Zed Agent Panel green-dot observation or a Zed
model-originated tool invocation. The running Zed process predated the settings
write, and the desktop was at the macOS lock screen; activating the application
did not establish reload evidence. The iteration did not bypass login or claim
UI acceptance.

The next bounded client step is a fresh Zed Agent Panel journey after the user
session is unlocked. ZCode remains on the generic `agents_compatible` contract,
and ChatGPT web remains the separately provisioned public HTTPS or secure-tunnel
track.
## Next governed wave: T10-41 Documents execution retirement

The remaining `_runtime` and `.kems` material is not one homogeneous class.
The next wave therefore separates active executors, Workspace read inputs,
generated runtime/cache/index artifacts, and business content before any
physical operation. `daily-health-run.py` and the KOS ingest schedule are the
first explicit consumers to map. No permanent deletion is authorized by this
wave; quarantine and deletion require separate evidence and human-gated
decisions.

The acceptance boundary is `consumer=0` for a candidate, a verified Workspace
replacement where execution is involved, unchanged business-document bytes and
metadata, and a recoverable rollback package. An unknown or semantically
ambiguous candidate remains in place and is reported as unresolved.

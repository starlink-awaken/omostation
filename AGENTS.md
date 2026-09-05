---
type: ssot
owner: governance-team
last_updated: 2026-09-04
---

# AGENTS.md — Workspace Development Guide

> Root operating guide for AI coding agents. **Keep operational** — runtime facts go in SSOT files, not here.

## 0. Worktree Policy (Mandatory)

> **Main workspace is read-only. Every new change starts from an isolated worktree.**

| Action | Required |
|--------|----------|
| New feature / fix / cleanup | `bash bin/gac/gac-worktree.sh claim <session>` |
| Direct commit to main | ❌ Prohibited |

**Full policy**: [`GOVERNANCE.md`](GOVERNANCE.md) § Worktree Isolation

---

## 1. Read This First (Before Every Edit)

1. Read [`CLAUDE.md`](CLAUDE.md) for session startup context.
2. Read the target project `AGENTS.md` / `CLAUDE.md`.
3. Check `git status --short`.
4. **需求迭代强制 Workflow（ADR-0203）** — Run `bootstrap → start --profile → claim` before any requirement delivery edit. Use `bin/agent-workflow.py compliance` for compliance audit.
5. For governed state, use OMO/C2G brokers instead of direct `.omo` writes.
6. For multi-file or high-risk changes, explain the edit surface before applying patches.
7. All local/edge LLM inference MUST route through **AetherForge (`bos://compute/aetherforge/infer`)**.

### Key SSOT Registries

| Registry | Purpose |
|----------|---------|
| `.omo/_truth/registry/agent-workflows/` | Agent workflow facts |
| `.omo/_truth/registry/ci-surfaces.yaml` | CI 平面检查接线 |
| `.omo/_truth/registry/runtime-projections.yaml` | Runtime projections |
| `.omo/_truth/registry/governance-checks.yaml` | GaC rules |
| `docs/project-registry.yaml` | Project metadata |

### Governance Quick Reference

| Need | Command |
|------|---------|
| MOF constraint check | `ecos-constraint explain/audit/eval/drift` |
| Domain truth hygiene | `make hygiene-patrol` |
| Policy-as-code | `ecos-constraint policy audit/explain/list` |
| Intent-to-spec | `ecos-constraint intent compile` |
| Shadow challenge | `ecos-constraint challenge [--auto-patch]` |
| Sovereign compute | `omlxc fabric snapshot` |
| Cartridge factory | `ecos-constraint cartridge list/export/validate` |

**Binding architecture (DFSQ/SFOP)**: Mesh (`COMP-WS-omo`) is the only active `S` slot. Do **not** add a second dispatcher or fifth ontology.

### 能力发现

| 需求 | 入口 |
|------|------|
| 查看所有可用 skills | `cat .agents/skills/INDEX.md`（按域分组，由 generator 派生; 运行 `find .agents/skills -name SKILL.md | wc -l` 取实时计数） |
| 查看所有 workflows | `cat .omo/_truth/registry/agent-workflows/INDEX.md`（按 generator 派生; 运行 `find .omo/_truth/registry/agent-workflows -name "*.yaml" | wc -l` 取实时计数） |
| 智能推荐 workflow | `uv run python bin/agent-workflow.py suggest --from-diff --profile <agent>` |
| Cockpit CLI 命令 | `cockpit <domain> <verb>`（详见 `docs/CLI-REFERENCE.md`） |
| BOS 服务发现 | `.omo/_truth/registry/capability-providers.yaml` |
| MCP 工具清单 | `docs/generated/capability-registry.yaml` |
| MCP/BOS URI 完整性 | `python3 bin/gac/check-mcp-bos-uri-completeness.py`（`--warn` 模式审计不阻断） |

---

## 2. Documentation SSOT Contract

| Document | Owns |
|----------|------|
| `README.md` | Front door and quick orientation |
| `CLAUDE.md` | AI session startup protocol |
| `AGENTS.md` | Workspace operating rules |
| `ARCHITECTURE.md` | Stable architecture contracts |
| `docs/project-registry.yaml` | Project metadata facts |
| `.omo/_truth/registry/governance-checks.yaml` | GaC rules |

**Do not hard-code** current phase, health score, test counts, or port values in Markdown. Use pointers.

Full contract: [`.omo/standards/doc-ssot-contract.md`](.omo/standards/doc-ssot-contract.md)

---

## 3. Architecture Summary

Stable architecture contracts: [`ARCHITECTURE.md`](ARCHITECTURE.md)
Project layer placement: [`docs/generated/project-layer-index.md`](docs/generated/project-layer-index.md)

**道法术器 (DFSQ/v1)**: `python3 bin/gac/check-sfop-slots.py --json`
**Execution chain**: `python3 bin/gac/check-execution-chain.py --json`

---

## 4. Governance Boundaries

| Surface | Rule |
|---------|------|
| `.omo/` | State/evidence plane. Do not add long-lived execution logic. |
| `projects/omo/` | Governance kernel: schema, audit, sync, broker, lint. |
| `projects/ecos/` | Protocol and MOF layer. |
| `bin/` | Governance tools. Do not edit runtime state manually. |
| `config/` | Machine identity. Do not edit manually. |
| `kos/` | Knowledge index. Runtime product, do not edit manually. |

---

## 5. Essential Commands

### Agent Workflow (single entry)

```bash
uv run --with "pyyaml" python "bin/agent-workflow.py" bootstrap
uv run --with "pyyaml" python "bin/agent-workflow.py" compliance
uv run --with "pyyaml" python "bin/agent-workflow.py" start <workflow-id> --profile <agent-profile> --bet <BET-ID> --objective "<summary>"
uv run --with "pyyaml" python "bin/agent-workflow.py" claim <run-id> --path <path>
uv run --with "pyyaml" python "bin/agent-workflow.py" closeout <run-id>
```

### Gates & Lint

```bash
make gac-local-gate          # Full local governance gate
make ci-local                # All local CI checks
python3 bin/gac/ci-check-runner.py --workflow governance-check.yml
```

### Testing

```bash
bash "tests/integration/run-all.sh"    # Root integration suite
cd "projects/knowledge/kairon" && make test-diff
cd "projects/knowledge/gbrain" && bun test
```

### SSOT & State

```bash
make ssot-guardian && make ssot-sync
python3 bin/gac/meta-doctor.py --workspace . --json
```

**Full catalog**: [`bin/README.md`](bin/README.md) | **CLI reference**: [`docs/CLI-REFERENCE.md`](docs/CLI-REFERENCE.md)

---

## 6. Git And Submodules

- Do not run `git commit`, `git push`, `git reset --hard`, or branch switching unless explicitly asked.
- **Submodule pointer update**: `bash bin/ssot/submodule-pointer-transaction.sh --message "..."`.
- **禁止 `sed -i` 做添加/删除条目操作** — use Python `read → check → modify → write`.
- **子模块 commit 三步走**: ① `cd projects/<sub> && git add && git commit` ② `git push` (子模块内) ③ `cd 主仓 && git add projects/<sub> && git commit && push`.
- **pull --rebase 风险**: 本地 commit 基于旧 main 时可能丢弃改动。rebase 后用 `git reflog` 确认。

### 高危 git 操作守门

- **`reset --hard` 前三确认**: ① 当前分支 ② reset 目标 = 该分支的 origin 状态 ③ 工作树干净。
- **改"看起来是子项目"的代码前确认仓库边界**: `ls -d <path>/.git` + `git -C <path> remote -v`.

### PR 工作流

```bash
bash bin/gac/gac-worktree.sh claim <session>   # 起隔离 worktree
bash bin/gac/gac-worktree.sh submit <session>   # push 分支 + 开 PR
bash bin/gac/gac-worktree.sh merge <session>    # squash 合并 PR
```

---

## 7. Testing Guidance

| Change Surface | Minimum Verification |
|----------------|----------------------|
| Documentation only | `make gac-local-gate` and diff review |
| Python code | Targeted `uv run pytest` |
| kairon | `make test-diff` from `projects/knowledge/kairon` |
| gbrain | `bun test` |
| Cross-project | Targeted tests on every touched consumer |

If a test cannot run, report why and what risk remains.

---

## 8. Closeout Checklist

1. Review `git diff --stat`.
2. Run the verification appropriate for the change.
3. Prefer `make agent-workflow-closeout RUN_ID=<run-id>` for governed runs.
4. Mention files changed and checks run.
5. Do not create commits unless explicitly requested and confirmed.
6. **大任务后复盘+固化**: 教训写 memory + AGENTS.md (协议层) + hook (harness 层).

---

## 9. Architecture Standards (Agent 必读)

**场景卡生命周期** (5 级): `draft → shadow → assisted → supervised → routine`
- 标准: `.omo/standards/scene-card-lifecycle.yaml`
- 升级必须按顺序，shadow 需 3-sample，assisted 需 30-sample + calibration ≥ 0.6

**业务域** (5 域): `work` / `health` / `research` / `knowledge` / `governance`
- 标准: `.omo/standards/business-domains.yaml`

**维度系统** (12 维度): 治理维 4 + 业务维 7 + 新增维 1
- 标准: `.omo/standards/dimension-system.yaml`

**价值循环** (5 阶段): 信号感知 → 信号分类 → 旅程执行 → 价值记录 → 进化反馈
- 标准: `.omo/standards/value-loop-standard.yaml`

**架构校验**: `make architecture-check`

---

## 10. Harness 集成 (Phase 8)

- **Cockpit CLI**: `cockpit harness <command>` (12 子命令)
- **8 阶段 DAG**: `admission → spec → grill → dispatch → execute → verify → audit → accept`
- **Hook 层**: 6 个 exit 1 拦截点 (pre-commit)
- **GaC 规则**: 32 个强制/高优先级规则

```bash
python3 bin/gac/harness-compliance-check.py --report
cockpit harness compliance|full|status
```

---

## 11. Key Patterns & References

- **Historical patterns**: `.omo/_knowledge/patterns/` (P75, P91, P43, P71, P72, P78, etc.)
- **分支等价性判据**: 只用 **内容 diff** (`git diff origin/main...<branch>`)
- **动手前先查 main 是否已自愈 (PITFALL-GAT-006)**: claim/start 前先 `git fetch origin main` 并做内容等价检查 — 被改文件在最新 main 是否已含目标内容 (`git diff origin/main...<branch>` 是否为空/仅剩预期增量), `git log --oneline origin/main -N` 是否已有同类 PR. 多 agent 并发下修复目标可能已被其他 PR 达成 (total_bets #3099 / scene-cards #3097 两次复发); 已合入则放弃分支, 勿开 PR — 否则 PR 合并会回退 main 正确值.
- **Resident Agent**: `make resident-status` | BOS: `bos://resident/*`
- **BCOS**: `make bcos-evolve` | `python3 bin/bc-os/evolution_engine.py --json`
- **ADR index**: `.omo/_knowledge/decisions/`

---

## 12. 归档/收敛项目说明

- agora-dashboard 独立入口已收敛 (能力并入 cockpit/agora)
- (归档) hermes-console 与 dashboard_server 作为子应用挂载 (L3 入口能力收敛到 cockpit/agora)

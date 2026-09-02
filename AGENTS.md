---
last-reviewed: 2026-08-26
---

# AGENTS.md — Cockpit

    > Scope: project-local developer guide for `cockpit`.
    > Workspace rules live in [`../../AGENTS.md`](../../AGENTS.md); project metadata lives in [`../../docs/project-registry.yaml`](../../docs/project-registry.yaml).

    ## Role

    - Layer: L3
    - Stack: Python / uv / pytest
    - Responsibility: 统一人类 CLI/Web 入口与 HITL 操作面

    Do not copy volatile facts such as test counts, tool counts, service counts, ports, or current health into this file.

    ## Before Editing

    1. Read this file and [`CLAUDE.md`](CLAUDE.md) when it exists.
    2. Check `git status --short` inside this project and at the workspace root.
    3. Read the specific source or tests you are about to change.
    4. Prefer project-local commands and targeted tests.

    ## Commands

    ```bash
    uv sync
uv run pytest "src/cockpit/tests/" -q
uv run ruff check "src/"
    ```

    ## Key Files

    - `src/cockpit/cli.py`
- `src/cockpit/commands/`
- `src/cockpit/dashboard_server.py`
- `scripts/cockpit_mcp.py`

    ## Gotchas

    - `测试主目录在 src/cockpit/tests/，不要默认写到根 tests/。`
- `Web/API 入口保持 L3 收敛，新入口先更新边界与端口注册表。`

    ## Verification

    - Documentation-only changes: run `uv run --with "pyyaml" python "../../bin/ssot/doc-ssot-lint.py" --json` from this project or from the workspace root.
    - Code changes: run the narrowest relevant project test first, then broaden if shared contracts changed.
    - Cross-layer behavior: verify the caller and the callee, not just the touched module.

    ## SSOT Pointers

    - Workspace architecture: [`../../ARCHITECTURE.md`](../../ARCHITECTURE.md)
    - Layer index: [`../../LAYER-INDEX.md`](../../LAYER-INDEX.md)
    - Project metadata: [`../../docs/project-registry.yaml`](../../docs/project-registry.yaml)
    - Runtime state: [`../../.omo/state/system.yaml`](../../.omo/state/system.yaml)
    - System index: [`../../docs/SYSTEM-INDEX.md`](../../docs/SYSTEM-INDEX.md) — 统一导航入口
    - Projects index: [`../../docs/INDEX-PROJECTS.md`](../../docs/INDEX-PROJECTS.md) — 项目索引
    - Tools index: [`../../docs/INDEX-TOOLS.md`](../../docs/INDEX-TOOLS.md) — 工具索引
    - Knowledge index: [`../../docs/INDEX-KNOWLEDGE.md`](../../docs/INDEX-KNOWLEDGE.md) — 知识索引
    - Agents index: [`../../docs/INDEX-AGENTS.md`](../../docs/INDEX-AGENTS.md) — Agent索引

## Knowledge API 链路 (ADR-0294, 2026-08-01)

### 关键文件

| 文件 | 职责 |
|:-----|:-----|
| `src/cockpit/web/api_knowledge.py` | `/api/knowledge/search` + `/api/knowledge/put` 路由，网络优先 BOS 解析 |
| `src/cockpit/web/knowledge_indexer.py` | 事件消费者，dual-accept `bos://memory/events/card_updated` + legacy `bos://brain/events/card_updated` |
| `src/cockpit/adapters/agora.py` | 进程内兼容适配器（仅供降级路径使用，不直接调用） |

### API 契约

```
POST /api/knowledge/put   → 写入 data/cards/{slug}.md
                          → 非阻塞发射 bos://memory/events/card_updated (canonical)
                          → KnowledgeIndexer 消费 → KOS/LanceDB upsert

POST /api/knowledge/search → 网络解析 AGORA_HTTP_ENDPOINT/bos/resolve
                           → 兼容降级 cockpit.adapters.agora.resolve_bos_uri()
```

### 环境变量

| 变量 | 默认值 | 说明 |
|:-----|:-------|:-----|
| `AGORA_HTTP_ENDPOINT` | port-registry SSOT (agora-mcp-sse=7431) | Agora 网关（BOS 解析 + 事件总线; 由 `web/_agora_ports.py` 读取） |
| `KOS_HTTP_ENDPOINT` | `http://127.0.0.1:7428` | KOS 向量索引服务 |

### SSOT 决策

- 架构决策: [`../../.omo/_knowledge/decisions/0294-knowledge-gateway-decoupling-and-event-pipeline.md`](../../.omo/_knowledge/decisions/0294-knowledge-gateway-decoupling-and-event-pipeline.md)
- 操作手册: [`../../docs/architecture/knowledge-foundry-cron.md`](../../docs/architecture/knowledge-foundry-cron.md) §5
- BOS 域越界登记: [`../../.omo/standards/bos-uri-domain-standard.md`](../../.omo/standards/bos-uri-domain-standard.md)

> ⚠️ Producer 已规范为 `bos://memory/events/card_updated`；Consumer dual-accept 遗留 `bos://brain/events/card_updated`（ADR-0372 D5 / ADR-0294）。

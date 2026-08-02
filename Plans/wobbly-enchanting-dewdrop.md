# 能力全景覆盖 · Cockpit 全通道对齐

> **创建时间**: 2026-08-02 | **模式**: Plan Mode | **前置**: Phase 49 已交付 (health=81, X3=8)
> **时间窗**: 2026-08-02 ~ 2026-08-23 (3 周)
> **目标**: 全量暴露 26 MCP 服务器·~394 工具·184 BOS 服务·46 CLI 命令，help 自动生成，文档自动同步，治理规则 CI 门禁

---

## 0. Context — 为什么要做这件事

### 0.1 当前矛盾

```
能力爆炸 (394 MCP 工具 + 184 BOS 服务 + 46 CLI 命令)
    ← 矛盾 →
用户可见 (27 文档化命令 + 20 文档化工具 + 0 用户文档)
```

**数据差距**:

| 通道 | 文档化 | 实际 | 未暴露率 |
|------|--------|------|----------|
| Cockpit CLI 命令 | 27+ | 46 | 41% |
| Cockpit MCP 工具 | 20 | 30 | 33% |
| Agora MCP 工具 | 35 | 71 | 51% |
| BOS URI 服务 | 114 | 184 | 38% |
| KOS MCP 工具 | 25 | 44 | 43% |
| 全生态 MCP 服务器 | 0 | 26 | 100% |
| 全生态 MCP 工具 | 0 | ~394 | 100% |

### 0.2 已识别的结构性问题

| 编号 | 问题 | 影响 |
|------|------|------|
| S1 | `cockpit agent` 错链到 agent-workflow | 用户跑 `cockpit agent bootstrap` 报错 |
| S2 | `cockpit debt` 忽略子命令永远调 score | 无法 `cockpit debt list` |
| S3 | `cockpit cards` 双实现 (cmd_cards vs l4bridge) | 行为不一致 |
| S4 | gbrain 无 MCP server | 44 篇知识库无法通过 MCP 治理 |
| S5 | metaos MCP deprecated (ADR-0181) | 11 个工具无 MCP 通道 |
| S6 | CAPABILITY-MAP.md 停留在 0.4.0 (2026-06-12) | 文档与实际严重脱节 |
| S7 | docs/INDEX-TOOLS.md 无 cockpit CLI 入口 | 用户找不到 cockpit 命令索引 |
| S8 | cockpit-ui 13 组件可达不可见 | 功能存在但用户用不了 |
| S9 | 10 BOS 服务 deprecated/unimplemented 仍注册 | 用户调了才发现不可用 |
| S10 | agent-gac-rules.md (184) vs agent-redlines.md (188) 数字漂移 | 治理文档互相对不上 |

---

## 1. 总体架构：四通道一张图

### 1.1 能力暴露模型

```
┌─────────────────────────────────────────────────────────────────┐
│                       用户入口层                                  │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐        │
│  │ Cockpit  │  │ Cockpit  │  │  Agora   │  │ Cockpit  │        │
│  │   CLI    │  │   Web    │  │   MCP    │  │   MCP    │        │
│  │ 46 cmds  │  │ 35 views │  │ 71 tools │  │ 30 tools │        │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘        │
│       │              │              │              │              │
│  ┌────┴──────────────┴──────────────┴──────────────┴────┐        │
│  │            统一能力注册表 (capability-registry.yaml)   │        │
│  │     SSOT: 每个工具的 ID / 描述 / 归属 / 通道标签       │        │
│  └──────────────────────┬───────────────────────────────┘        │
│                         │                                        │
│  ┌──────────────────────┴───────────────────────────────┐        │
│  │              子系统能力层 (26 MCP Servers)             │        │
│  │  omo(19) kos(44) l4(51) agora(71) ecos(27) ...      │        │
│  └──────────────────────────────────────────────────────┘        │
└─────────────────────────────────────────────────────────────────┘
```

### 1.2 核心设计原则

1. **SSOT**: `capability-registry.yaml` 是所有能力的唯一真源，help/文档/UI 均从它生成
2. **DRY**: 不重复造轮子，已有 MCP 工具通过 BOS URI 暴露，不重写 CLI
3. **渐进暴露**: P0 修结构 + 基础设施，P1 全量覆盖，P2 治理同步
4. **自动优先**: 能自动生成的绝不手写，CI 门禁兜底

---

## 2. 能力注册表 SSOT

### 2.1 新建文件: `docs/generated/capability-registry.yaml`

> 这是整个方案的**核心新增文件**。所有后续的 help/文档/UI 都从它生成。

```yaml
# docs/generated/capability-registry.yaml
# 全生态能力注册表 — SSOT
# 自动生成，请勿手动编辑
# 生成器: bin/cockpit/gen-capability-registry.py

version: "1.0.0"
generated_at: "2026-08-02T00:00:00Z"
total_tools: 394
total_servers: 26
total_bos_services: 184
total_cli_commands: 46

# ── MCP 服务器清单 ──
mcp_servers:
  - id: omo
    name: "OMO Agent OS Kernel"
    layer: L2
    file: "projects/omo/src/omo/mcp_server.py"
    transport: stdio
    tool_count: 19
    tools: [validate_task, omo_bridge, omo_worker_dispatch, ...]

  - id: kos
    name: "KOS Knowledge Retrieval"
    layer: L2
    file: "projects/kairon/packages/kos/src/kos/mcp/fastmcp_app.py"
    transport: stdio
    tool_count: 44
    tools: [...]

  - id: l4-kernel
    name: "L4 Self-Layer Kernel"
    layer: L4
    file: "projects/l4-kernel/src/l4_kernel/mcp_server.py"
    transport: stdio/http/sse
    ports: {http: 7455, sse: 7456}
    tool_count: 51
    tools: [...]

  # ... 全部 26 个服务器

# ── BOS URI 服务清单 ──
bos_services:
  domain: memory
  count: 38
  services:
    - uri: "bos://memory/kos/search"
      mcp_tool: "kos_search"
      description: "KOS 语义搜索"
    - uri: "bos://memory/kos/index"
      mcp_tool: "kos_index"
      description: "KOS 索引管理"
    # ...

  domain: capability
  count: 52
  services: [...]

  # ... 全部 14 个 domain

# ── Cockpit CLI 命令清单 ──
cli_commands:
  - name: research
    description: "深度研究"
    subcommands: [ask, list, show, archive, export]
    mcp_equivalent: null  # CLI 独有
    bos_equivalent: null

  - name: omo
    description: "委派 omo CLI"
    subcommands: []
    mcp_equivalent: "omo_*"
    bos_equivalent: "bos://omo/*"

  # ... 全部 46 个命令
```

### 2.2 生成器: `bin/cockpit/gen-capability-registry.py`

```python
#!/usr/bin/env python3
"""能力注册表生成器 — 扫描全生态 MCP/BOS/CLI，输出 capability-registry.yaml.

扫描源:
  - projects/*/src/*/mcp_server.py        → MCP 工具
  - projects/*/src/*/mcp.py              → MCP 工具
  - projects/agora/etc/bos-services.yaml  → BOS 服务
  - projects/cockpit/src/cockpit/cli.py  → CLI 命令
"""

import ast
import os
import re
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[2]

def scan_mcp_tools(file_path: Path) -> list[dict]:
    """从 MCP server 文件中提取 @mcp.tool() 注册的工具."""
    content = file_path.read_text()
    # 匹配 @mcp.tool() / @mcp.tool(name=...) / @_h("name")
    tools = []
    # ... AST 解析或正则提取 ...
    return tools

def scan_bos_services() -> list[dict]:
    """从 bos-services.yaml 提取所有服务."""
    # ... yaml 解析 ...
    pass

def scan_cli_commands() -> list[dict]:
    """从 cli.py 提取所有 add_parser 注册."""
    # ... 正则提取 sub.add_parser(...) ...
    pass

def main():
    registry = {
        "version": "1.0.0",
        "generated_at": ...,  # datetime.now(timezone.utc).isoformat()
        "mcp_servers": [],
        "bos_services": {},
        "cli_commands": [],
    }
    # 1. 扫描所有 MCP server 文件
    # 2. 扫描 BOS services
    # 3. 扫描 CLI commands
    # 4. 交叉引用 (CLI ↔ MCP ↔ BOS)
    # 5. 输出 YAML
    output = WORKSPACE / "docs/generated/capability-registry.yaml"
    output.write_text(yaml.dump(registry, allow_unicode=True, sort_keys=False))

if __name__ == "__main__":
    main()
```

---

## 3. 分阶段实施

### Phase 0: 结构修复 + 基础设施 (P0, 2d)

> **目标**: 修现有 bug + 建能力注册表生成器 + 打通自动生成管线

#### P0-T1: 修复 3 个 CLI  dispatch 异常

| 文件 | 修复 |
|------|------|
| `projects/cockpit/src/cockpit/cli.py:1214` | `agent` 错链 → 改为独立 dispatch 到 `cmd_agent_runtime` |
| `projects/cockpit/src/cockpit/cli.py` | `debt` 忽略子命令 → 改为 dispatch 字典路由 score/list/summary |
| `projects/cockpit/src/cockpit/cli.py:1005-1012` | `cards` 双实现 → 统一走 l4bridge，`cockpit.commands.cards` 标 deprecated |

#### P0-T2: 新建能力注册表生成器

| 文件 | 说明 |
|------|------|
| `bin/cockpit/gen-capability-registry.py` | 扫描 MCP + BOS + CLI → YAML |
| `bin/cockpit/gen-help-docs.py` | 从注册表生成 CAPABILITY-MAP.md |
| `bin/cockpit/gen-cli-reference.py` | 从注册表生成 docs/CLI-REFERENCE.md |

#### P0-T3: 清理 BOS 废弃服务

| 文件 | 操作 |
|------|------|
| `projects/agora/etc/bos-services.yaml` | 10 个 deprecated/unimplemented 标 `status: deprecated` 或移除 |

#### P0-T4: 补齐 gbrain MCP server

| 文件 | 说明 |
|------|------|
| `projects/gbrain/src/mcp_server.py` | **新建** — 暴露 gbrain 核心工具 (query/status/migrate/health) |

```typescript
// projects/gbrain/src/mcp_server.ts (bun/TypeScript 生态)
import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";

const server = new McpServer({ name: "gbrain", version: "0.1.0" });

server.tool("gbrain_query", "查询 gbrain 知识数据库", {
  query: z.string(),
  limit: z.number().default(10),
}, async ({ query, limit }) => {
  // 调用 gbrain Postgres 查询
});

server.tool("gbrain_status", "gbrain 数据库健康状态", {}, async () => {
  // 表大小 / 连接数 / 查询延迟
});

// 5-8 个工具
```

#### P0-T5: metaos MCP 替代

| 文件 | 操作 |
|------|------|
| `projects/metaos/src/metaos/mcp_server.py` | 确认 ADR-0181 状态，如已废弃则通过 BOS proxy 暴露 |

#### P0 验收

- [ ] `cockpit agent bootstrap` 正常工作
- [ ] `cockpit debt list` 正常工作
- [ ] `cockpit cards list` 行为一致
- [ ] `gen-capability-registry.py` 运行输出 YAML
- [ ] gbrain MCP 可独立启动
- [ ] BOS 10 个废弃服务已清理

---

### Phase 1: 全量 CLI 覆盖 (P1, 3d)

> **目标**: 所有 26 MCP 服务器的核心能力都可通过 cockpit CLI 调用

#### P1-T1: 新增 cockpit 子命令组

| 新增命令 | 实现文件 | 模式 | 覆盖能力 |
|----------|----------|------|----------|
| `cockpit knowledge search/status/stats` | `commands/knowledge.py` | kos_proxy HTTP | KOS 5193 篇索引治理 |
| `cockpit kems domains/status/scan` | `commands/kems.py` | l4bridge 复用 | 28 域注册状态 |
| `cockpit workflow mesh/delivery` | `commands/workflow_mesh.py` | 读 events.jsonl | workflow-mesh 暗面可视化 |
| `cockpit c2g status/pipeline` | `commands/c2g.py` | subprocess → c2g | C2G 全局状态 |
| `cockpit gbrain query/status` | `commands/gbrain.py` | 扩展现有 | 知识库查询 + 健康度 |
| `cockpit toolbox list/invoke` | `commands/toolbox.py` | BOS capability | 外部工具 (wps-office-mcp 等) |

#### P1-T2: 为每个已有命令补全 --help

> 目前很多命令的 help 只有一句话。统一标准:

```
cockpit omo --help
  → "OMO 治理中枢 — 债务/状态/锁/MCP 工具 (19 tools)"
  → 子命令列表 + 对应 MCP 工具名

cockpit kairon --help
  → "Kairon 知识引擎 monorepo — 16 packages, KOS 44 MCP tools"
  → 每个 package 一行 + MCP 工具数
```

#### P1-T3: 全量 BOS URI 注册

| 文件 | 操作 |
|------|------|
| `projects/agora/etc/bos-services.yaml` | 确保 184 个服务全部可 resolve |
| `projects/cockpit/src/cockpit/commands/bos.py` | 扩展 capability 域覆盖 toolbox 外部工具 |

#### P1 验收

- [ ] `cockpit knowledge search "借调"` 返回 KOS 结果
- [ ] `cockpit kems domains` 显示 28 域状态
- [ ] `cockpit workflow mesh` 显示 delivery 状态
- [ ] 所有 184 BOS 服务 cockpit bos list 可见
- [ ] 每个命令 --help 有 MCP 工具映射信息

---

### Phase 2: Help 自动生成 + 文档同步 (P1, 2d)

> **目标**: help 命令自动从注册表生成，文档零手工

#### P2-T1: 改造 `cockpit help` 命令

**文件**: `projects/cockpit/src/cockpit/commands/status.py` (cmd_help 函数)

**改造方向**: 从静态硬编码改为动态生成

```python
def cmd_help(args: Namespace) -> int:
    """cockpit help — 动态生成的产品能力地图."""
    registry = load_capability_registry()  # 读 docs/generated/capability-registry.yaml

    # 按类别分组输出
    print("🧭 Cockpit 能力全景")
    print(f"   CLI 命令: {registry.total_cli_commands}")
    print(f"   MCP 工具: {registry.total_tools} (26 servers)")
    print(f"   BOS 服务: {registry.total_bos_services} (14 domains)")
    print()

    # 按场景分组 (研究/治理/系统/生活)
    for category in ["research", "governance", "system", "life"]:
        cmds = [c for c in registry.cli_commands if c.category == category]
        print(f"📂 {category}:")
        for cmd in cmds:
            mcp_info = f" ↔ MCP:{cmd.mcp_equivalent}" if cmd.mcp_equivalent else ""
            print(f"   cockpit {cmd.name:<20} {cmd.description}{mcp_info}")

    print()
    print("🔍 搜索: cockpit search <keyword>")
    print("📖 详情: cockpit <command> --help")
    print("🌐 Web:   cockpit dashboard")
```

#### P2-T2: 自动生成 CAPABILITY-MAP.md

**文件**: `bin/cockpit/gen-help-docs.py`

```python
def generate_capability_map(registry: dict) -> str:
    """从注册表生成 CAPABILITY-MAP.md."""
    lines = [
        "# Cockpit 能力地图",
        "",
        f"> 自动生成于 {registry['generated_at']} | 版本 {registry['version']}",
        f"> 源: capability-registry.yaml | 请勿手动编辑",
        "",
        f"## 概览",
        f"",
        f"| 通道 | 数量 |",
        f"|------|------|",
        f"| CLI 命令 | {registry['total_cli_commands']} |",
        f"| MCP 工具 | {registry['total_tools']} |",
        f"| BOS 服务 | {registry['total_bos_services']} |",
        f"| MCP 服务器 | {registry['total_servers']} |",
        "",
        "## CLI 命令清单",
        "",
        "| 命令 | 描述 | MCP 映射 | BOS 映射 |",
        "|------|------|----------|----------|",
    ]
    for cmd in registry["cli_commands"]:
        lines.append(f"| `{cmd['name']}` | {cmd['description']} | {cmd.get('mcp_equivalent', '-')} | {cmd.get('bos_equivalent', '-')} |")

    lines.extend([
        "",
        "## MCP 服务器清单",
        "",
        "| 服务器 | 层 | 工具数 | 传输 |",
        "|--------|-----|--------|------|",
    ])
    for srv in registry["mcp_servers"]:
        lines.append(f"| `{srv['id']}` | {srv['layer']} | {srv['tool_count']} | {srv['transport']} |")

    return "\n".join(lines)
```

#### P2-T3: 自动生成 docs/CLI-REFERENCE.md

> 新增用户-facing 文档: 每个命令的用法 + 示例 + MCP 等价物

#### P2 验收

- [ ] `cockpit help` 输出动态生成 (非硬编码)
- [ ] CAPABILITY-MAP.md 自动更新
- [ ] CLI-REFERENCE.md 包含全部 46 命令
- [ ] 文档中 MCP ↔ CLI ↔ BOS 交叉引用正确

---

### Phase 3: 治理规则同步 + CI 门禁 (P2, 2d)

> **目标**: SSOT 变更自动同步到所有生成文档，CI 检测漂移

#### P3-T1: 统一文档生成 Makefile

**文件**: `Makefile` (追加)

```makefile
# ── 能力注册表 + 文档自动生成 ──
sync-capability-registry:
	uv run python "bin/cockpit/gen-capability-registry.py"

sync-help-docs: sync-capability-registry
	uv run python "bin/cockpit/gen-help-docs.py"

sync-all-docs: sync-help-docs
	uv run python "bin/cockpit/gen-cli-reference.py"
	uv run python "bin/cockpit/gen-agent-gac-rules.py"
	uv run python "bin/cockpit/gen-agent-redlines.py"

check-docs-drift: sync-all-docs
	git diff --exit-code docs/generated/ || (echo "❌ 文档漂移! 运行 make sync-all-docs" && exit 1)
```

#### P3-T2: CI 门禁集成

**文件**: `.github/workflows/ci.yml` 或 CI 配置

```yaml
- name: Check documentation drift
  run: make check-docs-drift
```

#### P3-T3: 补齐 INDEX-TOOLS.md

**文件**: `docs/INDEX-TOOLS.md`

```markdown
## Cockpit CLI
- `cockpit research` — 深度研究 (20+ 子命令)
- `cockpit omo` — OMO 治理中枢 (19 MCP tools)
- `cockpit kairon` — 知识引擎 monorepo (16 packages, 44 KOS tools)
- ... 全部 46 命令

## MCP Servers
- `omo` — 19 tools (任务/锁/债务/CARDS)
- `kos` — 44 tools (知识检索/索引/排序)
- `l4-kernel` — 51 tools (域管理/KEMS/健康)
- ... 全部 26 服务器
```

#### P3 验收

- [ ] `make sync-all-docs` 生成全部文档
- [ ] `make check-docs-drift` 检测漂移
- [ ] CI 门禁包含 docs-drift 检查
- [ ] INDEX-TOOLS.md 包含 cockpit CLI + MCP 全量索引

---

### Phase 4: Cockpit-UI 系统全景视图 (P2, 3d)

> **目标**: Web 端可见全生态能力

#### P4-T1: 新增 SystemMap 视图

**文件**: `projects/cockpit-ui/src/views/SystemMap.tsx` (已有 api_system_map 后端)

> 后端 `api_system_map.py` (51.7KB) + `api_system_map_catalog.py` (59.8KB) 已存在
> 只需确保前端视图完整可达

#### P4-T2: 新增 CapabilityExplorer 视图

**文件**: `projects/cockpit-ui/src/views/CapabilityExplorer.tsx`

```tsx
// 展示 394 个 MCP 工具的分类浏览 + 搜索
// 按 server 分组，每个工具显示: 名称/描述/所属层/传输方式
// 支持按层(L0-L4) / 按 server / 按关键词过滤
```

#### P4-T3: 修复 13 个不可达组件

> 将 cockpit-ui 中已构建但导航不可达的组件接入路由

#### P4 验收

- [ ] `/system-map` 显示全生态项目 + 工具数
- [ ] `/capabilities` 可浏览全部 394 MCP 工具
- [ ] 13 个不可达组件全部可导航
- [ ] 前端构建成功

---

## 4. 文件变更总览

### 4.1 新建文件 (12)

| 文件 | 阶段 | 说明 |
|------|------|------|
| `docs/generated/capability-registry.yaml` | P0 | 能力注册表 SSOT |
| `bin/cockpit/gen-capability-registry.py` | P0 | 注册表生成器 |
| `bin/cockpit/gen-help-docs.py` | P0 | CAPABILITY-MAP.md 生成器 |
| `bin/cockpit/gen-cli-reference.md` | P0 | CLI 参考文档生成器 |
| `projects/gbrain/src/mcp_server.ts` | P0 | gbrain MCP server |
| `projects/cockpit/src/cockpit/commands/knowledge.py` | P1 | KOS 知识治理命令 |
| `projects/cockpit/src/cockpit/commands/kems.py` | P1 | KEMS 域管理命令 |
| `projects/cockpit/src/cockpit/commands/workflow_mesh.py` | P1 | workflow-mesh 可视化 |
| `projects/cockpit/src/cockpit/commands/c2g.py` | P1 | C2G 全局状态 |
| `projects/cockpit/src/cockpit/commands/toolbox.py` | P1 | 外部工具入口 |
| `projects/cockpit-ui/src/views/CapabilityExplorer.tsx` | P4 | 能力浏览器前端 |
| `docs/CLI-REFERENCE.md` | P2 | 用户-facing CLI 参考 |

### 4.2 修改文件 (15)

| 文件 | 阶段 | 改动 |
|------|------|------|
| `projects/cockpit/src/cockpit/cli.py` | P0 | 修 3 个 dispatch 异常 + 注册新命令 |
| `projects/cockpit/src/cockpit/commands/status.py` | P2 | cmd_help 改为动态生成 |
| `projects/cockpit/src/cockpit/commands/bos.py` | P1 | 扩展 capability 域 |
| `projects/cockpit/src/cockpit/commands/gbrain.py` | P1 | 扩展 query/status |
| `projects/agora/etc/bos-services.yaml` | P0 | 清理 10 个废弃服务 |
| `projects/cockpit/CAPABILITY-MAP.md` | P2 | 自动生成的内容覆盖 |
| `docs/INDEX-TOOLS.md` | P3 | 补 cockpit CLI + MCP 索引 |
| `Makefile` | P3 | 追加 sync-* 和 check-docs-drift |
| `projects/cockpit-ui/src/routes.tsx` | P4 | 注册新视图路由 |
| `projects/cockpit-ui/src/App.tsx` | P4 | 导航补全 13 个不可达组件 |
| `.omo/_truth/registry/governance-checks.yaml` | P3 | 如需要则更新 (由生成器驱动) |
| `projects/cockpit/src/cockpit/commands/omo.py` | P0 | 确认 debt 子命令路由 |
| `projects/cockpit/src/cockpit/commands/cards.py` | P0 | 统一为 l4bridge |
| `projects/cockpit/src/cockpit/commands/agent_runtime_cli.py` | P0 | 补 agent 独立 dispatch |
| `projects/cockpit/README.md` | P3 | 更新文档链接 |

---

## 5. 依赖关系

```
P0-T1 (修 dispatch) ──→ P1-T2 (补 --help)
P0-T2 (注册表生成器) ──→ P2-T1 (动态 help) ──→ P2-T2 (CAPABILITY-MAP)
P0-T2 (注册表生成器) ──→ P3-T1 (Makefile sync)
P0-T4 (gbrain MCP)   ──→ P1-T1 (gbrain 命令)
P0-T5 (metaos 替代)  ──→ P1-T1 (metaos 命令)
P1-T1 (新命令)       ──→ P1-T2 (--help 补全)
P1-T3 (BOS 全注册)   ──→ P4-T2 (CapabilityExplorer)
P2-T2 (CAPABILITY)   ──→ P3-T2 (CI 门禁)
P3-T1 (Makefile)     ──→ P3-T2 (CI 门禁)
```

**关键路径**: P0-T2 → P2-T1 → P3-T1 → P3-T2 (注册表 → 帮助 → 文档 → 门禁)

---

## 6. 验证方案

### 6.1 每阶段验收

| 阶段 | 验证命令 | 期望 |
|------|----------|------|
| P0 | `cockpit agent bootstrap` | 正常执行不报错 |
| P0 | `cockpit debt list` | 列出债务 |
| P0 | `uv run python bin/cockpit/gen-capability-registry.py` | 输出 YAML, total_tools ≥ 394 |
| P1 | `cockpit knowledge search "test"` | 返回 KOS 结果 |
| P1 | `cockpit kems domains` | 显示 28 域 |
| P1 | `cockpit bos list \| wc -l` | ≥ 184 |
| P2 | `cockpit help` | 输出动态生成 (非静态) |
| P2 | `make sync-all-docs` | 全部文档生成无报错 |
| P3 | `make check-docs-drift` | CI 通过 (git diff 为空) |
| P4 | `cd projects/cockpit-ui && bun run build` | 构建成功 |
| P4 | 浏览器访问 /capabilities | 显示 394 工具 |

### 6.2 全局验证

```bash
# 1. 注册表完整性
uv run python "bin/cockpit/gen-capability-registry.py"
# 期望: total_tools ≥ 394, total_servers = 26, total_bos = 184

# 2. 文档无漂移
make check-docs-drift
# 期望: git diff 为空

# 3. CLI 全量 --help
for cmd in $(cockpit --help | grep -o 'cockpit [a-z-]+' | awk '{print $2}'); do
  cockpit $cmd --help > /dev/null || echo "FAIL: $cmd"
done
# 期望: 无 FAIL

# 4. MCP 全量可发现
cockpit mcp --list | grep "Tool count"
# 期望: 显示全部工具数

# 5. BOS 全量可解析
cockpit bos list | wc -l
# 期望: ≥ 184

# 6. 前端构建
cd projects/cockpit-ui && bun run build
# 期望: 0 errors

# 7. 测试
cd projects/cockpit && uv run pytest tests/ -q
# 期望: ≥ 950 pass (当前 935)
```

---

## 7. 风险与缓解

| 风险 | 概率 | 影响 | 缓解 |
|------|------|------|------|
| gbrain MCP 需要 Bun 运行时 | 中 | 中 | 用 TS 写，复用 gbrain 现有 CLI 代码 |
| 注册表生成器解析 MCP 工具遗漏 | 中 | 中 | 多策略: AST + 正则 + 手动补底 |
| BOS 184 服务部分实际不可用 | 高 | 低 | 标记 status: unavailable，不删除 |
| cockpit-ui 构建工具链问题 | 中 | 中 | 先验证 `bun run build` 能跑通 |
| 文档自动生成格式不完美 | 高 | 低 | 先生成骨架，后续迭代优化 |
| metaos MCP 替代方案不明确 | 中 | 低 | 通过 BOS proxy 暴露，不重写 |

---

## 8. 时间线 (3 周)

```
Week 1 (08-02 ~ 08-09): P0 结构修复 + 基础设施
├── P0-T1: 修 3 个 dispatch 异常 (0.5d)
├── P0-T2: 能力注册表生成器 (1d)
├── P0-T3: 清理 BOS 废弃服务 (0.5d)
├── P0-T4: gbrain MCP server (1d)
├── P0-T5: metaos MCP 确认 (0.5d)
└── P0 验收 (0.5d)

Week 2 (08-09 ~ 08-16): P1 全量覆盖 + P2 文档同步
├── P1-T1: 新增 6 组子命令 (1.5d)
├── P1-T2: --help 补全 (0.5d)
├── P1-T3: BOS 全量注册 (0.5d)
├── P2-T1: cockpit help 动态化 (0.5d)
├── P2-T2: CAPABILITY-MAP 自动生成 (0.5d)
├── P2-T3: CLI-REFERENCE 生成 (0.5d)
└── P1+P2 验收 (0.5d)

Week 3 (08-16 ~ 08-23): P3 治理同步 + P4 UI
├── P3-T1: Makefile sync 目标 (0.5d)
├── P3-T2: CI 门禁集成 (0.5d)
├── P3-T3: INDEX-TOOLS 补全 (0.5d)
├── P4-T1: SystemMap 视图完善 (1d)
├── P4-T2: CapabilityExplorer 视图 (1d)
├── P4-T3: 13 不可达组件修复 (0.5d)
└── 全量验证 + 文档更新 (0.5d)
```

---

## 9. 成功标准 (Definition of Done)

- [ ] `gen-capability-registry.py` 输出 total_tools ≥ 394, total_servers = 26
- [ ] `cockpit help` 动态生成，显示全量能力统计
- [ ] `cockpit knowledge search/status/stats` 可用
- [ ] `cockpit kems domains/status` 可用
- [ ] `cockpit workflow mesh/delivery` 可用
- [ ] `cockpit agent bootstrap` 不再错链
- [ ] `cockpit debt list/score` 正常分发
- [ ] gbrain MCP server 独立可启动
- [ ] `make sync-all-docs` 生成全部文档
- [ ] `make check-docs-drift` CI 通过
- [ ] cockpit-ui 构建成功 + CapabilityExplorer 可浏览
- [ ] 全部 184 BOS 服务 cockpit bos list 可见
- [ ] cockpit 测试 ≥ 950 pass
- [ ] SSOT lint 通过
- [ ] GaC local gate 通过

---

## 10. 关键文件路径索引

```
# 新增
docs/generated/capability-registry.yaml          # 能力注册表 SSOT
bin/cockpit/gen-capability-registry.py           # 注册表生成器
bin/cockpit/gen-help-docs.py                     # 文档生成器
projects/gbrain/src/mcp_server.ts                # gbrain MCP
projects/cockpit/src/cockpit/commands/knowledge.py  # KOS 治理
projects/cockpit/src/cockpit/commands/kems.py       # KEMS 治理
projects/cockpit/src/cockpit/commands/workflow_mesh.py  # mesh 可视化
projects/cockpit/src/cockpit/commands/c2g.py         # C2G 状态
projects/cockpit/src/cockpit/commands/toolbox.py     # 外部工具
projects/cockpit-ui/src/views/CapabilityExplorer.tsx  # 能力浏览器

# 修改
projects/cockpit/src/cockpit/cli.py              # dispatch 修复 + 新命令注册
projects/cockpit/src/cockpit/commands/status.py  # help 动态化
projects/cockpit/src/cockpit/commands/bos.py     # BOS 扩展
projects/cockpit/src/cockpit/commands/gbrain.py  # gbrain 扩展
projects/agora/etc/bos-services.yaml             # 清理废弃
Makefile                                         # sync 目标
docs/INDEX-TOOLS.md                             # 补全索引
projects/cockpit/CAPABILITY-MAP.md              # 自动覆盖
projects/cockpit/README.md                       # 链接更新
projects/cockpit-ui/src/routes.tsx               # 新路由
projects/cockpit-ui/src/App.tsx                  # 导航补全
```

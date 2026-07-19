# G-DEL.4 角色记忆共享 · 调用链

> 口径：`single_repo_gbrain`（非多机）。与 G-DEL.2a handoff 载荷对齐。

## 调用链

```
agent-A (writer)
    │  cockpit MCP shared_context_write  ──或──  shared-context-cli write
    ▼
.omo/_delivery/shared-context/{scope}/{key}.json   (atomic file store)
    │  cockpit MCP shared_context_read  ──或──  shared-context-cli read
    ▼
agent-B (reader)  — 可见性：readers 空=全员；非空=白名单
    │  shared-context-cli export-kos --db kos/kos-index.sqlite
    ▼
KOS documents (canonical_path=gbrain://shared-context/...)
    │  shared-context-cli retrieve-kos --query collab.handoff
    ▼
检索命中 → 后续 agent / cockpit 可引用 key
```

gbrain 侧同源实现：`projects/gbrain/src/core/agent-shared-context.ts`（同可见性规则）。  
cockpit MCP 工具：`shared_context_write` / `shared_context_read` / `shared_context_list`
（实现：`projects/cockpit/.../scripts/cockpit_mcp.py`，底层复用 `bin/delivery/shared_context_store.py`）。

## CLI

```bash
python3 bin/delivery/shared-context-cli.py write \
  --writer agent-A --key collab.handoff \
  --value "G-DEL.2a contract ready" --scope bet-b7da --tag handoff

python3 bin/delivery/shared-context-cli.py read \
  --reader agent-B --key collab.handoff --scope bet-b7da

python3 bin/delivery/shared-context-cli.py export-kos \
  --scope bet-b7da --db kos/kos-index.sqlite

python3 bin/delivery/shared-context-cli.py retrieve-kos \
  --query collab.handoff --db kos/kos-index.sqlite
```

## MCP（cockpit）

| Tool | 作用 |
|------|------|
| `shared_context_write` | writer/key/value + optional scope/readers/tags |
| `shared_context_read` | reader 可见性过滤读 |
| `shared_context_list` | 列出 reader 在 scope 下可见条目 |

## 测量

```bash
python3 bin/delivery/role_memory.py          # 或 measure_all → g_del_4
python3 -m pytest tests/test_shared_context.py tests/test_delivery_g_del.py -q
# cockpit
cd projects/cockpit && python3 -m pytest src/cockpit/tests/test_scripts_l4_bridge.py::TestSharedContextMcp -q
```

`meets_gate=true` 当：进程内可见性 + **跨进程 CLI handoff** + KOS seed/retrieve 均过。  
MCP 为 agent 入口增强，**不改变** physical caliber（仍非多机）。

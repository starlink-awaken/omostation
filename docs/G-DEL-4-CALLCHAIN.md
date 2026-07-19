# G-DEL.4 角色记忆共享 · 调用链

> 口径：`single_repo_gbrain`（非多机）。与 G-DEL.2a handoff 载荷对齐。

## 调用链

```
agent-A (writer)
    │  shared-context-cli write --writer agent-A --key collab.handoff --value ...
    ▼
.omo/_delivery/shared-context/{scope}/{key}.json   (atomic file store)
    │  shared-context-cli read --reader agent-B
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

## 测量

```bash
python3 bin/delivery/role_memory.py          # 或 measure_all → g_del_4
python3 -m pytest tests/test_shared_context.py tests/test_delivery_g_del.py -q
```

`meets_gate=true` 当：进程内可见性 + **跨进程 CLI handoff** + KOS seed/retrieve 均过。

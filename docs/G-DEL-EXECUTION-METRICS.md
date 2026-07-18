---
title: G-DEL 执行面门禁 · 实测说明
status: active
type: metrics
related: [BET-7e074, BET-664e3, BET-3e602, BET-8c7c, ADR-0221]
---

# G-DEL 执行面门禁

| Goal | KPI | Harness |
|------|-----|---------|
| G-DEL.1 | schedule success > 99% | `python3 bin/delivery/measure_all.py` → `g_del_1` |
| G-DEL.2b | collab complete > 95% | `g_del_2b` |
| G-DEL.3 | sync p99 < 100ms | `g_del_3` |
| G-DEL.5b | accuracy > 80% + kill-switch | `g_del_5b` |

**环境声明**: 多机口径为 **in-process multi-node simulation**（4 逻辑节点），非物理多主机。
单机环境可复现；不得捏造跨机网络数字。

```bash
python3 -m pytest tests/test_delivery_g_del.py -q
python3 bin/delivery/measure_all.py
```

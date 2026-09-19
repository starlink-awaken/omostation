---
title: T10-48 resident ledger test and replay evidence
date: 2026-08-29
status: verified
type: ephemeral
---

# T10-48 测试与回放证据

本报告是根仓可解析的持久证据。`projects/omo` 是 gitlink，不能作为根仓
completion matrix 的文件 receipt；实际测试仍在 OMO 子仓执行，命令与结果在此固化。

## Verification command

```text
uv run --with pyyaml --with pytest python -m pytest projects/omo/tests/unit/test_resident_status.py -q
```

## Result

本轮 focused test 结果：9 passed，退出码 0。

该 focused suite 覆盖 transient SQLite contention 的 bounded retry、持久锁的
truthful degraded status、broker close，以及正常 resident ledger read-status
路径；重复执行同一命令作为 T10-48 的 replay evidence。

## Scope boundary

本证据只证明测试/回放命令在当前提交树中的可复现结果，不把测试通过等同于
主线集成、宿主机运行态或用户价值验收。宿主机无数据库、WAL、进程信号、
launchd 或服务重启操作。

# G-DEL.2b / 5b 运维入口

> 口径：process-local（非多机）。  
> 2b 实现 G-DEL.2a 握手；5b 尊重 ADR-0221 fail-closed 默认。

## G-DEL.2b · 协作

```bash
# 跑一轮完整握手（assign → claim → handoff → verify → complete）
python3 bin/delivery/collab_cli.py run-handshake

# 查看历史
python3 bin/delivery/collab_cli.py history --task-ref task-xxxxxxxx

# 将握手结果写入 G-DEL.4 shared-context（下一 agent 可读）
python3 bin/delivery/collab_cli.py handoff-link \
  --task-ref task-xxxxxxxx --writer orch-1 --scope bet-b7da
```

历史落盘：`.omo/_delivery/collab/{task_ref}.jsonl`

## G-DEL.5b · 涌现 + kill-switch

| 环境变量 | 默认 | 含义 |
|----------|------|------|
| `ECOS_EMERGENCE_ENABLED` | `0` | 总开关；0=禁止 detect |
| `ECOS_EMERGENCE_WRITES` | `0` | 写副作用；0=禁止写 |

```bash
python3 bin/delivery/emergence_cli.py status
python3 bin/delivery/emergence_cli.py detect --text "swarm consensus multi-agent vote" --force-enable
python3 bin/delivery/emergence_cli.py kill          # 会话级 kill 文件
python3 bin/delivery/emergence_cli.py clear-kill
python3 bin/delivery/emergence_cli.py measure       # 准确率 + kill 有效性
```

会话 kill 文件：`.omo/_delivery/emergence/session.kill`（多进程共享）。

## 测量

```bash
python3 bin/delivery/measure_all.py   # g_del_2b / g_del_5b
python3 -m pytest tests/test_delivery_g_del.py tests/test_collab_emergence_cli.py -q
```

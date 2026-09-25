---
id: BET-Y2Q3-T9-02
date: 2026-09-25
type: retro
status: draft
---

# BET-Y2Q3-T9-02 Receipt 持久化 + Dashboard 居民状态

## 交付

| 项 | 证据 |
|----|------|
| receipt.py append-only 审计 | `.omo/_delivery/resident-orchestrator/receipts.jsonl`；daemon._route() 挂钩 attempted/ok/blocked/error/skipped |
| daemon._route() 改造 | attempted→ok→error 三态 receipt; blocked 也记录 |
| /api/v1/resident | daemon 活性(进程名兜底) + heartbeat 统计 + 角色活性(JSONL source) + receipt + log tail |
| 前端居民活性条 | swarm 板块 `#zx-resident-bar`: 5 角色圆点 + daemon PID + 最近 5 条 receipt |

## 教训

- live_server.py 路径解析: `Path(__file__)` 在模块导入时 parents 计数与直接运行不同; 且 `/Users/xiamingxing/.omo` 存在导致 `.omo` 锚点误匹配. 改用 `.omo/_truth` 双锚点 + 进程名兜底 pgrep
- node --check 单引号拼接长 HTML 时易触发 "Invalid regex" 误报; 改用 forEach + var 拼接更稳
- watermark 仅 byte_offset 无 ts; 角色活跃度须从 heartbeat/monitor JSONL source 字段反推

## 验证

- MAIN SCRIPT node --check OK (203KB)
- daemon PID 43241 运行; /api/v1/resident HTTP 200
- receipts 每个事件 attempted+ok 双写(可接受); 实时增长确认
- dashboard/swarm 渲染居民条

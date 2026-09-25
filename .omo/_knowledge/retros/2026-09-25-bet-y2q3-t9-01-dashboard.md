---
schema: md/v1
status: draft
lifecycle: history
owner: governance-team
last-reviewed: 2026-09-25
type: retro
id: BET-Y2Q3-T9-01
date: 2026-09-25
---


# BET-Y2Q3-T9-01 Retro — 织星驾驶舱 P2 体验迭代、漂移可观测与真实算力副驾

## 交付

| 项 | 证据 |
|----|------|
| drift 检测结构化报告 | `bin/gac/zhixing-host-sync.py check` 每次写 `host-drift-report.json`（原子写）；exit 语义不变 |
| runbook 漂移判读 | `.omo/_knowledge/ops/zhixing-dashboard-runbook.md` |
| `GET /api/v1/compute/live` | omlxc 实时 daemon + 26 模型 loaded/available/ready；失败降级快照 |
| `POST /api/v1/compute/infer` | 本机-only + 6rpm/IP 限流 + omlxc 白名单 + AetherForge Keychain 密钥；实测 gemma-4-e4b → 4s |
| 前端 P2-5 降级横幅 | `zxRenderSourceBanner` 读 source_states |
| 前端 P2-7 搜索历史 | localStorage 8 条 |
| 前端 P2-10 差异化 | know/learnings 副标题 + 互链 |
| 前端 P2-3 暗色对比度 | tooltip 暗色模式提亮 + 边框 |
| 知行副驾升级 | 双标签页（算力状态实时 + 本地推理控制台），30s 自动刷新 |
| CLAUDE.md 运维指针 | runbook / host-sync / 端点 |
| 台账 + spec | `BET-Y2Q3-T9-01` in 3y-bet-ledger.yaml |

## 教训

- launchd 服务重启后旧 .pyc 可能残留导致运行旧代码；重启后必须验证端点行为而非只看进程
- 子代理 5h 配额耗尽时，主代理直接接手可并行任务（前端/后端/脚本）是可行降级
- AetherForge 网关密钥走 Keychain（`security find-generic-password -s aetherforge-gateway`），禁止硬编码

## 验证

- `python3 -m py_compile live_server.py` ✅
- 内联脚本 `node --check` 全 3 block ✅
- dashboard HTTP 200；live 返回 real data；infer 白名单+限流+真实推理 ✅
- drift check exit 0（capture 后）✅

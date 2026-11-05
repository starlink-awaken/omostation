---
schema_version: specification/v1
spec_version: 1.0.0
title: BET-Y2Q4-T10-285 specification
bet_id: BET-Y2Q4-T10-285
status: accepted
lifecycle: contract
owner: governance-team
last-reviewed: 2026-11-04
---


# Spec: agora daemon HTTP /health + 7433 端口注册 + 健康扫描接线

## 0. 背景与前提修正

Multica SIRI-51 的原始前提（"agora-gateway 目前只有 UDP 42024，没有 HTTP /health"）
经实测已过时：

- 全 Workspace 代码库中不存在 UDP 42024；该数字只出现在 2026-07-16 战略分析的
  服务表快照里。agora 真实的 UDP 面是 swarm discovery/heartbeat，
  `AGORA_SWARM_UDP_PORT` = **7455**（protocols/port-registry.yaml）。
- 独立 agora-gateway 进程 2026-09-08 官方废弃（agora commit d128c5f，
  "P2-5 SSE/gateway 双进程统一"）：SSE 进程经 `AGORA_GATEWAY_OWNER=1` 接管
  gateway 职责，7422 无监听是设计而非故障（~/runtime/matrix.yaml RETIRED 注记）。
- 本机唯一常驻 agora 服务是 `com.agora.daemon`（A2A bus，FastAPI，
  src/agora/daemon.py），且因安装根 `~/.local/opt/omostation` 的 agora 检出
  缺 7c8269f（types.py → agent_types.py，PR 125）而 crash-loop——
  旧 types.py 遮蔽 stdlib types，`import asyncio` 即 ImportError。

## 1. 目标

给 agora 的常驻服务面补一个真实可 curl 的 HTTP /health，并让既有健康扫描
机制（cron-service → MatrixScheduler → ~/runtime/matrix.yaml health_url）
消费它，替代"只能查 PID"的盲区。

## 2. 变更内容

1. `src/agora/daemon.py`（agora 子仓）：
   - 新增 `GET /health` → `{"status": "ok", "uptime_s": <int>, "udp_port": <int>}`。
     `udp_port` 读 `AGORA_SWARM_UDP_PORT`（默认 7455，与 port-registry 一致），
     只回报配置，不启动任何 UDP 逻辑。
   - HTTP 监听端口改读 `AGORA_DAEMON_HTTP_PORT`（默认 **7433**）。
     旧默认 7432 与 ecos-event-listener 的注册冲突，不再占用。
2. `protocols/port-registry.yaml`（主仓）：注册 `7433 / AGORA_DAEMON_HTTP_PORT /
   agora-daemon-http (http, active)`。
3. `~/runtime/matrix.yaml`（机器运行时状态，非仓内文件）：新增 agora-daemon
   条目（type daemon，launchd_label com.agora.daemon，port 7433，
   health_url http://127.0.0.1:7433/health）。
4. 安装根部署：`~/.local/opt/omostation/projects/agora` 同步到含 7c8269f +
   本变更的提交，launchctl 重启后 daemon 恢复常驻。

## 3. 非目标

- 不复活独立 agora-gateway 进程（P2-5 架构决策不变）。
- 不改任何 UDP/swarm 逻辑。
- 不改 cron-service / MatrixScheduler 代码（health_url 是既有机制）。
- 不 bump 主仓 submodule 指针；agora 变更走子仓 PR，人工审批后合并。

## 4. 验收

- `curl -fsS http://127.0.0.1:7433/health` → 200 +
  `{"status":"ok","uptime_s":N,"udp_port":7455}`。
- `python3 bin/ssot/matrix-consistency-lint.py`：agora-daemon 条目 0 ERROR。
- 健康扫描落盘 `~/runtime/system_health.yaml`（或 .omo/state）中 agora-daemon
  healthy 且带 health_check。
- agora 子仓 `uv run pytest tests/unit/test_daemon_health.py -q` 通过，
  `uv run ruff check src/` 无新违规。
- `launchctl list | grep com.agora.daemon` 非 crash-loop（exit 0 常驻）。

## 5. 风险与回退

- 端口迁移 7432→7433：7432 当前无监听者（daemon 崩循环、ecos listener 未部署），
  无存量消费者受影响；回退 = revert 提交 + kickstart。
- 安装根同步：仅前移 agora 子仓检出，不改主仓安装根结构；回退 = checkout 原
  commit（4ae1a58）。

## 6. 反指标

- daemon 进程存在时长（uptime 本身）不作为成功度量——launchd KeepAlive 会把
  crash-loop 也刷成"长期存在"。
- 不以"门禁全绿"为成功度量：预存 9 个 lint 问题是存量，与本 bet 无关，不在
  本 bet 修复范围。
- 不以新增代码行数为度量：/health 是三键只读端点，膨胀即违背 KISS。

## 7. Decision Log (grill-me)

| # | 分叉 | 裁定 | 理由 |
|---|------|------|------|
| 1 | issue 原文要求 `udp_port: 42024` 硬编码进 JSON | 不采纳；回报真实配置 7455（AGORA_SWARM_UDP_PORT） | 42024 全仓不存在（仅 2026-07-16 快照），硬编码即制造新的 SSOT 漂移；SIRI-51 的本质诉求是"健康检查可见"，不是该数字 |
| 2 | /health 加在独立 gateway 还是 daemon | daemon (com.agora.daemon) | 独立 gateway 已废弃（P2-5）；daemon 是本机唯一常驻 agora launchd 服务，也是当前实际崩坏的面 |
| 3 | 沿用 7432 还是新端口 | 新注册 7433 + AGORA_DAEMON_HTTP_PORT | 7432 已注册给 ecos-event-listener；占他人端口违反 port-registry SSOT 契约 |
| 4 | 健康扫描怎么接 | matrix.yaml health_url 条目，零 runtime 代码改动 | MatrixScheduler 已原生支持 HTTP health_url 探活；改 runtime 代码扩大写面，违背最小变更 |
| 5 | 安装根怎么修 | 子仓检出前移到含修复的提交 + kickstart | 崩因是安装根陈旧（缺 7c8269f），不是代码缺失；改 plist/复制文件都是绕开既有部署形态 |

---
schema_version: specification/v1
spec_version: 1.0.0
title: A5 AetherForge 门面常驻化恢复 — launchd 服务缺失修复
bet_id: BET-Y1Q4-T10-153
status: accepted
lifecycle: contract
owner: governance-team
last-reviewed: 2026-09-11
---

# A5 AetherForge 门面常驻化恢复

## 1. Problem

`com.aetherforge.gateway` 的 launchd plist（`~/Library/LaunchAgents/`，不在本仓库内）
已缺失，`.omo/_truth/registry/services.yaml` 里对应条目标注
`enabled: false` / `config_source: ... — 已移除`。结果：所有理应经
`http://127.0.0.1:9290/v1` 这个唯一认证门面接入本地算力的 OpenAI 兼容客户端
（OpenCode、Pi、Kilo Code 等）实际连不上——不是配置或算力问题，是网关服务
根本没在跑。

守护脚本 `~/.local/bin/aetherforge-gw-guard`、项目 venv、Keychain 密钥
（`aetherforge-gateway`）均完好，未受影响；`ENG-OMLX-LOCAL`/
`ENG-LMSTUDIO-MACBOOKPRO` 等 compute_engine SSOT 引用路径也都正确。

## 2. Goal

重建 launchd plist，把 `services.yaml` 里的 `aetherforge.gateway` 条目改回
`enabled: true`，验证服务常驻运行、health 检查通过、真实推理请求可用。

## 3. Non-goals

- 不修改 `aetherforge-gw-guard` 脚本本身或网关代码逻辑
- 不新增 Anthropic Messages / Google generateContent 协议转译层（后续独立评估）
- 不处理 omlxc 侧 inventory_drop 告警（另一个已知、独立的问题）

## 4. Change

1. 新建 `~/Library/LaunchAgents/com.aetherforge.gateway.plist`（Label
   `com.aetherforge.gateway`，`ProgramArguments` 指向
   `/bin/bash ~/.local/bin/aetherforge-gw-guard`，`KeepAlive`/`RunAtLoad` true，
   日志落 `~/Library/Logs/aetherforge-gateway.log`），与 `services.yaml`
   里记录的 `config_source`/`program`/`outputs` 字段一致。
2. `.omo/_truth/registry/services.yaml`：`aetherforge.gateway.enabled`
   `false → true`，`config_source` 去掉"已移除"标注，`notes` 追加
   2026-09-11 修复记录。

## 5. Acceptance

- [x] `plutil -lint` 通过
- [x] `launchctl load` 后 `launchctl list | grep aetherforge.gateway` 显示真实 PID
- [x] `curl http://localhost:9290/health` 返回 200
- [x] 带 Keychain 密钥的 `curl .../v1/models` 返回 200，能看到多引擎模型列表
- [x] 真实 `POST /v1/chat/completions` 请求（`model: coding`）返回正确响应

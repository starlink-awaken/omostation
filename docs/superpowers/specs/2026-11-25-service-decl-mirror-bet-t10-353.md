---
schema: md/v1
schema_version: specification/v1
status: accepted
lifecycle: spec
owner: governance-team
last-reviewed: 2026-11-25
accepted: "2026-11-25 Principal 会话原话「go」— 8 服务声明镜像回填正式化"
bet_id: BET-Y2Q4-T10-353
spec_version: 1.0.0
---

# BET-Y2Q4-T10-353 spec

## 背景

T10-349 修好 `gen-service-configs.py --check` 假红 (plistlib 语义等价判定) 后,
真漂移集体现形: 本机安装平面注入了 `EnvironmentVariables.PATH` 与 (resident 6 服务)
`StandardOutPath`/`StandardErrorPath`, 而 services.yaml 声明侧未跟上。

- 2026-11-25 上午实测: agent-brief-materialize、resident.{decision,execute,
  event-ingest,signals,inbox,promote}、zhixing-projection-republisher 共 8 个
  launchd 服务 plist 与声明不一致 (7 + 1 前者)。
- 本机 plist 注入值 (8 服务一致):
  `PATH=/Users/xiamingxing/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin`
- resident 6 服务日志落盘: `~/.local/log/omostation/<label>.log` (stdout=stderr 同文件)。
- plist mtime 10:28/10:53 (2026-11-25) —— 另一安装平面动作重写, 与声明生成器不同源。

## 变更 (write_surfaces)

单一文件 `.omo/_truth/registry/services.yaml`, 纯增量 34 行:

1. 8 个服务 environment 块回填 `PATH` (镜像本机实际值)。
2. resident 6 服务补 `outputs.stdout`/`outputs.stderr` (镜像本机 plist 落盘路径)。

## 验收 (done_when / verify)

- `uv run --with pyyaml python bin/mof/gen-service-configs.py --check`
  → `0 drift (78 launchd services)`。
- `make gac-local-gate` 中 `service-config-drift` 项 PASS。

## 非目标 (non_goals)

- 不收编安装器 PATH 注入源头 (注入方与声明生成器不同源; 重装可能再漂) —— 留债
  登记后续 BET, 由安装平面 owner 决定同源策略。
- 不改 `gen-service-configs.py` 渲染逻辑 (T349 已收口)。
- 不动 orchestrator/sediment/monitor/heartbeat 等无漂移服务。

## 风险与回滚

- L1: 纯声明回填, 无运行时写面; 回滚 = revert 单提交。
- 若后续安装平面再重写 plist 且注入值变化, drift 会如实再现 (语义对比的设计意图)。

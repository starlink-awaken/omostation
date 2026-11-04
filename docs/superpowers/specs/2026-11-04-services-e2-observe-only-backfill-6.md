---
schema_version: specification/v1
spec_version: 1.0.0
title: ADR-0456 B3 批次 6 — 1 条已装未声明 label observe-only 回填 (E2 复零)
bet_id: BET-Y2Q4-T10-284
status: accepted
lifecycle: contract
last-reviewed: 2026-11-04
---

# ADR-0456 B3 批次 6 — `com.user.omlx-smart-gateway` observe-only 回填

## 0. 触发与基线

plan `nimble-bay-asp` 的 B4b 行写着逐批验收判据「每批切完 `--reality-check` E2 仍为 0」，
中止判据「任一批后 E2 ≠ 0 即停」。批次 1 之后复测 E2 = 1，B4b 批次 2 因此被自己的判据按住。

实测基线（隔离检出 `04b1a669c` = 当时 `origin/main`，只读运行
`python3 bin/mof/gen-service-configs.py --reality-check --json`）：

| 字段 | 值 |
|---|---|
| `ok` | False |
| `e1_drift` / `e3_lint_debt` | 0 / 0 |
| `e2_undeclared` | **1** = `['com.user.omlx-smart-gateway']` |
| `e4_prefix_ok` | False（未分区 22 条） |
| `e5_enabled_missing` / `e5_disabled_residual` | 0 / 0 |
| `installed_total` | 87 |
| `owned_installed` / `owned_declared` | **51 / 50** |
| `registry_declared_total` | 78 |
| `external` / `unclassified` | 8 / 0 |

`--validate --json` ok=true violation_count=0；`--check` rc=0。等式 `owned_declared ==
owned_installed` 差 1 —— 集合相等是 B3 的完成判据本体。

## 1. 现场取证（这条 label 是什么）

| 面 | 实测 |
|---|---|
| 本机 plist | `~/Library/LaunchAgents/com.user.omlx-smart-gateway.plist`，mtime 2026-11-04 11:36 本地 |
| `launchctl print gui/501/com.user.omlx-smart-gateway` | `state = running`，`type = LaunchAgent`，`active count = 1` |
| ProgramArguments | `/usr/bin/python3 /Users/xiamingxing/.local/bin/omlx-smart-gateway.py` |
| KeepAlive / RunAtLoad | true / true |
| 监听 | `lsof` 实测 `TCP 127.0.0.1:18080 (LISTEN)` |
| 探针 | `GET http://localhost:18080/gateway/status` → HTTP 200（脚本内无 `/health` 路由，`do_GET` 只特判 `/gateway/status`，其余透传上游） |
| 仓内出处 | `rg -l "omlx-smart-gateway"` 全仓 **0 命中**（含台账、spec、bin/ops/launchd 镜像）；`git log --all -S` 亦 0 —— 它不是本仓任何交付的产物 |
| 用途 | 双 Mac Studio 的透明最低延迟网关，转发到 LAN/Tailscale 上游 |

结论：这是 principal 手工装到本机的**异主个人工具**，与本仓代码无隶属关系；它的出现不是
B4b 改道造成的孤儿，而是一次机器侧新增。判据是数字，所以「即停」照样生效 —— 停的是批次 2，
不是对本条的处置。

## 2. 机制选择：为什么是 observe-only 服务条目

E2 的构成（`bin/mof/gen-service-configs.py:731`）：
`e2_gap = set(buckets["workspace"]) - declared`，而 `buckets` 只由**已装** plist 构成。
`classify_label()`（`:403`）先查 `workspace_prefixes`，命中即 `workspace`，`exempt_labels`
只有在未命中时才被读。本仓 `workspace_prefixes` 含 `com.user`（由 T10-206 定点写入，
`.omo/_truth/registry/services.yaml:6491`），故本条 label 落进 workspace 桶。

三条候选路径里只有一条在本轮授权面内：

1. **动 `workspace_prefixes`（删 `com.user`）** —— 会把本条推成 `unmanaged_unknown`，
   E2 归零但 E4 未分区 22→23，且推翻 T10-206 已署名的分区决定。台账里 T10-253 / T10-258
   的 `circuit_breaker` 明文写着「需要动 exempt_labels / workspace_prefixes → 停止并保留原判据」。
2. **动 `exempt_labels` 加一条 external** —— 结构上不通：`classify_label` 先命中
   `com.user` 前缀返回 `workspace`，exempt 项永远读不到（死数据），且 E4 的遮蔽断言
   （`:746`）会新增一条「exempt 项被 workspace 前缀遮蔽」。
3. **加 `generate: false` + `enabled: true` 的服务条目** —— `declared` 由
   `declared_labels(services)` 给出（`:475`），条目一加等式即闭合；`generate: false` 使
   `validate_service_declaration` 早返回（`:211`）、`--check` 比对循环跳过（`:1023`），
   对 E1/E3 零扰动；`enabled: true` 且本机确已安装，使 E5 两个方向都保持 0
   （`:790-791`）。这正是 T10-246 / T10-253 / T10-258 三次「E2 归零」用的机制。

路径 3 同时避开了任务 #150 的形状：那一条是 `generate: true` 而本机无 plist ⇒ 比较器恒
drift。本条相反，plist 真实在跑且 `generate: false`，声明只表达「注册表知道它在跑」，
不夺取 plist 的写权。注册表内此类 observe-only 条目在本条之前实测 57 条（`generate: false` 计数，随登记增长，勿当固定基线），含 `com.lmstudio.server`、
`com.aetherforge.gateway` 等同族个人/跨主算力服务，`ports:` 也不要求登记进
`protocols/port-registry.yaml`（`1234` 先例）。

## 3. 变更

`.omo/_truth/registry/services.yaml` 追加一条（字段形状照 `com.aetherforge.gateway`）：

```yaml
- id: user.omlx-smart-gateway
  enabled: true
  generate: false
  config_source: ~/Library/LaunchAgents/com.user.omlx-smart-gateway.plist
  scheduler: launchd
  trigger: keepalive
  label: com.user.omlx-smart-gateway
  program:
    interpreter: /usr/bin/python3
    entrypoint: ~/.local/bin/omlx-smart-gateway.py
    args: []
  run_at_load: true
  ports:
  - 18080
  outputs:
    stdout: ~/.local/state/omlx-gateway.log
    stderr: ~/.local/state/omlx-gateway.err
  liveness:
    signal: http
    endpoint: http://localhost:18080/gateway/status
    max_stale_hours: 24
  depends_on: []
  notes: <异主说明 + 取证 + 不做写权主张>
```

路径一律 `~` 相对，不写 `/Users/xiamingxing` 字面量（B4b 的改道面不引入新的 host 锚）。

## 4. 验收

- ISC-1 同检出 `--reality-check --json`：`e2_undeclared == 0` 且
  `owned_declared == owned_installed == 51`。
- ISC-2 **反证**：临时摘掉本条声明，`e2_undeclared` 必须回到 1 且点名本 label、
  `owned_declared` 回到 50。只断言 0 不算 —— 判据可能因桶为空而空真。
- ISC-3 零扰动：`e1_drift` / `e3_lint_debt` / `e5` 两项 / `installed_total` / `external` /
  `unclassified` / `e4` 未分区计数与基线逐字段相同（0/0/0+0/87/8/0/22）。`ok` 仍为 False，
  由 E4 驱动 —— 本轮不宣称 `--reality-check` 整体转绿。
- ISC-4 `--validate --json` ok=true violation_count=0；`--check` rc=0（生成面零变化）。
- ISC-5 `pytest tests/test_service_registry_reality.py -q` 全绿（该文件的 E2 用例走
  tmp_path 合成注册表，不读真实台账，故本轮无计数需重签）。
- ISC-6 本机 launchd 零改动：不 bootout/bootstrap/kickstart，不写 `~/Library/LaunchAgents`，
  交付前后该 plist 的 mtime_ns + size + sha256 + `launchctl print` 的 state 逐字节一致。
- ISC-7 `make gac-local-gate` 硬失败集合等于基线（零新增）。

## 5. 非目标

- 不动 `workspace_prefixes` / `exempt_labels` / `--reality-check` 任一判据本体。
- 不把本条声明成 `generate: true`，也不替它写 plist —— 写权仍在 principal。
- 不收口 E4 的 22 条未分区（署名裁定面，任务 #147）。
- 不推进 B4b 批次 2 的机器侧改道（逐批授权面，任务 #91）；本轮只解除它的前置阻塞。
- 不宣称 ADR-0456 B1/B3/B4/B5 或整个 plan 完成。

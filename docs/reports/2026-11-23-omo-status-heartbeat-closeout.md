---
schema: md/v1
status: active
lifecycle: history
owner: governance-agent
last-reviewed: 2026-11-23
type: report
bet_id: BET-Y2Q4-T10-348
title: BET-Y2Q4-T10-348 closeout — omo-status healthy_count 按秒龄真算 + header 全绿才 HEALTHY
---

# BET-Y2Q4-T10-348 收口收据

代码主体在 PR #5425（squash `93b54639c`）落地，其中 `projects/cockpit` gitlink 由
`submodule_pointer_bump: projects/cockpit -> bet/t10-348-heartbeat-false-positive (2e6acc0)` 起步，
末条 commit 又 bump 到 cockpit `main` 的 `c5146edc7`（含 #265 修 `test_swarm_collector` 时钟炸弹）。
**origin/main 当前记录的 gitlink = `b26258fd5bb7554f2aa414458032722f3f6cfcb7`**（cockpit #267），
本轮收口不再改子模块，只复核 + 收据 + 台账。

本文件是 `completion-evidence-matrix/v1` 的 `tests` / `diff` / `rollback` / `fresh_receipt` / `live_canary` /
`cleanup` 载体；`replay` 载体是 `.omo/_knowledge/retros/BET-Y2Q4-T10-348.md`（#5425 作者所写，按 sha256 绑定，不改写）。

## 三处生产变更的存在性（在 gitlink 检出上直读）

| 落点 | 实测内容 |
|---|---|
| `projects/cockpit/src/cockpit/tui/swarm_collector.py:229` | `healthy_count=sum(1 for h in heartbeats if h.status == "healthy")` —— 不再取 tick JSON 自报的 `ok_count`，也不再 `agent_count - failed` 兜底 |
| 同文件 `:214` | `st = "healthy" if sec_ago < 600 else "stale"` —— 600s 阈值未动（spec 非目标第 1 条） |
| `src/cockpit/tui/swarm_cli.py:30/37/39` | `● HEALTHY` 仅在全绿时取，否则 `○ DEGRADED`（由 `healthy_count > 0` 收紧） |
| `src/cockpit/tests/test_swarm_heartbeat_staleness.py` | 3 条用例（25 天陈旧 ⇒ healthy_count=0 且全 stale；新鲜 ⇒ 6/6；第三条覆盖无 tick） |

## 受控测试（verify[0] 的可执行子集）

```
cd projects/cockpit && uv run --no-project --with pytest --with pyyaml \
  python -m pytest src/cockpit/tests/test_swarm_heartbeat_staleness.py -q -p no:randomly -o addopts=""
=> 3 passed in 0.01s   (rc=0)
```

补齐那四个 sibling 的检出文件后（`git -C projects/<sibling> checkout --force <gitlink> -- .`，不动 HEAD、不改
gitlink），verify[0] 原句在隔离 worktree 内**跑通**：

```
cd projects/cockpit && timeout 900 uv run pytest src/cockpit/tests/ -q
=> 1 failed, 1626 passed, 7 warnings in 564.84s (0:09:24)
   FAILED src/cockpit/tests/test_dashboard_server.py::TestDashboardEndpoints::test_unknown_path_returns_404
      [XPASS(strict)] …
```

**唯一 fail 与本 BET 无因果关系，且是 worktree 装置**：该用例是 `xfail(strict)`，fail 的原因是它现在**通过**了
（XPASS），而通过的原因是隔离 worktree 里 `projects/cockpit-ui` 只有 gitlink 没有检出 ⇒
`dist/index.html` 缺席 ⇒ FastAPI 的 SPA catch-all 对未知路径回 404。判据不是推理：同装置下
`bin/ssot/check-cockpit-ui-dist.py` 报 `🚨 ARCHITECTURE FAULT: cockpit-ui static assets (dist/index.html) are missing!`
并自行尝试 `bun run build` / `npm run build` 失败（`package.json` 都不存在）；补齐该子模块检出后同一检查
`✅ cockpit-ui static assets are aligned and present in dist.` rc=0。数量对照也与 #5425 作者落地当天自述的
`1626 passed / 0 failed / 1 xfail` **同档**（1627 条），差异只在 xfail 一侧因装置翻成 XPASS-strict。
目标用例模块单独复跑仍 3 passed；**本 BET 三项语义（陈旧→healthy_count=0→DEGRADED）零回归**。

## 判读要点（live canary）

| 判据 | 读数 |
|---|---|
| `bin/omo-status --json` 的 agents 段 | `{'total_agents': 6, 'healthy_count': 0, 'failed_count': 0, 'last_tick_iso': 'N/A', …}` —— 本机无新鲜 tick 时 healthy_count 为 0，若仍信心跳自报会得到 6 |
| `bin/omo-status` 的 swarm header | `│   ○ DEGRADED  ·  OMOSTATION MULTI-AGENT SWARM  ·  0/6 Agents Active  ·` —— 对照 spec 立案时的 `"6/6 Agents Active + HEALTHY"`，假阳性消失 |
| 台账 verify[1] 原句 | `bin/omo-status --no-subprojects` **rc=2**：`python -m cockpit.tui.swarm_cli: error: unrecognized arguments: --no-subprojects`（该 CLI 只有 `--json` / `--probe-remote`）—— 验收命令按原句写会造成假红，已按 `bin/omo-status` / `bin/omo-status --json` 复现并订正进台账 |
| circuit_breaker（`healthy_count` 语义在别处被消费？） | 全仓扫描：子模块外的 `healthy_count` 只出现在台账文案与 `bin/_archive/2026-09-20-b13-archive/journey-spec-health.py`（自己的局部变量，指 journey spec，非 swarm 语义）；cockpit 内消费方是 `tui/swarm_app.py:261-264`（header，同批已收紧）与 `tests/`；`commands/status.py:92`、`web/api_agora.py:265` 的 `healthy_count` 是**服务**健康度的局部计数，与 tick 自报无关 ⇒ 不触发熔断，无需 owner 追加裁决 |

## operational-轴

| 项 | 读数 |
|---|---|
| fresh_receipt | 本文件，2026-11-23 在 `origin/main@c8efc46b8` 的隔离 worktree（`projects/cockpit` 检出对齐 gitlink `b26258fd5`）现采 |
| live_canary | 上表 header 与 `--json` 两项，均为运行态读数而非源码推断 |
| cleanup | 无写入：只读 `bin/omo-status` 与只读子模块检出；worktree 内 `projects/{metaos,l4-kernel,omlxc,observability,bus-foundation,family-hub,model-driven}` 用 `git checkout --force <gitlink> -- .` 补齐（**不动 HEAD、不改 gitlink**，`git submodule status` 对 cockpit/metaos 无 `+`） |
| 未执行动作 | 未改心跳写入方（resident daemon tick JSON）与 600s 阈值；未动 agent 表 SEEN 列；未处理 scene-card 69/70 blocker（spec 非目标） |

## 门禁面（本机 `make gac-local-gate`，与伴生 BET-Y2Q4-T10-349 同一读数）

```
scope=staged change_lane_files=0
[PASS] service-config-drift :: bin/mof/gen-service-configs.py --check     ← 11-10 起恒 FAIL 的那条（本对 BET 的解除点）
[PASS] service-config-validate :: gen-service-configs.py --validate
…
GaC local gate: FAIL | 2 SOFT WARN
[FAIL] check-cockpit-ui-dist   ← worktree 装置：子模块未检出（补齐后单跑 ✅ rc=0，见上）
[FAIL] omo-state-write-guard   ← state-plane：write-owners.yaml 声明的 7 个键在 .omo/state/system.yaml 不存在
```

两条 FAIL 均与本 BET 写面零交集：前者已复现并消除（装置），后者是 state 面键位缺失（`ghost-declaration`），
不是 swarm 健康度语义，且本 BET 未触碰 `bin/gac/omo-state-write-guard.py` 与 `write-owners.yaml`。
如实入证，不私改 —— 与 spec 非目标「不处理 scene-card 69/70 blocker」同一口径。

## rollback

回滚 = 把 cockpit gitlink 退回 #5425 之前（`git revert` 根仓那条 gitlink 行），代码侧三处（collector :229、
:214 阈值、swarm_cli header）彼此独立，但**只回退 header 收紧会重新出现「部分健康却 HEALTHY」**，
只回退 collector 会重新出现「25 天陈旧心跳仍 healthy_count=6」—— 两者是同一条假阳性的两半，应整体回退。

## §14.2 运行记录

```json
[
  {
    "run": "cockpit-targeted-test",
    "inputs": ["projects/cockpit@b26258fd5:src/cockpit/tests/test_swarm_heartbeat_staleness.py",
               "projects/cockpit/src/cockpit/tui/swarm_collector.py"],
    "basis": "台账 verify[0] 的目标用例；AGENTS.md §8（子模块测试按项目 runner）",
    "approver": "principal（2026-11-23「充分授权，全面推进」）",
    "result": "3 passed in 0.01s, rc=0；补齐 sibling 检出后 verify[0] 原句复跑 1 failed/1626 passed，唯一 fail 是 cockpit-ui 未检出的装置性 XPASS（见「受控测试」）",
    "duration_ms": null,
    "model_usage": "none（纯脚本）"
  },
  {
    "run": "cockpit-full-suite-and-gac-gate",
    "inputs": ["projects/cockpit/src/cockpit/tests/（1627 条）", "projects/{agora,l4-kernel,metaos,omo,cockpit-ui}（按 gitlink 补检出，只读）",
               "make gac-local-gate"],
    "basis": "台账 verify[0]/done_when[2]「cockpit 测试套件无回归」+ #5425 作者自述 1626 passed 的对照",
    "approver": "principal（同上）",
    "result": "套件 `1 failed, 1626 passed in 564.84s`（fail 为 `test_unknown_path_returns_404` 的 XPASS-strict，装置原因＝cockpit-ui dist 缺席，补齐后 `check-cockpit-ui-dist` ✅）；门禁 `service-config-drift` 转 [PASS]，余 2 条 FAIL（1 装置已消除、1 为 write-owners/state 键位 ghost-declaration）与本 BET 写面零交集",
    "duration_ms": 564840,
    "model_usage": "none（纯脚本）"
  },
  {
    "run": "omo-status-live-canary",
    "inputs": ["bin/omo-status", ".omo/state/agent-tick-daemon.jsonl（只读）"],
    "basis": "done_when[0]/[1] 的 header 语义 + 台账 verify[1]",
    "approver": "principal（同上）",
    "result": "header `○ DEGRADED · 0/6 Agents Active`；`--json` `healthy_count=0 total_agents=6`；台账原句 `--no-subprojects` rc=2 属命令口径错误，已订正",
    "duration_ms": 21500,
    "model_usage": "none（纯脚本）"
  },
  {
    "run": "consumer-surface-audit",
    "inputs": ["projects/cockpit/src/**", "bin/**", "docs/plans/3y-bet-ledger.yaml"],
    "basis": "台账 circuit_breaker（healthy_count 自报语义在别处被消费即停止并交 owner）",
    "approver": "principal（同上）",
    "result": "无跨面对象：swarm 语义的消费方仅 swarm_app header（同批收紧）+ 测试；同名局部变量属服务/journey 域 ⇒ 熔断未触发",
    "duration_ms": null,
    "model_usage": "none（rg 扫描）"
  }
]
```

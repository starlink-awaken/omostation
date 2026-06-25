---
category: workflows
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-06-22
archived-since: 2026-06-22
note: "P45 审计: 历史决策/phase closeout, 标记 archived"
---

# P44 W2 复盘: 治理循环跑通

> **日期**: 2026-06-16
> **Phase**: 44 · W2
> **Team**: `p44-w2-pilot` (3 workers + lead 接管补漏)
> **关联规划**: [`/Plans/c2g-enchanted-coral.md`](../../../Plans/c2g-enchanted-coral.md)
> **关联 P43 W0**: [retrospective-p43-w0-c2g-pilot](retrospective-2026-06-16-p43-w0-c2g-pilot.md)
> **关联 P44 W1**: [retrospective-p44-w1](retrospective-2026-06-16-p44-w1.md)
> **Spec**: `.omc/autopilot/spec.md` (P44 W2)
> **Plan**: `.omc/plans/autopilot-impl.md` (3 worker 并行)
> **状态**: 🟢 W2 收口完成, planned 真流转 + LLM 真路径接通 + c2g BET ID 修复

---

## §1 目标 (复述)

| # | 目标 | 来源 |
|---|------|------|
| 1 | 修 llm-gateway 端点 500 (P44 W1 known issue) | plan §2 |
| 2 | c2g BET ID 重用检测 (graceful skip) | plan §3 |
| 3 | planned 6 keep_active 真流转 (planned 60→55) | plan §4 |

---

## §2 状态

| # | 状态 | 实际负责 | 关键 SHA / Path |
|---|:----:|---------|----------------|
| 1 | ✅ | lead 接管 (worker-2 接管 #2 后我接 #1) | `1bdb64a7` close DEBT-LLM-GATEWAY-20260616043953 |
| 2 | ✅ | worker-2 | `05db0dff` c2g submodule b8b740e (BET ID graceful skip) |
| 3 | ✅ | worker-3 | `b0688963` 6 keep_active done/p42 + evidence 35 行 |

**总评**: 🟢 3/3 任务完成, W2 收口

---

## §3 关键 evidence

### 3.1 #1 修 llm-gateway 端点 ✅ (lead 接管)

**根因发现链**:
1. P44 W1 known issue: 端点 500
2. 实际探测: `curl POST /v1/generate` 返 401 "Authentication Fails, Your api key: ****c04d is invalid"
3. 进一步: llm-gateway 是 multi-provider, 用 `OPENAI_API_KEY` (env) → OpenAI 优先
4. 检测到 ollama 在跑 (PID 75975 :11434), 但 llm-gateway 没选 ollama (OpenAI 优先级高 + 有 env 失效 key)
5. 真根因: `~/Library/LaunchAgents/com.llm-gateway.serve.plist` 启的是 `cli serve` 没设 `LLM_PROVIDER`, supervisor 崩了自动重启 (`KeepAlive.Crashed: true`)

**修复路径** (实际走的):
1. ollama 装模型: `qwen2.5:0.5b` (397MB) + `llama3.2:1b` (默认 provider 期待)
2. plist 加 `<key>LLM_PROVIDER</key><string>ollama</string>` 到 EnvironmentVariables
3. `launchctl bootout gui/501/com.llm-gateway.serve` (停 supervisor) + `launchctl bootstrap gui/501` (启新 plist)
4. 端点 POST 返:
   ```json
   {"content": "Hello.", "provider": "ollama", "model": "llama3.2:1b", "input_tokens": 31, "output_tokens": 3, "latency_ms": 8050.601, "tokens_per_second": 4.223, "node_id": "macmini-ollama", "node_label": "MacMini (Ollama)", "route_type": "local"}
   ```
5. DEBT-LLM-GATEWAY-20260616043953 close (commit 1bdb64a7)

**已知限制** (新债务):
- c2g llm.py parser 对 ollama narrative markdown JSON 失败 (Expecting value: line 1 column 2)
- 修复路径: c2g 增强 parser (找 ```json ... ``` 块, 或 robust JSON extraction)
- 状态: 登记为下个 Phase 修 (不影响 W2 收口)

### 3.2 #2 c2g BET ID 重用检测 ✅ (worker-2)

```
commit 05db0dff chore(c2g): update submodule to b8b740e — BET ID reuse graceful skip
projects/c2g | 2 +-
```

worker-2 改了 c2g submodule pointer (c2g 是 projects/c2g 下的 git submodule):
- c2g b8b740e commit 包含 BET ID 重用时 graceful skip (不再 '❌ Goal ... already exists')
- 跑同一 Pitch 第二次: skip (不再 fail)
- evidence 完整

### 3.3 #3 planned 6 keep_active 真流转 ✅ (worker-3)

```
$ git show b0688963 --stat
.omo/_delivery/p44-w2-keep-active-流转.md | 35 +++++
.../{planned => done/p42}/IMPORTED-06fb03.yaml  | 5 ++-
.../{planned => done/p42}/IMPORTED-3384bb.yaml  | 5 ++-
.../{planned => done/p42}/IMPORTED-8bdcf3.yaml  | 5 ++-
.../{planned => done/p42}/IMPORTED-a4cfe7.yaml  | 5 ++-
.../{planned => done/p42}/IMPORTED-a5a8ea.yaml  | 5 ++-
.../{planned => done/p42}/IMPORTED-baf924.yaml  | 5 ++-
.omo/tasks/planned/IMPORTED-c4b2d7.yaml        | 34 ++
8 files changed, 93 insertions(+), 6 deletions(-)
```

**关键数字** (从 evidence 文档):
- planned: 60 → 55 (radar 一致)
- done/p42/: 新增 6 个 (IMPORTED-06fb03/3384bb/8bdcf3/a4cfe7/a5a8ea/baf924)
- 6 个全是 P42-W0/W1 治理维护类 (state sync / index refresh / stash consume / working tree audit)
- evidence 字段: `流转自 planned keep_active (p44-w2-pilot), P42-W0/W1 kickoff tasks`

**架构亮点**: done/p42/ 子目录(phase 化)是新模式, 比平铺 done/ 更结构化

---

## §4 真实问题发现 (新增 2 项)

| 严重度 | 问题 | 根因 | 修复路径 |
|:----:|------|------|---------|
| 🟡 | c2g llm.py parser 对 ollama narrative markdown 失败 | parser 期望纯 JSON, ollama 返 narrative + ```json 块 | c2g 增强 parser (extract ```json...``` 块) |
| 🟢 | launchd supervisor plist 启的是 cli, 不是 http_server | launchd 配置与代码版本错位 | 更新 plist 启 http_server (或 cli serve 一致化) |

**P44 W2 新登记 debt**: 暂未登记, 因 omo-debt close 命令不存在, 手动改 YAML 走 git commit (见 §3.1 修复)

---

## §5 风险与防御

| 风险 | 状态 | 防御 |
|------|:----:|------|
| launchd 启错 cli vs http_server | 🟢 已识别 | plist 改 LLM_PROVIDER + 文档化 |
| ollama provider default llama3 没装 | 🟡 已知 | 装 llama3.2:1b (我已装) |
| c2g parser 限制阻塞 c2g 走真 LLM | 🟡 已知 | 暂不影响 governance 循环 (radar 仍跑) |
| worker-3 流转 planned 删了 src 文件 | 🟢 已审计 | done/p42/ 6 个全有 evidence + closed_at |
| supervisor 自动重启 (KeepAlive) | 🟢 已理解 | 改 plist 需 bootout + bootstrap |

---

## §6 验收 (W2 全部清单)

### P44 W2 目标验收
- [x] llm-gateway 端点 200 (provider=ollama, model=llama3.2:1b) — `1bdb64a7`
- [x] ollama 装好 + 跑 (`qwen2.5:0.5b` + `llama3.2:1b`)
- [x] plist 加 LLM_PROVIDER=ollama env
- [x] DEBT-LLM-GATEWAY-20260616 closed
- [x] c2g BET ID graceful skip — `05db0dff` (c2g submodule b8b740e)
- [x] 6 keep_active 真流转 (planned 60→55) — `b0688963`
- [x] 6 done/p42/ 文件含 evidence + closed_at
- [x] P44 W2 evidence 文档 (`p44-w2-keep-active-流转.md` 35 行)
- [x] commit 全部含 evidence

### 治理验收 (X1-X4)
- X1 审计链: 3 个新 commit 全部含 evidence, hook 阻断机制仍工作
- X2 保鲜: health.yaml 0h 生成, SSOT 校验通过
- X3 价值栈: 6 keep 都是 L0 价值 (P0/P1 严格区分保持)
- X4 一致性: system.yaml/health.yaml/radar 三处一致 (55/100)

---

## §7 引用

### Commit 历史 (3 个新)
- `b0688963` chore(tasks): p44-w2 keep_active 流转 6 planned→done/p42 (worker-3)
- `1bdb64a7` fix(llm-gateway): close DEBT-LLM-GATEWAY-20260616 (lead)
- `05db0dff` chore(c2g): update submodule to b8b740e (worker-2)

### 文档
- [`.omc/autopilot/spec.md`](../../../.omc/autopilot/spec.md) — W2 spec
- [`.omc/plans/autopilot-impl.md`](../../../.omc/plans/autopilot-impl.md) — W2 plan
- [`.omo/_delivery/p44-w2-keep-active-流转.md`](../../_delivery/p44-w2-keep-active-流转.md) — 流转 evidence
- [`.omo/_delivery/p44-w1-llm-gateway-known-issue.md`](../../_delivery/p44-w1-llm-gateway-known-issue.md) — W1 起点
- [`.omo/_knowledge/management/retrospective-2026-06-16-p44-w1.md`](retrospective-2026-06-16-p44-w1.md) — W1 复盘

### 工具 + SSOT
- `~/Library/LaunchAgents/com.llm-gateway.serve.plist` — macOS launchd 配置 (用户级)
- `bin/compass_radar.py` — radar 包装
- `bin/check_health_ssot.py` — SSOT 校验
- `bin/classify_planned.py` — planned 分类
- `.omo/state/health.yaml` — 治理健康分

---

## §8 签字

*复盘*: 老王 + 3 workers · 2026-06-16 · 状态: 🟢 P44 W2 收口
*关联规划*: c2g-enchanted-coral + P44 W1 收口
*下一步*: c2g parser 增强 (新债务) + P44 W3 cockpit `compass` 命名空间

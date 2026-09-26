---
schema_version: specification/v1
spec_version: 1.0.0
title: Dev Port Band and Production UI Entry Truth
bet_id: BET-Y2Q4-T10-205
status: accepted
lifecycle: contract
owner: governance-team
last-reviewed: 2026-09-26
adr: ADR-0456
---

# dev 端口段与生产 UI 入口真相（ADR-0456 B2）

> 权威取值只在本契约的实现载体 `protocols/port-registry.yaml`；本文只立规则。
> 下文测量全部于 2026-09-26 在同一检出（base == `origin/main`）复现，非引用二手描述。

## Problem

ADR-0456 要把开发与运行拆开，B2 的前置条件是**端口能被注册表表达**。实测三处表达不出来：

| 事实 | 测量 |
|---|---|
| 4000 未注册 → 门禁恒红 | `check-hardcoded-ports.py --json`：`registered_total 54`、`unregistered 1`、`ok false`，唯一项是 `port 4000`（20 处命中），`tests/test_hardcoded_ports.py::test_unregistered_is_zero` 因此在 main 上红 |
| 4000 是谁的 | PID 96878 = `python -m llm_gateway.openai_proxy --port 9290,4000 --bind tailnet`（aetherforge venv），**与已注册的 9290 同一进程**，且同时绑 `127.0.0.1` 与 tailnet 地址 |
| 5173 被豁免成"外部工具" | `bin/ssot/check-hardcoded-ports.py` `LEGACY_OK_PORTS` 收 5173，注释 `Vite dev server (工具默认)`；但监听者 PID 19871 = `node ~/Workspace/projects/cockpit-ui/node_modules/.bin/vite`，是本仓自己的进程 |
| 注册表宣称的入口没有监听 | `cockpit.dashboard :8090` 在 `.omo/_truth/registry/services.yaml` 里 `enabled: true` 且注释"唯一人类 Web 入口"；实测 `curl :8090/health` 连接拒绝，`launchctl print gui/501/com.cockpit.dashboard` → `Could not find service` |
| 实际入口是手工拉起的 dev shell | PID 19871 于 2026-09-25 09:31 手工启动，`:5173/` 返回 200 但只有 932 字节，`:5173/api/health` 返回 **502**（其 upstream `:8090` 根本没在跑） |
| 连"入口"本身也没注册 | `bin/panorama/sunset_redirector.py`（PID 51218）`--port 43910 --target http://localhost:5173/panorama`，实测 43910/43922/43923/43924 上共 3 个实例，`4391x` 全部不在 `ports:` 里 |

结论：vite 不是"生产 UI 用了 dev server"这么一件事，而是**注册表、门禁与运行时三者对"人类入口是谁"给出的答案互相矛盾**。
B2 先把矛盾拆开：注册表写真值（本 bet），入口切回声明的服务（B2-B，有运行时 blast radius，须逐项确认）。

## Contract

### C1 端口先注册后使用，且豁免表只容纳"不归本仓管"的端口

- `4000` 注册为 aetherforge LLM 网关的 OpenAI 兼容面（与 `9290` 同进程双监听），
  并进 `env_vars`，取值入口沿用该进程已有的 URL 型 seam（`C2G_LLM_URL` / `LLM_GATEWAY_URL`），不新造变量。
- `5173` 从 `LEGACY_OK_PORTS` 移入 `ports:`，判定为**本仓 dev-profile UI 端口**。
  豁免表的语义收窄为：外部标准（如 OTLP `4318`）或外部仓的默认端口；
  本仓自己拉起的进程**不得**借"工具默认"之名绕过注册。
- `43910` 注册为 panorama sunset redirector，并说明 `4391x` 的自增占用行为。

### C2 dev 端口段：显式表，不是算式

dev profile 的端口取自 `protocols/port-registry.yaml` 的 `dev_ports:` 显式表，落在 `dev_band` 声明的区间内。
**禁止任何算术推导**（如 `15000 + p % 1000`、`p + 20000`）。两个候选算式都已被实测否证：前者在段内产生 12 处
自身碰撞，后者把 `43191` 送进 `63191` —— 落在 ephemeral 区间，与系统临时端口争用。
端口一经分配即固定，不因"看起来更整齐"而重排；新增条目只追加，不改写既有条目。

### C3 dev 端口表必须同时满足三条（由测试执行，不靠人眼）

1. **contained**：每个 `dev_ports` 端口都在 `dev_band` 内。
2. **injective**：dev 端口两两不同（一个 prod 端口对应唯一一个 dev 端口）。
3. **disjoint**：dev 端口与所有已注册生产端口、与 `LEGACY_OK_PORTS` 均无交集；
   且段内不得与任一已注册端口重叠。

段的选择另附一条运行时判据：不得与测量时刻在听的端口重叠（实测本机 41 个 LISTEN，段内零命中；
CI 无监听者，故该项只在本地跑，不作为 CI 断言）。

### C4 dev 端口只能从环境取值

`python3 bin/ssot/check-hardcoded-ports.py --dev-env --profile dev` 是 dev 端口的唯一打印入口
（每行一条 `NAME=PORT`，可被 shell `eval`）。`projects/*/src/**/*.py` 里出现 dev 端口字面量必须被判为未注册 ——
dev 值进源码就等于把 dev profile 写死成第二套生产配置。
不新增 `bin/` 脚本：打印模式加在既有扫描器上（`bin/` 有净新增配额门禁）。

### C5 人类入口唯一，且必须可被门禁验证

生产入口是 `cockpit.dashboard :8090`，静态资源来自 `projects/cockpit-ui/dist`。
该路径**已存在**：`projects/cockpit/src/cockpit/dashboard_server.py` 已挂载
`COCKPIT_UI_DIST/assets` 并带 SPA fallback，`COCKPIT_UI_ROOT` / `COCKPIT_UI_DIST` / `COCKPIT_DASHBOARD_PORT`
三者均可环境覆盖。因此 B2-B 不是写新功能，而是**让已声明的服务真的承载已构建的产物**，
并把 vite 降为 dev-profile 专用进程。sunset redirector 的 target 属于这次切换的一部分。

## Adjacent findings（登记，不在本 bet 处置）

| 发现 | 为什么不在本 bet 修 |
|---|---|
| 端口门禁的 CI 接线是**死信**：`.github/workflows/port-registry-enforce.yml` 经 `ci-check-runner.py` 解析 `ci-surfaces.yaml:358-362`，该 scanner 记为 `status: orphan` → 命中 0 项检查；`.pre-commit-config.yaml` 的 `port-hardcode-check` 指向不存在的 `scripts/check-vault-paths.py --check-ports`；而 root 扫描器 `bin/ssot/check-hardcoded-ports.py` 根本没有 `--check-ports` 这个参数（实测 argparse 只有 `--json / --threshold / --env-var-check`，2026-09-26 本 bet 加 `--dev-env / --profile`）。即"增量 enforce"在三处被描述、零处存在 | 翻这条接线等价于改变门禁效力，属 principal 决策（同 #4209 移除 `--require-main` 的量级）。本 bet 只把"门禁红"变成真值，不动"门禁是否执行" |
| `projects/agora/bin/ssot/check-hardcoded-ports.py` 是 root 扫描器的 vendored 副本，`LEGACY_OK_PORTS` 相同、仅格式漂移 | 同步它要开子仓 PR + 合并 + 主仓 bump gitlink，为零门禁收益付出跨仓链 |
| `cockpit.dashboard` 注册为 `enabled: true` 却不在 launchd 里 | 这是 B3「registry == 已安装 label 集合」门禁要抓的那一类，本 bet 只留证据 |
| 340 条服务里只有 2 条声明 `environment`；无任何已注册服务声明 `OMOSTATION_*` | profile 注入点的收口属 B3/B4 |
| `projects/metaos/src/metaos/run.py:25` 把 `127.0.0.1:4000/health` 当作 "Ollama 是否活跃" 的探针（真身是 aetherforge 网关；ollama 是 11434），且无环境兜底 | 在 `projects/` 下，本 bet 的 circuit breaker 禁止触碰 |
| worktree 里的 `projects/cockpit-ui/dist` 只有 24 KB，主工作区同名目录 2.4 MB —— 构建产物随检出漂移 | 属 B2-B 的实际构建动作，不在注册 bet 里顺手重建 |

## Handoff

- **B2-B**（`#86`）：加载 `com.cockpit.dashboard` 使 `:8090` 服务已构建 dist、重建 dist、
  退役手工 vite、修正 sunset redirector target。每一条都会改动"正在被绑定的端口/正在跑的人类入口"，
  须逐批与 principal 确认后执行。
- **B3**：37 个未登记 launchd label 回填 + label 加 profile 前缀 + `gen-service-configs.py --check`
  双 profile 干净；并接手 `projects/omo` 内核侧 17 处 root 解析的 fork（ADR-0456 §7）。
  **B3 是 B4 的中止判据**：做不到 registry == installed 集合，就停在 B4 之前。

## Verification

- `python3 bin/ssot/check-hardcoded-ports.py --json` → `unregistered == 0`、`ok true`
- `python3 -m pytest tests/test_hardcoded_ports.py -q` → 全绿（含 C3 的三条一致性断言）
- `python3 bin/ssot/check-hardcoded-ports.py --dev-env --profile dev` → 每条 `dev_ports` 一行
  `NAME=PORT`，且打印的端口不与任何已注册生产端口重合
- `python3 bin/ssot/check-hardcoded-ports.py --dev-env --profile prod` → 不打印任何覆盖、exit 0
- `python3 bin/ssot/check-hardcoded-ports.py --dev-env`（无 `--profile`）→ 非 0 退出：宁可拒绝，也不猜 profile
- 运行时判据（本地）：`lsof -nP -iTCP -sTCP:LISTEN` 的端口集合 ∩ `dev_band` 区间 == 空

## Out of scope

不改 `.omo/_truth/registry/governance-checks.yaml`、`ci-surfaces.yaml`、`.pre-commit-config.yaml`；
不改 `protocols/port-hardcode-baseline.yaml` 的语义；不启停任何 launchd/crontab 项；
不动 `projects/**`；不切换人类 UI 入口；不回填他人的 evidence。

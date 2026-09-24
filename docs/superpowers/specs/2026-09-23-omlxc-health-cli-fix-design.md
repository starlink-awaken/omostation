---
type: ssot
status: active
lifecycle: contract
owner: governance-team
last-reviewed: 2026-09-24
last_updated: 2026-09-24
bet_id: BET-Y2Q3-T10-OMLXC-01
spec_version: 1.0.0
schema_version: specification/v1
---



# omlxc 体系深度诊断 + 分阶段修复计划

## 〇、现状诊断报告（2026-09-23 实测，只读）

### 结论一句话
**算力链路健康，控制面引用与 inventory 声明层有问题**：3/3 节点 healthy、daemon ready、四后端全通；但 doctor degraded（2 处 placement 失配）、7 个模型全 placement 不可用、命令体系 21 条优化点（4 条 P0 已实测失败）。

### 节点状态 ✅
| 节点 | 状态 | 心跳 (observed_at) |
|---|---|---|
| mbp-m5-max-128g | healthy | 2026-09-23T12:55:11Z |
| macmini-m4pro-24g | healthy | 2026-09-23T12:52:35Z |
| y7000p-rtx4070-8g | healthy | 2026-09-23T12:54:25Z |

- `com.omlxc.daemon` running (PID 70755)；`omlxc status --json` = `ready / storage_healthy`
- 后端全通：LM Studio :1234、oMLX App :8000、Ollama :11434、AetherForge :9290/:4000 均 200/ok
- AetherForge 日报 2026-09-23：完成 2、失败 0；累计推理 153,086 请求

### 模型状态 ⚠️
- **26 模型 / 38 placement / 20 可用**；7 个全 placement 不可用：`coding-fast, coding-next, mid-local, ornith-9b, qwen-3.8-27b, reasoning-lite, vision-large`（与 watchdog 20:52 告警一致）
- `omlxc doctor --direct` = **degraded**，2 项失败：
  - `mbp-omlx-app`：3/18 placements 指向后端不服务的模型（coding-next-local / ornith-9b-local / qwen3-8-27b-local）
  - `mbp-lm_studio`：**15/15 全部 model_mismatch**（inventory_drop baseline 45→1）
- conf/models.json 声明 33 模型 vs 可用 20，差 13 个待归因
- memory-sentinel：可用 24.7GB、**swap 27.1GB 偏高**；高风险模型 `qwen3.6-35b-a3b-splash` (19.5GB ctx=262144) 加载中

### 观测盲点（4 处）
1. `~/.config/omlxc/state.db` 的 `health_snapshots` **0 行**（节点健康从未落库）
2. `status-history.log` **停更 16 天**（2026-09-07）
3. `.omo/state/mesh-telemetry.json` 空（`omlxc.dma_daemon` enabled=false）
4. `omlxc routes show` → E100；`omlxc benchmark report` → E900；jobs list 多条卡 progress=0.2

### 命令体系总评
主 CLI（Typer，49 注册项）质量尚可，cockpit 委派接线符合入口收敛治理；问题集中在：**① 三重身份 + 三份漂移 omlx 副本；② 调用方/文档仍用已消失的遗留子命令（2 处实测失败）；③ 输出契约细节不达标**。详见 Phase 1/3/4。

---

## 硬约束（全程适用）

- **主工作区只读**：每批改动先 `bash bin/gac/gac-worktree.sh claim <session>` 起隔离 worktree
- **ADR-0203**：编辑前先 `uv run --with "pyyaml" python bin/agent-workflow.py bootstrap → start --profile <agent> --bet <BET-ID> → claim`
- **不主动 git commit**（除非用户明确要求）；子模块三步走：`projects/omlxc` 内提交 → push → 主仓指针更新（`bash bin/ssot/submodule-pointer-transaction.sh`）
- 每批可独立小步交付；写操作必须先存档基线、标风险门

---

## Phase 1 — 诊断固化 + P0 快修（低风险，1 批）

> 先固化证据链（防自愈时基线漂移），再清 3 条死引用；三份 omlx 副本只开票。

| # | 文件 | 改什么 | 风险 |
|---|---|---|---|
| 1a | （只读存档） | `omlxc status --json`、`doctor --direct --json`、`nodes list`、`models list --json` 输出存档到 worktree `docs/reports/`（ephemeral，完成后按 T6-17 归档） | 无 |
| 1b | `bin/gac/gac-compute-onboard.py:193-194` | `omlxc cluster` / `omlxc gw status`（实测 exit 2）→ `omlxc status --json` + `omlxc nodes list` | 低 |
| 1c | `.agents/skills/nextgen-cognitive-mesh/SKILL.md:50-52` | `omlxc fabric mesh *`（不存在）→ 实际 fabric 子命令（inspect/triage/vram/warm/compact/snapshot/speculative-eval/dma/replay 9 个之一）或 `cockpit mesh` 透传 | 低 |
| 1d | `projects/omlxc/src/omlxc/cli_presenter.py:180` + `projects/omlxc/tests/unit/test_cli_presenter.py:176` | 错误指引 `omlxc models resolve` → `omlxc resolve`（cli.py:427）；同步改测试（子模块三步走） | 低 |
| 1e | 三份漂移 omlx 副本 | **只开票不动手**：仓内 `projects/omlxc/bin/omlx`、`~/omlx/bin/omlx`（`gateway.py:471` 调用）、`/Volumes/Model/omlx/bin/omlx`（`api_compute.py:191 OMLX_BIN` 调用，为 2026-08-10 迁移前旧副本）。涉及运行时热路径，单独窗口处理 | **高** |

**验证**
```bash
grep -n "omlxc cluster\|omlxc gw status" bin/gac/gac-compute-onboard.py   # 空
grep -n "omlxc fabric mesh" .agents/skills/nextgen-cognitive-mesh/SKILL.md # 空
grep -n "omlxc models resolve" projects/omlxc/src/omlxc/cli_presenter.py  # 空
cd projects/omlxc && uv run pytest tests/unit/test_cli_presenter.py -q
make gac-local-gate
```

---

## Phase 2 — 模型 inventory 自愈（中风险，先诊断后动手，2 批）

> **纪律：根因未明禁止直接跑写操作。**

### 2A 诊断（只读，零风险）
```bash
omlxc status --json
omlxc doctor --direct --json | tee /tmp/omlxc-doctor.json
omlxc models list --json > /tmp/models-before.json    # 26/38/20 基线
omlxc nodes list --json
omlxc fabric inspect
tail -n 50 ~/.config/omlxc/watchdog.log
python3 -m json.tool projects/omlxc/conf/models.json > /tmp/conf-models.json
```
**三问必须有答案再进 2B**：
1. mbp-omlx-app 的 3 个模型：后端下线了，还是 placement 名漂了？
2. mbp-lm_studio 15/15 全 mismatch：baseline 45→1 是否 stale placement？
3. conf 33 声明 vs 可用 20：差的 13 个是 intentional disabled 还是孤儿声明？

### 2B 自愈（写操作，双风险门）
- 门①：2A 三问有答案 + 基线 JSON 已存档
- 门②：worktree 内操作 + `models list` diff 预览

| 顺序 | 操作 | 期望 | 回滚 |
|---|---|---|---|
| 1 | `omlxc models reconcile`（按 doctor 建议逐 placement） | 消除 model_mismatch | diff 写前 `/tmp/models-before.json` 逐条 restore |
| 2 | 后端确实不服务的 3 模型：摘除 placement 或重启后端恢复 | mbp-omlx-app 失败项清零 | 摘除记录落日志，可重加 |
| 3 | `omlxc models sync-parameters`（仍需时） | conf 与实际收敛 | 先备份 `conf/models.json` |
| 4 | `omlxc models load …`（最后手段） | 拉起 7 个不可用模型 | unload |

**验证**
```bash
omlxc doctor --direct --json        # 期望 0 失败
omlxc models list --json > /tmp/models-after.json && diff /tmp/models-before.json /tmp/models-after.json
omlxc status --json                 # inventory_drop 清零或可解释
tail -n 20 ~/.config/omlxc/watchdog.log   # 不复报同 7 模型
```
**回滚总原则**：任何一步 doctor 比写前更差 → 立即停，用写前 JSON 存档恢复。

---

## Phase 3 — P1 CLI 契约一致性（低-中风险，2 批，全在 `projects/omlxc` 子模块）

### 批 3a（契约修复）
| # | 文件 | 改什么 |
|---|---|---|
| 1 | `src/omlxc/cli.py:211,240` | `schema_version` 字符串 `"1"` → 统一 int `1`（与 `cli.py:264,288`、`daemon/__init__.py:45` 对齐）；同步查消费方双分支解析 |
| 2 | `src/omlxc/cli.py:1248-1252` | 删除 benchmark 顶层死桩（与 `cli.py:115/126` 分组同名注册竞态） |
| 3 | `src/omlxc/cli.py:1882-1930` | `fabric snapshot` 非法 action 补 else → 报错非静默 exit 0 |
| 4 | `src/omlxc/cli.py:1976-1979,2033` | `fabric dma/replay` 的 `Path.cwd()` → 固定配置解析（违 README socket-only 边界） |
| 5 | `src/omlxc/cli.py:918,922` | `jobs watch` 错误输出跟随 `--output` 而非强制 JSON |

### 批 3b（帮助文本覆盖）
- 44 个子命令补 docstring（重点：`doctor`、`nodes.*`、`benchmark.*` 实测 --help 空行）
- `--json` help 统一 `help="Emit versioned JSON."`（现状 2/45，对齐 `cli.py:416,430`）
- `--yes` help 统一（现状 4/16）

**验证**
```bash
cd projects/omlxc && uv run pytest -q          # 全量单测
uv run omlxc status --json | python3 -c "import sys,json; assert isinstance(json.load(sys.stdin)['schema_version'], int)"
uv run omlxc doctor --direct --json | python3 -c "import sys,json; assert isinstance(json.load(sys.stdin)['schema_version'], int)"
uv run omlxc fabric snapshot bad-action; test $? -ne 0   # 不再静默成功
uv run omlxc doctor --help                     # 有描述
make omlxc-lint                                # ruff + pyright strict
```

---

## Phase 4 — P2/P3 入口收敛 + 文档卫生（低风险，2-3 批，主仓为主）

### 批 4a（入口收敛）
| # | 文件 | 改什么 |
|---|---|---|
| 1 | `Makefile:82-83,95-96,222-223` | 三组双别名保留一套，另一套转 deprecation 注释（fabric-inspect/omlxc-fabric、fabric-bench/omlxc-benchmark、test-omlxc/omlxc-test） |
| 2 | `projects/cockpit/src/cockpit/commands/mesh.py:35-132` | umbrella 拆分：`fabric/triage/vram/warm/compact` 已由 `cockpit omlxc` 委派覆盖 → 只留无独立 CLI 的能力（nodes/status/route/hud） |
| 3 | `projects/cockpit/src/cockpit/_subcommands.py:561 vs 1063` | `cockpit mesh` vs `cockpit compute mesh` 改名消歧；`fabric-mesh` deprecated 桩（:161）评估移除 |
| 4 | 三份 omlx 副本（承接 1e 票） | 单独立项：以仓内为唯一源，先修 `api_compute.py:191` 指旧副本，再收敛 gateway 调用；`bin/omlx:2673` `prog="omlxc"` 命名矛盾一并处理（参考 spec `2026-08-11-omlxc-local-compute-hub-redesign.md:148` 退役计划） |

### 批 4b（文档/注册表卫生）
| # | 文件 | 改什么 |
|---|---|---|
| 1 | 版本口径 | 统一：`pyproject.toml:9`=3.4.0 为 semver 真源；`SKILL.md:14` v5.2.0 与 `dma_daemon.py:238` V5.0 标为 ADR 代号或对齐；`docs/project-registry.yaml:165` 3.0.15 → 3.4.0 |
| 2 | `docs/CLI-REFERENCE.md` | 补 `omlxc` 条目（现 0 条）；`cockpit mesh` 描述由 "nodes/route/serve" 改为实际 20 子命令 |
| 3 | `bin/README.md` | 补 `omlxc-node-wakeup.py` 条目 |
| 4 | `projects/omlxc/docs/ARCHITECTURE-FABRIC.md:64-71` / `projects/omlxc/AGENTS.md:19-20` | fabric CLI 表 4/5 → 9 个补齐 |
| 5 | `.omo/_truth/registry/services.yaml:112,137` | `config_source` 失效路径 `projects/omlxc/packaging/` → 实际 `projects/omlxc/launchd/`；消解 `ports:[7432]` 与 notes 矛盾；dma_daemon enabled=false 与 ADR-0439 声明对齐（或在 skill/手册标注当前未启用） |
| 6 | `projects/cockpit/docs/command-audit/omlxc.yaml` | 完成首次审计（`last_audited: null`，16 维度全空） |
| 7 | ADR/引用卫生 | ADR-0433/0434/0436/0439 frontmatter archived vs 正文 ACCEPTED 矛盾；`capability-registry.yaml:1453` hud 误标 ADR-0435；README:184 悬空引用；failover spec 声称的 `dataplane/failover.py` 不存在（实际在 `orchestrator.py:672`）；MOF `COMP-WS-omlxc.yaml` layer L2 vs registry L1 |

### 批 4c（观测盲点，可选增强）
- `health_snapshots` 0 行：查 daemon 为何不落库（代码 bug 或表废弃），修复或文档声明废止
- `status-history.log` 停更 16 天：查 full-status.sh 周期任务是否断供（cron/launchd）
- `routes show` E100 / `benchmark report` E900：修复或从命令树移除
- 卡住的 jobs（progress=0.2）：`jobs cancel` 清理（写操作，单独确认）

**验证**
```bash
make gac-local-gate && make ci-local
python3 bin/gac/check-mcp-bos-uri-completeness.py --warn
grep -rn "omlxc fabric mesh\|omlxc cluster\|omlxc gw " docs/ .agents/ bin/   # 空
make fabric-inspect                                     # 单一别名仍工作
```

---

## 排期与并行

| 批次 | 内容 | 依赖 | 可并行 |
|---|---|---|---|
| B1 | Phase 1（1a-1d） | 无 | 与 B4 并行 |
| B2 | Phase 2A 诊断 | 无 | 独立 |
| B3 | Phase 2B 自愈 | B2 三问有答案 | 独立（写操作独占） |
| B4 | Phase 3（3a+3b） | 无 | 与 B1 并行（子模块 worktree） |
| B5 | Phase 4a+4b | B1 完成（避免引用回改） | 4a/4b 可并行 |
| B6 | Phase 4c + omlx 副本收敛票 | B3 完成 | 单独立项 |

**建议执行顺序**：B2（诊断，10 分钟只读）→ B1+B4 并行 → B3（自愈）→ B5 → B6 按需。

## 风险判断摘要

| 建议做 | 只开票不动手 |
|---|---|
| Phase 1 死引用快修（3 条实测失败） | 三份 omlx 副本收敛（运行时热路径） |
| Phase 2 诊断 2A（纯只读） | cockpit mesh umbrella 拆分（影响面大，单独评审） |
| Phase 3 契约修复 + 测试护航 | ADR 状态批量翻转（治理流程，需走 governance） |
| Phase 4b 文档卫生 | health_snapshots 落库修复（先定位根因再定方案） |
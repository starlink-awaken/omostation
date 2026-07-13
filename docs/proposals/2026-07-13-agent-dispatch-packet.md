# Agent 派单指令包 · Track A 执行

> 日期: 2026-07-13 · 用法: 每段是一份自包含指令，直接复制给对应 agent。
> 全局护栏（所有 agent 适用）:
> - 不直接写 `.omo/` 或 `spaces/`——受治理状态一律走 `omo` CLI/MCP broker 或 c2g ingress。
> - 未经明确确认不 commit / push / reset / 移动子模块（见 AGENTS.md §6）。
> - 一次只动一个子模块，改完在该子模块内闭环，避免 submodule dirty（P60 坑）。
> - 报"不存在/零实现"前必须实证交叉验证（P73/verify-claim-three-layers），勿凭路径直觉。
> - 派单顺序: **先 A3-step1（重扫，纯读）→ A2 / A3 / A4 可并行 → A5 结项**。

---

## 指令 1 · A3 首步：活体健康重扫（最先做，纯读，解阻一切）

**Profile**: `project-code-change` ｜ **依赖**: 无 ｜ **预计**: 0.5 天

**前置阅读**: `docs/proposals/2026-07-13-A3-daemon-health-findings.md`

**目标**: 当前 `health.yaml` 是 7/09（ADR-0179 修复前）数据、`system_health.yaml` 陈旧 ~11 天。跑一次活体健康投影，拿到 ADR-0179 修复后的真实在线率数字，并修好采集管道。

**步骤**:
1. 触发活体健康扫描 + 投影刷新:
   ```bash
   uv run --project projects/omo omo state sync --json
   uv run --with pyyaml python bin/compass_radar.py    # 重生成 .omo/state/health.yaml
   ```
2. 诊断 7/12 weekly-daemon-summary 的 `rollout_returncode:1 / fallback_used`（源: `runtime/omo/_delivery/audit-rollout/2026-07-12-weekly-daemon-summary.json`），定位 audit-rollout 管道 primary 失败根因并修复。
3. 记录重扫前后的 `service_online_ratio`、`health_score`、runtime 贡献分对比。

**验收**:
- `health.yaml` `generated_at` 为今天，`service_online_ratio` 为活体实测值。
- audit-rollout 连续跑 2 次 `returncode:0`（无 fallback）。
- 产出一页对比: 修复前 vs 修复后的健康分项。

**注意**: 修好探测器后在线率可能**短期下降**（agora-gateway 日志 heartbeat 陈旧，活体校验可能判 degraded）——这是正确的，别为凑数把它改回 PID 判定。

**启动**:
```bash
uv run --with pyyaml python bin/agent-workflow.py start project-code-change \
  --profile project-code-change --objective "A3-step1 活体健康重扫 + 修 audit-rollout 采集管道"
```

---

## 指令 2 · A3 主体：注销 hermes-gateway（决策已定）

**Profile**: `project-code-change` + 一次真机 launchctl ｜ **依赖**: 指令1 完成后 ｜ **预计**: 0.5 天

**前置阅读**: `docs/proposals/2026-07-13-ADR-draft-hermes-deprecate-and-gac-probe-rules.md`（决策 1）

**目标**: hermes-gateway 是遗留孤儿 daemon（工作区外 `~/.hermes/`、无端口、exit 113、不在调度契约）。已决策**注销不修复**，让在线率反映真实服务全绿。

**步骤**:
1. 真机停并注销 launchd（需用户在其机器执行/授权）:
   ```bash
   launchctl bootout gui/$(id -u)/ai.hermes.gateway 2>/dev/null || true
   mkdir -p ~/.hermes/archived-plists
   mv ~/Library/LaunchAgents/ai.hermes.gateway.plist ~/.hermes/archived-plists/ 2>/dev/null || true
   ```
2. `projects/runtime/scripts/service-ctl.sh`: 删 `LAUNCHD_SERVICES` 里 hermes 行(:31) + usage 服务名(:16)。
3. 经 omo broker 清引用（**勿手改 .omo**）: `system.yaml:201`、`projects/omo/.omo/registry/*capabilities.yaml` 的 `cap:hermes-gateway`、`projects/runtime/src/runtime/i0.py:38` 的 `"hermes-gateway":"I0"`。
4. 重跑指令1 的扫描确认 hermes 消失。

**验收**:
- `bash projects/runtime/scripts/service-ctl.sh list` 不再列 hermes。
- 活体扫描后在线率不含 hermes，且无孤儿告警。
- 无残留 `cap:hermes-gateway` 引用（`rg hermes-gateway` 仅剩历史 ADR/pattern 文档）。

**启动**:
```bash
uv run --with pyyaml python bin/agent-workflow.py start project-code-change \
  --profile project-code-change --objective "A3 注销孤儿 daemon hermes-gateway"
```

---

## 指令 3 · A2：修复剩余 5 条 BOS resolve 断层

**Profile**: `project-code-change` ｜ **依赖**: 无（可与 A3 并行）｜ **预计**: 2-3 天

**前置阅读**: `docs/proposals/2026-07-13-A1-bos-gap-audit-findings.md` + `artifacts/bos_resolve_audit.csv`

**目标**: A1 已确认真实断层仅 5 条，修复方向已定。

**步骤**:
1. **4 条声明改写**（低成本）: `core-models` schema/validate + `health-profile` query/update 的包只有 `__main__.py` 无 `cli.py`。在 `projects/agora/src/agora/mcp/resolver/services.py`（及 `etc/bos-services.yaml` 若一致）把 `-m core_models.cli <action>` 改为 `-m core_models <action>`，`health_profile` 同理；先确认 `__main__.py` 接受该 action 参数，否则补 `cli.py` 薄封装。
2. **1 条真缺口**: `bos://governance/protocols-layer/trigger` 在 kairon 无对应包 → **先 deprecate/标 UNIMPLEMENTED 止血**（改 description 加 `[UNIMPLEMENTED]` 或从 registry 移除），能力实现另立项。
3. **收口（关键）**: 对 A1 判为 OK 的 43 条**抽样跑真实 `uv run` 活体 resolve**，把"静态可解析"升级为"活体通过"。注意 ADR-0179 §5 提到"19 backend 在 MCP 握手层 disconnected"——这批与本任务是同一鸿沟的两面，一并归类。
4. 核对 `etc/bos-services.yaml`（运行时真源）与 `services.py` fallback 是否一致。

**验收**:
- 5 条断层清零或正确标注。
- 活体 resolve 抽样通过率 ≥95%（去掉设计性 UNIMPLEMENTED）。
- 新增回归测试锁定；`test_default_registry_is_valid` 转 green（顺带修 ADR-0179 §5 提的 3 个 kos 服务 drift）。

**启动**:
```bash
uv run --with pyyaml python bin/agent-workflow.py start project-code-change \
  --profile project-code-change --objective "A2 修复 5 条 BOS resolve 断层 + 活体收口"
```

---

## 指令 4 · A4：注册两条探测真实性 GaC 规则（决策已定）

**Profile**: `governance-state-mutation` ｜ **依赖**: 无 ｜ **预计**: 1 天

**前置阅读**: `docs/proposals/2026-07-13-ADR-draft-hermes-deprecate-and-gac-probe-rules.md`（决策 2）+ ADR-0179 §4

**目标**: governance-team owner 已批准 GaC 冻结豁免。把 ADR-0179 §4 起草的两条规则正式落地。

**步骤**:
1. 把 ADR 草案正式编号（下一个可用 ADR 号）入 `.omo/_knowledge/decisions/`，走 ADR 流程 + 更新 INDEX。
2. 经 broker 向 `.omo/_truth/registry/governance-checks.yaml` 追加两条 checker（YAML 见 ADR 草案决策 2，`lifecycle: draft`）。
3. 更新 freeze 块: `max_rules: 173→175`，加 `exemptions` 留痕（adr 号 / date / rules / approver）。
4. 实现两个 checker 薄封装（复用 `projects/runtime/src/runtime/scheduler.py` 已有的 `_check_launchd` / `_check_log_freshness` 交叉校验逻辑），类名 `RuntimeProbeTruthChecker` / `DeclExecConsistencyChecker`。

**验收**:
- 两条规则在 registry 中 `lifecycle: draft`，`max_rules:175` 且 exemptions 有记录。
- checker 可被 GaC 执行（`bin/gac-local-gate.py` 能加载不报 ghost_rule）。
- 7 天后由 radar 验证执行 → 自动转 active（或验证不过回退）。

**启动**:
```bash
uv run --with pyyaml python bin/agent-workflow.py start governance-state-mutation \
  --profile governance-state-mutation --objective "A4 注册 RUNTIME-PROBE-TRUTH + DECL-EXEC-CONSISTENCY 规则"
```

---

## 指令 5 · A5：Track A 结项验证（最后做）

**Profile**: `governance-audit` ｜ **依赖**: 指令 1-4 全部完成 ｜ **预计**: 0.5 天

**目标**: 确认"绿色变真"，给 Track B 立项一个可信地基。

**步骤**:
1. 复跑活体健康扫描 + BOS 全量 resolve，记录最终 `service_online_ratio`、resolve 通过率、health runtime 贡献分。
2. 确认: 真实服务全绿、resolve ≥95%、两条探测规则在 draft、audit-rollout 稳定 returncode:0。
3. 写结项复盘（一页），作为 B1 立项依据。

**验收**: 结项复盘归档；健康分为**可信**值（即便数字比虚高的 84 低，也是真的）。

**启动**:
```bash
uv run --with pyyaml python bin/agent-workflow.py start governance-audit \
  --profile governance-audit --objective "A5 Track A 结项验证"
```

---

## 派单节奏建议

```
第1批（立即，可并行）:  指令1(重扫) · 指令3(A2) · 指令4(A4)
第2批（指令1后）:        指令2(注销 hermes)
第3批（1-4 全绿后）:     指令5(A5 结项) → 解阻 Track B
并行全程:               C1 治理过度工程审计（纯读，不入本批，见规划文档）
```
每个 workflow 走完整生命周期: `start → claim <run-id> --path <路径> → verify <run-id> --from-diff --execute → closeout <run-id>`。

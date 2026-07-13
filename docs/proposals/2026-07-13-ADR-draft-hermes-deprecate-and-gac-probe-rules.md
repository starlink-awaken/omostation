# ADR 草案 · hermes-gateway 注销 + GaC 探测真实性双规则解冻

> 状态: **DRAFT（待正式编号并入 `.omo/_knowledge/decisions/`）** · 日期: 2026-07-13
> 决策人: governance-team owner（已口头批准本草案两项决策）
> 依据: ADR-0179（探测假阳性治本）· ADR-0178/P79（GaC 173 冻结）· A1/A3 诊断报告
> ⚠️ 本草案放在 `docs/proposals/`，正式生效需经 ADR 流程 + broker 写入受治理 registry，勿直接手改 `.omo/`。

---

## 决策 1 · hermes-gateway 注销（deprecate）

### 背景
hermes-gateway 是遗留孤儿 daemon：启动源在工作区外（`$HOME/.hermes/hermes-agent`，launchd label `ai.hermes.gateway`）、无 port 无 health_url、不在 `services.yaml` 调度契约、exit 113 确定性故障、曾自愈死循环 6 天（ADR-0179 已用 `unrecoverable` 终结）。6/28 审计两次标注"需用户决策"。它是把在线率从"真实服务全绿"拉到 60% 的唯一孤儿。

### 决策
**注销，不修复。** 从 launchd + 所有 registry 移除，使在线率反映真实服务全绿态。若未来确需 hermes 能力，另行立项以合规方式（进 `services.yaml` 调度契约 + 配 port/health/log 真活信号）重建。

### 执行清单（派单 profile: `project-code-change` + 一次真机 launchctl 操作）
1. **停并注销 launchd**（你的真机执行，需授权）：
   ```bash
   launchctl bootout gui/$(id -u)/ai.hermes.gateway 2>/dev/null || true
   # 归档 plist（勿直接删，留可回滚锚点）
   mkdir -p ~/.hermes/archived-plists
   mv ~/Library/LaunchAgents/ai.hermes.gateway.plist ~/.hermes/archived-plists/ 2>/dev/null || true
   ```
2. **从 `service-ctl.sh` 移除**：删除 `LAUNCHD_SERVICES` 里 `"hermes-gateway|ai.hermes.gateway|—|$HOME/.hermes/hermes-agent"` 行 + usage 里的服务名（`projects/runtime/scripts/service-ctl.sh:16,31`）。
3. **清 registry/state 引用**（经 omo broker，勿手改）：
   - `.omo/state/system.yaml:201`（daemon 列表移除 hermes-gateway）
   - `.omo/state/system_health.yaml`（下次活体扫描自然消失，或 broker 清）
   - `projects/omo/.omo/registry/*capabilities.yaml` 里 `cap:hermes-gateway`（manual/projects 两处）
   - `projects/runtime/src/runtime/i0.py:38` 的 `"hermes-gateway": "I0"` 映射
4. **验证**：`bash projects/runtime/scripts/service-ctl.sh list` 不再列 hermes；活体健康扫描后在线率反映真实服务全绿。

---

## 决策 2 · GaC 冻结豁免 · 注册两条探测真实性规则

### 背景
ADR-0179 §4 已起草两条规则防"假绿灯"复发，但被 GaC 冻结挡住（`governance-checks.yaml` freeze: `max_rules:173`, `exemption_process: "ADR + governance-team approval"`）。governance-team owner 已批准本豁免。

### 决策
**批准冻结豁免，`max_rules:173→175`，以 `draft` 生命周期注册两条规则**（走 `draft_to_active_days:7` 机制，7 天后由 radar 验证执行后自动转 active——比强行 active 更诚实）。

### 待追加的 checker YAML（追加至 `governance-checks.yaml` `checkers:` 列表，经 broker 写入）
```yaml
  # ── 探测真实性 (ADR-0179 §4, 冻结豁免 2026-07-13) ──
  - id: runtime-probe-truth
    dimension: X4
    name: "运行时探测真实性检查器"
    description: "健康探测禁止仅凭 launchd/docker PID 判 running；必须交叉校验端口监听/HTTP health/日志新鲜度(stdio)，不符降级 degraded"
    module: "runtime.scheduler"        # 治本逻辑已存在 (_check_launchd/_check_log_freshness)
    class: "RuntimeProbeTruthChecker"  # TODO: 薄封装暴露为 checker
    type: python
    severity: high
    enabled: true
    schedule: "daily"
    lifecycle: draft
    created_at: 2026-07-13
    adr_ref: 0179

  - id: decl-exec-consistency
    dimension: X4
    name: "声明/执行一致性检查器"
    description: "system_health.yaml 声明的 port_listening/status 必须与实时 lsof/launchctl 交叉一致，不一致=drift"
    module: "runtime.scheduler"
    class: "DeclExecConsistencyChecker"  # TODO: 实现
    type: python
    severity: high
    enabled: true
    schedule: "daily"
    lifecycle: draft
    created_at: 2026-07-13
    adr_ref: 0179
```

### freeze 块更新
```yaml
  freeze:
    active: true
    since: "2026-07-08"
    max_rules: 175          # 173→175 (ADR-XXXX 豁免 2 条探测真实性规则)
    exemption_process: "ADR + governance-team approval"
    exemptions:             # 新增审计留痕
      - adr: XXXX
        date: 2026-07-13
        rules: [runtime-probe-truth, decl-exec-consistency]
        approver: governance-team
    reason: "P79 治理巩固 — 封顶防规则膨胀"
```

### 落地任务（派单 profile: `governance-state-mutation`，即原 A4）
1. 本草案正式编号入 ADR registry。
2. broker 写入上述 checker + freeze 更新。
3. 实现两个 checker 薄封装（复用 scheduler.py 已有交叉校验逻辑）。
4. 等 7 天 radar 验证 → draft 转 active，或验证不过则回退。

---

## 对 Track A 收口的影响
- **A3**：hermes 注销 + 活体健康重扫 = A3 可收口（在线率变真）。
- **A4**：本 ADR 决策 2 即 A4 的全部内容，已从"设计规则"降为"审批+注册+薄封装"，**现已解阻**。
- **A5 结项**：重扫后确认 runtime 贡献反映真实值，两条规则进 draft，即可结项进 Track B。

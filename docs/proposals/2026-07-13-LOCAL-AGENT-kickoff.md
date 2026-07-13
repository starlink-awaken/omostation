# 本机 Agent 总启动指令 · Track A 收尾

> 用法：在你 Mac 的 `~/Workspace` 里开 Claude Code，把下面 “==== PASTE ====” 之间整段贴进去。
> 它按序执行 A3→A2→A4→A5，每步带验收门，失败即停并报告，不硬闯。
> 依据文档（agent 应先读）：
> - `docs/proposals/2026-07-13-agent-dispatch-packet.md`（原派单）
> - `docs/proposals/2026-07-13-A1-bos-gap-audit-findings.md`（BOS 真实鸿沟）
> - `docs/proposals/2026-07-13-A3-daemon-health-findings.md`（daemon 诊断）
> - `docs/proposals/2026-07-13-A2-corrected-fix-and-cleanup-log.md`（A2 修正 + cli.py shim）
> - `docs/proposals/2026-07-13-ADR-draft-hermes-deprecate-and-gac-probe-rules.md`（hermes + GaC 决策）

==== PASTE ====

你在 omostation 工作区（eCOS v6）。先读 `CLAUDE.md` 的启动协议和 `docs/proposals/2026-07-13-*` 这 5 份文档。护栏：不直接写 `.omo/`（走 omo CLI/broker）；未经我确认不 commit/push/reset；一次只动一个子模块并在其内闭环；报“不存在/失败”前必须实证交叉验证（P73）。按下列顺序执行，**每个 STEP 的验收门不过就停下报告，不要继续下一步**。

STEP 0 · 预检（不改动）
- `git status --short`；确认无 `index.lock`、无野生根目录 `ecos/`（已由上游清理）。
- 列出 7 个子模块 agy 的未提交改动：`for s in agora runtime kairon aetherforge ecos l4-kernel bus-foundation cockpit; do echo "== $s =="; git -C projects/$s status --short; done`。
- 报告给我，等我确认这些改动“留/提交/还原”后再继续。**不要自行提交或丢弃它们。**

STEP 1 · A3 活体健康重扫（拿真实在线率）
- 跑 `uv run --project projects/omo omo state sync --dry-run --json`，记录 `service_online_ratio` / `health_score` / runtime 贡献。
- 再跑正式刷新（非 dry-run）重生成 `.omo/state/health.yaml`；对比重扫前(7/09: 84 / 0.600)与重扫后的数字。
- 诊断并修复 `runtime/omo/_delivery/audit-rollout/2026-07-12-weekly-daemon-summary.json` 里的 `returncode:1 / fallback_used`。
- 验收门：health.yaml `generated_at`=今天；ratio 为活体实测值；audit-rollout 连续 2 次 returncode:0。
- ⚠️ 修好探测器后在线率可能短期下降（agora-gateway 日志 heartbeat 陈旧→degraded），这是正确的，别改回 PID 判定凑数。

STEP 2 · A3 注销 hermes-gateway（决策已定：deprecate）
- `launchctl bootout gui/$(id -u)/ai.hermes.gateway`；`mkdir -p ~/.hermes/archived-plists && mv ~/Library/LaunchAgents/ai.hermes.gateway.plist ~/.hermes/archived-plists/`。
- 从 `projects/runtime/scripts/service-ctl.sh` 删 hermes 行(:31)+usage(:16)。
- 经 omo broker 清引用：`system.yaml` daemon 列表、`projects/omo/.omo/registry/*capabilities.yaml` 的 `cap:hermes-gateway`、`projects/runtime/src/runtime/i0.py:38`。
- 验收门：`bash projects/runtime/scripts/service-ctl.sh list` 不再列 hermes；重扫后在线率不含 hermes；`rg hermes-gateway` 仅剩历史 ADR/pattern。

STEP 3 · A2 先建真值再修（关键：别照静态名单盲补）
- 先对所有 stdio `.cli` 声明跑**活体 resolve** 拿真名单，例：`echo '{"args":[],"kwargs":{}}' | uv run --directory projects/kairon python -m core_models.cli schema`（期望打印 JSON 而非 ModuleNotFoundError）。
- 对每条跑不通的，按 `A2-corrected-fix` 文件里的薄 `cli.py` shim 修（core-models/health-profile 已给模板）。若发现 `.cli` 模式**系统性**跑不通（连 kos 都没 cli.py），停下报告——那要整套重修，不是逐个补。
- `protocols-layer/trigger`（bos-services.yaml:1112）加 `[UNIMPLEMENTED]` 或移除。
- 验收门：活体 resolve 通过率 ≥95%（去掉设计性 UNIMPLEMENTED）；`test_default_registry_is_valid` 转 green；新增回归测试。

STEP 4 · A4 注册两条探测真实性 GaC 规则（决策已定：解冻）
- 把 `ADR-draft-hermes-deprecate-and-gac-probe-rules.md` 正式编号入 `.omo/_knowledge/decisions/` + 更新 INDEX。
- 经 broker 向 `governance-checks.yaml` 追加 `runtime-probe-truth` + `decl-exec-consistency`（`lifecycle: draft`，YAML 见 ADR 草案）；freeze `max_rules:173→175` + 加 exemptions 留痕。
- 实现两个 checker 薄封装（复用 `runtime/scheduler.py` 已有 `_check_launchd`/`_check_log_freshness`）。
- 验收门：`bin/gac-local-gate.py` 能加载不报 ghost_rule；两规则 draft 态。

STEP 5 · A5 结项验证
- 复跑活体健康扫描 + BOS 全量 resolve，记录最终 ratio / resolve 通过率 / runtime 贡献分。
- 写一页结项复盘（存 `.omo/_knowledge/` 经 broker，或 docs/）。
- 验收门：真实服务全绿、resolve≥95%、两规则 draft、audit-rollout 稳定；健康分为**可信**值（哪怕比虚高的 84 低）。
- 全部过 → Track A 收口，可解阻 Track B（2 机状态同步立项）。

每步走 workflow 生命周期：`start <profile> → claim <run-id> --path <路径> → verify <run-id> --from-diff --execute → closeout <run-id>`。落地任何 commit 前先把改动文件清单报给我确认。

==== END PASTE ====

## 备注
- 每个 STEP 的 profile：STEP1/2/3=`project-code-change`，STEP4=`governance-state-mutation`，STEP5=`governance-audit`。
- 若本机 agent 在 STEP0 报告 agy 改动后你要我帮判去留，把它贴回来我来分析。

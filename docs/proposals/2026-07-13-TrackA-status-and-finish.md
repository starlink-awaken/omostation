# Track A · 状态总览 + Mac 收尾（合并版，重建自被清文档）

> 日期: 2026-07-13 · 说明: 前一批 `docs/proposals/*` 被并发 agent 的 `git clean` 清掉，本文件合并重建关键内容。agy 已停，本文件安全。

## 1. 已完成并已提交的工作

| 项 | 状态 | 证据 |
|----|------|------|
| **A1** BOS 鸿沟重审 | ✅ | 真实断层 5 条（非 102）；65 声明 47 OK / 18 UNIMPL / 0 FAIL |
| **A2** resolve 断层修复 | ✅ 已提交并验证 | 见下 |
| **C1** 治理过度工程审计 | ✅ | 见 §3 |
| 工作树清理 | ✅ | 删野生 `ecos/` + 6 个 index.lock + venv lock |

### A2 提交状态（已入库，已验证）
- **kairon**: `core-models/cli.py` + `health-profile/cli.py` (stdio shim) + 2 回归测试 → 在 `main` 的 `c167cc0`（被 agy 误捆进"8766 literal"提交，**功能已入库**；本地 `main == origin/main`）。
- **agora**: protocols-layer 双处 deprecate → 干净提交 `86aa438`，在分支 **`fix/a2-bos-resolve-2026-07-13`**（领先 origin/main 1 commit，待 push+PR）。
- **验证**: 4 个原断层 URI 活体 resolve 通过（真 subprocess，`_reachability: ok`）；`pytest` 4 passed；静态审计 5→0 FAIL。

## 2. 仍需在 Mac 上做的（venv / launchctl / GitHub 凭证，本沙箱无）

### 2a. 完成 A2 的 push + PR 合并
```bash
cd ~/Workspace/projects/agora
git push -u origin fix/a2-bos-resolve-2026-07-13      # 本沙箱无凭证, 你的 Mac 有
gh pr create -t "fix(bos): A2 resolve 断层收口 — protocols-layer deprecate" \
  -b "配合 kairon cli.py stdio shim (c167cc0); BOS resolve 断层 5→0; 回归测试 4 passed"
# CI/gate 通过后合并; 然后回 ~/Workspace bump 子模块指针:
cd ~/Workspace && git add projects/agora projects/kairon && git commit -m "chore: bump agora+kairon (A2 BOS resolve 断层修复)"
# 若 kairon origin/main 尚未真正 push, 先 cd projects/kairon && git push origin main
```
提交前请在 Mac 跑门禁：`make gac-local-gate`（本沙箱 venv 跑不了）。

### 2b. A3 活体健康重扫（拿真实在线率）
```bash
cd ~/Workspace
uv sync --project projects/omo          # 先修我这边搞残的 Linux venv
uv run --project projects/omo omo state sync --json    # 重生成 health.yaml
```
诊断并修 `runtime/omo/_delivery/audit-rollout/2026-07-12-weekly-daemon-summary.json` 的 `returncode:1`。预期：修好探测器后在线率可能短期↓（这是不再造假，正确）。

### 2c. A3 注销 hermes-gateway（决策=deprecate）
```bash
launchctl bootout gui/$(id -u)/ai.hermes.gateway
mkdir -p ~/.hermes/archived-plists && mv ~/Library/LaunchAgents/ai.hermes.gateway.plist ~/.hermes/archived-plists/
```
再从 `projects/runtime/scripts/service-ctl.sh`(:16,:31)、`i0.py:38` 删引用；经 omo broker 清 `system.yaml` + `*capabilities.yaml` 的 `cap:hermes-gateway`。

## 3. C1 审计核心结论（重建）+ A4 修订

GaC 规则注册表 **184 条，超 ADR-0178 冻结 cap(173) 达 11 条 → 冻结机制已失效**。低 ROI 候选：
- **弱牙规则 9 条**（仅 audit/radar 无拦截）：CR-X2-GAC-DRIFT / CR-X1-AGENT-AUDIT / CR-L2-MUTATION-BROKER / M4-HEALTH-SCORE / M4-DERIVED-PLANE-AUDIT / CR-META-METRIC-DEBT-FEATURE / CR-X-PROMOTION-LIFECYCLE / CR-CROSS-REPO / CR-PRINCIPLE-ENFORCEMENT。
- **cross-repo 3 条重叠**（CR-CROSS-REPO-CONSISTENT + CR-CROSS-REPO-CHECK 同 target + draft CR-CROSS-REPO）→ 合并为 1。
- **11 条无 ADR 溯源**；**~100 条 target=None** 无法机械校验；**6 条 draft**(7/08 建, 7/15 将自动转正, 需先确认 radar 验证)。

### A4（决策已定）· 先减后加，不只抬 cap
hermes deprecate + 注册两条探测真实性规则（ADR-0179 §4 已起草：`runtime-probe-truth` + `decl-exec-consistency`），但**别只 173→175**：
1. 先减：cross-repo 三合一(-2) + 冻结确认无用弱牙(≥-1)。
2. 后加：2 条探测规则(+2)。
3. 净额 184-3+2=**183**，cap 校准到真实净额并恢复执行。
→ 一次达成 A4 + C1 + Track C 减负纪律。落地经 `governance-state-mutation` broker（需 venv，Mac 做）。

## 4. 待你决定 · agy 遗留的未提交改动
agy 在 agora 留了 `bos_middleware.py`（限流/熔断埋点）、`server/mcp.py`、`commands_a2a.py` 未提交（看着是正经可观测性改动）。我没动它们。请决定：各自子模块内闭环提交，还是还原。

## 5. 收口路径
A2 push+PR 合并 → A3 重扫+hermes → A4 先减后加 → A5 结项验证（健康分变**可信**）→ 解阻 Track B（2 机状态同步）。

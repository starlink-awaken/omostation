---
status: active
lifecycle: history
owner: governance-team
last-reviewed: 2026-08-07
related:
  - ../patterns/delegation-infra-diagnosis-pattern.md
  - ../../plans/delegation-infra-reliability.md
  - ../../../docs/operations/delegation-infra-config.md
type: ephemeral
status: archived
---

# delegation-infra-reliability 复盘 — 2026-08-07 子代理委托基础设施系统性故障（P4b 知识固化）

> **触发**: omni-bus-phased-program 会话执行期间暴露 11 路子代理委托全灭 → 用户导向配置层诊断 → 三层根因定位 → 修复 → 全会话 8/8 完成
> **方法**: 配置优先诊断（opencode.json → curl 端点冒烟 → 网关路由对照 → 工具化校验）+ 直接测量终裁（P78 三维查证精神）
> **结论**: 委托故障根因 = 账户层 + 注册层 + 网关路由层三层叠加，另发现调度器为 opencode.json 权威写入者；"只叙述不落盘" 是模型路由故障强信号，非模型偷懒；治本固化为 runbook（P3a）+ 预检工具（P2）+ 本复盘（P4b）
> **计划**: [delegation-infra-reliability](../../plans/delegation-infra-reliability.md)（worktree `work/delegation-infra-reliability`，P1–P4 分阶段）
> **配套**: [诊断 runbook](../patterns/delegation-infra-diagnosis-pattern.md) · [配置 SSOT](../../../docs/operations/delegation-infra-config.md)

---

## 1. 时间线（Timeline）

| # | 阶段 | 事件 |
|---|------|------|
| 1 | **规划（planning）** | omni-bus-phased-program 会话早期，子代理委托出现系统性故障；用户据此立项 `delegation-infra-reliability` 计划（.omo/plans/），分 P1（路由 SSOT 化）/ P2（预检门禁）/ P3（runbook + 机制硬化）/ P4（BOS compute 域登记 + 知识固化）四阶段，全部在 worktree `work/delegation-infra-reliability` 开发。 |
| 2 | **执行（execution）** | 按阶段交付：P1a 别名双向校验工具、P1b mid-local/triage 路由决策（期间发现调度器覆盖）、P1c 配置修复态固化文档、P2 delegation-preflight 预检工具、P3a 诊断 runbook、P3b 机制硬化文档、P4a BOS compute 域登记；omni-bus-phased-program 交付物同步推进。 |
| 3 | **11 路委托失败** | subagent 委托 11 路全灭——`unspecified-high`×2、`quick`、`general`、`coder`、`scribe`、`Anvil`、`Forge`、`Engineer`、`executor`、`senior-engineer-p7`；症状三类：**只叙述不落盘** / **Insufficient Balance** / **30min 超时**。初期反应为盲目换 category 重试（11 次无效，浪费整个会话）。 |
| 4 | **用户导向诊断（user-directed diagnosis）** | 重试无效后，用户导向改为**配置优先诊断**：先读 opencode.json provider + agent 绑定，再 curl 目标模型端点冒烟，再对照网关 litellm-config.yaml 路由，最后工具化确认。 |
| 5 | **三层根因（3-layer root cause）** | ① 账户层：explore/reviewer/scribe 显式绑定 `opencode-go-b/deepseek-v4-flash`（备用 provider 余额不足）→ Insufficient Balance；② 注册层：`omlxc/triage` 模型未注册 → Model not found；③ 网关路由层：opencode 别名 `mid-local`/`triage` 不在 litellm-config.yaml model_list → 动态路由/空响应 → **只叙述不落盘的直接原因**。 |
| 6 | **修复（fix）** | `provider.omlxc.baseURL` → 127.0.0.1:8092（本机 mlx_lm）+ agent 模型绑定 → `deepseek/deepseek-v4-flash`（云，有余额）→ scribe 路由恢复可用。随后发现**调度器即权威**：`~/.config/opencode/` 是 git 仓库，`scripts/model-scheduler.sh`（launchd，PEAK/OFF-PEAK）定时重写 opencode.json，手动修复在下一次切换时被覆盖（已实测）——手动修复态须记录为瞬时态，而非持久配置。 |
| 7 | **全部完成（full completion）** | omni-bus-phased-program 8/8 交付完成，F1–F4 全部 APPROVE；delegation-infra-reliability P1a/P1b/P1c/P2/P3a/P3b/P4a 落地；P4b（本复盘 + learnings 补充）为计划收尾。 |
| 8 | **后续计划（follow-up plan）** | 本计划 `.omo/plans/delegation-infra-reliability.md` 内剩余项：preflight 集成进 start-work 技能；调度器模型池编辑属专门任务（超出默认 scope）；新会话开工前跑 preflight，委托故障在开工前暴露。 |

## 2. 根因分析（Root Cause Analysis）

### 2.1 三层分类（3-layer taxonomy，全部实测命中）

| 层 | 症状 | 根因 | 2026-08-07 案例 |
|----|------|------|-----------------|
| **账户层** | `Insufficient Balance` / 402 / 余额错误 | agent 模型绑定到无余额的 provider | explore/reviewer/scribe 绑 `opencode-go-b/deepseek-v4-flash`（备用 provider 余额不足） |
| **注册层** | `Model not found: omlxc/triage` | 模型别名未在目标端点注册 | `omlxc/triage`、`omlxc/mid-local` 在网关 `model_list` 无路由 |
| **网关路由层** | 子代理"只叙述不落盘"（narrate but never edit） | 端点返回**空 content**——网关无路由 / 路由到无响应后端 | opencode 有别名但 litellm-config.yaml 无对应路由 → 请求发出后无路可走 → 空 content |

**关键判读**：
- **"只叙述不落盘" = 模型路由故障强信号**（空 content / 错误端点），不是模型偷懒、不是换 category 能解决的——本次重试 11 次无效，浪费整个会话。
- **"模型名出现在 `provider.omlxc.models`" ≠ 可用**——路由注册 + model 字段兼容是两道独立门槛。
- 别一上来就重试子代理；先跑配置层诊断（见 runbook §2 顺序），再动手。

### 2.2 调度器即权威（scheduler-as-authority discovery）

P1b 执行期实测发现并纠正归属：

- `~/.config/opencode/` 是 git 仓库；**权威写入者是 `scripts/model-scheduler.sh`**（launchd `com.omo.model-scheduler.plist`，每小时 :05 RunAtLoad；PEAK 09–23 → `deepseek/deepseek-v4-flash`，OFF-PEAK → `glm-4.7-flash`），切换时重写 opencode.json model/small_model 与 `~/.omo/omo.jsonc` flash agents，成功即 commit、失败 checkout 恢复。
- **手动改 opencode.json 会被调度器在下一次切换时覆盖**——不是 bug，是机制；手动修复态是**瞬时态**，须在文档/runbook 中记录（`.bak-omlxfix` / `.bak-omlxfix-2022` 备份语义），并在每次调度切换后复查配置存活。
- 端口图（实测）：**8000** = omlx-server（接受 model 字段，但只认真实 id 如 `Qwen3.6-27B-MLX-4bit`；`omlxc/coder` 别名 → not_found）；**8092** = mlx_lm（拒绝 model 字段，opencode 总发 model 字段 → 本地 omlxc/* 对子代理不可靠）；**100.96.126.35:4000** = LiteLLM 网关；8183 = embedding；11434 = Ollama。
- **推论**：当前唯一验证可行的子代理路径是 deepseek 云模型绑定（`deepseek/deepseek-v4-flash`）；`coder` 保留 `omlxc/coder` 属已知例外。

## 3. 什么有效（What worked）

1. **配置优先诊断（重试浪费后转向）**：盲目重试 11 次全废后，用户导向改为先诊断配置层（opencode.json provider → curl 端点冒烟 → 网关路由对照 → 工具化校验），一次定位三层根因。正确第一步是配置层而非重试层。
2. **对每个 worker 的 "done" 声明都做验证**：编排者对 worker 的完成声明逐条核对（diff / 测试 / 落盘实况），多次抓到"声称完成但未落盘/未达 Acceptance"的假完成。
3. **P4 caveat 视为未完成信号**：worker 的 honest caveat（如"没改 cli.py"）被当作**未完成信号**而非可接受让步——编排者据此核对 Acceptance vs 实现缺口，补做 cli.py 注册，CLI 全链路可达。
4. **P3 矛盾用直接测量终裁**：终验波并行读同一文件产生互相矛盾的报告（F3 PASS vs F4 NOT CLOSED），因并发写入 + 时序；编排者亲自 grep 实测（mtime、行数、指标在场）终裁——**编排者实测是唯一终裁**。
5. **治理合规全程**：worktree 隔离开发、不混入 main 侧并发 dirty；文档/代码 lane 分离；doc-ssot-lint 基线 clean；Scope OUT 未突破；交付物与计划逐条对齐。

## 4. 什么失败 / 反模式（What failed / anti-patterns）

1. **配置诊断前 11 次盲目重试**：换 category 重试 11 次全部无效，浪费整个会话——委托故障必须分层诊断（账户/注册/网关路由/调度器），不盲目重试。
2. **把"只叙述不落盘"当成模型偷懒**：实为模型路由故障强信号（空 content / 错误端点），换 category 无法解决；应识别为配置层问题。
3. **轻信 worker 的 "done" 而未验证**：多次抓到 worker 声称完成但实际未落盘/未达 Acceptance——每个完成声明都必须有 diff/测试/落盘证据。
4. **P4 cli.py scope 缺口**：worker 严格遵守 MUST NOT DO 字面边界（不改 cli.py）却违背计划 Acceptance（完整 CLI 可达）——编排者必须核对 Acceptance vs 实现缺口，不能把 honest caveat 当完成。
5. **（runbook §8 补充）手工对抗调度器**：调度器是 opencode.json 权威写入者，对抗只会引入下一轮漂移——记录行为、工具化守护，而非锁文件。

## 5. 后续计划指针（Follow-up plan）

- **计划**：[`.omo/plans/delegation-infra-reliability.md`](../../plans/delegation-infra-reliability.md)（本计划，status: proposed → 阶段交付后更新）
- **诊断 runbook**：[`delegation-infra-diagnosis-pattern.md`](../patterns/delegation-infra-diagnosis-pattern.md)（P3a，四层症状分类 + 6 步诊断顺序 + 各层修复命令 + 预防 + 端口图）
- **配置 SSOT**：[`docs/operations/delegation-infra-config.md`](../../../docs/operations/delegation-infra-config.md)（P1c 修复后固定状态 + 调度器权威章节）
- **剩余项**：
  - P2 预检工具集成进 start-work 技能（新会话开工前跑 `bin/delegation-preflight.py --json`，委托故障在开工前暴露）；
  - 调度器模型池编辑（`scripts/model-scheduler.sh` / `dynamic-router.py` MODEL_POOL）属专门任务，超出本计划默认 scope；
  - 任何模型配置改动后跑 `bin/delegation-alias-check.py --json`（IN_OPENCODE_ONLY 非空 = 路由缺口，必须修）。

## 6. 验证记录（Verification）

| 检查 | 结果 |
|------|------|
| 本复盘文档 | `.omo/_knowledge/audits/2026-08-07-delegation-infra-reliability-retrospective.md`（新建，格式对齐 sibling audit：frontmatter + 分节） |
| doc-ssot-lint 基线（主工作区，runbook §6 / learnings 记录） | `{ok:true, conflicts:0, files_scanned:173, findings:[]}` |
| 本文件是否进入 lint 扫描 | `.omo/_knowledge/audits/*.md` 不在 doc-ssot-lint SCAN_GLOBS（入口文档 + docs/*.md + projects/* 文档）→ 新增文件不引入新 findings；无 stale pattern（eCOS v5 / 5+3+1 / 7 层 / Python 3.10+） |
| learnings 补充 | `.omo/notepads/omni-bus-phased-program/learnings.md` 追加 P4b 一行 |

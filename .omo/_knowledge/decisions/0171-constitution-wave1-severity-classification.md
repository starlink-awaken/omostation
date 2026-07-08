---
status: ACCEPTED
lifecycle: decision
owner: governance-team
last-reviewed: 2026-07-08
related: [ADR-0106, 宪法-Wave-1, PR-178]
---

# ADR-0171: 宪法 Wave 1 — 治理规则 severity 分层 (red/gray)

## 背景 (Context)

`governance-checks.yaml::gac.rules` 共 171 条规则 (2026-07-08 快照), **全部没有 severity 字段** (0/171).

"宪法体系" (夏提出的红线/灰线) 需要分层:
- 🔴 **红线 (red)**: 阻塞 merge, agent 必须遵守
- 🟡 **灰线 (gray)**: warn/审计, 不阻塞

不分层的问题: `gac-local-gate` / CI gate 对所有 check "一刀切" (scope staged 或 strict), 无法区分"必守红线"和"软性灰线". agent 也不知道哪些规则是底线.

## 决策 (Decision)

**用 executor 推导 severity** (不手动给 171 条加字段, 避免易错):

```python
# 抽取到 bin/gac_severity.py (code-review #1 DRY, gac-drift + gen-agent-redlines 共享)
RED_EXECUTORS = {"hook_pre_edit", "ci_gate"}  # 事前拦 / CI 拦
def derive_severity(rule):
    execs = set(rule.get("executor") or [])
    return "red" if (execs & RED_EXECUTORS) else "gray"
```

### 分类依据

| executor | severity | 理由 |
|----------|----------|------|
| `hook_pre_edit` | red | pre-edit hook 事前拦 (改动前阻止, 最严) |
| `ci_gate` | red | CI 门禁 (merge 前拦, 平台级) |
| `omo_audit` / `gac_local_gate` / `radar_cron` / `evidence_smoke` / `mcp_tool` / `mof_*` | gray | 审计/本地/cron, 不直接阻塞 merge |

注: 一条规则可多个 executor, severity 取"最严" (任一 red executor → red).

## 结果 (Consequences)

- **159 red + 12 gray = 171 rules** (2026-07-08 快照; 并发 agent 持续加规则, 后续会变)
- digest: `docs/generated/agent-redlines.md` (`bin/gen-agent-redlines.py` 生成, gitignored, CI 重生成)
- agent 启动可读 digest 知道 159 条红线

### executor 分布 (推导依据, 2026-07-08)

- ci_gate: 159 (CI 拦 → red)
- omo_audit: 136 (审计 → gray)
- radar_cron: 25 (cron → gray)
- gac_local_gate: 16 (本地 → gray)
- hook_pre_edit: 2 (事前拦 → red)
- 其他: evidence_smoke / mcp_tool / mof_validate / mof_audit (gray)

## Followup

| Wave | 内容 | 状态 |
|------|------|------|
| 1 | severity 推导 + digest + gac_severity 抽取 (code-review #1) | ✅ 本 ADR + PR#178 + PR#200 |
| 2 | `gac-local-gate` 读 severity (red=blocking, gray=warn; `--strict` 全 blocking) | ⏳ 集成点已定位 (`gate_checks` line 115 / `run_gate` line 219) |
| 3 | `hook_pre_edit` 扩展 (更多 red check 事前拦, 非 CI 事后拦) | ⏳ |
| 4 | 本 ADR 固化 severity 分类 (不可变) | ✅ 本 ADR |

## 备选方案 (Alternatives Considered)

- **手动给 171 条加 severity 字段**: 易错 (171 条), 工作量大, 且 severity 跟 executor 语义重复. 拒绝.
- **用 check_type 推导**: check_type 33 种, 比 executor 复杂, 跟"严重度"无直接映射. 拒绝.
- **用 dimension (X1-X4) 推导**: X1-X4 是治理维度 (审计/抗熵/价值/一致性), 跟"严重度"无关. 拒绝.

## 关联

- 脚本: `bin/gen-agent-redlines.py` (PR#178) + `bin/gac_severity.py` 抽取共享 (PR#200)
- code-review 7 findings 全修: PR#200 (regex gap + DRY + 声明面 + GAC_DRIFT_STRICT)
- 配套平台兜底: `AGENT-ISOLATION-ROLLOUT` Phase 3 enforce_admins (PR#178, 堵 admin 绕过)
- 病根: `decl-exec-gap-meta-pattern` (治理规则声明面 vs 执行面鸿沟)

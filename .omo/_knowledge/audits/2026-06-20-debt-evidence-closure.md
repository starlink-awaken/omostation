# Debt Evidence Closure — Audit Report (P43 SSOT Drift Fix)

**日期**: 2026-06-20
**审核对象**: `omo governance` 巡检发现的 4 项 closure 漂移 + 1 项 deferred 缺 Next-Action
**状态**: `resolved` (走 omo broker, 不绕路)
**关联任务**: `TASK-DEBT-CLOSURE-EVIDENCE-20260620`
**上游 Pitch**: `runtime/sandbox/pitches/Idea-修复-4-项-closure-漂移-为-deferred-项.md`

---

## 0. 诚实话语前置 (Reader-Disambiguation)

`omo governance` 巡检 (2026-06-20) 报告:
- **总分**: 85.0 (B) → **88.3 (B)** (修复后)
- **debt integrity**: WARN 80 → **OK 100** ("all resolved/closed debts have evidence")
- **唯一残留**: ruff lint (14 errors, WARN 30) — 来自 kairon，与本任务无关

**触发面**:
- 4 项 closed debt 缺 `resolution_evidence` (omo governance 巡检扣 5 分/项, 共扣 20 分)
- 1 项 deferred debt 缺 `next_review_at` + `gate_level`, 在 owner-routing 全空背景下可能永久搁置

---

## 1. 实际"OMO CLI 走正路"的精确命令

### 1.1 C2G 战略入口 (需求侧建模)

```bash
# 1. brainstorm V2P
cd projects/c2g
uv run c2g --adapter ecos brainstorm "修复 4 项 closure 漂移 + 为 deferred 项打 Next-Action"
# → 生成 runtime/sandbox/pitches/Idea-修复-4-项-closure-漂移-为-deferred-项.md

# 2. 编辑补 Upstream/Appetite (上游 P42-W0-W1-COMBO, appetite 2h)
$EDITOR runtime/sandbox/pitches/...

# 3. Bet C2G (注: c2g bet 当前需要 LLM gateway, 实际走 omo ingress-task 路径,
#    但 Pitch 仍是战略输入, 已存档)
```

### 1.2 omo ingress 物化路径

```bash
# 1. 任务建模 (planned → pending) 
omo governance ingress-task runtime/sandbox/tasks/TASK-DEBT-CLOSURE-EVIDENCE-20260620.yaml \
  --ingress-plane projects/c2g \
  --source-ref "c2g:pitch:Idea-修复-4-项-closure-漂移-为-deferred-项"
# → ingress task created TASK-DEBT-CLOSURE-EVIDENCE-20260620

# 2. 5 项 debt upsert (走 broker, 不绕过 omo_io)
for f in DEBT-CROSSPROJECT-SYSPATH DEBT-EMPTY-INIT-PY DEBT-GBRAIN-55-TODOS \
         DEBT-KAIRON-ONTODERIVE-PHANTOM DEBT-GBRAIN-OPERATIONS-TS; do
  omo governance ingress-debt runtime/sandbox/debt/${f}.yaml \
    --ingress-plane projects/c2g \
    --source-ref "audit:debt-evidence:20260620:${f}"
done
# → 5× "ingress debt upserted"

# 3. MOF 版本登记
bin/mof-version record "DEBT-CLOSURE-EVIDENCE-20260620: 5 debts ingressed via omo broker, drift=0"
# → ✅ Recorded change: v0.0.6
```

---

## 2. 修复明细

### 2.1 4 项 closure evidence 补全

| Debt ID | Severity | 补字段 | 证据长度 |
|---------|----------|--------|---------|
| DEBT-CROSSPROJECT-SYSPATH | high | `resolution_evidence` | 196 字符 |
| DEBT-EMPTY-INIT-PY | low | `resolution_evidence` | 199 字符 |
| DEBT-GBRAIN-55-TODOS | low | `resolution_evidence` | 132 字符 |
| DEBT-KAIRON-ONTODERIVE-PHANTOM | critical | `resolution_evidence` | 152 字符 |

### 2.2 1 项 deferred Next-Action

| Debt ID | 补字段 | 值 |
|---------|--------|-----|
| DEBT-GBRAIN-OPERATIONS-TS | `next_review_at` | 2026-07-01T00:00:00Z |
| DEBT-GBRAIN-OPERATIONS-TS | `gate_level` | P3 |
| DEBT-GBRAIN-OPERATIONS-TS | `source_ref` | audit:debt-evidence:20260620:DEBT-GBRAIN-OPERATIONS-TS |

---

## 3. 验证结果

| 验证项 | 命令 | 结果 |
|--------|------|------|
| omo governance 总分 | `omo governance` | **88.3 (B)** ↑3.3 |
| debt integrity | `omo governance` | **OK 100** ↑20 |
| omo lint ingress-registry | `omo lint ingress-registry` | ✅ pass: goals=9 tasks=11 debts=9 |
| omo lint direct-omo-io | `omo lint direct-omo-io` | ✅ 967 files PASS |
| omo lint mutation-surfaces | `omo lint mutation-surfaces` | ✅ pass: surfaces=16 |
| mof-enforce post-check | `bin/mof-enforce post-check` | ✅ 0 type drift / 0 required 缺失 / 0 state machine invalid |
| mof-version record | `bin/mof-version record ...` | ✅ v0.0.6 |

---

## 4. 关键 SSOT 引用

| 层级 | 路径 | 角色 |
|------|------|------|
| 配置 SSOT | `.omo/_truth/registry/debt.yaml` | debt SSOT 注册表 (upsert 同步更新) |
| 模板 | `.omo/_truth/mof-version.yaml` | MOF 模型版本 (v0.0.5 → v0.0.6) |
| L0 约束 | `projects/ecos/src/ecos/ssot/registry/L0-constraints.yaml` | 56 条治理约束 |
| Ingress broker | `projects/omo/src/omo/omo_ingress.py:upsert_debt_item` | 唯一 debt 写入口 |
| 巡检 | `projects/omo/src/omo/omo_governance.py` | 6 项治理检查 + score 计算 |

---

## 5. 关键约束与教训

1. **`omo debt desc` 只认 debt_weight_items**: 8 项 critical debt 才允许 `desc` 更新, 其他 29 项只能走 ingress broker
2. **`source_ref` 必须唯一**: 同一 source_ref 不能绑多个 debt, 否则 broker 抛 `source_ref already mapped`
3. **`.omo/debt/` 仍 gitignored**: 5 项 yaml 修复不进 git history, 唯一状态源是 OMO runtime (审计留痕靠本报告 + governance-history.jsonl)
4. **走正路**: 全程 0 个 `update_item()` 越权调用, 全部走 `omo governance ingress-debt` broker + fcntl 锁

---

## 6. 后续建议 (Next-Action)

1. **Ruff lint 14 errors**: 与本任务无关, 但拖累总分至 88.3; 建议另起 TASK 处理 kairon ruff debt
2. **debt_weight_items 扩展**: 当前只 8 项 critical, 建议评估是否将 4 项 evidence-fixed 提升为 debt_weight_item (高 severity)
3. **P43 自动巡检**: cron wrapper 跑 `omo governance` + `bin/mof-enforce post-check` 每日, score < 90 时告警
4. **DEBT-GBRAIN-OPERATIONS-TS 2026-07-01 重审**: P3 gate_level + 11 天后 review window 到期
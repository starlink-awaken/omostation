---
schema: md/v1
schema_version: specification/v1
status: accepted
lifecycle: spec
owner: governance-team
last-reviewed: 2026-11-23
accepted: "2026-11-23 Principal 授权「处理吧」（全面授权链）— journey 域 5 张 404 卡根治, autogen 为治理体系自带工具"
bet_id: BET-Y2Q4-T10-351
spec_version: 1.0.0
---

# scene-journey-autogen 数据源分裂修复 — 对齐 docs 体系 + 5 张 404 卡根治

台账：`docs/plans/3y-bet-ledger.yaml` `BET-Y2Q4-T10-351`

## 目标

journey-runner 对 5 张场景卡报 spec FileNotFoundError（404），而治理体系自带的
`scene-journey-autogen` 的 scan/generate/report 全部报告 0 missing——缺口对修复工具
不可见。本 BET 消除该数据源分裂并根治 5 张 404 卡。

## 根因（2026-11-23 实测证据，两层）

**第一层 · autogen 数据源分裂**：
- `SCENES_DIR = .omo/_truth/scenarios/v3`、`JOURNEYS_DIR = .omo/_truth/journeys/v3`
  ——与 journey-runner 实际数据源 `docs/scene-cards/` + `docs/journey-specs/` 完全脱节。
- covered 判定读 `runtime.journey_ref` 子字段——实测 70/70 卡**零张**使用该字段，
  真实挂接字段是顶层 `journey_id`（65 张命中既有 spec，5 张 404）。
- fallback 命名 `journey-<scene_id>` 与实际 spec 命名（`xxx-journey`/`xxx-workflow`）
  从不匹配。

**第二层 · 5 张卡 journey_id 指向不存在的 spec**：
- engineering-delivery → intent-to-evidence（404）
- family-asset-governance → family-financial-audit-workflow（404）
- knowledge-curation → capture-to-retrieval（404）
- research-deep-synthesis → research-deep-synthesis-workflow（404）
- health-gov-doc-cycle → health-gov-doc-cycle（自指 404）

## 修复方案

1. `bin/ssot/scene-journey-autogen.py`：目录常量切换到 `docs/scene-cards/` +
   `docs/journey-specs/`；covered 判定读顶层 `journey_id` 并验证 spec 文件实际存在
   （存在性 = journey_id 命中 JOURNEYS_DIR 的 stem 集合）。
2. 2 张改挂到既有真身 spec（铁证）：
   - engineering-delivery → **meeting-to-delivery**（其 spec steps 明确引用
     `scene: engineering-delivery`）
   - knowledge-curation → **knowledge-capture-pipeline**（全程引用
     knowledge-curation；research-to-insight 亦覆盖，取语义最贴）
3. 3 张欠账（research-deep-synthesis / family-asset-governance / health-gov-doc-cycle）
   用修复后的 `generate` 程序化生成 spec——工具本职设计（从卡面 scene_type/class/
   domain 生成模板状态机），非人工伪造业务语义。
4. 新增 `tests/test_scene_journey_autogen.py` 覆盖：covered 判定读顶层
   journey_id、404 检出、生成 spec 的结构合法性。

## 验证

- `uv run --with pyyaml python -m pytest tests/test_scene_journey_autogen.py -q`
- `uv run --with pyyaml python bin/ssot/scene-journey-autogen.py scan` —— 修复前
  对 docs 体系报 5 missing，数据修复后报 0
- `make journey-validate` —— 新生成 spec 全过校验
- 5 张卡 `journey-runner run --dry-run` 不再 FileNotFoundError

## 回滚

`git revert` 恢复 autogen 与 5 张卡字段；生成的 spec 文件独立可删，无状态迁移。

## 非目标

- 不改 journey-runner 与 shadow-scene-trials 落盘机制（43 张异步型卡的 trial 需
  真实消费者闭环）。
- 不处理 12 张 approval 未确认与 8 张 preflight 缺口。
- 不删除 `.omo/_truth/{scenarios,journeys}/v3` 旧目录（消费方未盘点，只切 autogen
  数据源；circuit_breaker 若发现活跃消费方则停）。

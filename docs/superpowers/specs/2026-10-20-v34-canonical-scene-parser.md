---
schema_version: specification/v1
spec_version: 1.0.0
title: GOAL-04 FIX-01 场景卡解析口径收敛
bet_id: BET-Y2Q4-T10-340401
status: accepted
lifecycle: contract
owner: governance-team
last-reviewed: 2026-10-20
---

# 场景卡解析口径收敛合同

用户已接受本合同的草案范围；接受原话、草案SHA与本次协调者分配记录见[接受记录](../../decisions/accepted/BET-Y2Q4-T10-340401.md)。实现尚未开始，Harness envelope 不替代原生 start/claim。

## 目标与写面

将 review、lifecycle、lineage 的解析收敛到一个纯读取库；保留 scene v1/v2 的既有字段和五档生命周期，不推导运行准入。

候选写面：

- `lib/scene_card_document.py`：共享库，不增加可执行 CLI。
- `bin/ssot/scene-card-review.py`：validate/status/promote 的读取。
- `bin/ssot/scene-card-lifecycle.py`：load/check/transition/activate 的读取。
- `bin/ssot/gen-scene-card-lineage.py`：body选择、scan错误传播。
- `tests/test_scene_card_document.py`、现有 lifecycle 测试及三调用者的定向回归。

以 fresh-main 隔离检出的审查为实施基线；不从 dirty 主区拷贝他人改动。若不需要修改 OMO 子仓源码，则不更新其 gitlink。

## 接口与规则

使用现有 PyYAML SafeLoader，不复制包内手写 YAML 子集解析器。候选接口：

```python
parse_scene_card_document(text, source=None) -> SceneCardDocument
load_scene_card_document(path) -> SceneCardDocument
```

结果保留 body、frontmatter、documents、canonical_index、source_sha256、structure。摘要证明输入字节，不证明准入。读取不得 mkdir、写文件、启动进程、联网或读取 authority。

1. 接受单个 mapping；接受明确的 FrontMatter + canonical body 两文档。
2. 两文档只能有一个正式 scene-card schema；空内容、空 body、非mapping、三文档或歧义报错。
3. 同一 mapping 重复键报错，包含来源、键与位置；嵌套 mapping 同样检查。
4. frontmatter/body 同名身份或状态字段冲突报错，不静默覆盖。受约束字段包括 scene_id、id、lifecycle、lifecycle_tier、status、sensitivity_class、data_class、原生 data_classification、approval_state、activation；值相同的冗余声明允许存在。mapping值作完整语义比较，不把部分mapping自动合并。无关metadata不受此状态字段规则约束。
5. 保留原生 YAML 的无缩进序列、嵌套、URI 标量、引号、注释、block scalar、多行文本等语义，不改变值和类型。
6. 解析与 schema/readiness 验证分离；不强塞包内 title/objective_id 等必填字段。不依据 active/routine 自动产生 ADMITTED_FOR_EXECUTION。

## 调用者与写回兼容性

review 的 required fields、返回格式、生命周期规则保持其既有合同。lifecycle 的 VALID_TRANSITIONS、v2验证、readiness、人工 actor 要求继续生效。lineage 的 catalog 输出不是运行覆盖证明。

promote/transition/activate 写回的业务变更目标仍是 canonical body；保留文档顺序和frontmatter的其他字段值，不能退化为单文档。若frontmatter已经冗余声明了本次获准变更的受约束字段，且旧值与body相等，则同时更新该镜像字段，避免写后形成自相矛盾的合法卡；不新增镜像字段，不更新本次未获准变更的approval/activation等字段。先按原生readiness/actor规则验证变更，再在内存中完成body与既有镜像的更新，重解析验证成功后才写回。测试仅用临时合成卡，不操作真实SceneCard或投影；不承诺保留序列化注释的原始字节。

lineage 遇到解析错误应带来源报错并使生成失败，不能跳过坏卡再生成“成功”投影。真实 research-pipeline 卡存在重复字段的历史线索须在 fresh-main 重新验证；如确认存在，只形成诊断，语义修卡另列审议面，不自动清洗。

## 验证计划与责任

实现者使用临时公开 fixture，独立 verifier 从冻结 diff、代码摘要与原始测试命令开始复核；先调用 `./omo-goal.sh blind-handoff --task FIX-01`。该命令当前硬编码的 probe 结果不计入证据，verifier 需自己执行合法输入和错误输入断言。

| 要证明的行为 | 最小证据 | 限制 |
|---|---|---|
| YAML兼容 | v1/v2、FrontMatter+Body、嵌套、无缩进序列、URI、block scalar、JSON mapping 的字段/类型对拍 | 合成fixture不证明所有真实卡通过 |
| 明确拒绝歧义 | 空/非mapping、单层/嵌套重复键、状态冲突、双schema、三文档，各有断言 | 无攻击链、无生产写入 |
| 三入口一致 | 同一合法卡的scene_id/lifecycle及错误传播对拍 | 不修改现有生命周期准入规则 |
| 写回完整 | 临时卡含body/frontmatter同值lifecycle，shadow→assisted往返后可再次解析且两处一致；无关metadata和非目标文档保持；未声明镜像时不新增 | 不执行生产activate/promote，不扩展状态变更权限 |
| 无隐式副作用 | 纯parser调用不mkdir/写入/联网；临时树逐字节检查 | 不以无git diff代替ignored状态校验 |
| 回归 | `tests/test_scene_card_lifecycle_check.py` 与 `tests/scene_v2/test_scene_card_registry_connector.py` 定向运行；报告共享parser实际模块文件路径，须位于当前检出 | 命令及依赖须按最新仓库核对；避免.pth/PYTHONPATH载入旧main |

所有结果实际产生前均为 NOT_RUN。记录解释器版本、依赖锁、root/子仓SHA、dirty摘要、命令、退出码与日志SHA。不用 chunk 数当 token，不把静态测试称为业务采纳。

## Broker 与治理边界

本 Spec 不修改 Claims Authority、原生数据库、激活态、WorkPacket 或 claim协议；不导入包内 SingleWriterLeaseBroker。WP-101/102 另做现有原生 lease/epoch/幂等与包内候选字段的映射审议。

bootstrap/status/compliance 可能创建 belief目录、自愈孤儿锁或补记 ledger，不能在主区称为“只读检查”。独立审阅副本需自有 `.git`、明确 state 根；生产 Claims Authority 使用 OS account home 定位，改 HOME/root env 不能隔离其 mutation接口。测试只用原生 `connect_for_test` fixture。

## 准入和交付

真实用户接受与本次协调者分配见接受记录；不借已done BET，不将URI格式当作接受证据。接受绑定经原生检查后：safe-insert dry-run→入册及ledger lint→原生start --profile/--bet→affected graph回执→claim→实施→定向测试→blind handoff→独立核验。

准入entry使用本次已分配ID、T10-TOOLING/Y2Q4及本合同真实摘要绑定；engineering=NOT_STARTED、operational/value=NOT_PROVEN。正文范围不因接受而改变；源码实施仍须真实start/claim。本轮不commit/push。

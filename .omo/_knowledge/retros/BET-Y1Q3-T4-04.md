---
status: active
lifecycle: entry
owner: auto-fix-loop
last-reviewed: 2026-08-29
type: ephemeral
status: archived
---
# BET-Y1Q3-T4-04 Retrospective — Product P0 WP4 Principal Authority Binding

- date: 2026-08-29
- bet: BET-Y1Q3-T4-04 (T4-OUTCOME, L3, 3d, human_gate, value_indicator_policy=false)
- status: engineering VERIFIED (三仓 merge + 三指针 bump + 174 测试 + 三端 canary)

## 三仓交付 (spec §5 child-first)

| Phase | 仓 | PR | 内容 |
|-------|-----|-----|------|
| 1 | omo | #116 (并行 agent) | PrincipalAuthorityReceipt + digest_receipt (不变字段重放锚) + 拒绝矩阵 |
| 2 | cockpit | #91 (老王) | extract_authority_fields 严格透传 (不构造不补全, secret 形态入口拒) |
| 3 | agora | #43 (老王) | invoke principal_authority 参数, shape 非法 → adapter 零调用, digest 转发 |

## 验证

- 三仓 verify: 80 + 59 + 35 = **174 测试全绿** (CI 等价环境)
- 三端 canary: OMO digest_receipt 产出 → Cockpit 透传保真 → Agora envelope digest 绑定 ✓
- 拒绝矩阵: missing/incomplete/unconfigured/mismatch/wrong-ref → 全部 decide 前拒, provider 零调用

## 撞车与协作 (诚实记录)

- 老王独立实现 Phase 1 (77 测试) 推 PR #115 后发现并行 agent #116 已先合 main 且
  设计更完整 → 关闭自己 PR, 77 测试作为交叉验证, 基于 main 接力 Phase 2/3
- 避坑: 多 agent 并行同一 BET 时, **先查 main 最新 commit 再动手**

## 过程事故自纠

1. 两轮脚本手滑产出垃圾代码 (pyright/运行时抓到)
2. 替换吞掉 start_receipt 函数头 (AST 骗过, 运行时 NameError 抓到)
3. digest 初版覆盖 verified_at 违反重放锚语义 (测试抓到)
4. agora 校验块写入脚本中途崩溃导致转发引用悬空 (NameError 抓到)
5. 本地 ecos 版本 vs CI pin 版差异造成 22 假失败 (P73 D1 环境探针坑)

## 剩余 (人到场)

- ~~spec 验收 4: 重放不新增 receipt 的 canary~~ **已完成 (2026-08-29)**: 新增
  `bin/ssot/principal-authority-canary.py` 跑真实 OMO verify → Cockpit 签发 → Agora
  转发链路, 报告 `docs/reports/2026-08-29-principal-authority-canary.json` (digest
  chain equal + replay idempotent + negatives zero-effect + missing fail-closed +
  fixture rejected 全绿)
- value 轴 NOT_PROVEN (policy=false → delivery_accepted 路径)

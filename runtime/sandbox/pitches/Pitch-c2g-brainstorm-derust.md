# 修真 c2g brainstorm — 从 Mock print 到真 Pitch 生成

> **Upstream**: MS-PRODUCT-WALKTHROUGH-V1 (个人全场景产品走查, 让 c2g 真能驱动持续迭代)
> **Appetite:** 1 day

## 背景与上下文

产品走查(2026-06-19)发现 c2g 灵魂入口 brainstorm 是 Mock:

```python
# cli.py:43-46 现状 (修真前)
if args.command == "brainstorm":
    print("🧠 正在拉起 MetaOS...")
    print("  -> (Mock) 提案生成成功")  # 啥都没干, 不产文件
```

用户 `cockpit compass brainstorm "优化首页"` → 只 print 两句话, 不拉 MetaOS, 不产 Pitch 文件。
这让「持续分析 + c2g 升级迭代」在第一步就断 — 战略想法根本收不进来, pitches 目录至今 6 个全是测试垃圾。

## 目标

brainstorm 从 Mock 升级为**真生成 Pitch 文件**(打通 想法→Pitch→Bet→Task 第一步):
- 解析 topic → 生成结构化 Pitch(Upstream/Appetite 占位 + 背景/目标/NoGos 模板)
- 落 `runtime/sandbox/pitches/Idea-{slug}.md`
- 输出下一步 bet 命令(含绝对路径, 规避路径 bug)

## NoGos (YAGNI)

- 不集成 MetaOS(先用模板生成, MetaOS 智能发散是后续独立 bet)
- 不改 bet/radar/gc(它们是真)
- 不做 LLM 智能发散(模板优先, KISS)

## 验收

- [ ] `cockpit compass brainstorm "优化首页"` 真生成 `Idea-优化首页.md`
- [ ] 文件含 `> **Upstream**` 占位(CR-STRATEGY-01 bet 前可补)
- [ ] 同名 Pitch 已存在时 graceful 提示, 不覆盖
- [ ] Mock print 移除, 单元测试覆盖 brainstorm 真生成

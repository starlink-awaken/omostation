# evidence/ — 交付证据

> 交付面执行证据归档。回答"我们交付了什么？可验证的证据在哪？"
>
> 参考: [DOC-ARCH.md](../DOC-ARCH.md) §4

---

## 证据目录

| Phase | 目录 | 说明 |
|-------|------|------|
| [phase12/](phase12/) | Phase 12 执行证据 | 元模型扫描、场景试点、ADR |
| [phase13/](phase13/) | Phase 13 执行证据 | 元认知基线、瓶颈提案、协作演练 |
| [phase14/](phase14/) | Phase 14 执行证据 | 集成分类、深度吸收试点 |
| [phase15/](phase15/) | Phase 15 执行证据 | 策略测试报告、恢复演练、用户价值循环 |
| [phase16/](phase16/) | Phase 16 执行证据 | 产品表面收敛 |
| [divergence/](divergence/) | 分歧标记 | 运行时分歧检测记录 |
| [handoffs/](handoffs/) | 交接记录 | 任务交接上下文 |
| [kos-reindex/](kos-reindex/) | KOS 重建 | KOS 索引重建日志 |

## 证据规范

- 每个证据文件标注 `phase`、`type`、`generated_at`
- 证据一旦写入不可删除，仅可标记 `archived`
- 引用证据时使用相对路径指针

---

*维护: 2026-06-03 · 证据状态以各子目录内容为准*

---
title: T6-01 gbrain + kairon 归并 knowledge 迁移设计 spec
type: plan
owner: engineering-agent
created: 2026-08-16
bet: BET-Y1Q3-T6-01
related:
  - docs/plans/3y-bet-ledger.yaml
  - .omo/_knowledge/decisions/0412-model-driven-disposition.md
  - docs/plans/closeout-submodule-sync-design.md
lifecycle: plan
last_updated: 2026-08-18
---

# T6-01 迁移设计 spec — gbrain + kairon → `projects/knowledge/`

## 0. 一句话形态

**治理层归一、构建栈保持异构**：`projects/knowledge/` 成为单一 registry 项目（L2），内含
`gbrain/`（bun/ts 原样内包）与 `kairon/`（python/uv monorepo 原样内包）两个子目录；
`.gitmodules` 两条目移除，双头治理面（registry/layer-contract/AGENTS/CI path filter）合并为一。

异构栈不强行统一 — 沿用 LifeOS 异构生态先例（各栈有效，不强制统一构建）。

## 1. 实测证据（2026-08-16 摸底）

| 维度 | gbrain | kairon |
|------|--------|--------|
| 栈 | bun / TypeScript (ESM) | python 3.13 / uv workspace |
| src LOC | 164,176 (ts) | ~118,000 (15 packages) |
| 测试 | test/ 154,680 (718 test files) | tests/ + 各包 (311 files) |
| 结构 | 单包 `src/{core,commands,mcp,eval,types}` | `packages/{kos,minerva,ontoderive,eidos,iris,forge,codeanalyze,kronos,mos,core-models,sophia,...}` |
| BOS 集成 | `bun run projects/knowledge/gbrain/src/cli.ts serve` (3 service) | `uv run --directory projects/knowledge/kairon --package <p>` (path filter 数十处) |
| 交互方式 | — | MOS 经 subprocess/HTTP 调 gbrain（`mos/adapters/live_backends.py`，ADR-0372），**非 import** |
| 子仓状态 | 指针 e2ec4e166 == 远端，无未推送 | 指针 0a31da635 == 远端 HEAD，无未推送 |
| Makefile | （根仓无专项目标） | kairon-test/lint/build 6 目标 |
| layer-contract | L2 | L2；omo→kairon (test-only, ADR-0217)；kairon→agora (test-only) |

## 2. 为什么是「目录内包」而不是「代码互融」

1. **异构栈物理不可互融**：ts 与 python 无共享构建图，强行统一 = 重写业务逻辑（non_goal）。
2. **运行时边界已经是进程级**：MOS→gbrain 走 subprocess/HTTP，BOS 两栈各起进程 —
   目录结构改变不影响任何调用路径。
3. **去重空间实测有限**：gbrain chunkers(ts code 分析) vs kairon codeanalyze(py analyzers)
   功能重叠但语言隔离；真正可去重的是**双头治理面**（双 .omo/、双文档骨架、双 registry 条目、
   BOS path filter 重复段、根仓包装脚本）。
4. **风险控制**：原样内包 = 文件级搬运，`git diff` 可逐文件复核，出问题回滚到 tag 即可。

## 3. 目标终态

```
projects/knowledge/
├── README.md            # knowledge 项目说明（合并双头叙述）
├── gbrain/              # 原 projects/gbrain 内容原样（bun/ts）
│   ├── src/ test/ package.json ...
├── kairon/              # 原 projects/knowledge/kairon 内容原样（python/uv monorepo）
│   ├── packages/ src/ tests/ pyproject.toml ...
```

- `.gitmodules`：`projects/gbrain`、`projects/knowledge/kairon` 两条目删除
- `docs/project-registry.yaml`：`kairon:`、`gbrain:` 两条目合并为 `knowledge:`（保留各自
  stack/layers 元数据子结构）
- `docs/layer-contract.yaml`：L2 projects 列表 `kairon, gbrain` → `knowledge`；内部依赖条目
  path 重写
- `projects/agora/etc/bos-services.yaml`：所有 `projects/gbrain` → `projects/knowledge/gbrain`，
  `projects/knowledge/kairon` → `projects/knowledge/kairon`
- 根仓 `Makefile` kairon-* 目标 path 重写
- 全仓引用（bin/、docs/、tests/、spaces/、protocols/）path 重写
- 回滚 tag：`pre-knowledge-merge-20260816` 打在归并第一个子 PR 合入前的 main

## 4. 去重清单模板（交付物，非拍脑袋数字）

每一项必须满足：功能重复证据（双方模块名+LOC+职责）→ 合并后删除项 → 删除行数。候选区
（spec 阶段不锁定，实施阶段逐项实测确认）：

| # | 候选 | gbrain 侧 | kairon 侧 | 处置方向 |
|---|------|-----------|-----------|----------|
| 1 | 双头 .omo/ 治理面 | .omo/(子仓内) | .omo/(子仓内，含 _delivery) | 内包后子仓级 .omo 目录处置：保留 kairon 的运行时状态目录但停止双头维护 |
| 2 | 文档骨架 | CLAUDE.md/AGENTS.md/README 双份 | 同左 | 合并为 knowledge 单份 |
| 3 | registry/层契约条目 | gbrain: 条目 | kairon: 条目 | 合并单条目 |
| 4 | CI 路径重复 | cascading-test 等 path filter | 同左 | 统一 |
| 5 | docker-compose 重复 | gbrain 无独立 compose | kairon docker/ | 保留 kairon 侧 |

**注意**：跨语言代码 chunkers vs codeanalyze 等**不列入**去重清单 — 语言隔离删除任一侧都是
砍能力不是去重。

## 5. 四子 PR 分解（依赖序）

| PR | 内容 | 验证 |
|----|------|------|
| PR-1 | 本 spec + 回滚 tag 打点指令 | 文档 review |
| PR-2 | gbrain 侧内包：`.gitmodules` 删条目 + `projects/gbrain` → `projects/knowledge/gbrain`（文件级搬运）+ 全仓引用重写 + registry/layer-contract 改 | `bun test`（gbrain 全量）；`make gac-local-gate`；BOS config 校验 |
| PR-3 | kairon 侧内包：同上 → `projects/knowledge/kairon` + Makefile/BOS/根仓 tests path 重写 | `make kairon-test-fast`；root `tests/integration/run-all.sh` |
| PR-4 | 收口：去重清单终版（附行数合计）+ surface 前后对比 + test_loc 核验 + AGENT-BRIEF L3 规程引用 | `bet-ledger.py surface` 双指标 + 集成套件 |

## 6. 保护量与红线

- **test_loc ≥ 350,854**（基线；当前 799,371，搬运不减测试文件）
- **src 下降量 == 去重清单合计**（只允许治理面去重贡献下降量，代码原样搬运）
- 全量测试通过（PR-2 gbrain 全量 / PR-3 kairon + 根仓集成）
- 回滚验证：tag 存在 + `git checkout tag` 可恢复双 submodule 结构
- L3 human_gate：四子 PR 全 merge 后停审，不自行置 done

## 7. 风险与对策

| 风险 | 对策 |
|------|------|
| BOS path filter 漏改 → 服务 unreachable | 全仓 rg 逐条重写 + bos-services config 校验 + memory-os-check 实跑 |
| 根仓 tests 硬编码 projects/knowledge/kairon | PR-3 全仓引用重写覆盖 tests/ |
| submodule-guard 拦指针 | 内包即删 gitlink，无指针操作 |
| .subtrees/ 残留 | PR-4 清 .subtrees/{gbrain,kairon} |
| 并发 agent 引用旧路径 | 每 PR merge 后主仓立即拉 main；submit 前先 rebase 隔离树 |

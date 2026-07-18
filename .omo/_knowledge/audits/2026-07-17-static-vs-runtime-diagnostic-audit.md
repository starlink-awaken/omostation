# 2026-07-17 静态 vs 运行时方法论审计 — 9 轮诊断翻案链

> **触发**: 用户需求演进 "产品功能全景分析 → 深挖产品功能架构 → 优先级方案设计 → 审计方案是否最优 → 为什么晚发现/再深一轮 → 固化"
> **方法**: 老王 9 轮 RedTeam 式自我对抗调研 (用户连续追问逼出方法论根因)
> **结论**: 系统治理健康度远超静态初判; 真债接近零; 教训固化成 [P78](../patterns/p78-triple-axis-diagnostic-pattern.md)
> **Workflow**: `20260717T104136Z-project-doc-change-524ce3e7` (governance-agent, ADR-0203)

## 1. 翻案链 (静态误判 → 三维查证纠正)

| # | 静态断言 (老王初判) | 三维查证纠正 (铁证) | 教训维度 |
|---|------|------|:--:|
| 1 | 6 条 module_path 悬空死罪 | `aetherforge.{swarm,gateway,mesh}.rpc` + `bus_foundation.facade.*` **真实存在**; 老王验证脚本路径前缀写错 | T2 |
| 2 | bus 7 项目裸奔 (retry 默认关) | `RETRY-OWNERSHIP.md` 单层重试哲学; `eventbus.py:4` L4 **3x 指数退避** + DLQ 兜底 | T3/纪律4 |
| 3 | evidence-smoke 94 条无覆盖 (grep POC=65) | `services.py:1249` YAML 驱动加载器, 运行时 POC=154; ADR-0219 实测 **gap=0 resolve=0.987** | T1 |
| 4 | 缺系统性 anti-drift 机制 | `evidence-smoke-gate.yml` + `sync-bos-registry.py` + `bos-tracking-gate.py` 三层 gate 已跑; `bos-registry.json` 当天 15:04 生成 (比 yaml 新) | 纪律4 |
| 5 | iris 3 条该改 active (声明过时) | `bos-unimplemented.yaml` P45+ **路标欠债**登记在案 (iris 包方法 ≠ BOS 适配层) | T3 |
| 6 | 公文/家庭/健康门户盲区 | cockpit `gongwen/health/family_hub/finance.py` 早有引导门 (SRP); health 有 4 BOS 服务 + 独立 CLI | 过时 |
| 7 | ADR-0128 未落地 (proposed) | `omo_ingress_state.py` **已实现** (broker 落地, Phase 2 done) | T3 |
| 8 | family-hub 独立 SQLite 违规, 该经 broker 物化 | ecos(`actions.py:331`)+cockpit(`api_omos.py:115/266/340`) **4+处直读** 既成耦合; schema 近期未漂移 → YAGNI | T4 |
| 9 | registry 114 三源 drift, P0 大活 | gen 脚本只管 version/python (114 手动); 下游文档用 digest 指针规避 → **ROI 低, 1h 选做** | — |

## 2. 方法论根因 (为什么 9 轮才到底)

老王用**静态分析**判断一个**声明/执行鸿沟频发**的系统, 而真相藏在**运行时**和**决策层**:

| 老王的静态判断 | 运行时/决策真相 |
|------|------|
| `grep '"bos://'`=65 → "POC 只覆盖 65" | 运行时 yaml 加载=154, gap=0 (ADR-0219) |
| "iris 有 validate 方法 → 该改 active" | BOS 适配层 ≠ 包方法, 是 P45+ 路标 |
| "6 条 module 路径查不到 → 悬空" | 查的路径前缀错, 实际都在 |
| "ADR-0128 proposed → 未落地" | broker 已实现 (看文件不看 status) |
| "缺 anti-drift 机制" | 38 gate + 60 工具 + ADR 体系早建好 |

**4 认知病根**:
1. **确认偏误** — 调研为假设找证据, 不找反证
2. **缺自我对抗** — 靠用户当 RedTeam, 不主动质疑自己结论
3. **基础设施盲区** — 不扫 `bin/ssot/` + `.github/workflows/`
4. **单向依赖** — 只查 X→外, 不查 外→X

**三维查证解法**: 静态(必要不充分) + 运行时(真相) + 决策层(意图), 缺一即误判. 详见 [P78](../patterns/p78-triple-axis-diagnostic-pattern.md).

## 3. 收敛后真账 (9 轮坍缩结果)

| 原"雷" (4 轮喊出) | 9 轮后真相 | 处置 |
|---|---|:--:|
| ~~evidence-smoke 94 条无覆盖~~ | ADR-0219 gap=0 全 154 | 🚫 伪命题 |
| ~~6 条 module 悬空~~ | 路径错, 全存在 | 🚫 误判 |
| ~~bus 7 项目裸奔~~ | L4 3x 重试 + DLQ | 🚫 误判 |
| ~~门户盲区~~ | cockpit 有门 + health 4 BOS | 🚫 过时 |
| ~~iris 改 active~~ | P45+ 路标 | 🚫 概念混淆 |
| ~~方案 D 默认 fcntl~~ | 撞 ADR-0128 次优 | 🚫 方向错 |
| registry 114 手动快照 | gen 脚本只管 ver/py; 下游 digest 规避 | 🟢 选做 1h |
| ADR-0128 推进 | broker 已实现 | 🚫 误判 |
| family-hub 边界 | 既成耦合, schema 稳定 | 🟡 YAGNI 缓 |

**真正"要做" = 接近零** (仅 registry 可选 1h 小活, ROI 还低).

## 4. 固化 (三层, 按 AGENTS.md §9:297)

- **memory (feedback)**: `triple-axis-diagnostic-discipline` (跨会话避坑)
- **协议层**: [P78 pattern](../patterns/p78-triple-axis-diagnostic-pattern.md) + AGENTS.md §8 指针 + §9 诊断前置 4 问
- **harness 层**: (留后续, 可考虑 hook 提醒"诊断前过 4 问")

## 5. 教训一句话

> **在一个声明/执行鸿沟是标志性反 pattern 的系统里, 静态 grep 和路径直觉是失效的 — 真相在运行时 (evidence-smoke gap), 意图在决策层 (ADR). 任何只走静态层的诊断都是切片, 必翻车. 最理想方案常是"少做": 能证明"自己开的药是多余的"比"开更多药"专业.**

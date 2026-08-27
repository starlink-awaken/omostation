---
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-06-23
archived-since: 2026-06-23
note: "P55 R1: Phase 1-13 历史执行计划归档, 当前阶段/状态以 .omo/state/system.yaml + .omo/goals/current.yaml 为准"
---
# Governance Phase 2 — 核心链路闭环

> 周期: 2026-05-29 ~ 2026-06-02 (5天) | 负责人: sisyphus (P9)
> 目标: 深度研究链路完整闭环: 输入 → 处理 → 输出 → 保存 → 可回顾

---

## Sprint 2.1: 研究持久化（2 天）

### Wave 2.1.A — minerva 输出持久化（P8: prometheus）

| Task ID | 描述 | 验收标准 | 预估 |
|---------|------|---------|------|
| T028 | minerva research 输出自动保存到 `~/.minerva/research/<id>/report.md` | 每次 research 完成后自动写文件 | 1h |
| T029 | 保存格式标准化：元信息(时间/来源/耗时) + 摘要 + 全文 + 来源列表 | 文件结构包含 frontmatter | 30min |
| T030 | minerva research list CLI 展示最近研究 | `minerva research list` 显示最近 N 条 | 30min |
| T031 | minerva research open <id> 展示全文 | `minerva research open 1` 输出完整报告 | 20min |

### Wave 2.1.B — workspace CLI 基础对接（P8: prometheus）

| Task ID | 描述 | 验收标准 | 预估 |
|---------|------|---------|------|
| T032 | `workspace research` 命令对接 minerva CLI | `workspace research "topic"` 触发研究 | 30min |
| T033 | `workspace research list` 对接存储 | 结果与 `minerva research list` 一致 | 20min |
| T034 | `workspace research open <id>` 对接存储 | 结果与 `minerva research open` 一致 | 20min |

---

## Sprint 2.2: 体验闭环（3 天）

### Wave 2.2.A — 进度反馈（P8: prometheus + P7: epimetheus）

| Task ID | 描述 | 验收标准 | 预估 |
|---------|------|---------|------|
| T035 | minerva L3 研究加入进度指示器（当前步骤/已完成来源数/预计剩余） | >5s 的操作有可视化进度 | 1h |
| T036 | workspace research 输出步骤指示（toolforge→derive→research） | 每个步骤前有 `[N/M]` 标记 | 30min |
| T037 | 超时保护：research 超过 120s 自动提示用户是否继续 | 120s 时输出警告，不静默卡死 | 30min |

### Wave 2.2.B — 后续追问（P8: prometheus）

| Task ID | 描述 | 验收标准 | 预估 |
|---------|------|---------|------|
| T038 | `workspace research --ask <id> "xxx"` 基于已有研究结果追问 | 上下文包含已有报告，返回补充结果 | 45min |
| T039 | 追问结果追加到原研究记录 | `research open <id>` 包含原始+追问内容 | 30min |

### Wave 2.2.C — 30秒 demo 前序（P8: prometheus）

| Task ID | 描述 | 验收标准 | 预估 |
|---------|------|---------|------|
| T040 | `workspace demo` 骨架：串起 health → research → list | `workspace demo` 不报错，输出 3 步 | 30min |
| T041 | demo 失败时输出友好提示（"请先启动 agora web"等） | 每步失败有明确下一步指引 | 20min |

---

## 依赖关系

```
T028 ──→ T029 ──→ T030 ──→ T031
T030 ──→ T033
T031 ──→ T034
T028 ──→ T032 ──→ T035 ──→ T036
T032 ──→ T038 ──→ T039
T032 ──→ T040 ──→ T041
T007 ──→ T040 (依赖 Phase 1 agora health 修复)
```

## Phase 2 门禁

```
☐ `workspace research "test"` → 保存到文件 → 关终端 → 再打开 → `list` 看到结果 → `open` 看到全文
☐ `workspace research --ask 1 "more"` 返回补充结果
☐ `workspace demo` 输出 3 步不报错
☐ 全程 < 30 秒完成首次有意义操作
```

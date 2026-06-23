---
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-06-23
archived-since: 2026-06-23
note: "P55 R1: Phase 1-13 历史执行计划归档, 当前阶段/状态以 .omo/state/system.yaml + .omo/goals/current.yaml 为准"
---
# Governance Phase 1 — 基础设施清理

> 周期: 2026-05-24 ~ 2026-05-28 (5天) | 负责人: sisyphus (P9)
> 目标: 配置0污染 + 配置管理自动化 + 测试基线建立

---

## Sprint 1.1: 配置洁净（2 天）

### Wave 1.1.A — agora 配置冻结（P8: prometheus）

**目标**: agora 的 services/routes/events 配置不再被测试数据污染

| Task ID | 描述 | 验收标准 | 预估 |
|---------|------|---------|------|
| T001 | 清洗 agora-services.json，只保留 9 个真实服务 | `agora list` 输出无 192.0.2.x 地址 | 15min |
| T002 | 清洗 agora-routes.json，只保留真实服务路由 | routes 数 = 9，无 test/api/grpc/bad 等条目 | 15min |
| T003 | 清洗 agora-events.json，清除测试事件 | events 数组为空 | 5min |
| T004 | 建立配置变更审计：配置被修改时自动记录到 STATE.md | hook 或 CI check 可检测配置增量 | 30min |
| T005 | agora-routes.json 加 JSON Schema 校验 | `agora routes --validate` 通过 | 30min |

### Wave 1.1.B — 端到端测试修复（P8: prometheus + P7: epimetheus）

**目标**: 所有 E2E 测试可重复运行、不依赖宿主环境

| Task ID | 描述 | 验收标准 | 预估 |
|---------|------|---------|------|
| T006 | `tests/e2e/test_cross_project.py` 全部 `shutil.which` 路径 + skipif 标记 | `pytest tests/e2e/ -q` 无硬编码路径 | 20min |
| T007 | `agora health` 全路径覆盖 — 无 mock 也能输出有效结果 | `agora health` 不崩溃，返回格式一致 | 30min |
| T008 | unit test 运行：`agora list`/`health`/`discover` CLI 测试 | `pytest tests/ -q` pass | 20min |

---

## Sprint 1.2: 基线建立（3 天）

### Wave 1.2.A — 全项目 ruff 基线（P8: prometheus）

**目标**: 所有活跃 Python 项目 ruff 0 errors

| Task ID | 描述 | 验收标准 | 预估 |
|---------|------|---------|------|
| T009 | ontoderive ruff 0 errors | `cd ontoderive && ruff check src/` 0 errors | 30min |
| T010 | pallas ruff 0 errors | 同上 | 15min |
| T011 | sophia ruff 0 errors | 同上 | 15min |
| T012 | minerva ruff 0 errors | 同上 | 30min |
| T013 | agora ruff 0 errors | 同上（已验证） | 5min |
| T014 | eidos ruff 0 errors | 同上 | 15min |
| T015 | kronos ruff 0 errors | 同上 | 15min |
| T016 | codeanalyze ruff 0 errors | 同上 | 15min |
| T017 | iris ruff 0 errors | 同上 | 15min |
| T018 | kos ruff 0 errors | 同上 | 15min |
| T019 | bos-skill-cli ruff 0 errors | 同上 | 15min |
| T020 | eCOS ruff 0 errors | 同上 | 15min |

### Wave 1.2.B — 项目健康度审计（P8: prometheus）

**目标**: 所有项目健康度评分更新到 INVENTORY.md

| Task ID | 描述 | 验收标准 | 预估 |
|---------|------|---------|------|
| T021 | 审计 MetaOS：归档 or 补充最小测试 | STATE.md 记录决策 | 30min |
| T022 | 审计 SSOT：归档 or 补充最小测试 | STATE.md 记录决策 | 30min |
| T023 | 审计 agentmesh engine/toolkit 标记实验性 | ENGINE.md/CLAUDE.md 加入 `@experimental` | 20min |
| T024 | 更新 `.omo/INVENTORY.md` 反映最新状态 | 所有项目版本/测试/LOC 最新 | 30min |

### Wave 1.2.C — 配置管理自动化（P8: prometheus + P7: epimetheus）

**目标**: 配置被污染时自动预警

| Task ID | 描述 | 验收标准 | 预估 |
|---------|------|---------|------|
| T025 | Makefile 添加 `make check-config` 检测测试数据 | `make check-config` 在 services.json 有 192.0.2.x 时退出 1 | 30min |
| T026 | agora 启动脚本加入配置自检 | `start-agora.sh` 启动前先 check-config | 15min |
| T027 | 配置快照机制：每次变更前自动备份到 `.omo/backups/` | `ls .omo/backups/` 有时间戳文件 | 20min |

---

## 依赖关系

```
T004 ──→ T025 ──→ T026
T001 ──→ T002 ──→ T003
T006 ──→ T007 ──→ T008
T009~T020 (可以并行)
T021 ──→ T022 ──→ T023 ──→ T024
```

## Phase 1 门禁

```
☐ `agora list` 输出无测试数据
☐ `agora routes` 输出无测试路由
☐ `make check-config` 在 workspace 根目录可用
☐ 所有活跃项目 ruff 0 errors
☐ MetaOS/SSOT 已做归档决策
☐ agentmesh engine/toolkit 已标记实验性
```

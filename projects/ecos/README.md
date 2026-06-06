# ecos — L0 协议编织层

> 独立项目 · 从 omostation kairon monorepo 拆出 (P31-W0-ECOS-EXTRACT, 2026-06-06)
> 架构归属: **L0 协议层** (SSB 协议 + 涌现计算)

## 职责

- **SSB (Semantic Spreading Brain) 协议**：签名链、序列迁移、完整性验证、模式迁移
- **涌现计算**：calc_emergence / snapshot_emergence / emergence_watch / emergence_auto
- **认知监控**：kos_health_monitor、constitution_watcher、critic_auto_trigger
- **协议编织**：content_integrity、realtime_guard、email_sender、integrate_pipeline、planner、model_balancer
- **CLI**：dashboard、scheduler、watchdog、ssb-client

## 规模

- **代码行数**: 6,288 行 (src/ecos/ 下 17 顶层 + core 13 + cli 4)
- **测试数**: 10 测试文件 (conftest, test_core, test_core_unit, test_core_extended, test_e2e_baseline, test_imports, test_kos_health_monitor, test_phase9_push, test_redteam_v3, T7/T8 e2e)

## 快速开始

```bash
# 安装依赖
uv sync

# 验证
uv run python -c "import ecos; print('OK')"

# 运行测试
uv run pytest tests/ -q

# CLI 入口
uv run ecos-ssb --help
uv run ecos-dashboard --help
uv run ecos-scheduler --help
```

## 依赖关系

- **被依赖**: 0（kairon monorepo 无任何 import ecos） — 验证: `grep -rln "from ecos|import ecos" /Users/xiamingxing/Workspace/projects/kairon --include="*.py"` 无输出
- **依赖**: pyyaml, requests, beautifulsoup4, jinja2（仅 LLM/模板相关，全协议核心用标准库）
- **SSB 数据**: 本地 SQLite (`LADS/ssb/ecos.db`) + JSONL 事件日志 (`LADS/ssb/ecos.jsonl`)

## 架构位置

```
L0 协议层 (本项目)
  ↓
L1 知识工程层 (kairon)
  ↓
L2 集成层
  ↓
L3 Agent 层
  ↓
L4 知识存储层
```

ecos 是 L0 编织层，独立于知识工程栈，可被任意上层调用。

## 迁移历史

- **2026-06-06 (P31-W0)**: 从 `projects/kairon/packages/ecos` 拆出为独立项目
  - 决策依据: `.omo/_knowledge/management/architecture-pure-analysis.md` v3 终态标注"0 依赖、0 被依赖"
  - 补做原因: P30 决策文档 `decision-p30-architecture-final.md` 未明列 ecos，但 v3 终态要求独立
  - 包数变化: kairon 21 → **20 包**（达成 W2-PKG-SLIM ≤20 目标）
  - 物理迁移: P30-M1.2 commit `32bccb4` 已完成源码移动（git 跟踪已无 kairon/packages/ecos/），P31-W0 补做收尾：清理空壳目录 + 移除 workspace 引用 + 文档同步

## 治理归属

- **决策**: L0 协议层自治（kairon 不再治理）
- **依赖注入**: 上层通过 HTTP / MCP / 直接 import 三种方式接入
- **演进**: 协议变更需经 L0 协议层 RFC 流程

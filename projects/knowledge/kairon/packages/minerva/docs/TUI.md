---
title: TUI
type: doc
---

# Minerva TUI — 终端交互界面规划

> 状态: 规划中 | 目标版本: v0.8.0+ | 2026-05-12

---

## 技术选型

**Textual** — Python 原生 TUI 框架，基于 Rich 生态。

| 维度 | 选择 | 理由 |
|------|------|------|
| 框架 | Textual (>=2.0) | 与现有 Rich 进度条无缝衔接，CSS 布局，异步原生 |
| 数据流 | 管道事件 → Queue → Widget 更新 | 解耦管道执行和 UI 渲染 |
| 键盘 | Textual keybindings | 内置 vim/emacs 模式支持 |
| 主题 | 继承终端颜色方案 | 自动适配 light/dark |

---

## 界面布局

```
┌──────────────────────────────────────────────────────────────┐
│  Minerva Deep Research                         [L2] [Running]│  ← Header
├────────────────────┬─────────────────────────────────────────┤
│  Pipeline Stages   │  Stage Detail                           │  ← Body
│                    │                                         │
│  ✓ decompose  1.2s │  Query: What is MoE architecture?       │
│  ✓ search     3.5s │  Sub-questions: 10                      │
│  ◌ entity_extract  │  Sources found: 25                      │
│                    │  Entities: 45                            │
│  ◌ deep_read       │                                         │
│                    │  Latest log:                             │
│  ◌ cross_analyze   │  [12:03:05] search: DDG=8, Scholar=5,  │
│  ◌ quality_gate    │  arXiv=3, Metaso=5, Exa=4              │
│  ◌ output          │  [12:03:08] RRF fusion: 25 unique      │
│                    │  [12:03:12] entity_extract: 45 entities │
│                    │  [12:03:15] deep_read: starting...      │
├────────────────────┴─────────────────────────────────────────┤
│  [Q]uit  [P]ause  [R]estart  [S]ave  [E]xport  [V]erify     │  ← Footer
└──────────────────────────────────────────────────────────────┘
```

### 组件树

```
MinervaApp (App)
├── Header (Static) — 标题栏 + 级别 + 状态指示灯
├── Body (Container, horizontal)
│   ├── StageTree (Tree, 40%) — 管道阶段树
│   │   ├── 完成: ✓ green
│   │   ├── 进行中: ◌ yellow + spinner
│   │   ├── 失败: ✗ red
│   │   └── 待执行: ○ dim
│   └── DetailPanel (Container, vertical, 60%)
│       ├── StageInfo (Static) — 当前阶段详情
│       ├── LogView (RichLog, 自动滚动) — 实时日志流
│       └── MetricsBar (Static) — API调用/Token/成本
└── Footer (Static) — 快捷键提示栏
```

---

## 交互模式

### 键盘快捷键

| 键 | 动作 | 描述 |
|----|------|------|
| `Q` / `Ctrl+C` | 退出 | 优雅关闭，保存状态 |
| `P` | 暂停/继续 | 冻结管道执行 |
| `R` | 重启 | 重新运行当前查询 |
| `↑` / `↓` | 导航 | 在阶段间移动焦点 |
| `Enter` | 展开/折叠 | 查看阶段详细输出 |
| `S` | 保存报告 | 导出为 EN/ZH markdown |
| `E` | 导出 JSON | 完整管道上下文导出 |
| `V` | 验证 | 手动触发 GlobalVerifier |
| `L` | 切换日志级别 | DEBUG/INFO/WARNING/ERROR |

### 鼠标支持

- 点击阶段节点 → 展开详情
- 点击日志行 → 复制到剪贴板
- 滚动日志面板 → 查看历史

---

## 数据流

```
Pipeline.execute()
  → structlog events
    → asyncio.Queue
      → Textual worker (async)
        → Widget.update()
          → Screen refresh (60fps)
```

每阶段执行前后通过 `structlog` 发出事件，Textual 的 async worker 消费队列并更新 UI。管道和 UI 完全解耦。

---

## 实现阶段

### Phase 1 — 基础布局（v0.8.0，~3h）
- Textual App 骨架 + 三栏布局
- 静态 StageTree（硬编码数据）
- 基础键盘快捷键（Q退出）
- `minerva tui` CLI 入口

### Phase 2 — 实时数据（v0.8.1，~3h）
- 管道事件队列 → Widget 实时更新
- LogView 滚动日志
- 进度条 + spinner 动画
- 阶段状态颜色切换

### Phase 3 — 交互控制（v0.9.0，~3h）
- 暂停/继续/重启
- 报告保存/导出
- 手动触发验证
- 级别实时切换
- 主题定制

---

## 与 CLI 的关系

| 特性 | CLI (`minerva research`) | TUI (`minerva tui`) |
|------|--------------------------|---------------------|
| 适用场景 | 脚本化、CI/CD、后台 | 交互式探索、调试、演示 |
| 输出 | Markdown 文件 | 实时终端界面 |
| 控制 | 一次性运行 | 可暂停/继续/重启 |
| 日志 | stdout | 滚动 LogView |
| 管道状态 | 最终报告 | 每阶段实时可见 |

两者共享同一 Pipeline/Executor 层，仅入口不同。CLI 保留为默认模式。

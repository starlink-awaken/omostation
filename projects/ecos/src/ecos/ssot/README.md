# 织星 L0 — 协议编织层

> eCOS v5.3 | 织星架构 (Stellar Weave) | 2026-06-06
> L0 是 MetaOS 的架构 DNA 编译器——系统的自我描述与治理引擎

---

## 快速导航

| 你想做什么 | 去这里 |
|-----------|--------|
| 理解 L0 的架构 | 读本文 |
| 查看系统拓扑 | `registry/topology.yaml` |
| 查看架构模式 | `registry/patterns.yaml` |
| 查看层边界规则 | `registry/layer-boundary.yaml` |
| 查看协议注册表 | `registry/L0-constraints.yaml` |
| 查看元模型定义 | `mof/m2/` (18 个 M2 类型) |
| 查看全量资产节点 | `mof/m1/` (575 个 M1 节点) |
| 运行架构校验 | `python3 tools/mof-validate.py` |
| 运行自举检查 | `python3 tools/mof-bootstrap.py` |
| 运行漂移审计 | `python3 tools/mof-audit.py` |
| 运行层合规检查 | `python3 tools/mof-enforce.py` |

---

## 架构

```
ssot/                               ← L0 SSOT
├── README.md                       ← 本文件
├── validator.py                    ← 统一入口校验器
│
├── registry/                       ← 注册表
│   ├── topology.yaml               ← 6层拓扑·包依赖
│   ├── patterns.yaml               ← 7 架构模式
│   ├── layer-boundary.yaml         ← 层边界规则
│   ├── L0-constraints.yaml         ← 9 约束定义
│   └── governance/                 ← 治理配置
│       ├── x3-value-stack.yaml
│       ├── agent-manifest.yaml
│       ├── hooks.yaml
│       └── kos-index.yaml
│
├── mof/                            ← 织星 MOF 引擎
│   ├── m3.yaml                     ← M3 元元模型 (19类型·17关系)
│   ├── m2/ (18 文件)               ← M2 元模型 (每类型一个文件)
│   ├── m1/ (18 目录)               ← M1 节点 (576个·按类型分目录)
│   ├── m0/snapshot.yaml            ← M0 运行时快照
│   └── ontology.yaml               ← 本体映射
│
└── tools/ (10 个)                  ← 工具链
    ├── mof-validate.py             ← M1↔M2 校验
    ├── mof-scan.py                 ← 自动扫描 → M1
    ├── mof-model.py                ← 全量资产建模
    ├── mof-audit.py                ← M1↔M0 漂移审计
    ├── mof-derive.py               ← 本体推理
    ├── mof-extract.py              ← 逆向提炼
    ├── mof-enforce.py              ← 层合规强制执行
    ├── mof-sla.py                  ← SLA 执行 + M0快照
    ├── mof-bootstrap.py            ← L0 自举校验
    └── mof-register-tasks.py       ← 任务/脚本注册
```

## MOF 四层模型

```
M3  元元模型     19 Element 类型 · 17 Relation 类型
     ↓ 定义"定义的方式"
M2  元模型       18 种要素类型 (架构·协议·模式·流程·实体...)
     ↓ 定义"每一种东西长什么样"
M1  节点声明     575 个节点 (全系统的模型化表达)
     ↓ 声明"系统中有哪些东西"
M0  运行时快照    daemon 每 6h 刷新 (实际运行状态)
     ↑ 反馈"系统实际在怎么跑"
```

## 工具链与 daemon 循环

```
daemon 每 6h:
  bootstrap → enforce → sla → audit → health-check → digest
```

## 数字快照

| 维度 | 数字 |
|------|:---:|
| M2 类型 | 18 |
| M1 节点 | 576 |
| 工具链 | 10 |
| 注册表文件 | 8 |
| 校验通过率 | 575/575 ✅ |
| 自举健康 | 全绿 ✅ |

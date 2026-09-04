---
title: CAPABILITY-MAP
type: doc
---

# kairon 能力地图

> 16 个包的功能全景 · 场景覆盖 · 依赖关系

---

## 一、架构总览

```
┌─────────────────────────────────────────────────────────────┐
│                    kairon 能力地图                            │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  应用层                                              │   │
│  │  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐  │   │
│  │  │  minerva │ │  kronos  │ │  forge  │ │  sophia │  │   │
│  │  │ 深度研究 │ │ 知识摄取 │ │ 资产管理│ │符号研究 │  │   │
│  │  └─────────┘ └─────────┘ └─────────┘ └─────────┘  │   │
│  └─────────────────────────────────────────────────────┘   │
│                           │                                 │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  引擎层                                              │   │
│  │  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐  │   │
│  │  │   kos   │ │  iris   │ │  eidos  │ │ontoderive│  │   │
│  │  │ 知识OS  │ │ 连接器  │ │ Schema  │ │ 本体推导 │  │   │
│  │  └─────────┘ └─────────┘ └─────────┘ └─────────┘  │   │
│  └─────────────────────────────────────────────────────┘   │
│                           │                                 │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  基础层                                              │   │
│  │  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐  │   │
│  │  │core-models│ │  code   │ │ kairon- │ │ kairon- │  │   │
│  │  │核心模型  │ │ analyze │ │  utils  │ │pipeline │  │   │
│  │  └─────────┘ └─────────┘ └─────────┘ └─────────┘  │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## 二、包能力清单

### 2.1 基础层

| 包名 | 功能 | 场景 | 测试数 | 状态 |
|------|------|------|--------|------|
| **core-models** | 实体/关系/知识图谱/神经网络 | (声明, 实际 0 外部 import) | 6 | ⚠️ **死基础层**(eidos 有自己 models, 全仓无人用, 待活跃化/删决策) |
| **codeanalyze** | AST分析/代码图/审查图 | 代码质量/安全/重构 | 13 | ✅ |
| **kairon-utils** | 工具库(原子写入/锁/重试/日志) | 通用工具 | 10 | ✅ |
| **kairon-pipeline** | 数据处理管线 | ETL/数据流 | 2 | ⚠️ |
| **kairon-lib-events** | 事件库 | 事件驱动 | 1 | ⚠️ |
| **kairon-observability** | 可观测性(监控/日志) | 监控/告警 | 2 | ⚠️ |
| **kairon-plugin-sdk** | 插件SDK | 插件开发 | 1 | ⚠️ |
| **health-profile** | 健康档案 | 健康数据管理 | 1 | ⚠️ |

### 2.2 引擎层

| 包名 | 功能 | 场景 | 测试数 | 状态 |
|------|------|------|--------|------|
| **kos** | 知识操作系统(搜索/索引/本体) | 跨域搜索/知识管理 | 23 | ✅ |
| **iris** | 连接器(WPS/微信读书/平台) | 平台集成/数据同步 | 10 | ✅ |
| **eidos** | **认知记忆系统**(memory/nks/continuity/CRDT/learning + schema 子集) | 记忆/语义搜索/会话连续/认知学习 | 24 | ✅ **kairon 枢纽**(39K LOC, 9 外部 import 第一) |
| **ontoderive** | 本体推导(推理/验证/渲染) | 语义推理/文档生成 | 48 | ✅ |

### 2.3 应用层

| 包名 | 功能 | 场景 | 测试数 | 状态 |
|------|------|------|--------|------|
| **minerva** | 深度研究(8引擎+4LLM) | 研究/分析/报告 | 37 | ✅ |
| **kronos** | 知识摄取(采集/解析/入库) | 数据采集/ETL | 9 | ✅ |
| **forge** | 数字资产管理(同步/图谱) | 资产管理/协作 | 11 | ✅ |
| **sophia** | 符号化研究(编译器/运行时) | 形式化推理 | 2 | ⚠️ |

---

## 三、能力矩阵

### 3.1 按场景分类

| 场景 | 涉及包 | 能力 |
|------|--------|------|
| **知识管理** | kos, kronos, core-models | 搜索/索引/摄取/建模 |
| **深度研究** | minerva, iris | 研究/分析/报告/平台集成 |
| **代码分析** | codeanalyze | AST/图谱/审查 |
| **数据校验** | eidos, ontoderive | Schema/本体/推导 |
| **资产管理** | forge, iris | 资产/同步/连接 |
| **可观测性** | kairon-observability, kairon-utils | 监控/日志/工具 |

### 3.2 按依赖关系

```
core-models ←── eidos, kos, kronos, minerva, ontoderive
kairon-utils ←── 所有包
kairon-lib-events ←── forge, kronos
kairon-pipeline ←── kronos, minerva
```

---

## 四、CLI 命令速查

| 包名 | 命令 | 说明 |
|------|------|------|
| codeanalyze | `codeanalyze scan <path>` | 代码扫描 |
| eidos | `eidos validate <file>` | Schema 验证 |
| forge | `forge list` | 列出资产 |
| iris | `iris connect <platform>` | 连接平台 |
| kos | `kos search "关键词"` | 跨域搜索 |
| kronos | `kronos ingest <source>` | 数据摄取 |
| minerva | `minerva research "topic"` | 深度研究 |
| ontoderive | `ontoderive derive <input>` | 本体推导 |
| sophia | `sophia compile <input>` | 符号编译 |

---

## 五、MCP 工具

| 包名 | 工具数 | 说明 |
|------|--------|------|
| kos | 9 | search, get, status, domains, sync, entity, rebuild |
| forge | 5 | list, get, create, update, delete |
| minerva | 4 | research, draft, audit, report |
| iris | 3 | connect, sync, status |

---

## 六、测试覆盖地图

| 包名 | 测试文件 | 测试用例(估) | 覆盖率 | 优先级 |
|------|----------|--------------|--------|--------|
| ontoderive | 48 | ~384 | 高 | - |
| minerva | 37 | ~296 | 高 | - |
| kos | 23 | ~184 | 高 | - |
| eidos | 24 | ~192 | 高 | - |
| codeanalyze | 13 | ~104 | 高 | - |
| forge | 11 | ~88 | 高 | - |
| iris | 10 | ~80 | 高 | - |
| kairon-utils | 10 | ~80 | 高 | - |
| kronos | 9 | ~72 | 中 | - |
| core-models | 6 | ~48 | 中 | - |
| sophia | 2 | ~16 | 低 | P1 |
| kairon-observability | 2 | ~16 | 低 | P1 |
| kairon-pipeline | 2 | ~16 | 低 | P1 |
| health-profile | 1 | ~8 | 低 | P2 |
| kairon-lib-events | 1 | ~8 | 低 | P2 |
| kairon-plugin-sdk | 1 | ~8 | 低 | P2 |

---

*最后更新: 2026-07-12 (eidos 纠偏: Schema→认知记忆系统, kairon 枢纽; core-models 标死 0 外部 import)*

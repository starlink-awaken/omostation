---
schema: knowledge-domains/v1
status: active
lifecycle: active
owner: governance-team
last-reviewed: 2026-09-20
type: taxonomy
---

# Knowledge Domains — 跨域学习分类 (FORWARD-PLAN v2 §B1.3)

> 区分学术 / 工程 / 个人知识域，支持 .omo/_knowledge/scholar/ 子目录扩展。
> 2026-09-20 初版: 工程域已成熟，学术/个人域待扩展。

## 分类原则

1. **学术 (academic)**: 论文阅读、概念笔记、文献综述、方法论
2. **工程 (engineering)**: 代码、架构、运维、工具链、CI/CD
3. **个人 (personal)**: 健康、财务、关系、个人成长、生活管理

## 域定义

domains:
  - id: academic
    name: 学术研究
    description: 论文阅读、概念笔记、方法论、文献综述
    path: .omo/_knowledge/scholar/
    status: planned
    target_files: 0
    current_files: 0
    examples:
      - paper-note: 论文精读笔记 (title, authors, key findings, methodology)
      - concept-index: 跨论文概念索引
      - review-summary: 文献综述摘要
    criteria:
      - 来源为 peer-reviewed 或 preprint
      - 含方法论/实验设计分析
      - 有个人批判性评价

  - id: engineering
    name: 工程实践
    description: 代码、架构、运维、工具链、CI/CD、系统设计
    path: .omo/_knowledge/
    status: active
    target_files: 100
    current_files: 489
    examples:
      - retro: 项目复盘
      - pattern: 工程模式 (P75-P105)
      - decision: ADR 架构决策记录
      - report: 审计报告、架构分析
    criteria:
      - 与代码仓库直接关联
      - 含可复用的工程实践
      - 有具体的技术决策记录

  - id: personal
    name: 个人成长
    description: 健康、财务、关系、个人成长、生活管理
    path: .omo/_knowledge/personal/
    status: planned
    target_files: 20
    current_files: 0
    examples:
      - health-log: 健康数据记录
      - finance-review: 财务复盘
      - growth-note: 个人成长笔记
    criteria:
      - 与个人生活直接相关
      - 含可操作的自我改进建议
      - 有定期复盘记录

## 交叉引用

- .omo/_knowledge/patterns/ — 工程模式 (engineering)
- .omo/_knowledge/retros/ — 项目复盘 (engineering)
- .omo/_knowledge/decisions/ — ADR 架构决策 (engineering)
- .omo/_knowledge/network/ — 网络配置文档 (engineering)
- .omo/_knowledge/scholar/ — 学术笔记 (academic, planned)
- .omo/_knowledge/personal/ — 个人笔记 (personal, planned)

## 统计

statistics:
  total_files: 489
  engineering: 489
  academic: 0
  personal: 0
  last_updated: 2026-09-20

## 路线图

roadmap:
  - phase: v1 (2026-Q4)
    goal: 工程域基线建立
    target: 当前 489 文件维持质量
    status: done

  - phase: v2 (2027-Q1)
    goal: 学术域扩展
    target: 新增 .omo/_knowledge/scholar/，5+ paper notes
    status: planned

  - phase: v3 (2027-Q2)
    goal: 个人域扩展
    target: 新增 .omo/_knowledge/personal/，健康+财务笔记
    status: planned

  - phase: v4 (2027-Q3)
    goal: 跨域交叉引用
    target: 建立 academic→engineering→personal 知识链
    status: planned

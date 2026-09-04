---
title: README
type: doc
---

# KOS — Knowledge Operating System

> 薄薄的知识操作系统层。10 域 6,691 文档跨域搜索 · 40 实体本体建模 · 8 定时任务自动维护。

---

## 一、核心理念

你不需要把文件搬到一个地方。KOS 在你的文件之上建一层索引和本体，让所有 Agent 和工具用统一接口访问所有知识。

```
你的文件夹（不动）  →  KOS 索引层  →  搜索 / 本体 / 图谱 / 报告
```

## 二、快速开始

### 新用户（一键初始化）

```bash
# 1. 安装
pip install -e .

# 2. 设置 KOS_HOME
export KOS_HOME=$HOME/.kos_home
bash init_kos_home.sh
echo 'export KOS_HOME=$HOME/.kos_home' >> ~/.zshrc

# 3. 初始化
kos init                    # 交互式向导：选目录 → 扫描域 → 生成配置
kos init --dry-run          # 预览，不写入文件
```

### 外部工具集成状态

| 工具 | 集成方式 | 版本兼容 | 状态 |
|---|---|---|---|
| Minerva 深度研究 | CLI adapter（自动探测 + 版本协商） | ✅ 动态适配 | 可用 |
| Semantic Scholar | HTTP adapter（Schema 防御解析） | ✅ 降级兼容 | 可用 |
| Claude Desktop (MCP) | stdio JSON-RPC（协议协商） | ✅ 向后兼容 | 可用 |
| WPS Note | MCP 声明式（由 WPS 侧实现） | — | 配置中 |
| FastAPI Web UI | 可选依赖 | — | 需手动安装 |

当外部工具更新时，KOS 适配器会自动探测版本、协商协议，缺失时返回友好降级提示。

### 已有配置用户

```bash
export KOS_HOME=/Users/xiamingxing/Workspace/kos
echo 'export KOS_HOME=/Users/xiamingxing/Workspace/kos' >> ~/.zshrc

# 常用命令
kos search "关键词"        # 跨域搜索
kos status                 # 系统状态
kos digest                 # 每日摘要
kos help                   # 帮助
```

## 三、功能清单

### 3.1 跨域全文搜索

一次搜索命中所有域。

```bash
kos search "信息化"                       # 全域搜索
kos search "考核" --domains gongwen        # 限定公文域
kos search "发言稿" --templates            # 包含模板库
kos search "平台" --domains gongwen,guozhuan --limit 5
```

**特性：** 228K 公文模版默认不参与搜索。加 `--templates` 才查模版。

### 3.2 系统状态一览

```bash
kos status              # 全貌：5 域文档数 + DB 状态
kos status --domain gongwen  # 单域
kos domains             # 域列表
kos digest              # 每日摘要卡片
```

### 3.3 本体知识图谱

77 个实体、112 条关系、8 种命名谓词。

```bash
kos onto card P:xia-mingxing              # 实体卡片
kos onto path P:xia-mingxing P:chai-hua   # 关系路径
kos onto list --type Person               # 按类型列出
kos onto graph --type Person              # Mermaid 图谱
kos onto discover                         # 隐含关联发现
kos onto rebuild                          # 一键重建
```

**8 种谓词：** `reports_to` `manages` `coordinates` `invites_to` `liaises_with` `owns` `works_on` `member_of`

### 3.4 智能推荐

查一个文档时自动发现相关文档。

```bash
kos related "数字化平台"     # 通过共享实体 + 关键词找到关联文档
```

### 3.5 周报与每日摘要

```bash
kos digest    # 今日知识概况
kos report    # 本周知识动态（最近文档 + 域统计）
```

**自动推送：** 每日 8:00 cross-domain-sync 完成后自动推送摘要。

### 3.6 索引管理

SHA-256 指纹增量索引，8 线程并行。

```bash
kos index                    # 全量重建
kos index --incremental      # 增量更新（秒级）
kos index --domain gongwen --jobs 8  # 单域并行
kos diff                     # 查看变更文件
```

### 3.7 质量维护

四种自动检查。

```bash
kos audit         # 质量审计：缺标签、待审过期
kos staleness     # 衰减检测：canonical 超 6 个月
kos contradict    # 矛盾检测：跨域冲突
kos suggest       # 建议引擎：标签推荐
kos all           # 全量巡检
```

### 3.8 域管理

```bash
kos onboard ~/新目录 "域名" --identity "角色"   # 接入新域
kos init                                        # 初始化向导
kos discover                                    # 跨域关联发现
```

---

## 四、十域总览

| 域 | 图标 | 文档数 | 索引策略 | 访问 |
|----|------|--------|---------|------|
| 📂 Workspace | 项目代码 | 2,796 | full_text | 读 |
| 🔴 驾驶舱 | 架构/治理 | 303 | full_text | 读 |
| 🟡 学习进化 | Vault 知识库 | 626 | full_text | 读 |
| 💼 工作文档 | 公文/卫健委/国转 | 1,464 | full_text | 读 |
| 🟢 个人 | 事务/健康/财务 | 29 | full_text | 读 |
| 🎨 创意创作 | 创意内容 | 562 | full_text | 读 |
| 🌐 公共 | 共享资源 | 41 | full_text | 读 |
| 🏠 家庭生活 | 家庭管理 | 1 | full_text | 读 |
| ⚙️ OPC | 运营中心 | 18 | full_text | 读 |
| 📋 OMO | 治理层 | 851 | full_text | 读 |

**总计: 6,691 个文档**

## 五、自动化

| 任务 | 频率 | 内容 |
|------|------|------|
| cross-domain-sync | 每日 8:00 | 增量索引 + 实体提取 + 每日摘要 |
| kos-weekly-health-check | 周一 9:00 | 质量审计 + 衰减 + 矛盾 |
| emr-biweekly-report | 周四 | 电子病历双周报 |
| emr-monthly-report | 每月18日 | 电子病历月报 |
| friday-check | 周五 | 周末工作检查 |
| waiting-queue-weekly | 周一 | 候诊排队周汇总 |
| quarterly-review | 季末25日 | 项目季度评审 |

## 六、MCP 工具（Claude Desktop 可用）

搜索、实体、状态等 9 个 tool 可在 Cowork 中直接调用。

## 七、CLI 命令速查

```
search   domains   status   digest   report   related
index    diff      audit    staleness  contradict  suggest
onto     discover  roles    onboard  init     help
```

`kos help <command>` 查看详细用法。

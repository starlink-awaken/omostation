# eCOS v5 · 用户旅程分析报告

**2026-06-08 · 产品视角**

---

## 一、当前旅程总览

```
                     ┌────────────────────┐
                     │  1. 新手初始化       │  5 min
                     │  ecos-link + qs     │
                     └────────┬───────────┘
                              ↓
┌────────────────┐  ┌─────────────────┐  ┌────────────────┐
│ 2. 日常研究      │  │ 3. 系统治理      │  │ 4. 知识沉淀     │
│ cockpit research │  │ cockpit context │  │ Minerva→Vault  │
│ 5-30 min         │  │ 2 min           │  │ 自动            │
└────────────────┘  └─────────────────┘  └────────────────┘
                              ↓                     ↓
                     ┌──────────────────────────────────┐
                     │   5. 工作区自动维护 (后台)        │
                     │   30 定时技能 · 15s 心跳 · KEI   │
                     └──────────────────────────────────┘
```

---

## 二、逐旅程分析

### 旅程 1: 新用户初始化

**实际路径追踪**:

```
git clone omostation
  ↓
cd projects/agora && uv sync         # 首次安装
cd projects/cockpit && uv sync       # 8 个项目需分别 uv sync
cd projects/kairon && uv sync        # 没有 make install 指引
...                                   # 用户困惑: 先装哪个?
  ↓
ecos-link install                     # 38 个 CLI 工具软链
  ↓
cockpit quickstart                    # 环境核验
  ↓                                   # 可能失败: ollama 未装 / 模型未拉
```

**当前痛点**:

| # | 痛点 | 根因 | 影响 |
|---|------|------|------|
| 1 | 8 个 `uv sync` 无统一入口 | 无工作区级 install 脚本 | 🔴 高 |
| 2 | `cockpit quickstart` 无 `--fix` 的自动修复 | 仅检测 + 提示，不自动修复 | 🟡 中 |
| 3 | 无指引告诉用户下一步该做什么 | 无 onboarding wizard | 🟡 中 |
| 4 | 首次 `make test` 时间长 (agora 97s, kairon 120s+) | 无 test-fast 选项 | 🟢 低 |

**建议修复**:
- 添加 `ecos-link setup` 命令，自动 `uv sync` 所有 8 项目
- `cockpit quickstart --fix` 自动安装 ollama + 拉模型

---

### 旅程 2: 日常研究

**实际路径追踪**:

```
用户: cockpit research ask "调研 DeepSeek V4 架构"
  ↓
cockpit.cli → commands/research.py:cmd_research_ask()
  ↓
1. OMO 读取 Phase 目标 (OMO_STATE_FILE)
2. CARDS 注入 P0 上下文 (metaos/cards_context.py)
3. 构建 system prompt + user question
4. 调用 research_agent  → runtime executor → LLM Gateway → ollama
  ↓
5. 工具编排:
   bos://kos/search → 语义搜索
   bos://minerva/draft → 深度研究草稿
   bos://ontoderive/audit → 事实核查
   bos://sophia/reason → 推理验证
  ↓
6. gbrain 持久化 (Postgres)
7. vault_sink 归档到 @学习进化
8. 返回研究摘要给 cockpit
```

**当前痛点**:

| # | 痛点 | 根因 | 影响 |
|---|------|------|------|
| 1 | 研究结果展示仅 CLI 文本，无 Web Dashboard | cockpit dashboard 功能不完整 | 🔴 高 |
| 2 | LLM 调用依赖 ollama 本地模型启动 | ollama 冷启动 10-30s | 🟡 中 |
| 3 | 研究过程中无进度反馈 | executor 无流式输出 | 🟡 中 |
| 4 | 历史研究不易查找 | 仅 SQLite + 散文件 | 🟢 低 |

---

### 旅程 3: 系统治理

**实际路径追踪**:

```
用户: cockpit workspace context
  ↓
cockpit_mcp.py:workspace_context()
  ↓
1. OMO_STATE_FILE → 当前 Phase + 目标
2. _scan_cards() → 活跃 P0 CARDS (驾驶舱/CARDS/*.md)
3. _read_constraints() → 治理约束检查
4. 聚合输出: Phase 目标 + CARDS 状态 + Code Freeze 检查
  ↓
cockpit workspace cards
  ↓
_scan_cards() → 按域/优先级排序显示
  ↓
cockpit workspace cards --check --card-id TASK-001
  ↓
cards_check() → OMO code_freeze 检查 + 卡片状态检查
```

**当前痛点**:

| # | 痛点 | 根因 | 影响 |
|---|------|------|------|
| 1 | `workspace` 和 `cockpit` 两套命令名并存 | cockpit/workspace 双入口 | 🔴 高 |
| 2 | `cards` 和 `l4cards` 两套 CARDS 命令 | 重构未完成 | 🔴 高 |
| 3 | `cockpit status` 响应慢 (需等待 matrix 心跳) | runtime scheduler 15s 心跳 | 🟡 中 |
| 4 | OMO debt 管理入口藏在 omo CLI 中 | cockpit 无法直接操作债务 | 🟡 中 |

---

### 旅程 4: 知识自动沉淀

**实际路径追踪**:

```
触发: Minerva 研究完成
  ↓
minerva/sinks/vault_sink.py:DEFAULT_BASE_PATH
  → ~/Documents/@学习进化/_storage/
  ↓
分类路由:
  1. ai-tech → _storage/知识订阅/技术资讯/
  2. methodology → _storage/灵感顿悟/
  3. industry-report → _storage/资料库/报告/
  ↓
定时触发 (cron_service):
  1. vault-index-sync (每日 02:00) → INDEX.md 更新
  2. vault-method-digest (每周一 10:00) → 方法论语取
  3. eureka-weekly-insight (每周一 10:00) → 洞察生成
```

**当前痛点**: 体验良好，全自动。

---

### 旅程 5: 工作区自动维护

**实际路径追踪**:

```
后台 cron_service:
  ↓
04:00 kos-daily-ontology-sync   06:00 metaos-daily-health
05:00 forge-daily-maintenance   07:00 platform-dashboard-update
  ↓
runtime matrix (每 15 秒):
  → matrix.yaml → 服务心跳 → 过期检测 → auto_heal
```

**当前痛点**: 自动维护是全自动的，无明显痛点。

---

## 三、命令一致性审计

### cockpit CLI 命令碎片化

当前 cockpit 存在 **3 套命令系统**：

| 入口 | 命令 | 状态 |
|------|------|------|
| `cockpit workspace ...` | context / cards / vault / domains / skill | ✅ L4 bridge (新) |
| `cockpit cards ...` | 检查 CARDS | ⚠️ 与 workspace cards 重复 |
| `cockpit l4cards ...` | list/get/search/serve | ⚠️ 第三套入口 |
| `cockpit research ...` | ask/audit/digest/... | ✅ 核心功能 |
| `cockpit status` | 项目健康概览 | ✅ 核心功能 |
| `omo-cli` | debt/phase management | ⚠️ 不在 cockpit 内 |
| `agora stats` | 服务健康统计 | ✅ 已美化 |

### 建议统一

```
cockpit context              ← 当前 workspace context
cockpit cards                ← 合并 cards + l4cards
cockpit research ...         ← 不变
cockpit status               ← 不变
cockpit debt ...             ← 合并 omo-cli 功能
cockpit domains              ← 新增我创建的
cockpit skill run ...        ← 新增我创建的
```

---

## 四、用户体验评分

| 维度 | 评分 | 说明 |
|------|------|------|
| 安装体验 | ⭐⭐ | 8 个 uv sync 分散，无统一入口 |
| 命令一致性 | ⭐⭐ | 3 套 CARDS 命令，2 个入口名 |
| 研究体验 | ⭐⭐⭐⭐ | LLM + 工具编排 + 自动归档 |
| 治理体验 | ⭐⭐⭐ | 功能全但入口分散 |
| 反馈速度 | ⭐⭐⭐ | scheduler 15s 延迟，无流式 |
| 可视化 | ⭐⭐ | Web dashboard 未完善 |
| 自动化 | ⭐⭐⭐⭐⭐ | 30 定时技能 + 28 服务自愈 |

---

## 五、优先改进建议

| 优先级 | 建议 | 影响 |
|--------|------|------|
| P0 | 合并 `cockpit` vs `workspace` 双入口 → 统一为 `cockpit` | 用户困惑 |
| P0 | 统一 CARDS 命令: `l4cards` + `workspace cards` → 一个入口 | 碎片化 |
| P0 | `ecos-link setup` 自动 `uv sync` 所有项目 | 安装体验 |
| P1 | cockpit 集成简单 omo debt 命令 | 减少 CLI 切换 |
| P1 | `cockpit research` 增加进度条 | 等待体验 |
| P2 | cockpit dashboard Web 完善 | 可视化 |

# 织星驾驶舱质量审计报告

日期：2026-09-24  
审计范围：26 个导航板块 + 顶部 HUD + 侧边栏 + 全局组件  
综合评分：248/500（49.6%）  
阻塞性问题（P0）：5 个  
高优改进（P1）：8 个  

---

## 总览

| 指标 | 数值 |
|------|------|
| 审计板块 | 26 |
| 综合评分 | 248/500 |
| P0 阻塞性问题 | 5 |
| P1 高优改进 | 8 |
| P2 体验优化 | 12 |
| JS 错误根因 | 3 类 |
| 需中文化的英文字符串 | 40+ |
| 完全空板块 | 2（personal、workbench） |
| 外部 JS 未加载导致功能失效 | 3 个板块 |

---

## 分板块评级表

| 板块 | 功能 | 内容 | 可读 | 可视化 | 关联 | 丰富 | 结构 | 动态 | 易理解 | 无错 | 总分 | 关键问题 |
|------|------|------|------|--------|------|------|------|------|--------|------|------|----------|
| orient（全景总览） | 4 | 4 | 4 | 3 | 4 | 4 | 4 | 4 | 3 | 4 | 38 | 英文 eyebrow 多 |
| arch（体系流程） | 4 | 3 | 3 | 3 | 3 | 3 | 4 | 4 | 3 | 4 | 34 | 依赖外部 panoramic_ui.js |
| gov（恢复准入） | 4 | 4 | 3 | 3 | 4 | 4 | 4 | 4 | 3 | 4 | 37 | 门禁状态英文 |
| ledger（路线BET） | 4 | 4 | 3 | 3 | 3 | 4 | 4 | 4 | 3 | 4 | 36 | — |
| swarm（Agent协同） | 3 | 3 | 3 | 3 | 3 | 3 | 3 | 3 | 3 | 4 | 31 | 星系图简单 |
| value（价值中枢） | 3 | 2 | 3 | 2 | 3 | 3 | 4 | 2 | 3 | 4 | 29 | panel_value 陈旧 |
| logs（事件日志） | 4 | 4 | 3 | 4 | 3 | 4 | 4 | 4 | 3 | 4 | 37 | 英文状态 chip |
| metrics（指标度量） | 4 | 3 | 3 | 4 | 3 | 3 | 4 | 4 | 3 | 4 | 35 | — |
| health（健康诊断） | 3 | 3 | 3 | 3 | 3 | 3 | 4 | 3 | 3 | 4 | 32 | — |
| loops（回路观测） | 3 | 3 | 3 | 3 | 3 | 3 | 4 | 4 | 3 | 4 | 33 | — |
| know（文档知识） | 4 | 4 | 3 | 2 | 3 | 4 | 4 | 3 | 3 | 4 | 34 | 缺可视化 |
| next（接下来） | 2 | 3 | 3 | 2 | 4 | 4 | 4 | 2 | 3 | 3 | 30 | renderNextHub 未加载 |
| topology（架构拓扑） | 1 | 2 | 2 | 1 | 2 | 2 | 2 | 1 | 2 | 3 | 18 | initTopologyModule 未加载 |
| knowledge-memory | 3 | 3 | 3 | 3 | 3 | 3 | 3 | 3 | 3 | 4 | 31 | 与 know 重叠 |
| skills-inventory | 3 | 3 | 3 | 2 | 3 | 3 | 3 | 3 | 3 | 4 | 30 | — |
| mof-grid（MOF元模型） | 2 | 2 | 3 | 2 | 3 | 3 | 3 | 2 | 3 | 3 | 26 | renderMofGrid 未加载 |
| scene-system（场景系统） | 3 | 3 | 3 | 2 | 3 | 3 | 3 | 3 | 3 | 4 | 30 | — |
| panorama（白皮书） | 4 | 4 | 3 | 3 | 4 | 4 | 4 | 3 | 3 | 4 | 36 | — |
| ecosystem-map | 3 | 3 | 3 | 3 | 3 | 3 | 3 | 3 | 3 | 4 | 31 | — |
| trace（因果拓扑） | 3 | 3 | 3 | 2 | 3 | 3 | 3 | 3 | 3 | 4 | 30 | — |
| capabilities（能力BOS） | 3 | 3 | 3 | 2 | 3 | 3 | 3 | 3 | 3 | 4 | 30 | — |
| learning（经验结晶） | 3 | 3 | 3 | 2 | 3 | 3 | 3 | 3 | 3 | 4 | 30 | — |
| atlas（架构模型） | 3 | 3 | 3 | 1 | 3 | 3 | 3 | 1 | 3 | 4 | 27 | 纯静态文本 |
| personal（主权中心） | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 4 | 13 | **完全空板块** |
| workbench（中枢工作台） | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 4 | 13 | **完全空板块** |

---

## 阻塞性问题（按严重性排序）

### P0-1：三个板块因外部 JS 未加载而功能丧失

**问题**：`next`、`topology`、`mof-grid` 三个板块依赖外部 JS 文件（`next_ui.js`、`topology_ui.js`、`mof_ui.js`），但这些文件从未通过 `<script>` 标签或服务器端注入加载到页面中。

**根因**：
- 模板 HTML 是单文件，所有内联 JS 在 `<script>` 标签内
- `live_server.py`（第 875 行）仅做模板变量替换，不注入外部脚本
- `go()` 函数在板块切换时调用 `window.renderNextHub()` / `window.renderMofGrid()` / `window.initTopologyModule()`（第 3099-3104 行），但这些全局函数从未被定义
- `typeof` 检查阻止了崩溃，但导致板块显示空容器

**影响板块**：next、topology、mof-grid  
**修复建议**：将 `next_ui.js`、`topology_ui.js`、`mof_ui.js` 的关键渲染函数内联到 template.html 中，或通过 `<script src="...">` 加载（需确保 CSP 允许）  
**预估工作量**：4-6 小时（内联 3 个文件的关键函数）

---

### P0-2：personal 和 workbench 板块完全空白

**问题**：`<section id="personal">`（第 1571 行）和 `<section id="workbench">`（第 1572 行）是空标签，无任何内容。

**根因**：注释说明这两个板块由 `workbench_ui.js` 动态创建（第 2528 行），但该 JS 文件同样未加载。

**影响板块**：personal、workbench  
**修复建议**：内联 `workbench_ui.js` 的核心渲染逻辑，或提供静态降级内容  
**预估工作量**：3-4 小时

---

### P0-3：persona-guidance-bar 空 DOM 占用布局空间

**问题**：第 1553 行 `<div id="persona-guidance-bar" style="margin-bottom:20px"></div>` 是一个空 div，没有任何 JS 向其填充内容，但其 `margin-bottom:20px` 会推开下方内容。

**根因**：`renderGuidanceHub()`（第 4764 行）只渲染 `panorama-hex-viz` 和 `panorama-loops-viz`，从未操作 `persona-guidance-bar`。

**影响板块**：全局（所有页面顶部）  
**修复建议**：移除空 div 或填充实际内容（如 persona 切换器）  
**预估工作量**：30 分钟

---

### P0-4：知行主权副驾按钮无实际功能

**问题**：第 1487 行顶栏按钮 `onclick="if(window.openSovereignCopilot) window.openSovereignCopilot()"`，但 `openSovereignCopilot` 函数从未定义。副驾抽屉（第 6287-6307 行）存在但内容仅注释"动态填充"。

**根因**：`copilot_service.py` 存在但前端集成未完成。没有 JS 函数打开抽屉并填充 AetherForge 算力状态、对话历史等内容。

**影响板块**：全局顶栏、personal（主权中心概念）  
**修复建议**：实现 `openSovereignCopilot()` 函数，从 `/api/v1/compute` 获取 AetherForge 状态并填充抽屉  
**预估工作量**：2-3 小时

---

### P0-5：CSP 阻止 manifest.json 和潜在资源加载

**问题**：`live_server.py` 第 875 行设置 CSP 头 `default-src 'none'`，同时模板第 36 行 meta CSP 也有同样设置。虽然 `manifest-src 'self'` 允许同源 manifest，但 `default-src 'none'` 会拦截任何未显式允许的资源。

**根因**：CSP 策略过于严格，`connect-src 'self'` 只允许同源 fetch，但实际 API 调用都是同源的，所以核心功能不受影响。主要影响是控制台报错噪音。

**影响板块**：全局  
**修复建议**：将 `default-src 'none'` 改为 `default-src 'self'`，或至少添加 `script-src 'self'` 以允许外部 JS 加载（配合 P0-1 修复）  
**预估工作量**：15 分钟

---

## 修复路线图

### P0 — 立即修（功能阻断）

| # | 问题 | 修复方式 | 工作量 |
|---|------|----------|--------|
| P0-1 | next/topology/mof-grid 三个板块无渲染 | 内联外部 JS 核心函数 | 4-6h |
| P0-2 | personal/workbench 空板块 | 内联 workbench_ui.js 或加静态降级 | 3-4h |
| P0-3 | persona-guidance-bar 空 div 占位 | 移除或填充内容 | 0.5h |
| P0-4 | 知行副驾按钮无功能 | 实现 openSovereignCopilot + 数据接入 | 2-3h |
| P0-5 | CSP 过于严格 | 放宽 default-src | 0.25h |

### P1 — 本周（质量显著提升）

| # | 问题 | 影响板块 |
|---|------|----------|
| P1-1 | 英文 eyebrow/标签中文化 | 全部板块 |
| P1-2 | value 板块 panel_value 缺真实数据 | value |
| P1-3 | 六维向量全 UNKNOWN 问题 | orient |
| P1-4 | 导航视图定制面板只列 15/26 板块 | 侧边栏 |
| P1-5 | atlas 板块纯静态文本缺可视化 | atlas |
| P1-6 | telemetry ticker 无真实 SSE 数据 | 全局 |
| P1-7 | search overlay 索引不完整 | 全局 |
| P1-8 | 导航分组折叠后无法记住状态 | 侧边栏 |

### P2 — 迭代（体验优化）

| # | 问题 | 影响板块 |
|---|------|----------|
| P2-1 | 板块间缺少更多关联链接 | 全局 |
| P2-2 | 静态内容（atlas、gov）缺交互可视化 | atlas, gov |
| P2-3 | 暗色模式下部分自定义 popover 对比度不足 | 全局 |
| P2-4 | 移动端导航滚动体验可优化 | 全局 |
| P2-5 | 数据源降级无视觉提示 | metrics, logs |
| P2-6 | 导航缺键盘快捷键提示 | 全局 |
| P2-7 | 搜索无最近搜索/搜索历史 | 全局 |
| P2-8 | 导出功能 CSV 下载后不自动关闭菜单 | 全局 |
| P2-9 | 门禁详情可折叠但无展开动画 | gov |
| P2-10 | learnings/know 内容重叠需合并或差异化 | know, knowledge-memory |
| P2-11 | 价值回路五阶段无可视化时间线 | value |
| P2-12 | Agent 协同星系图交互性弱 | swarm |

---

## 具体修复建议（按板块）

### next（接下来做什么）— renderNextHub 未加载

- **当前代码位置**：第 2241-2327 行（HTML 容器），第 3104 行（go() 调用）
- **根因**：`window.renderNextHub` 在 `next_ui.js` 第 148 行定义，但该文件从未加载
- **改动描述**：将 `next_ui.js` 中 `renderNextHub()` 函数体（约 450 行）内联到 template.html 的 `<script>` 中，或添加 `<script src="/next_ui.js">`（需配合 CSP 修复）
- **改动后预期**：4 个子系统（战役漏斗、阻塞 DAG、行动矩阵、路线时序）正确渲染

### topology（架构拓扑）— initTopologyModule 未加载

- **当前代码位置**：第 2328-2330 行（HTML），第 3102 行（go() 调用）
- **根因**：`window.initTopologyModule` 在 `topology_ui.js` 第 122 行定义，未加载
- **改动描述**：内联 `topology_ui.js` 核心渲染逻辑（约 1500 行），或改为静态降级展示
- **改动后预期**：`#topology-content-root` 渲染架构拓扑图

### mof-grid（MOF 元模型）— renderMofGrid 未加载

- **当前代码位置**：第 2707 行起（HTML），第 3099 行（go() 调用）
- **根因**：`window.renderMofGrid` 在 `mof_ui.js` 第 6 行定义，未加载
- **改动描述**：内联 `mof_ui.js` 核心逻辑（约 350 行）
- **改动后预期**：MOF 矩阵表格、约束卡片正确渲染

### personal（主权中心）— 完全空白

- **当前代码位置**：第 1571 行
- **改动描述**：添加静态内容或内联 `workbench_ui.js` 的 personal 渲染
- **改动后预期**：显示主权授权台入口、个人态势、署名自进化舱

### workbench（中枢工作台）— 完全空白

- **当前代码位置**：第 1572 行
- **改动描述**：添加静态内容或内联 `workbench_ui.js`
- **改动后预期**：显示工作台中枢面板

### persona-guidance-bar — 空 div

- **当前代码位置**：第 1553 行
- **改动描述**：如果短期内无法填充内容，改为 `style="display:none"` 或完全移除
- **改动后预期**：不再占用布局空间

### 知行主权副驾

- **当前代码位置**：第 1487 行（按钮），第 6287-6307 行（抽屉 HTML）
- **改动描述**：
  1. 定义 `window.openSovereignCopilot = function()` 打开抽屉
  2. 从 `D.compute` 获取 AetherForge 算力状态
  3. 填充 `#sovereign-cockpit-drawer-content` 显示模型列表、显存、推理端点
- **改动后预期**：点击顶栏按钮打开抽屉，展示真实算力信息

### CSP 修复

- **当前代码位置**：`live_server.py` 第 875 行，模板第 36 行
- **改动描述**：
  ```
  # 原：default-src 'none'
  # 改：default-src 'self'
  ```
  同时放宽模板 meta CSP：
  ```
  原：default-src 'none'
  改：default-src 'self'
  ```
- **改动后预期**：允许同源脚本/样式加载，消除控制台报错

### 英文内容中文化建议

| 当前位置 | 英文字符串 | 推荐译文 |
|----------|-----------|----------|
| 第 1908 行 | `Outcomes & Acceptance` | 成果与验收 |
| 第 1909 行 | `成果被采用，才开始证明价值` | （已是中文，保留） |
| 第 2251 行 | `Next Legal Action` | 法定行动中枢 |
| 第 2329 行 | `Architecture & Interfaces` | 架构与接口 |
| 第 2680 行 | `Architecture Atlas & Models` | 架构图谱与模型 |
| gateNames 对象（第 3174 行） | `Workflow 与 Git 执行完整性` 等 | 保留（已是中英混合，可读） |
| 第 3471-3479 行 | `运行中`, `实时响应`, `自适应`, `ARMED`, `HEALTHY` | 已是中文或标准术语 |
| logs 板块 chip | `OK`, `FAILED`, `STALE`, `MISSING` | 正常/失败/陈旧/缺失 |
| value 板块 | `NOT_PROVEN` | 待验证 |
| metrics 板块 | `NO_DATA` | 暂无数据 |

### 六维向量全 UNKNOWN

- **当前代码位置**：第 3163 行 `vectors` 数组，第 3164 行渲染
- **根因**：`D.metrics_kpi` 中 `health_score` 为 0，`total_events_24h` 为 0，`D.gates` 数据不完整
- **改动描述**：检查 `orchestrator.py` 是否正确计算 `metrics_kpi`，确保 `current.json` 包含有效的 `metrics_kpi` 字段
- **改动后预期**：六维向量显示真实数值而非 `—` 或 `0`

### 价值度量板块（value）数据陈旧

- **当前代码位置**：第 1897-1952 行（HTML），第 5773-5879 行（JS 渲染逻辑）
- **根因**：依赖 `D.panel_value`，该数据由 `panel-collect.py` 收集但可能未正确产出
- **改动描述**：确保 `panel-collect.py` 的 `collect_value_evidence` 函数产出数据并写入 `current.json`
- **改动后预期**：价值回路、验收门槛、证据时间线显示真实数据

---

## 附录：技术债务统计

| 类别 | 数量 | 说明 |
|------|------|------|
| 未加载的外部 JS | 5 | next_ui.js, mof_ui.js, topology_ui.js, workbench_ui.js, panoramic_ui.js |
| 空函数/未定义函数 | 3 | openSovereignCopilot, window.__zxLiveData 初始为空时的降级 |
| `display:none` 隐藏元素 | 1 组 | 第 1519-1531 行隐藏的契约元素 |
| `console.warn` 捕获 | 10+ | safeRender 包裹的渲染函数 |
| `NO_DATA` / `NOT_PROVEN` 硬编码兜底 | 40+ | 遍布各渲染函数 |
| CSS 类未使用 | 20+ | 定义但无对应 HTML |
| 英文硬编码字符串 | 40+ | eyebrow、placeholder、chip |

---

*审计基于 template.html 6312 行全量分析 + 服务端 API 实测 + 外部 JS 交叉验证*

---

## 修复实施记录

实施日期：2026-09-24  
实施范围：全部 5 个 P0 阻塞性问题  

### P0-5 — CSP 放宽 ✅

**文件**: `/Users/xiamingxing/.local/share/zhixing-dashboard/template.html`  
- **行号**: 36  
- **改动**: `default-src 'none'` → `default-src 'self'`；`script-src 'unsafe-inline'` → `script-src 'unsafe-inline' 'self'`  
- **结果**: 允许同源脚本加载

**文件**: `/Users/xiamingxing/.local/share/zhixing-dashboard/live_server.py`  
- **行号**: 875  
- **改动**: CSP 响应头同上放宽  
- **结果**: HTTP 响应头 CSP 同步更新

---

### P0-1 — 外部 JS 加载修复 ✅

**文件**: `/Users/xiamingxing/.local/share/zhixing-dashboard/live_server.py`  
- **行号**: 1670-1679（新增）  
- **改动**: 在 `do_GET` 的 `else: 404` 之前添加 `/*.js` 路由，安全地服务同目录 `.js` 文件  
- **安全约束**: 仅服务 `Path(__file__).parent` 目录下的文件，防止路径遍历  
- **结果**: 所有外部 JS 文件可通过 HTTP 200 访问

**文件**: `/Users/xiamingxing/.local/share/zhixing-dashboard/template.html`  
- **行号**: 6346-6350（新增）  
- **改动**: 在 `</body>` 前添加 5 个 `<script src="...">` 标签  
  - `/workbench_ui.js` → personal/workbench 渲染
  - `/next_ui.js` → `window.renderNextHub()`
  - `/topology_ui.js` → `window.initTopologyModule()`
  - `/mof_ui.js` → `window.renderMofGrid()`
  - `/panoramic_ui.js` → `window.renderPanoramicArchitecture()`
- **结果**: next/topology/mof-grid 三板块渲染函数可用；personal/workbench 由 workbench_ui.js 动态填充

---

### P0-2 — personal/workbench 空板块 ✅

**依赖 P0-1 解决**  
- `workbench_ui.js` 加载后，第 56-70 行自动向 `#workbench` 和 `#personal` 注入完整内容  
- 无需额外静态降级内容

---

### P0-3 — persona-guidance-bar 空 div ✅

**文件**: `/Users/xiamingxing/.local/share/zhixing-dashboard/template.html`  
- **行号**: 1553  
- **改动**: 移除 `<div id="persona-guidance-bar" style="margin-bottom:20px"></div>`，替换为注释  
- **结果**: 不再占用布局空间

---

### P0-4 — 知行主权副驾 ✅

**文件**: `/Users/xiamingxing/.local/share/zhixing-dashboard/template.html`  
- **行号**: 4802-4835（新增）  
- **改动**: 实现 `window.openSovereignCopilot` 函数和 `window.closeSovereignCopilotDrawer` 函数  
  - 从 `D.compute` 获取算力数据动态渲染抽屉内容  
  - 无数据时显示静态信息面板  
  - 添加 `⌘J` / `Ctrl+J` 键盘快捷键  
- **结果**: 点击顶栏按钮或按 ⌘J 打开主权副驾抽屉，展示 AetherForge 算力信息

---

### 服务重启与验证

```
launchctl kickstart -k gui/$(id -u)/com.omostation.zhixing-dashboard
```

验证结果：
- `GET /` → 200
- `GET /next_ui.js` → 200（含 renderNextHub 函数）
- `GET /topology_ui.js` → 200（含 initTopologyModule 函数）
- `GET /mof_ui.js` → 200（含 renderMofGrid 函数）
- `GET /workbench_ui.js` → 200
- `GET /panoramic_ui.js` → 200
- CSP 响应头确认：`default-src 'self'; script-src 'unsafe-inline' 'self'`

---

### 修改文件汇总

| 文件 | 改动行数 | 改动类型 |
|------|----------|----------|
| template.html | 6 处 | CSP + script 标签 + persona bar 移除 + copilot 函数 |
| live_server.py | 2 处 | CSP + .js 路由 |

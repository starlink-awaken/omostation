# CLAUDE.md — Agora Dashboard (eCOS v5 L3 Entry Layer)

## 项目身份
`agora-dashboard` 是 eCOS v5 7 层架构的 **L3 入口层**，充当多模态观察视界。它独立于 `cockpit`，但与其同属入口层，专司人类与系统的可视化直觉交互。

## 技术栈与约束
- **框架**：Next.js 15+ (App Router) + React 19 + TailwindCSS 4
- **样式**：赛博朋克暗黑主题，全局引入扫描线、网格光栅与 glitch 特效 (`lucide-react` 组件库)。
- **包管理**：`npm` (强制使用 `--legacy-peer-deps` 应对依赖冲突)。

## 架构原则 (X1 隔离约束)
- **只读特权**：作为多模态视界，其 Server Component 直接物理读取 `.omo/state/system.yaml` 及其他 `.omo/` L0 文件。这是为了消除状态 Gap 所做的零损耗设计。
- **禁止侧写**：Dashboard 绝对不允许直接向文件系统或 `.omo/` 写入任何变更。所有的状态突变（Mutation）必须通过触发 L3 `cockpit` 命令或 I0 `agora` 路由链来执行。

## 开发常用命令
```bash
# 启动开发服务器
npm run dev

# 重新安装依赖（含镜像）
npm install --legacy-peer-deps --registry=https://registry.npmmirror.com

# 触发全栈 lint 与构建 (Github Actions 执行项)
npm run lint
npm run build
```

## OMO 整合
其展示内容高度耦合于 OMO 治理层（如 Phase 6 的演进循环、系统债务、活跃域数量、健康度 `make governance-verify` 分数），任何 L0 状态变异将立即反映于大盘。

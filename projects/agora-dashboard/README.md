# Agora Dashboard (eCOS v5 L3 Entry Layer)

## 身份定位
`agora-dashboard` 是 eCOS v5 体系下的 **多模态观察视界**，与 `cockpit` (CLI) 平级，同属 L3 入口层。

它提供基于 Web 的现代化 UI（Next.js 15+ 栈，赛博朋克暗黑主题），直连底层的 `system.yaml` 等 L0/M0 知识库文件，为人类指挥官提供**零损耗**的状态直觉。

## 核心特性
1. **L0 物理穿透**：Next.js Server Components 直接读取 `.omo/state/system.yaml` 物理文件，确保 Dashboard 与 OMO 治理层零延迟同步。
2. **Phase 6 引擎大盘**：内置对 OPC-P6 (自我进化飞轮) 状态机、系统健康度 (Health Score)、遗留债务 (System Debt) 和活跃节点数的全景展示。
3. **沉浸式赛博美学**：全局引入 Glitch 特效与扫描线，采用 `lucide-react` 构建高科技质感的工业级图表组件。

## 快速启动
```bash
cd projects/agora-dashboard
npm install
npm run dev
```

打开 `http://localhost:3000` 即可进入控制枢纽。

## 架构约束 (SSOT 协议)
- 本组件作为 L3 观察层，**仅拥有 L0 态的只读权限**。
- 所有数据写入必须通过 L3 `cockpit` CLI 或者触发 I0 `agora` 的 BOS 路由进行，`agora-dashboard` 绝不能直接修改 `.omo/` 目录中的文件。

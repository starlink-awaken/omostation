# agora-dashboard — System Boundary

> 本文档描述 agora-dashboard 与 eCOS 系统其他部分的边界：暴露的接口、依赖的上游、影响的下游。
>
> 架构演进对比参见：[`docs/ARCHITECTURE-EVOLUTION.md`](../docs/ARCHITECTURE-EVOLUTION.md)

---

## 1. 暴露接口

### BOS URI



### 入口

- **HTTP dev**: `npm run dev` :3000
- **Build**: `npm run build` 

## 2. 上游依赖

- .omo/state/system.yaml
- cockpit (L3)

## 3. 下游影响



## 4. 配置 / SSOT

- 项目源码：`projects/agora-dashboard/`
- 入口定义：`projects/agora-dashboard/pyproject.toml` 或 `package.json`
- 测试：`cd projects/agora-dashboard && npm run lint && npm run build`

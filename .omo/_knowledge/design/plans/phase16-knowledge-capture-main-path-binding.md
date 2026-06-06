# Phase16 Knowledge Capture Main Path Binding

> 状态: proposed
> 日期: 2026-06-05
> 范围: `wksp -> agora -> gbrain/kairon -> .omo`
> 目标: 把 `knowledge-capture-search` 从场景壳，压成一条明确的主路径绑定

---

## 1. 为什么要单独绑定

现在已经有三样东西：

1. Phase16 场景契约：`knowledge-capture-search`
2. L3 入口矩阵：`wksp / runtime / agora / sharedbrain-bridge`
3. L0/L1/L4 状态桥：protocol -> runtime -> governance summary

但还缺一件事：

**这条用户主路径到底从哪进、经过谁、由谁给出结果状态。**

如果不把这条链绑死，Phase16 还是会停在“有 scenario、有 evidence、但没有稳定主入口”。

---

## 2. 主路径绑定

这里要明确区分两层：

1. **目标收敛绑定**
   `wksp -> agora -> gbrain/kairon -> .omo`
2. **当前可执行绑定**
   `wksp -> agora -> minerva-mcp -> .omo`

原因不是要改目标，而是当前仓内已经存在可验证的 `knowledge_ingest` / `knowledge_search`
路由契约，它们应由 `agora-routes.json` 给出。当前基线已经恢复到正式 route file；
只有在 live route file 再次漂移或被污染时，`wksp` probe 才回退到
`agora/src/agora/registry.yaml` 推导出 `minerva` knowledge facade。
如果文档继续只写 `gbrain`，
那就是规划和可执行事实脱节。

### 2.1 用户入口

默认入口：`wksp`

原因：

- `wksp` 目前最像产品/操作者统一入口
- 它已经承载 research/import/status/contracts/profile/demo 等用户旅程
- 它适合承接“输入一段知识 / 一个 markdown 文件 / 一个查询语句”的交互语义

### 2.2 集成织物

默认织物：`agora`

原因：

- 跨服务调用不应该由 `wksp` 直接散射
- `agora` 已经承担 MCP 聚合、服务发现、路由和代理
- 这条路径里的跨服务能力聚合，应统一收敛到 fabric

### 2.3 能力执行

目标分工：

- `gbrain`：capture / search / retrieval
- `kairon`：capability binding / trace / contract / governance-facing interpretation

边界：

- `gbrain` 负责“能不能抓、能不能搜、搜到了什么”
- `kairon` 负责“这条路径用了什么能力、为什么可信、证据如何挂载”

当前落地分工：

- `minerva-deep-research` / `minerva-mcp`：作为当前 live knowledge facade，暴露 `knowledge_ingest` / `knowledge_search` / `knowledge_closed_loop`
- `agora`：把这些 tool route 收口为 fabric contract
- `gbrain`：仍是目标中的专用知识 runtime，但这条主路径还没直接切过去

当前 live probe 结论也要明确区分两类问题：

- `agora-routes` 漂移：属于 route contract 基线问题，现已恢复
- `minerva` 健康检查未通过：属于当前 live knowledge facade 未就绪，仍阻断真实 capture/search

### 2.4 治理与结果态

治理与结果记录：`.omo`

记录内容：

- evidence refs
- recovery path
- blocked reason
- status summary

结果状态固定为：

- `ready`
- `needs_approval`
- `blocked`
- `failed_with_recovery`
- `completed`

---

## 3. 推荐执行链

```text
用户输入文本/markdown/query
  -> wksp 接住入口语义
  -> wksp 通过 agora 触发能力路由
  -> agora 调用当前 knowledge route target（当前基线是 minerva-mcp，目标收敛到 gbrain）
  -> kairon 生成 capability binding / trace
  -> .omo 记录 evidence / policy / recovery / closeout
  -> wksp 或 product shell 返回用户可读结果
```

### 3.1 当前可执行链

```text
wksp
  -> agora
  -> minerva-mcp.knowledge_ingest / knowledge_search
  -> .omo evidence / status
```

### 3.2 目标收敛链

```text
wksp
  -> agora
  -> gbrain capture/search/retrieval
  -> kairon binding/trace
  -> .omo evidence / status
```

---

## 4. 每层输出什么

### `wksp`

输出：

- 用户输入受理
- 结果页/结果文本
- 状态枚举

不输出：

- 底层路由细节
- 运行时健康快照

### `agora`

输出：

- 路由执行
- 服务选择
- 调用聚合

不输出：

- 用户结果文案
- 治理摘要

### `gbrain`

输出：

- capture receipt
- search hits
- retrieval result

### `kairon`

输出：

- capability binding
- scenario trace
- contract validation signal

### `.omo`

输出：

- evidence refs
- blocked / recovery / closeout state
- governance-visible summary

---

## 5. 最小实施顺序

### Step 1

让 `wksp` 拥有一个明确的 `knowledge-capture-search` 入口语义。

### Step 2

让 `wksp` 对跨服务调用优先走 `agora`，而不是直接散射到多个实现。

### Step 3

先承认并验证当前 `agora -> minerva` knowledge facade 的 route contract 是可执行基线。

### Step 4

让 `gbrain` 的 capture/search 结果能被 `kairon` 补齐 trace / binding，并逐步替换 `minerva-mcp` facade。

### Step 5

让 `.omo` 只记录状态与证据，不吞掉产品入口。

---

## 6. 验证口径

### 用户验证

用户能完成：

1. 输入知识
2. 发起查询
3. 收到结果状态
4. 知道为什么可信
5. 失败时知道下一步怎么办

### 系统验证

至少要能看到：

- `wksp` 作为入口
- `agora` 作为织物
- `gbrain` 产生 capture/search 结果
- `kairon` 提供 trace/binding
- `.omo` 产出 evidence/status

### 治理验证

主路径不允许：

- 绕过 Phase15 ledger
- 把 draft 自动变 active
- 把运行时快照混成治理状态

---

## 7. 结论

Phase16 真正要落地的，不是一个抽象“产品面收敛”口号，而是这条主路径：

`wksp -> agora -> gbrain/kairon -> .omo`

只要这条链能稳定跑、能稳定解释、能稳定失败恢复，Phase16 才算真的把架构往用户价值方向推了一步。

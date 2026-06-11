# R50 gbrain 探路报告 (2026-06-11)

## 仓类型
**TypeScript 真仓** — Bun 运行时（`"bun": ">=1.3.10"`），无 Node 特有依赖。核心堆栈：
- MCP SDK (`@modelcontextprotocol/sdk: 1.29.0`)
- PGlite WASM (`@electric-sql/pglite: 0.4.3`)
- AI SDK (`ai: ^6.0.168`)
- **zod: `^4.3.6`**（已有）
- TypeScript: `^5.6.0`

---

## 现有 .jsonl 写调用（文件:行号）

| 文件 | 函数 | 路径模式 | 原子性 |
|------|------|---------|--------|
| `src/core/minions/handlers/shell-audit.ts:55` | `fs.appendFileSync` | `~/.gbrain/audit/shell-jobs-YYYY-Www.jsonl` | append |
| `src/core/facts/phantom-audit.ts:71` | `fs.appendFileSync` | `~/.gbrain/audit/phantoms-YYYY-Www.jsonl` | append |
| `src/core/audit-slug-fallback.ts` | `fs.appendFileSync` | `~/.gbrain/audit/slug-fallback-YYYY-Www.jsonl` | append |
| `src/core/rerank-audit.ts` | `fs.appendFileSync` | `~/.gbrain/audit/rerank-failures-YYYY-Www.jsonl` | append |
| `src/core/budget/budget-tracker.ts` | `appendFileSync` | `~/.gbrain/audit/budget-YYYY-Www.jsonl` | append |
| `src/core/brainstorm/checkpoint.ts` | `fs.writeFileSync` | `~/.gbrain/audit/brainstorm-*.json` | 原子（.tmp+rename） |
| `src/core/remediation-checkpoint.ts` | `fs.writeFileSync` | `~/.gbrain/remediation/*.json` | 原子（.tmp+rename） |
| `src/core/memory-tree.ts:36` | `writeFileSync` | `memory-tree-pins.json` | **非原子** |
| `src/core/cross-modal-eval/receipt-write.ts` | `fs.writeFileSync` | `eval-receipts/*.json` | 原子 |

**注意**: `memory-tree.ts:36` 的 `writePinFile` 是直接覆盖写入，不是 append，**存在竞争风险**。

---

## .omo/ 目录状态
**不存在**。`projects/gbrain/.omo/` 路径下无任何治理目录。

---

## zod/AppendOnlyLog 等价物

### zod 现状
- 已依赖 `zod: ^4.3.6`
- `z.object` 使用广泛：
  - `src/core/schema-pack/manifest-v1.ts`: `SchemaPackManifestSchema = z.object({...})` — 完整的 pack manifest 校验
  - `src/core/schema-pack/` 下无 AppendOnlyLog
- `src/core/ai/gateway.ts:1901`: `ExpansionSchema = z.object({...})`

### AppendOnlyLog 现状
**完全不存在**。`grep -rn "AppendOnlyLog\|append_only\|AppendOnly" src/` 无任何结果。

### 现有的 JSONL 模式（可复用）
所有 audit writer 都使用同一套模式：
```typescript
// 共享自 src/core/audit-week-file.ts
import { isoWeekFilename, resolveAuditDir } from '../audit-week-file.ts';
import * as fs from 'node:fs';

function log(event: object) {
  const dir = resolveAuditDir();        // 兼容 GBRAIN_AUDIT_DIR
  const file = path.join(dir, isoWeekFilename('prefix'));
  fs.mkdirSync(dir, { recursive: true });
  fs.appendFileSync(file, JSON.stringify(event) + '\n');
}
```

这是标准的 ISO-week 轮转 append 模式，与 omo AppendOnlyLog 的设计高度一致——可直接对标移植。

---

## §12.2.2 TypeScript 5步接入清单

- [ ] **Step 1: AppendOnlyLog (zod 适配)**
  - 位置：`src/core/append-only-log.ts`（新建）
  - 依赖：已有 `zod: ^4.3.6`，无需安装
  - 核心类型：
    - `AppendOnlyLogOptions`（filePath, zodSchema, maxFileSize?, onCorruption?）
    - `append<T>(event: T): Promise<void>`（写入前校验 schema，原子 append）
    - `readEvents<T>(filter?: EventFilter): AsyncGenerator<T>`
    - `latest<T>(): Promise<T | null>`
    - `compact(targetVersion: string): Promise<void>`（可选）
  - 复用现有模式：`src/core/audit-week-file.ts` 的 `isoWeekFilename` + `resolveAuditDir` + `fs.appendFileSync`

- [ ] **Step 2: 迁移现有 JSONL 审计点**
  - `shell-audit.ts` → `AppendOnlyLog`
  - `phantom-audit.ts` → `AppendOnlyLog`
  - `audit-slug-fallback.ts` → `AppendOnlyLog`
  - `rerank-audit.ts` → `AppendOnlyLog`
  - `budget-tracker.ts` → `AppendOnlyLog`
  - **优先级高**：`memory-tree.ts:36` 的非原子写入需优先迁移

- [ ] **Step 3: 事件溯源事件总线**
  - `src/core/event-bus.ts`（新建）
  - 接口：`emit(event)`, `subscribe(type, handler)`, `subscribeOnce(type, handler)`
  - 内部使用 `AppendOnlyLog` 做持久化

- [ ] **Step 4: MCP 事件注入**
  - `src/mcp/events.ts`（新建）
  - 注入 MCP server，在每个 tool call 前/后 emit 事件
  - 消费端为 `AppendOnlyLog`

- [ ] **Step 5: .omo/ 治理初始化**
  - 创建 `projects/gbrain/.omo/` 目录结构
  - 接入 `xplane.ts` 探活覆盖率检测

---

## 接入工作量估算
**中等** — 具体分析：

| 因素 | 评估 |
|------|------|
| zod 版本 | `^4.3.6` 已安装，零额外依赖 |
| 现有模式 | `audit-week-file.ts` 提供了完美的参照实现 |
| JSONL writer 数量 | 5 个 append + 1 个非原子覆盖（`memory-tree.ts`），均可对标迁移 |
| AppendOnlyLog 复杂度 | 核心约 150-200 LOC（zod 校验 + 原子 append + 读取器） |
| 无其他 .omo 治理 | 从零搭建 .omo/ 目录，但 gbrain 已有完整测试基础设施 |
| 类型安全 | TypeScript 5.6 + zod v4 → 体验优秀 |

**结论**：接入比 kairon 更简单。gbrain 是单一进程、无多包 monorepo 结构；已有 5 个 JSONL append writer 构成天然的 AppendOnlyLog 候选队列；zod 充足；唯一挑战是 `memory-tree.ts` 的非原子写入需优先处理。

---

## 备注

1. **zod v4**：`package.json` 写的是 `"zod": "^4.3.6"`，注意不是 v3 — zod v4 的 API 有 breaking change（如 `z.object()` 的默认 strict 行为），接入时需注意。
2. **Bun 兼容性**：所有 `import { ... } from 'node:fs'` 在 Bun 中正常工作，无需 shim。
3. **竞争风险**：`memory-tree.ts:36` 的 `writePinFile` 是当前唯一非原子的 JSON 文件写入，**强烈建议作为 Step 2 的 P0 项**。
4. **无 fs-extra**：gbrain 直接用 `node:fs`，append 靠 `fs.appendFileSync`，原子写靠 `fs.writeFileSync` + `.tmp + rename`。
5. **命名空间前缀**：gbrain audit 文件都落在 `~/.gbrain/audit/` 下，AppendOnlyLog 接入时应同样尊重 `GBRAIN_AUDIT_DIR` 环境变量。

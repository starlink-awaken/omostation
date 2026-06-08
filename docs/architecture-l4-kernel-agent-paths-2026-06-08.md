# L4 Kernel · 两种使用路径下的约束机制

**2026-06-08 · 架构设计 · 回答核心问题**

---

## 问题

L4 有两种日常使用路径：

```
路径 1: 通过 agora (MCP/HTTP/CLI) → 触发 L4 操作
路径 2: Agent 直接进入 ~/Documents/@*/ 目录，加载 CLAUDE.md 产生约束
```

在这两种路径下，l4-kernel 如何起作用？

---

## 答案：三层介入

```
路径 1 (agora 触发)         路径 2 (Agent 直入)
     │                           │
     ▼                           ▼
┌─────────────┐          ┌─────────────┐
│  cockpit    │          │  Agent 读    │
│  MCP tools  │          │  CLAUDE.md  │
│             │          │  → 理解约束  │
│  import     │          │             │
│  l4_kernel  │          │  自由操作    │
│  ↓          │          │  文件系统    │
│  KemsPlane  │          │             │
│  统一读写    │          │             │
└─────────────┘          └──────┬──────┘
                               │
                    ┌──────────▼──────────┐
                    │   L4 Kernel 介入     │
                    │   (被动 · 事后校验)   │
                    │                     │
                    │  1. CLAUDE.md 模板化  │
                    │  2. 事后一致性扫描    │
                    │  3. 定时健康检查      │
                    └─────────────────────┘
```

---

## 路径 1: 通过 agora (MCP/HTTP/CLI) — 强约束

这是 l4-kernel 的**主战场**。cockpit 的 MCP 工具内部调用 l4-kernel API。

```
用户/Agent → cockpit MCP → l4-kernel API
                              │
                              ├─ KemsPlane.read_state()   → 自动校验 frontmatter
                              ├─ KemsPlane.write_state()  → 自动注入标准字段 + ts
                              ├─ KemsPlane.append_signal()→ 自动补 ts + 类型校验
                              ├─ CardsPlane.scan_cards()  → yaml.safe_load 正确解析
                              └─ CardsPlane.check_compliance() → OMO 约束 + 卡片状态
```

**约束力度**: 强制 — 通过 cockpit 的操作都经过 l4-kernel API，自动获得校验。

---

## 路径 2: Agent 直入目录 — 弱约束 (事后检测)

这是目前的现实：Agent 被加载到域目录下，读取 CLAUDE.md 理解约束，然后自由操作文件。

### 2.1 当前的问题

```
Agent 读 CLAUDE.md:
  §0 KEMS 六面      → Agent 理解: "有 6 个目录"
  §1 快速路由        → Agent 知道去哪找文件
  会话入口协议        → Agent 按顺序读 STATUS→STATE→MEMORY→signals→TIMELINE

Agent 写文件:
  → 直接 write STATE.md       ← 无 frontmatter 校验
  → 直接 append signals.md     ← 可能用错 emoji
  → 直接修改 MEMORY.md         ← 可能漏字段
```

**Agent 没有执行 l4-kernel 的校验规则。它只是读了 CLAUDE.md 的文本描述。**

### 2.2 Kernel 如何介入路径 2

Kernel 通过三个机制介入：

#### 机制 1: CLAUDE.md 模板化 — 让 Agent 自我约束

```
当前 CLAUDE.md 的 §0 KEMS 六面:
  只是描述性的: "_control/ | STATE MEMORY INDEX TIMELINE"

增强后的 CLAUDE.md (由 l4-kernel 生成):
  §0 KEMS 六面 + 操作约束:
  
  控制面文件必须遵循以下规范:
  - STATE.md: 必须含 YAML frontmatter (title, status, type, owner, created)
  - MEMORY.md: 必须含 YAML frontmatter (同上)
  - signals.md: 信号类型必须为 ✅/⚠️/🔴/ℹ️，格式 | 类型 | 日期 | 信号 |
  - STATUS.md: 当前状态必须为 STABLE/ALERT/CRITICAL 之一
  - control-rules.md: CR ID 格式为 CR01-CR99
  
  修改任何控制面文件后，必须执行:
    l4-kernel domain check <domain_id>
  
  如果 check 报 error，必须修复后重新操作。
```

**效果**: Agent 读到的不只是"有什么"，还有"怎么写才对"。Kernel 的 Schema 下沉到 CLAUDE.md 中。

#### 机制 2: 事后一致性扫描 — Kernel 作为质检员

```
定时 (runtime cron / cockpit health --full):
  │
  ├── l4-kernel.KemsValidator.validate_all()
  │   ├── V-CONTROL-01: 5 核心文件是否存在?
  │   ├── V-CONTROL-02: MEMORY.md frontmatter 必选字段?
  │   ├── V-CONTROL-03: STATUS.md 三态枚举正确?
  │   ├── V-CONTROL-04: signals.md 信号类型合法?
  │   └── V-CONTROL-07: owner 字段非空?
  │
  ├── 发现问题:
  │   ├── signals 信号: "⚠️ | 2026-06-08 | STATUS.md frontmatter 缺失 owner"
  │   ├── OMO debt: DEBT-L4-001 "域结构不完整"
  │   └── cockpit health --full 红色告警
  │
  └── Agent 下次读 CLAUDE.md:
      └── signals.md 中的 ⚠️ 信号 → Agent 知道需要修复
```

**效果**: Agent 自由操作 → Kernel 事后扫描 → 发现偏离 → 写入 signals → Agent 下次自愈。

#### 机制 3: cockpit MCP 工具作为统一出口

```
即使 Agent 直入目录修改文件，当需要"查询"时:

Agent: cockpit workspace context
  → cockpit_mcp.py → l4_kernel.DomainRegistry
  → 返回: Phase + CARDS + 域健康度 + 约束 violation 列表

Agent 看到 violation → 修复 → 下次 scan 通过
```

---

## 三、完整闭环

```
路径 2 的完整闭环:

1. Agent 进入 @学习进化/
   ↓ 读 CLAUDE.md (含 l4-kernel 生成的 Schema 约束)
   ↓
2. Agent 自由操作文件
   ↓
3. 定时: l4-kernel validate → 发现偏离
   ↓
4. 写入 signals: ⚠️ 信号
   ↓
5. Agent 下次 cockpit context:
   ↓ 看到 violation 列表
   ↓
6. Agent 修复偏离
   ↓
7. 定时 scan → 通过 → 信号转为 ✅
```

**这就是 l4-kernel 在路径 2 中的作用: 不是阻止 Agent，而是通过 CLAUDE.md 模板 + signals 信号 + 定时扫描，形成自愈闭环。**

---

## 四、实现：将 Schema 注入 CLAUDE.md

### 4.1 当前 CLAUDE.md 的问题

```
§0 KEMS 六面  → 只有结构描述，无操作约束
§1 快速路由    → 只有文件路径，无格式要求
会话入口协议   → 只有阅读顺序，无写入规范
```

### 4.2 增强方案

```python
# l4-kernel 生成增强版 CLAUDE.md

def generate_claude_entrypoint(domain: Domain) -> str:
    """生成包含 l4-kernel Schema 约束的 CLAUDE.md。"""
    
    return f"""# {domain.name} — 域入口协议

> L4 | KEMS 六面 | 操作约束由 l4-kernel 管理
> v5.2 | {today} | l4-kernel Schema 注入

## §0 KEMS 六面 + 操作约束

| 平面 | 目录 | 内容 | 写入规范 |
|------|------|------|---------|
| 控制面 | `_control/` | STATE MEMORY TIMELINE | 必须含 YAML frontmatter (title/status/type/owner/created) |
| 事实面 | `_entities/` | ENTITIES | 实体定义需含 id/type/domain/created |
| 知识面 | `_knowledge/` | 方法论/经验/概念 | Markdown + 可选 frontmatter |
| 资料面 | `_storage/` | 资料库 知识订阅 | 无格式约束 |
| 归档 | `_archive/` | 历史版本 | 无格式约束 |

## §0.1 控制面强制规范 (l4-kernel Schema)

修改以下文件时，必须遵守:

- **STATE.md**: frontmatter 必含 title, status, type, owner, created
- **MEMORY.md**: 同上
- **signals.md**: 信号类型 = ✅⚠️🔴ℹ️ | 格式 = `| 类型 | 日期 | 信号 |`
- **STATUS.md**: 当前状态 = STABLE|ALERT|CRITICAL | 必须含三态定义表
- **control-rules.md**: CR ID = CR01-CR99 | CR01-CR03 为内核规则(不可删)

## §0.2 操作后校验

修改任何控制面文件后，执行:
```
l4-kernel domain check {domain.id}
```

如果 check 报 error (红色)，必须修复后重新操作。
warning (黄色) 建议修复，info (灰色) 可忽略。

## §1 快速路由
{existing_routes}

## §2 会话入口协议

```
1. _control/STATUS.md    — 系统三态判定 (检查当前状态)
2. _control/STATE.md     — 域状态
3. _control/MEMORY.md    — 元事实与指针
4. _control/signals.md   — 最新信号 (检查是否有 ⚠️🔴)
5. _control/TIMELINE.md  — 时间线
6. `_inbox/`             — 收件箱
```

## §3 健康检查

定期执行 `l4-kernel health` 或 `cockpit health --full`
检查域健康度和 Schema 合规性。
"""
```

### 4.3 一键更新所有域的 CLAUDE.md

```python
from l4_kernel import DomainRegistry
from l4_kernel.templates import generate_claude_entrypoint

reg = DomainRegistry()
for domain in reg.list_document_domains():
    content = generate_claude_entrypoint(domain)
    (domain.path / "_control" / "CLAUDE.md").write_text(content)
```

---

## 五、总结

| 路径 | Kernel 介入方式 | 约束力度 | 时效性 |
|------|----------------|:---:|:---:|
| 路径 1 (agora) | KemsPlane API 自动校验 | 强 (实时) | 立即 |
| 路径 2 (Agent 直入) | CLAUDE.md 模板 → Agent 自我约束 | 中 (引导) | 操作前 |
| 路径 2 (Agent 直入) | KemsValidator 定时扫描 | 中 (事后) | 延迟 (cron) |
| 路径 2 (Agent 直入) | signals 信号 → Agent 自愈 | 中 (闭环) | 下次会话 |

**核心设计**: l4-kernel 不阻止 Agent 自由操作（这是 L4 的设计原则），但通过三个机制确保约束最终被遵守：
1. **事前**: CLAUDE.md 模板化 → Agent 知道怎么写
2. **事后**: 定时扫描 → 发现偏离
3. **闭环**: signals 信号 → Agent 自愈

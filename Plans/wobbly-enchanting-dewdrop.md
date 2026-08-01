# Phase 49: 知识流动 · 用户价值兑现

> **创建时间**: 2026-08-01 | **模式**: Plan Mode | **前置**: Phase 48 v2 已完成 (health=96, GAC 瘦身, Brain DRY)
> **时间窗**: 2026-08-01 ~ 2026-08-21 (3 周)
> **目标**: 让 5193 篇 KOS 知识流入日常工作流，个人大脑从 CLI 搬到 Web，X3 交付达标

---

## 0. Context — Phase 48 完成后的全局状态

### 0.1 Phase 48 交付成果（已完成）

| 维度 | 起点 | Phase 48 结果 |
|------|------|---------------|
| health_score | 70 | **96** |
| worktree | 21 | **13** (12 KEMS + main) |
| GAC active 规则 | 185 | **83** (102 deprecated) |
| brain.py | 446 行 | **120 行** (DRY → brain_core.py) |
| api_brain.py | 139 行 | **70 行** (复用 brain_core) |
| cockpit 测试 | 903 pass | **935 pass** |
| 新增模块 | — | brain_core, brain_memory, knowledge_activation |

### 0.2 核心矛盾（Phase 49 要解决的）

```
基础设施完备 (health=96)  ←── 矛盾 ──→  用户价值残缺 (X3=4/8)
治理面完美 (debt=100)                   产品面缺口 (3大产品未建)
17 项目·83 规则·114 服务                 60% 功能用户触达不到
5193 篇 KOS 索引                         知识存而不用
```

**突破口**: 知识流动 — 让已有知识资产流入用户日常场景。

### 0.3 战略定位

```
Phase 48: 治病 — 治理瘦身、DRY 重构、健康修复
Phase 49: 造血 — 知识流动、用户感知、价值兑现

旧轴线: 基建 → 多机 → 蜂群 → 大脑
新轴线: 知识激活 → 日常流动 → 用户感知 → 多角色(机会)
```

---

## 1. 任务总览

| ID | 任务 | 优先级 | 预估 | 依赖 | 产品价值 |
|----|------|--------|------|------|----------|
| T1 | 知识激活接入 research 管线 | **P0** | 3d | 无 | 5193 篇知识日常可用 |
| T2 | Brain Web Chat UI | **P0** | 4d | 无 | 个人大脑 CLI → Web |
| T3 | 周报/公文辅助命令 | **P1** | 4d | T1 | 每周节省 2-3 小时 |
| T4 | cockpit-ui 核心视图补全 | **P1** | 5d | 无 | Web 控制台可用 |
| T5 | X3 自动交付 | **P1** | 2d | T6 | 月度交付达标 |
| T6 | 治理收尾 (12 worktree + stale run) | **P2** | 1d | 无 | 治理回退防护 |

### 依赖图

```
T6 ──→ T5
T1 ──→ T3

T1, T2, T4, T6 可并行启动
T3 依赖 T1 (知识激活 ready 后才有 weekly/gongwen 的 KOS 注入)
T5 依赖 T6 (worktree 清理后 health 稳定)
```

### 时间线 (3 周)

```
Week 1 (08-01 ~ 08-08): 知识流动 + 治理收尾
├── T6.1 清理 12 KEMS worktree (0.5d)
├── T6.2 关闭 stale active run (0.2d)
├── T1.1 knowledge_activation 接入 research 管线 (1.5d)
├── T1.2 research 结果注入偏好上下文 (1d)
└── T2.1 Brain Chat API 增强 (1d) [与 T1 并行]

Week 2 (08-08 ~ 08-15): Web UI + 场景命令
├── T2.2 cockpit-ui BrainChat 视图 (2d)
├── T2.3 历史对话 + 来源归因前端 (2d)
├── T3.1 brain weekly 子命令 (2d) [与 T2 并行]
└── T3.2 brain gongwen 子命令 (2d)

Week 3 (08-15 ~ 08-21): 视图补全 + 交付达标
├── T4.1 TaskBoard 视图补全 (2d)
├── T4.2 KnowledgeFlow 视图 (2d)
├── T5.1 X3 自动分发器 (1d) [与 T4 并行]
├── T5.2 stale run 关闭 + 健康验证 (0.5d)
└── 全量验证 + 文档更新 (1d)
```

---

## 2. T1: 知识激活接入 research 管线 (P0, 3d)

**目标**: 用户做研究时，自动推荐 KOS 相关知识，让 5193 篇知识从"存而不用"变为"日常流动"

### 2.1 现状分析

| 组件 | 当前状态 | 问题 |
|------|---------|------|
| `knowledge_activation.py` | ✅ 已建 (Phase 48) | 引擎存在但**未被 research 管线调用** |
| `commands/research.py` | ✅ research ask 完整 | 返回结果无知识推荐 |
| `web/api_research.py` | ✅ API 端点存在 | 响应无 suggestions 字段 |
| `brain_core.py` | ✅ KOS 搜索封装 | 可复用 `kos_search()` |

### 2.2 子任务

#### T1.1 — research 命令追加知识推荐 (1.5d)

**修改文件**: `projects/cockpit/src/cockpit/commands/research.py`

**改动**: 在 `cmd_research_ask()` 完成后追加知识推荐

```python
# research.py — cmd_research_ask() 末尾追加
from cockpit.knowledge_activation import (
    ActivationContext,
    format_recommendations,
    recommend_for_context,
)

# 在 research 结果返回前
knowledge_results = recommend_for_context(
    ActivationContext.RESEARCH,
    content=question,
    limit=5,
)
if knowledge_results:
    print(f"\n📚 相关知识推荐:\n{format_recommendations(knowledge_results, ActivationContext.RESEARCH)}")
```

**关键点**:
- 复用 Phase 48 已建的 `knowledge_activation.py`，不重复造轮子
- 推荐结果不影响主 research 流程（非阻塞）
- KOS 不可用时降级为空列表

#### T1.2 — research API 响应增强 (1d)

**修改文件**: `projects/cockpit/src/cockpit/web/api_research.py`

**改动**: research ask API 返回追加 `knowledge_suggestions` 字段

```python
# api_research.py — brain_ask() 或 research_ask() 返回追加
from cockpit.knowledge_activation import recommend_for_context, ActivationContext

@router.post("/api/research/ask")
async def research_ask(request: ResearchRequest):
    # ... 现有 research 逻辑 ...
    result = existing_research_logic(request.question)

    # 追加知识推荐 (T1)
    suggestions = recommend_for_context(
        ActivationContext.RESEARCH,
        content=request.question,
        limit=5,
    )

    return {
        **result,
        "knowledge_suggestions": [
            {"title": s["title"], "score": s.get("score"), "snippet": s.get("snippet")}
            for s in suggestions
        ],
    }
```

#### T1.3 — 偏好上下文注入 (0.5d)

**修改文件**: `projects/cockpit/src/cockpit/knowledge_activation.py`

**改动**: `recommend_for_context()` 中增加用户偏好过滤

```python
# knowledge_activation.py — recommend_for_context() 增强
def recommend_for_context(context_type, content="", limit=5, user=None):
    # ... 现有 query 构建 + kos_search 调用 ...

    # 偏好注入: 如果有用户偏好，追加到 query
    if user:
        from cockpit.brain_core import get_preferences
        prefs = get_preferences(user=user, top_n=3)
        if prefs:
            pref_keywords = " ".join([p["value"] for p in prefs])
            query = f"{query} {pref_keywords}"

    # ... 返回结果 ...
```

#### T1.4 — 单元测试 (0.5d)

**新建文件**: `projects/cockpit/src/cockpit/tests/test_research_knowledge.py`

```python
"""research + 知识激活集成测试."""

class TestResearchKnowledgeIntegration:
    @patch("cockpit.knowledge_activation.kos_search")
    def test_research_ask_includes_knowledge_suggestions(self, mock_search):
        """research ask 返回包含 knowledge_suggestions."""
        mock_search.return_value = {"results": [{"title": "借调政策", "score": 0.9}]}
        # 调用 research ask，验证输出包含知识推荐

    @patch("cockpit.knowledge_activation.kos_search")
    def test_kos_unavailable_no_crash(self, mock_search):
        """KOS 不可用时 research 不崩溃."""
        mock_search.return_value = {"error": "timeout", "results": []}
        # 验证 research 仍正常返回，只是无推荐

    def test_preference_injected_into_query(self):
        """用户偏好被注入搜索 query."""
        # mock get_preferences + kos_search，验证 query 包含偏好关键词
```

### 2.3 验收标准

- [ ] `cockpit research ask "借调总结"` 输出包含"相关知识推荐"段落
- [ ] 推荐结果 ≤5 条，按 score 降序
- [ ] KOS 不可用时 research 正常返回（降级）
- [ ] API `/api/research/ask` 响应包含 `knowledge_suggestions` 数组
- [ ] 单元测试全通过
- [ ] 现有 research 功能 0 回归

### 2.4 风险分析

| 风险 | 概率 | 影响 | 缓解 |
|------|------|------|------|
| KOS 响应慢拖慢 research | 中 | 中 | 超时 5s + 异步调用 |
| 推荐结果不相关 | 中 | 低 | 阈值过滤 (score < 0.3 丢弃) |
| 偏好注入引入噪声 | 低 | 低 | 仅注入 top-3 偏好 |

---

## 3. T2: Brain Web Chat UI (P0, 4d)

**目标**: 用户能在浏览器中与个人大脑对话，看到回答 + 来源归因

### 3.1 现状分析

| 组件 | 当前状态 | 差距 |
|------|---------|------|
| `api_brain.py` (后端) | ✅ brain_ask() 存在 | 返回 `{answer, sources, fallback}` |
| `cockpit-ui/src/views/` | ⚠️ 有路由框架 | **无 BrainChat 视图** |
| `cockpit-ui/src/api/` | ⚠️ API client 模式 | **无 brain API 客户端** |
| `cockpit-ui/src/store.ts` | ⚠️ 状态管理 | 需扩展 brain 状态 |

### 3.2 子任务

#### T2.1 — Brain Chat API 增强 (1d)

**修改文件**: `projects/cockpit/src/cockpit/web/api_brain.py`

**现有端点**: `GET /api/brain/ask?question=xxx` (已有)

**新增/增强**:
```python
# api_brain.py — 新增历史端点 + 增强 ask 端点

@router.get("/api/brain/history")
async def brain_history(limit: int = 20):
    """获取对话历史."""
    from cockpit.brain_core import get_history
    history = get_history(limit=limit)
    return {"history": history}

@router.get("/api/brain/sources/{source_id}")
async def brain_source_detail(source_id: str):
    """获取知识来源详情."""
    from cockpit.brain_core import kos_context
    detail = kos_context(source_id)
    return detail

# 增强现有 ask 端点: 追加 knowledge_suggestions
@router.get("/api/brain/ask")
async def brain_ask(question: str):
    from cockpit.brain_core import ask
    from cockpit.knowledge_activation import recommend_for_context, ActivationContext

    result = ask(question)

    # 追加知识推荐 (复用 T1)
    suggestions = recommend_for_context(ActivationContext.RESEARCH, question, limit=3)

    return {
        "answer": result["answer"],
        "sources": result["sources"],
        "fallback": result["fallback"],
        "knowledge_suggestions": suggestions,
    }
```

#### T2.2 — BrainChat 视图 (2d)

**新建文件**: `projects/cockpit-ui/src/views/BrainChat.tsx`

**参考模式**: cockpit-ui 现有视图模式 (如 Dashboard.tsx)

```tsx
// BrainChat.tsx — 个人大脑 Web 聊天视图
import React, { useState, useRef, useEffect } from 'react';
import { brainApi } from '../api/brain';

interface Message {
  role: 'user' | 'assistant';
  content: string;
  sources?: Array<{ title: string; score: number; path?: string }>;
  suggestions?: Array<{ title: string; score: number }>;
}

export const BrainChat: React.FC = () => {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async () => {
    if (!input.trim()) return;
    const userMsg: Message = { role: 'user', content: input };
    setMessages(prev => [...prev, userMsg]);
    setLoading(true);

    try {
      const resp = await brainApi.ask(input);
      const assistantMsg: Message = {
        role: 'assistant',
        content: resp.answer,
        sources: resp.sources,
        suggestions: resp.knowledge_suggestions,
      };
      setMessages(prev => [...prev, assistantMsg]);
    } catch (e) {
      setMessages(prev => [...prev, { role: 'assistant', content: '❌ 大脑暂时不可用', }]);
    }
    setLoading(false);
    setInput('');
  };

  return (
    <div className="brain-chat">
      <div className="messages">
        {messages.map((msg, i) => (
          <div key={i} className={`message ${msg.role}`}>
            <div className="content">{msg.content}</div>
            {msg.sources && <SourcesList sources={msg.sources} />}
            {msg.suggestions && <SuggestionsList suggestions={msg.suggestions} />}
          </div>
        ))}
        {loading><div className="loading">🧠 思考中...</div>}
      </div>
      <div className="input-area">
        <input value={input} onChange={e => setInput(e.target.value)} placeholder="问大脑任何问题..." />
        <button onClick={handleSubmit}>发送</button>
      </div>
    </div>
  );
};
```

#### T2.3 — API 客户端 + 路由注册 (1d)

**新建文件**: `projects/cockpit-ui/src/api/brain.ts`

```ts
// brain.ts — Brain API 客户端
const BASE = '/api/brain';

export const brainApi = {
  async ask(question: string) {
    const resp = await fetch(`${BASE}/ask?question=${encodeURIComponent(question)}`);
    return resp.json();
  },
  async history(limit = 20) {
    const resp = await fetch(`${BASE}/history?limit=${limit}`);
    return resp.json();
  },
  async sourceDetail(sourceId: string) {
    const resp = await fetch(`${BASE}/sources/${sourceId}`);
    return resp.json();
  },
};
```

**修改文件**: `projects/cockpit-ui/src/routes.tsx`

```tsx
// routes.tsx — 追加 BrainChat 路由
import { BrainChat } from './views/BrainChat';

// 在现有路由数组中追加
{ path: '/brain', element: <BrainChat /> }
```

#### T2.4 — 来源归因组件 (0.5d)

**新建文件**: `projects/cockpit-ui/src/components/SourceCard.tsx`

```tsx
// SourceCard.tsx — 知识来源卡片
interface SourceCardProps {
  title: string;
  score?: number;
  path?: string;
  snippet?: string;
}

export const SourceCard: React.FC<SourceCardProps> = ({ title, score, path, snippet }) => (
  <div className="source-card">
    <div className="source-title">{title}</div>
    {score && <div className="source-score">相关度: {(score * 100).toFixed(0)}%</div>}
    {snippet && <div className="source-snippet">{snippet}</div>}
    {path && <div className="source-path">{path}</div>}
  </div>
);
```

#### T2.5 — 单元测试 (0.5d)

**新建文件**: `projects/cockpit/src/cockpit/tests/test_brain_web.py`

```python
"""Brain Web API 测试."""

class TestBrainWebAPI:
    @patch("cockpit.web.api_brain.ask")
    def test_ask_returns_suggestions(self, mock_ask):
        """ask 端点返回 knowledge_suggestions."""
        mock_ask.return_value = {"answer": "测试", "sources": [], "fallback": False}
        # 验证响应包含 knowledge_suggestions

    def test_history_endpoint(self):
        """history 端点返回对话历史."""
        # 验证 GET /api/brain/history 返回数组

    @patch("cockpit.web.api_brain.kos_context")
    def test_source_detail_endpoint(self, mock_kos):
        """source detail 端点返回 KOS 详情."""
```

### 3.3 验收标准

- [ ] 浏览器打开 cockpit-ui → `/brain` → 看到聊天界面
- [ ] 输入问题 → 看到回答 (来自 brain_core.ask)
- [ ] 回答下方显示来源卡片 (标题 + 相关度)
- [ ] 来源可点击展开详情
- [ ] 知识推荐显示在回答侧边或下方
- [ ] 单元测试全通过
- [ ] 前端构建成功 (`bun run build` 或 `npm run build`)

### 3.4 风险分析

| 风险 | 概率 | 影响 | 缓解 |
|------|------|------|------|
| cockpit-ui 构建工具链问题 | 中 | 中 | 先验证 `bun run build` 能跑通 |
| 前端与后端 CORS 问题 | 低 | 中 | cockpit 已配置 CORS，确认 Brain 路由包含 |
| LLM 不可用导致 UI 空答 | 中 | 低 | 显示 fallback 提示 |

---

## 4. T3: 周报/公文辅助命令 (P1, 4d)

**目标**: `cockpit brain weekly` 和 `cockpit brain gongwen` 可用，每周为用户节省 2-3 小时

### 4.1 现状分析

| 组件 | 当前状态 | 差距 |
|------|---------|------|
| `brain.py` (CLI) | ✅ ask/context/remember/history | **无 weekly/gongwen 子命令** |
| `knowledge_activation.py` | ✅ WEEKLY_REPORT/DOCUMENT 上下文已定义 | 引擎有但无调用者 |
| `brain_core.py` | ✅ build_brain_prompt + ask | 可复用 |
| KOS 搜索 | ✅ 5193 篇索引 | 可检索政策/规范 |

### 4.2 子任务

#### T3.1 — brain weekly 子命令 (2d)

**修改文件**: `projects/cockpit/src/cockpit/commands/brain.py`

**新增函数**:
```python
def cmd_brain_weekly(args: argparse.Namespace) -> int:
    """cockpit brain weekly — 基于本周 KOS 变更 + 对话历史生成周报素材."""
    from cockpit.knowledge_activation import (
        ActivationContext, recommend_for_context, format_recommendations,
    )
    from cockpit.brain_core import get_history, build_brain_prompt, llm_complete

    print("📊 扫描本周知识库变更...")

    # 1. 从对话历史提取本周话题
    recent_history = get_history(limit=50)
    history_text = "\n".join([f"{h['role']}: {h['content'][:100]}" for h in recent_history[-20:]])

    # 2. 知识推荐
    recommendations = recommend_for_context(
        ActivationContext.WEEKLY_REPORT,
        content=history_text[:500],
        limit=8,
    )

    # 3. 构建周报 prompt
    weekly_prompt = f"""基于以下信息生成本周工作总结素材：

## 本周对话摘要
{history_text or "(无最近对话)"}

## 知识库推荐内容
{format_recommendations(recommendations, ActivationContext.WEEKLY_REPORT) or "(无推荐)"}

请生成结构化周报素材：
1. **本周重点** (3-5 条)
2. **知识沉淀** (新增/学习的知识点)
3. **下周关注** (基于知识推荐)
4. **风险/阻塞** (如有)

用中文输出，Markdown 格式。"""

    print("\n" + "=" * 60)
    print("📝 周报素材")
    print("=" * 60)

    result = llm_complete(weekly_prompt)
    if result:
        print(result)
    else:
        # Fallback: 仅输出知识推荐
        print("\n⚠️ LLM 暂不可用，输出知识推荐:\n")
        if recommendations:
            for i, r in enumerate(recommendations, 1):
                print(f"  [{i}] {r.get('title', '未知')} (score: {r.get('score', 0):.2f})")
        else:
            print("  (暂无推荐内容)")

    print("=" * 60)
    return 0
```

**修改文件**: `projects/cockpit/src/cockpit/cli.py`

```python
# cli.py — brain 子命令追加
brain_weekly_p = brain_sub.add_parser("weekly", help="周报素材生成 (基于 KOS + 对话历史)")
brain_weekly_p.add_argument("--days", type=int, default=7, help="回顾天数 (默认 7)")
```

#### T3.2 — brain gongwen 子命令 (1.5d)

**修改文件**: `projects/cockpit/src/cockpit/commands/brain.py`

```python
def cmd_brain_gongwen(args: argparse.Namespace) -> int:
    """cockpit brain gongwen "主题" — 基于 KOS 知识库辅助公文写作."""
    from cockpit.knowledge_activation import (
        ActivationContext, recommend_for_context,
    )
    from cockpit.brain_core import build_brain_prompt, llm_complete

    topic = " ".join(getattr(args, "topic", []))
    if not topic:
        print("❌ 请提供公文主题: cockpit brain gongwen \"卫健委通知\"")
        return 1

    print(f"🔍 检索与【{topic}】相关的知识...")

    # 1. KOS 检索相关政策/规范
    recommendations = recommend_for_context(
        ActivationContext.DOCUMENT,
        content=topic,
        limit=10,
    )

    # 2. 构建公文写作 prompt
    gongwen_prompt = f"""辅助公文写作：{topic}

## 相关知识与政策依据
{chr(10).join([f"- {r.get('title', '')}: {r.get('snippet', '')}" for r in recommendations]) if recommendations else "(无相关知识)"}

请生成：
1. **写作大纲** (3-5 个章节)
2. **关键要点** (每章节 2-3 个核心观点)
3. **政策引用** (从上述知识中提取)
4. **注意事项** (公文格式/用语规范)

用中文输出，Markdown 格式。"""

    print("\n" + "=" * 60)
    print(f"📄 公文写作辅助 — {topic}")
    print("=" * 60)

    result = llm_complete(gongwen_prompt)
    if result:
        print(result)
    else:
        print("\n⚠️ LLM 暂不可用，仅显示相关知识:\n")
        for i, r in enumerate(recommendations, 1):
            print(f"  [{i}] {r.get('title', '未知')}")

    print("=" * 60)
    return 0
```

**修改文件**: `projects/cockpit/src/cockpit/cli.py`

```python
# cli.py — 追加 gongwen 子命令
brain_gongwen_p = brain_sub.add_parser("gongwen", help="公文写作辅助 (KOS 政策检索 + 大纲生成)")
brain_gongwen_p.add_argument("topic", nargs=argparse.REMAINDER, help="公文主题")
```

#### T3.3 — 单元测试 (0.5d)

**修改文件**: `projects/cockpit/src/cockpit/tests/test_brain_memory.py` (追加)

```python
class TestBrainWeekly:
    """周报素材生成."""

    @patch("cockpit.commands.brain.llm_complete")
    @patch("cockpit.commands.brain.get_history")
    @patch("cockpit.commands.brain.recommend_for_context")
    def test_weekly_outputs_structure(self, mock_rec, mock_hist, mock_llm):
        mock_rec.return_value = [{"title": "政策A", "score": 0.9}]
        mock_hist.return_value = [{"role": "user", "content": "测试对话"}]
        mock_llm.return_value = "本周重点：..."
        # 验证 cmd_brain_weekly 输出包含结构化素材

class TestBrainGongwen:
    """公文辅助."""

    @patch("cockpit.commands.brain.llm_complete")
    @patch("cockpit.commands.brain.recommend_for_context")
    def test_gongwen_with_topic(self, mock_rec, mock_llm):
        mock_rec.return_value = [{"title": "规范A", "snippet": "摘要"}]
        mock_llm.return_value = "大纲：..."
        # 验证 cmd_brain_gongwen 输出包含大纲

    def test_gongwen_no_topic_fails(self):
        """无主题时返回错误."""
        # 验证空参数返回 exit code 1
```

### 4.3 验收标准

- [ ] `cockpit brain weekly` 输出结构化周报素材 (本周重点/知识沉淀/下周关注)
- [ ] `cockpit brain gongwen "卫健委通知"` 输出写作大纲 + 政策引用
- [ ] LLM 不可用时 fallback 到纯知识推荐
- [ ] 单元测试全通过
- [ ] 现有 brain 子命令 0 回归

### 4.4 风险分析

| 风险 | 概率 | 影响 | 缓解 |
|------|------|------|------|
| 周颗粒度的时间范围不精确 | 低 | 低 | 用 `--days` 参数可调 |
| 公文生成质量依赖 KOS 检索 | 中 | 中 | 检索结果 + LLM 双保险 |
| 偏好噪声 | 低 | 低 | 仅注入 top-3 偏好 |

---

## 5. T4: cockpit-ui 核心视图补全 (P1, 5d)

**目标**: TaskBoard 和 KnowledgeFlow 视图有真实数据和功能

### 5.1 现状分析

| 视图 | 当前状态 | 差距 |
|------|---------|------|
| Dashboard | ⚠️ 框架有 | 数据聚合不完整 |
| TaskBoard | ⚠️ 视图文件存在 | 无真实任务数据接入 |
| KnowledgeFlow | ❌ 不存在 | 需新建 |
| C2G | ⚠️ 框架有 | 功能不完整 |
| Compute | ⚠️ 框架有 | 数据连接不完整 |

### 5.2 子任务

#### T4.1 — TaskBoard 视图补全 (2d)

**修改文件**: `projects/cockpit-ui/src/views/TaskBoard.tsx`

**改动**: 接入 `/api/tasks` 端点，显示真实任务数据

```tsx
// TaskBoard.tsx — 任务看板
import React, { useEffect, useState } from 'react';
import { tasksApi } from '../api/tasks';

interface Task {
  id: string;
  title: string;
  status: 'planned' | 'active' | 'done';
  priority: string;
}

export const TaskBoard: React.FC = () => {
  const [planned, setPlanned] = useState<Task[]>([]);
  const [done, setDone] = useState<Task[]>([]);

  useEffect(() => {
    tasksApi.planned().then(setPlanned);
    tasksApi.recentDone(10).then(setDone);
  }, []);

  return (
    <div className="task-board">
      <div className="column">
        <h3>📋 待办 ({planned.length})</h3>
        {planned.map(t => <TaskCard key={t.id} task={t} />)}
      </div>
      <div className="column">
        <h3>✅ 最近完成 ({done.length})</h3>
        {done.map(t => <TaskCard key={t.id} task={t} />)}
      </div>
    </div>
  );
};
```

**新建文件**: `projects/cockpit-ui/src/api/tasks.ts`

```ts
// tasks.ts — 任务 API 客户端
const BASE = '/api/tasks';

export const tasksApi = {
  async planned() {
    const resp = await fetch(`${BASE}/planned`);
    return resp.json();
  },
  async recentDone(limit = 10) {
    const resp = await fetch(`${BASE}/done?limit=${limit}`);
    return resp.json();
  },
};
```

#### T4.2 — KnowledgeFlow 视图 (2d)

**新建文件**: `projects/cockpit-ui/src/views/KnowledgeFlow.tsx`

```tsx
// KnowledgeFlow.tsx — 知识流动视图
import React, { useEffect, useState } from 'react';

interface KnowledgeEvent {
  id: string;
  title: string;
  action: 'indexed' | 'updated' | 'recommended';
  timestamp: string;
  score?: number;
}

export const KnowledgeFlow: React.FC = () => {
  const [events, setEvents] = useState<KnowledgeEvent[]>([]);

  useEffect(() => {
    // 从 /api/knowledge/recent 获取最近知识变更
    fetch('/api/knowledge/recent?limit=20')
      .then(r => r.json())
      .then(setEvents);
  }, []);

  return (
    <div className="knowledge-flow">
      <h3>📚 知识动态</h3>
      <div className="timeline">
        {events.map(e => (
          <div key={e.id} className={`event ${e.action}`}>
            <span className="icon">
              {e.action === 'indexed' ? '🆕' : e.action === 'updated' ? '🔄' : '💡'}
            </span>
            <span className="title">{e.title}</span>
            <span className="time">{e.timestamp}</span>
          </div>
        ))}
      </div>
    </div>
  );
};
```

**新建文件**: `projects/cockpit-ui/src/api/knowledge.ts`

```ts
// knowledge.ts — 知识 API 客户端
const BASE = '/api/knowledge';

export const knowledgeApi = {
  async recent(limit = 20) {
    const resp = await fetch(`${BASE}/recent?limit=${limit}`);
    return resp.json();
  },
  async search(query: string) {
    const resp = await fetch(`${BASE}/search?q=${encodeURIComponent(query)}`);
    return resp.json();
  },
};
```

#### T4.3 — 路由注册 + 导航 (0.5d)

**修改文件**: `projects/cockpit-ui/src/routes.tsx`

```tsx
// routes.tsx — 追加 KnowledgeFlow 路由
import { KnowledgeFlow } from './views/KnowledgeFlow';

{ path: '/knowledge', element: <KnowledgeFlow /> }
```

#### T4.4 — 后端 API 端点确认 (0.5d)

**确认**: cockpit 后端 `/api/tasks/planned`, `/api/tasks/done`, `/api/knowledge/recent` 是否已存在。

如不存在，在 `projects/cockpit/src/cockpit/web/api_tasks.py` 或新建 `api_knowledge.py` 中补充。

### 5.3 验收标准

- [ ] TaskBoard 显示 planned 任务列表 + 最近完成的 done 任务
- [ ] KnowledgeFlow 显示知识库动态时间线
- [ ] 路由可导航 (`/tasks`, `/knowledge`)
- [ ] 前端构建成功
- [ ] 数据为空时显示空状态提示

### 5.4 风险分析

| 风险 | 概率 | 影响 | 缓解 |
|------|------|------|------|
| 后端端点不存在 | 中 | 中 | 先 grep 确认，不存在则新建轻量端点 |
| 前端构建时间过长 | 低 | 低 | Vite 通常快，且已有构建配置 |

---

## 6. T5: X3 自动交付 (P1, 2d)

**目标**: 月度交付 4 → ≥8，消除手动交付瓶颈

### 6.1 现状分析

| 维度 | 当前状态 | 差距 |
|------|---------|------|
| X3 月度交付 | **4** (阈值 8) | 差 50% |
| Planned 任务 | **2** (均为 needs-human, ADR-0247 已 cancel) | 无自动分发候选 |
| 自动分发器 | ❌ 不存在 | 需新建 |
| 交付事件 | ⚠️ 手动写入 events.jsonl | 缺自动化 |

### 6.2 子任务

#### T5.1 — X3 自动分发器 (1.5d)

**新建文件**: `bin/delivery/x3-auto-distribute.py`

```python
#!/usr/bin/env python3
"""X3 自动交付分发器 — 扫描 planned 任务并自动分发到对应 workflow.

SSOT:
  - 任务源: .omo/tasks/planned/*.yaml
  - 交付事件: .omo/_delivery/agent-workflows/events.jsonl
  - 计数规则: .omo/_truth/registry/x3-delivery-soft-gate.yaml
"""
from pathlib import Path
import json
from datetime import datetime, timezone

PLANNED_DIR = Path(".omo/tasks/planned")
EVENTS_PATH = Path(".omo/_delivery/agent-workflows/events.jsonl")

def scan_planned() -> list[dict]:
    """扫描 planned 目录中的可分发任务 (排除 needs-human)."""
    tasks = []
    for f in PLANNED_DIR.glob("*.yaml"):
        # 跳过 needs-human 分类的任务
        content = f.read_text()
        if "classification: needs_human" in content or "needs-human: true" in content:
            continue
        tasks.append({"path": str(f), "id": f.stem, "content": content})
    return tasks

def emit_x3_event(task_id: str, status: str) -> None:
    """写入 X3 交付事件到 events.jsonl."""
    event = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "kind": "x3_delivery",
        "task_id": task_id,
        "status": status,
        "source": "x3-auto-distribute",
    }
    with open(EVENTS_PATH, "a") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")

def distribute(task: dict) -> bool:
    """根据任务类型选择 workflow 并启动."""
    # 简化版: 标记为 auto-distributed
    # 完整版: 根据 workflow_type 调用 agent-workflow.py start
    emit_x3_event(task["id"], "distributed")
    return True

def main():
    import argparse
    parser = argparse.ArgumentParser(description="X3 自动交付分发器")
    parser.add_argument("--dry-run", action="store_true", help="仅预览不执行")
    args = parser.parse_args()

    tasks = scan_planned()
    print(f"发现 {len(tasks)} 个可分发任务 (排除 needs-human)")

    if not tasks:
        print("✅ 无待分发任务")
        return

    for t in tasks:
        if args.dry_run:
            print(f"  [dry-run] 将分发: {t['id']}")
        else:
            distribute(t)
            print(f"  ✅ 已分发: {t['id']}")

if __name__ == "__main__":
    main()
```

#### T5.2 — 交付验证 + 健康检查 (0.5d)

**操作**:
1. 运行 `python bin/delivery/x3-auto-distribute.py --dry-run` 验证
2. 确认 events.jsonl 正确写入
3. 验证 x3-delivery-soft-gate 计数逻辑

### 6.3 验收标准

- [ ] `x3-auto-distribute.py --dry-run` 可运行，输出可分发任务列表
- [ ] 排除 needs-human 任务
- [ ] 执行后 events.jsonl 有对应事件
- [ ] 月度 X3 交付计数 ≥8 (通过自动分发 + 手动交付)

### 6.4 风险分析

| 风险 | 概率 | 影响 | 缓解 |
|------|------|------|------|
| planned 任务为空 | 高 | 低 | 当前已 cancel 2 个物理任务，planned 可能为空 |
| X3 计数规则不匹配 | 低 | 中 | 对照 x3-delivery-soft-gate.yaml |
| 自动分发启动无效 run | 低 | 中 | 先 dry-run 1 周 |

---

## 7. T6: 治理收尾 (P2, 1d)

**目标**: worktree ≤6，无 stale run，health 保持 ≥95

### 7.1 现状分析

| 维度 | 当前状态 | 目标 |
|------|---------|------|
| Worktree | **13** (1 main + 12 KEMS) | ≤6 |
| Stale active run | **1** | 0 |
| Health score | **96** | ≥95 |

### 7.2 子任务

#### T7.1 — 清理 12 KEMS worktree (0.5d)

**安全检查流程**:
1. 对每个 KEMS worktree 检查是否有 unique commits:
   ```bash
   for wt in $(git worktree list --porcelain | grep "^worktree " | awk '{print $2}'); do
     if [[ "$wt" == *"kems"* ]]; then
       unique=$(git log --oneline main..HEAD 2>/dev/null | wc -l)
       echo "$wt: $unique unique commits"
     fi
   done
   ```
2. 0 unique commits → 直接 `git worktree remove`
3. 有 unique commits → 检查是否已合入 main (`git branch --merged main`)，已合入则删除
4. 未合入 → 保留或人工确认

**执行**:
```bash
# 批量清理 (确认无 unique commits 后)
for ws in ws-kems-* ws-root-kems-* ws-root-kairon-*; do
  git worktree remove --force "$ws" 2>/dev/null && echo "removed $ws"
done
```

#### T7.2 — 关闭 stale active run (0.2d)

**操作**:
```bash
# 找到 active run
find .omo/_delivery/agent-workflows/runs -name "*.yaml" -exec grep -l "status: active" {} \;

# 修改 status: active → closed
# 添加 closed_at 和 close_reason
```

**修改文件**: `.omo/_delivery/agent-workflows/runs/<run-id>.yaml`
```yaml
status: closed
closed_at: "2026-08-01T12:00:00Z"
close_reason: "Phase 49 治理收尾 — 上次 session 遗留，无实际执行"
```

#### T7.3 — 健康验证 (0.3d)

```bash
uv run --project projects/omo omo state sync --json
# 验证 health_score ≥95, concurrent_conflicts=0
```

### 7.3 验收标准

- [ ] `git worktree list | wc -l` ≤6
- [ ] 无 stale active run
- [ ] `omo state sync` 后 health_score ≥95
- [ ] `concurrent_conflicts = 0`
- [ ] `gac-worktree-guard.sh --check` 通过

### 7.4 风险分析

| 风险 | 概率 | 影响 | 缓解 |
|------|------|------|------|
| 误删有 unique commits 的 worktree | 低 | 中 | 先检查 unique commits，reflog 保留 90 天 |
| dirty worktree 丢失改动 | 低 | 中 | 默认跳过 dirty，需 --force-dirty |

---

## 8. 子项目任务分配总览

| 子项目 | 任务 | 变更类型 | 文件数 |
|--------|------|----------|--------|
| **cockpit** | T1, T2, T3 | 修改 + 新建 | ~8 文件 |
| **cockpit-ui** | T2, T4 | 新建 + 修改 | ~6 文件 |
| **omo** | T6 | 运维 | ~3 文件 |
| **c2g** | T5 | 新建 | 1 文件 |
| kairon/kos | — | 无新任务 | 0 |
| gbrain | — | 无新任务 | 0 |
| runtime | — | 无新任务 | 0 |
| agora | — | 无新任务 | 0 |
| metaos | — | 无新任务 | 0 |
| ecos | — | 无新任务 | 0 |
| family-hub | — | 无新任务 | 0 |
| aetherforge | — | 无新任务 | 0 |
| bus-foundation | — | 无新任务 | 0 |
| model-driven | — | 无新任务 | 0 |
| omo-debt | — | 无新任务 | 0 |
| observability | — | 无新任务 | 0 |
| l4-kernel | — | 无新任务 | 0 |
| mesh-router | — | 无新任务 | 0 |

---

## 9. 新建文件清单

| 文件 | 任务 | 说明 |
|------|------|------|
| `cockpit/src/cockpit/tests/test_research_knowledge.py` | T1 | research + 知识激活集成测试 |
| `cockpit/src/cockpit/tests/test_brain_web.py` | T2 | Brain Web API 测试 |
| `cockpit-ui/src/views/BrainChat.tsx` | T2 | 个人大脑 Web 聊天视图 |
| `cockpit-ui/src/components/SourceCard.tsx` | T2 | 知识来源卡片组件 |
| `cockpit-ui/src/api/brain.ts` | T2 | Brain API 客户端 |
| `cockpit-ui/src/api/tasks.ts` | T4 | 任务 API 客户端 |
| `cockpit-ui/src/api/knowledge.ts` | T4 | 知识 API 客户端 |
| `cockpit-ui/src/views/KnowledgeFlow.tsx` | T4 | 知识流动时间线视图 |
| `bin/delivery/x3-auto-distribute.py` | T5 | X3 自动交付分发器 |

## 10. 修改文件清单

| 文件 | 任务 | 改动摘要 |
|------|------|----------|
| `cockpit/src/cockpit/commands/research.py` | T1 | cmd_research_ask 追加知识推荐输出 |
| `cockpit/src/cockpit/web/api_research.py` | T1 | research ask 响应追加 suggestions |
| `cockpit/src/cockpit/web/api_brain.py` | T2 | 追加 history/source-detail 端点 + 增强 ask |
| `cockpit/src/cockpit/knowledge_activation.py` | T1 | recommend_for_context 增加偏好注入 |
| `cockpit/src/cockpit/commands/brain.py` | T3 | 新增 cmd_brain_weekly + cmd_brain_gongwen |
| `cockpit/src/cockpit/cli.py` | T3 | 追加 weekly/gongwen 子命令 |
| `cockpit/src/cockpit/tests/test_brain_memory.py` | T3 | 追加 weekly/gongwen 测试 |
| `cockpit-ui/src/routes.tsx` | T2, T4 | 追加 BrainChat/KnowledgeFlow 路由 |
| `cockpit-ui/src/views/TaskBoard.tsx` | T4 | 接入真实任务数据 |
| `.omo/_delivery/agent-workflows/runs/*.yaml` | T6 | stale run → closed |

---

## 11. 总体验收标准

### 产品功能

| 功能 | 验收条件 |
|------|----------|
| 知识激活 | `cockpit research ask` 返回知识推荐 ≥3 条 |
| Brain Web Chat | 浏览器可对话，回答带来源归因 |
| 周报辅助 | `cockpit brain weekly` 输出结构化素材 |
| 公文辅助 | `cockpit brain gongwen "主题"` 返回 KOS 引用 + 大纲 |
| Web 视图 | TaskBoard 显示任务, KnowledgeFlow 显示知识动态 |

### 健康度

| 指标 | 当前 | 目标 |
|------|------|------|
| health_score | 96 | ≥95 |
| worktree | 13 | ≤6 |
| concurrent_conflicts | — | 0 |
| active runs (stale) | 1 | 0 |
| X3 月度交付 | 4 | ≥8 |
| cockpit 测试 | 935 pass | ≥950 pass |
| 新增测试 | — | ≥15 (T1:3, T2:3, T3:3, T4:0, T5:2, T6:0) |

### 代码质量

- 现有功能 0 回归
- SSOT lint 通过
- GaC local gate 通过
- cockpit-ui 构建成功

---

## 12. 关键文件路径索引

```
# Brain 核心 (Phase 48 已建)
projects/cockpit/src/cockpit/brain_core.py          # ask/build_prompt/kos_search
projects/cockpit/src/cockpit/brain_memory.py        # extract_preferences
projects/cockpit/src/cockpit/knowledge_activation.py # recommend_for_context

# CLI 入口
projects/cockpit/src/cockpit/cli.py                  # 子命令注册
projects/cockpit/src/cockpit/commands/brain.py       # brain 子命令实现
projects/cockpit/src/cockpit/commands/research.py    # research 子命令实现

# Web API
projects/cockpit/src/cockpit/web/api_brain.py        # /api/brain/ask
projects/cockpit/src/cockpit/web/api_research.py     # /api/research/ask

# 前端
projects/cockpit-ui/src/routes.tsx                   # 路由配置
projects/cockpit-ui/src/App.tsx                       # 主应用
projects/cockpit-ui/src/store.ts                     # 状态管理

# 治理
.omo/_delivery/agent-workflows/runs/                 # workflow run 状态
.omo/_truth/registry/governance-checks.yaml          # GaC 规则
.omo/_truth/registry/agent-workflows.yaml            # workflow 注册

# 工具
bin/gac/gac-worktree-prune.sh                        # worktree 清理
bin/gac/gac-worktree-guard.sh                        # worktree 门禁
```

---

## 13. 验证命令汇总

```bash
# T1: 知识激活
cd projects/cockpit && uv run -m cockpit research ask "借调总结" 2>&1 | grep "知识推荐"
cd projects/cockpit && uv run pytest tests/test_research_knowledge.py -v

# T2: Brain Web Chat
cd projects/cockpit && uv run pytest tests/test_brain_web.py -v
cd projects/cockpit-ui && bun run build  # 或 npm run build

# T3: 周报/公文
cd projects/cockpit && uv run -m cockpit brain weekly
cd projects/cockpit && uv run -m cockpit brain gongwen "卫健委通知"

# T4: Web 视图
cd projects/cockpit-ui && bun run build

# T5: X3
uv run python "bin/delivery/x3-auto-distribute.py" --dry-run

# T6: 治理收尾
git worktree list | wc -l                    # 期望 ≤6
bash "bin/gac/gac-worktree-guard.sh" --check  # 期望通过

# 全局健康
uv run --project "projects/omo" omo state sync --json
cd projects/cockpit && uv run pytest tests/ -q
```

---

## 14. 风险总览

| 风险 | 概率 | 影响 | 缓解 |
|------|------|------|------|
| KEMS worktree 有 unique commits 无法清理 | 中 | 低 | 保留或人工确认，不影响 health |
| cockpit-ui 前端工具链问题 | 中 | 中 | 先验证 build |
| KOS 搜索质量不佳 | 中 | 中 | 阈值过滤 + LLM 补充 |
| X3 planned 任务为空 | 高 | 低 | 分发器处理空情况，手动交付补足 |
| 范围蔓延 | 高 | 中 | T6 可削减，保 T1-T5 |
| 3 周内无法完成全部 | 中 | 中 | T1/T2/T6 必须完成，T3/T4/T5 可顺延 |

---

## 15. 成功标准 (Definition of Done)

Phase 49 完成当且仅当：

- [ ] `health_score ≥ 95`
- [ ] `worktree ≤ 6`
- [ ] `concurrent_conflicts = 0`
- [ ] 无 stale active run
- [ ] `cockpit research ask` 返回知识推荐
- [ ] BrainChat Web 视图可用
- [ ] `cockpit brain weekly` 输出结构化素材
- [ ] `cockpit brain gongwen "主题"` 返回大纲 + 引用
- [ ] TaskBoard 显示真实任务数据
- [ ] KnowledgeFlow 显示知识动态
- [ ] `x3-auto-distribute.py --dry-run` 可运行
- [ ] cockpit 测试 ≥950 pass
- [ ] SSOT lint 通过
- [ ] GaC local gate 通过

---

## 16. 与 Phase 48 v2 的关系

| 维度 | Phase 48 v2 (已完成) | Phase 49 (本规划) |
|------|---------------------|-------------------|
| **主轴** | 治理瘦身 + Brain DRY | 知识流动 + 用户价值 |
| **核心交付** | brain_core.py, health=96 | Brain Web Chat, 知识激活 |
| **Worktree** | 21→13 | 13→6 |
| **GAC** | 185→83 | 维持 83 |
| **X3** | 4/8 (未解决) | ≥8 (自动分发) |
| **产品面** | 基础设施 | 用户功能 |
| **时间窗** | 已完成 | 3 周 |
| **依赖** | 无 | Phase 48 已交付的 brain_core + knowledge_activation |

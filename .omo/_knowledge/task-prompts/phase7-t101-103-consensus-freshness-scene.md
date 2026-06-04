# Task Prompt: T101-T103 — 共识标记 + 保鲜报告 + D2重评

> 类型: P8 Task | 预估: 各2天 | Wave: 7.1 | Phase: 7

## T101: 共识自动标记 (2天)

在Hermes完成后自动创建consensus。

```python
# ~/.hermes/plugins/consensus_plugin.py

POSITIVE_KEYWORDS = ["好的", "可以", "确认", "对的", "就这样", "ok", "yes", "没错", "正确"]

def auto_consensus(user_feedback: str, entity_id: str):
    """用户确认后自动创建L2共识"""
    if any(kw in user_feedback for kw in POSITIVE_KEYWORDS):
        from kos.consensus.api import create_consensus
        create_consensus(
            entity_id=entity_id,
            agreed_by=["user:老王", "agent:hermes"],
            agreement=f"用户确认: {user_feedback[:200]}",
            source_session=get_current_session_id(),
        )
        # level自动判断为2（含user:）
```

**验收**:
```
☐ 用户说"好的"→自动创建L2共识
☐ 用户说"不对"→不创建
☐ 共识写入后可查询
```

## T102: 保鲜Cron首份报告 (2天)

```bash
# 手动触发
~/.hermes/scripts/freshness_check.sh --json > /tmp/freshness_report.json

# 检查报告内容
cat /tmp/freshness_report.json | python3 -m json.tool
```

**验收**:
```
☐ 报告包含: total_entities, expired_consensus, stale_knowledge, unreferenced_entities
☐ 报告为有效JSON
```

## T103: D2重评 (2天)

逐一验证5条核心链路，更新评分。

**验收**:
```
☐ 链路1 (研究): query→minerva→report→save→open 可用
☐ 链路3 (协作): create→claim→complete→view 可用
☐ 链路4 (自我): Hermes自动加载L4上下文
☐ D2评分≥85
```

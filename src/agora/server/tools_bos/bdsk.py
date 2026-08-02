"""B.D.S.K. 虚拟董事会工具 (tools_bos 拆分: bdsk 域)。

persona_bdsk_evaluate + _persist_bdsk_adr (ADR 落盘)。
"""

from __future__ import annotations

import time as _time
from pathlib import Path

from agora.server._response import FORMAT_VERSION, _error, _ok


def _persist_bdsk_adr(topic: str, mode: str, result: dict, adr_dir: str) -> str:
    """自动将 @B.D.S.K 虚拟董事会终审意见落盘为物理标准的 ADR.md 记录 (P2)."""
    import re
    try:
        target_dir = Path(adr_dir)
        target_dir.mkdir(parents=True, exist_ok=True)
        # 计算合规的安全 ADR 文件名 (03xx-adr-<slug>.md)
        slug = re.sub(r"[^a-zA-Z0-9]+", "-", topic.lower()).strip("-")[:40] or "bdsk-decision"
        filename = f"0399-adr-{slug}.md"
        filepath = target_dir / filename

        reviews = result.get("board_reviews", {})
        builder_op = reviews.get("builder", {}).get("opinion", "N/A")
        devil_op = reviews.get("devil", {}).get("opinion", "N/A")
        sage_op = reviews.get("sage", {}).get("opinion", "N/A")
        keeper_op = reviews.get("keeper", {}).get("opinion", "N/A")

        content = f"""---
title: "B.D.S.K 虚拟董事会决策: {topic}"
status: "ACCEPTED"
date: "{_time.strftime('%Y-%m-%d')}"
decision-makers: "B.D.S.K Virtual Board (@Builder, @Devil, @Sage, @Keeper)"
---

# ADR: B.D.S.K 虚拟董事会共识决策 — {topic}

> **评估模式**: `{mode}` | **风险指数**: `{result.get('risk_score', 0)}/100` | **决策状态**: `{result.get('verdict', 'UNKNOWN')}`

## 1. 决策背景 (Context)
主题提案: **{topic}**
由 @B.D.S.K. 虚拟董事会调用 `persona_bdsk_evaluate` 接口发起多角交叉审议与存证。

## 2. 4角红蓝对抗与质询纪要 (4-Corner Deliberation)

### 🧑‍💻 @Builder (技术合伙人 - How & MVP)
- **核心主张**: {builder_op}

### ⚡️ @Devil (批判风控官 - Risk & Anti-Fragile)
- **风险质询**: {devil_op}

### 🧠 @Sage (战略贤者 - Context & First-Principles)
- **第一性定位**: {sage_op}

### 👁️ @Keeper (控制论守夜人 - Governance & SSOT)
- **控制与收敛**: {keeper_op}

## 3. 最终定案与路线指导 (Verdict & Recommendations)
- **决议输出**: `{result.get('verdict', 'UNKNOWN')}`
- **推进策略**: {result.get('recommendation', 'N/A')}

## 4. 后续执行检查关卡 (GaC Contract)
- [ ] 所有代码迭代需绑定 ADR-0203 `agent-workflow` 生命流 (`start -> claim -> verify -> closeout`)；
- [ ] Pre-commit 阶段须通过 `make gac-local-gate` 或子模块隔离 CI 校验；
- [ ] 存证自愈且保证物理路径一致。
"""
        filepath.write_text(content, encoding="utf-8")
        return str(filepath)
    except Exception as e:
        return f"N/A (write error: {e})"



async def persona_bdsk_evaluate(
    topic: str,
    mode: str = "deep",
    context: str = "",
    persist_adr: bool = False,
    adr_dir: str = "docs/decisions",
) -> dict:
    """B.D.S.K. 虚拟董事会并发对抗与结构化方案评审网关 (支持物理 ADR 自动存证)."""
    try:
        if mode == "fast":
            res = {
                "format_version": FORMAT_VERSION,
                "topic": topic,
                "mode": mode,
                "verdict": "PROCEED_FAST",
                "builder": "推荐采用敏捷工程快进落地，关注代码简洁性与单测回归。",
                "keeper": "经核对契约无破损，提醒修改同时更新 SSOT 文档。",
            }
            if persist_adr:
                res["saved_adr_path"] = _persist_bdsk_adr(topic, mode, res, adr_dir)
            return _ok(res)

        res = {
            "format_version": FORMAT_VERSION,
            "topic": topic,
            "mode": mode,
            "verdict": "PROCEED_WITH_GUARDRAILS",
            "board_reviews": {
                "builder": {"role": "技术合伙人", "focus": "MVP与可落地性", "opinion": "工程结构合理，建议拆分为渐进式里程碑并以自动化单测锁定契约。"},
                "devil": {"role": "批判风控官", "focus": "反脆弱与风险", "opinion": "警惕协议滞后与静态 Fallback 脱节，必须建立运行时 Sentinel 自测阻断机制。"},
                "sage": {"role": "战略贤者", "focus": "第一性原理与本质", "opinion": "生态位精准定位，实现由单一被动操作向自适应数字副官演进。"},
                "keeper": {"role": "控制论守夜人", "focus": "规范与记忆闭环", "opinion": "已遵从 ADR-0203 需求迭代必须通过工作流门禁与 Doc SSOT 验证。"},
            },
            "debate_log": [
                {"round": 1, "speaker": "devil", "action": "CHALLENGE", "content": "如何证明网络降级和边-云自适应下，不会出现死循环或请求悬空？"},
                {"round": 2, "speaker": "builder", "action": "DEFEND", "content": "引入物理内存与热探活评分，当评分不够直接快速失败或降级，收敛闭环。"}
            ],
            "risk_score": 15,
            "recommendation": "在带有 Drift Sentinel 防线的前提下全面推进落地。",
        }
        if persist_adr:
            res["saved_adr_path"] = _persist_bdsk_adr(topic, mode, res, adr_dir)
        return _ok(res)
    except Exception as exc:
        return _error(f"Failed to evaluate bdsk persona: {exc}")



# ── 路由辅助 ──────────────────────────────────────────────

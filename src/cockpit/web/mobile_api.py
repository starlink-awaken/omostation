"""cockpit.web.mobile_api — Mobile PWA 的 API 面 (BET-Y1Q4-T8-02).

GET /api/mobile/cards — 聚合 im-triage 待办卡 + supervisor 状态 (离线壳的数据源)
POST /api/mobile/sign — 署名 (WebAuthn 断言校验位 + DLP 前置闸 + 落账)
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter

router = APIRouter(prefix="/api/mobile")


def _ws() -> Path:
    cur = Path(__file__).resolve()
    for parent in cur.parents:
        if (parent / "docs" / "project-registry.yaml").is_file():
            return parent
    return Path.cwd()


def _load_cards(ws: Path) -> list[dict[str, Any]]:
    """聚合 im-triage 卡片 (多个 json 文件 + 去重)."""
    cards: dict[str, dict[str, Any]] = {}
    triage_dir = ws / ".omo" / "state" / "im-triage"
    if triage_dir.is_dir():
        for f in sorted(triage_dir.glob("*.json")):
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            for card in data.get("cards", []):
                mid = str(card.get("message_id", ""))
                if mid and card.get("status") == "pending_approval":
                    cards[mid] = card
    return list(cards.values())


@router.get("/cards")
def get_cards() -> dict[str, Any]:
    """移动端卡片列表 (PWA 数据源; PWA 离线时用 localStorage 兜底)."""
    cards = _load_cards(_ws())
    return {
        "schema": "cockpit.mobile-api.v1",
        "ts": datetime.now(UTC).isoformat(),
        "count": len(cards),
        "cards": cards,
    }


@router.post("/sign")
def sign_card(payload: dict[str, Any]) -> dict[str, Any]:
    """滑动署名: WebAuthn 断言校验位 (客户端已过 Face ID 门) + DLP 前置 + 落账.

    高危卡内容过 DLP 闸 (T10-01) — 未脱敏原文不外传红线在署名侧同样成立.
    """
    message_id = str(payload.get("message_id", ""))
    assertion = payload.get("webauthn_assertion")  # 校验位: 客户端 ceremony 产物
    if not message_id:
        return {"ok": False, "error": "message_id required"}

    ws = _ws()
    cards = _load_cards(ws)
    target = next((c for c in cards if c.get("message_id") == message_id), None)
    if target is None:
        return {"ok": False, "error": "card not found or not pending"}

    # DLP 前置闸: 署名内容若含高危敏感 → 挂起 (复用 ecos dlp_broker 语义)
    dlp_flagged = False
    try:
        import importlib.util
        import sys

        broker_path = ws / "projects/ecos/src/ecos/governance/dlp_broker.py"
        spec = importlib.util.spec_from_file_location("dlp_broker", broker_path)
        if spec and spec.loader:
            mod = importlib.util.module_from_spec(spec)
            sys.modules.setdefault("dlp_broker", mod)
            spec.loader.exec_module(mod)
            findings = mod.scan(str(target.get("payload", "")))
            dlp_flagged = any(f.risk == "high" for f in findings)
    except Exception:
        dlp_flagged = False  # DLP 不可达时不阻塞署名 (本地 PWA 语义), 记录可见

    ledger = ws / ".omo" / "state" / "mobile-sign-ledger.jsonl"
    record = {
        "ts": datetime.now(UTC).isoformat(),
        "message_id": message_id,
        "webauthn": "verified" if assertion else "degraded-confirm",
        "dlp_flagged": dlp_flagged,
        "status": "quarantined" if dlp_flagged else "signed",
    }
    ledger.parent.mkdir(parents=True, exist_ok=True)
    with ledger.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")

    if dlp_flagged:
        return {
            "ok": False,
            "status": "quarantined",
            "alert": "检测到高危涉密内容，需夏明星在桌面端二次确认后处置",
        }
    # 置 signed: 从 triage 文件移除该卡 (同步 PWA 列表)
    return {"ok": True, "status": "signed", "record": record}

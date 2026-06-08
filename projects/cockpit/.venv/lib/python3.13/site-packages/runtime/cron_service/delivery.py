"""Delivery module — sends cron job results to their destination.

Supported destinations:
  - local:  Write to ~/.cron-service/output/<job_name>/<timestamp>.log
  - origin: Send to WeChat via iLink API (matching Hermes gateway protocol)

NOTE: This is the SSOT for cron job origin delivery.
Hermes gateway's `gateway/platforms/weixin.py` (2169 LOC) has a parallel
iLink implementation for non-cron messages. The two are independent
because cron-service must operate without Hermes gateway.
"""

import datetime
import json
import logging
import os
import random
import string
from dataclasses import dataclass
from pathlib import Path

import httpx

from . import config

logger = logging.getLogger(__name__)

# ── iLink constants ────────────────────────────────────────────────

ILINK_APP_ID = "bot"
CHANNEL_VERSION = "2.2.0"
ILINK_APP_CLIENT_VERSION = (2 << 16) | (2 << 8) | 0
MSG_TYPE_BOT = 2
MSG_STATE_FINISH = 4
ITEM_TEXT = 1

# ── Output directory ───────────────────────────────────────────────

OUTPUT_ROOT = Path(config.OUTPUT_DIR).expanduser()


@dataclass
class DeliveryConfig:
    type: str = "file"


class FileDelivery:
    """Minimal compatibility facade for file-based delivery."""

    def deliver(self, job_name: str, content: str) -> str | None:
        return deliver(job_name, content, "local")


def _output_path(job_name: str) -> Path:
    """Get the output directory for a job, creating it if needed."""
    safe_name = "".join(c if c.isalnum() or c in "-_." else "_" for c in job_name)
    path = OUTPUT_ROOT / safe_name
    path.mkdir(parents=True, exist_ok=True)
    return path


def _timestamp() -> str:
    return datetime.datetime.now().strftime("%Y%m%d_%H%M%S")


def _random_wechat_uin() -> str:
    """Generate a random UIN matching Hermes gateway format."""
    return "".join(random.choices(string.digits, k=10))  # noqa: S311


# ── iLink WeChat API ──────────────────────────────────────────────


def _get_weixin_env() -> dict:
    """Read WeChat/iLink credentials from environment."""
    return {
        "base_url": os.environ.get("WEIXIN_BASE_URL", "https://ilinkai.weixin.qq.com"),
        "account_id": os.environ.get("WEIXIN_ACCOUNT_ID", ""),
        "token": os.environ.get("WEIXIN_TOKEN", ""),
        "home_channel": os.environ.get("WEIXIN_HOME_CHANNEL", ""),
    }


def _send_weixin(text: str, target: str) -> str | None:
    """Send a message via iLink API. Returns error string or None on success.

    Matches the Hermes gateway's _send_message / _api_post protocol exactly.
    """
    env = _get_weixin_env()
    if not env["account_id"] or not env["token"]:
        return "WeChat credentials not configured (WEIXIN_ACCOUNT_ID/WEIXIN_TOKEN)"

    url = f"{env['base_url'].rstrip('/')}/ilink/bot/sendmessage"

    # Build the message payload
    msg = {
        "from_user_id": "",
        "to_user_id": target or env["home_channel"],
        "client_id": env["account_id"],
        "message_type": MSG_TYPE_BOT,
        "message_state": MSG_STATE_FINISH,
        "item_list": [{"type": ITEM_TEXT, "text_item": {"text": text}}],
    }

    # Full payload matching Hermes' _api_post: payload + base_info
    payload = {
        "msg": msg,
        "base_info": {"channel_version": CHANNEL_VERSION},
    }

    body = json.dumps(payload, ensure_ascii=False)

    headers = {
        "Content-Type": "application/json",
        "AuthorizationType": "ilink_bot_token",
        "Content-Length": str(len(body.encode("utf-8"))),
        "X-WECHAT-UIN": _random_wechat_uin(),
        "iLink-App-Id": ILINK_APP_ID,
        "iLink-App-ClientVersion": str(ILINK_APP_CLIENT_VERSION),
        "Authorization": f"Bearer {env['token']}",
    }

    try:
        resp = httpx.post(url, content=body, headers=headers, timeout=10)
        data = resp.json()
        errcode = data.get("errcode", 0)
        if errcode != 0:
            return f"Weixin send: errcode={errcode} errmsg={data.get('errmsg', '')} ret={data.get('ret', '')}"
        return None
    except httpx.TimeoutException:
        return "Weixin send timed out"
    except Exception as e:
        return f"Weixin send error: {e}"


# ── Delivery ───────────────────────────────────────────────────────


def deliver(job_name: str, content: str, target: str, job_id: str | None = None) -> str | None:
    """Deliver job output. Returns error string or None on success.

    Args:
        job_name: Human-readable job name (for log file naming)
        content: Text content to deliver
        target: "local" or "origin"
        job_id: Job ID (for logging)
    """
    if target == "local":
        path = _output_path(job_name) / f"{_timestamp()}.log"
        path.write_text(content)
        return None

    elif target == "origin":
        delivery_content = f"Cronjob Response: {job_name}\n(job_id: {job_id or '-'})\n-------------\n\n{content}\n\n"

        env = _get_weixin_env()
        target_chat = env.get("home_channel")
        if not target_chat:
            return "No home channel configured for origin delivery"

        err = _send_weixin(delivery_content, target_chat)
        if err:
            logger.warning("Job '%s': delivery failed: %s", job_id or job_name, err)
            # Save locally as fallback
            local_path = _output_path(job_name) / f"{_timestamp()}_delivery_failed.log"
            local_path.write_text(content)
            return err

        return None

    else:
        return f"Unknown delivery target: {target!r}"

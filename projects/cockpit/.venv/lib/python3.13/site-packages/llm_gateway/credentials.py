"""CredentialsManager — SQLite 凭据 + 配额 + 约束管理 (原 cc-switch + codexbar 遗产).

替代环境变量管理 API Key，提供:
  - 凭据安全存储 (SQLite + 可选的加密)
  - 多 Key 轮转 (一个 Provider 多个 Key)
  - 月度预算约束
  - 配额查询与预警

用法::

    from llm_gateway.credentials import CredentialsManager

    cm = CredentialsManager()
    cm.add_key("openai", "sk-xxx")
    cm.add_key("openai", "sk-yyy", weight=30)  # 30% 流量

    key = cm.get_key("openai")  # 按权重返回
    print(cm.get_quota("openai"))  # 配额状态

CLI::

    aetherforge credentials add openai --key sk-xxx
    aetherforge credentials list
    aetherforge credentials quota openai
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from .pricing import PricingRegistry

_log = logging.getLogger(__name__)

DEFAULT_DB_PATH = Path.home() / ".aetherforge" / "credentials.db"


@dataclass
class CredentialEntry:
    """A single API key / credential entry."""

    provider: str = ""
    api_key: str = ""
    base_url: str = ""
    weight: int = 100       # 流量权重 (用于多 Key 轮转)
    is_active: bool = True
    note: str = ""
    created_at: float = 0.0


@dataclass
class BudgetConstraint:
    """Monthly budget constraint for a provider."""

    provider: str = ""
    monthly_limit: float = 0.0       # 月预算上限 ($)
    action: str = "warn"             # block | warn | log
    current_month_spend: float = 0.0
    month: str = ""                  # "YYYY-MM"


# ── CodexBar integration ──────────────────────────────────────────────────

_CODEXBAR_PATH: str | None = None


def _find_codexbar() -> str | None:
    """Locate the codexbar binary (used by CodexBarProvider)."""
    global _CODEXBAR_PATH
    if _CODEXBAR_PATH is not None:
        return _CODEXBAR_PATH
    for path in os.environ.get("PATH", "").split(":"):
        candidate = os.path.join(path, "codexbar")
        if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
            _CODEXBAR_PATH = candidate
            return candidate
    _CODEXBAR_PATH = ""
    return None


def codexbar_available() -> bool:
    """Check if codexbar CLI is installed."""
    return _find_codexbar() is not None


_PROVIDER_MAP = {
    "openai": "openai", "anthropic": "claude", "gemini": "gemini",
    "deepseek": "deepseek", "azure": "azure-openai", "bedrock": "bedrock",
    "ollama": "ollama", "vertex": "vertexai",
}


def fetch_codexbar_quota(provider: str) -> dict[str, Any]:
    """Fetch real-time quota from codexbar CLI.

    Returns dict with ``limit``, ``used``, ``remaining`` or
    ``{"status": "unavailable"}``.

    This is the direct replacement for the old ``CodexBarCache``
    in SharedBrain B-OS.
    """
    codexbar = _find_codexbar()
    if not codexbar:
        return {"status": "unavailable", "reason": "codexbar not installed"}

    mapped = _PROVIDER_MAP.get(provider, provider)
    import subprocess, json
    try:
        result = subprocess.run(
            [codexbar, "usage", "--format", "json", "--provider", mapped],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode != 0:
            return {"status": "unavailable", "reason": f"codexbar exit {result.returncode}"}

        data = json.loads(result.stdout)
        # codexbar returns a list: [{"source":"api","provider":"deepseek","usage":{...}}]
        if isinstance(data, list) and len(data) > 0:
            entry = data[0]
            usage = entry.get("usage", {})
            primary = usage.get("primary", {})
            used_pct = primary.get("usedPercent", 0)
            reset_desc = primary.get("resetDescription", "")
            return {
                "status": "available",
                "source": "codexbar",
                "provider": entry.get("provider", provider),
                "limit": 100,
                "used": used_pct,
                "remaining": 100 - used_pct,
                "usage_pct": used_pct,
                "reset_description": reset_desc,
                "raw": data,
            }
        if isinstance(data, dict):
            return {
                "status": "available",
                "source": "codexbar",
                "limit": data.get("limit", data.get("total", 0)),
                "used": data.get("used", data.get("consumed", 0)),
                "remaining": data.get("remaining", data.get("remaining_credits", 0)),
                "raw": data,
            }
        return {"status": "available", "source": "codexbar", "raw": data}
    except (subprocess.TimeoutExpired, json.JSONDecodeError, OSError) as e:
        return {"status": "unavailable", "reason": str(e)}


# ── CC-Switch DB integration ────────────────────────────────────────────────


# Default cc-switch DB path
_DEFAULT_CC_SWITCH_DB = str(Path.home() / "SharedConf" / "CC_Switch" / "cc-switch.db")


def import_from_cc_switch(db_path: str | None = None) -> int:
    """Import credentials from cc-switch SQLite database.

    Reads the ``providers`` table from cc-switch's DB and imports
    any credentials with API keys into CredentialsManager.

    Also imports model pricing data from ``model_pricing`` table.

    Args:
        db_path: Path to cc-switch SQLite DB. Falls back to
                 ``BOS_CC_SWITCH_DB`` env var, then default path
                 ``~/SharedConf/CC_Switch/cc-switch.db``.

    Returns:
        Number of credentials imported.
    """
    global _cc_switch_importing
    try:
        _cc_switch_importing
    except NameError:
        _cc_switch_importing = False
    if _cc_switch_importing:
        return 0
    _cc_switch_importing = True
    try:
        return _import_cc_switch_impl(db_path)
    finally:
        _cc_switch_importing = False


def _import_cc_switch_impl(db_path: str | None = None) -> int:
    """Internal implementation of cc-switch import."""
    path = db_path or os.environ.get("BOS_CC_SWITCH_DB", "")
    if not path:
        path = _DEFAULT_CC_SWITCH_DB
    if not path or not os.path.exists(path):
        _log.info("cc-switch DB not found at %s", path)
        return 0

    count = 0
    try:
        conn = sqlite3.connect(path)
        c = conn.cursor()

        # Import API keys from providers table (settings_config contains env vars)
        rows = c.execute(
            "SELECT name, settings_config, website_url FROM providers"
        ).fetchall()
        conn.close()

        cm = CredentialsManager()
        for name, settings_json, website_url in rows:
            if not settings_json:
                continue
            try:
                settings = json.loads(settings_json)
                env = settings.get("env", {})
                # Extract API key from env config
                auth_token = env.get("ANTHROPIC_AUTH_TOKEN", "") or env.get("OPENAI_API_KEY", "")
                base_url = env.get("ANTHROPIC_BASE_URL", "") or env.get("OPENAI_BASE_URL", "")
                if auth_token:
                    provider_key = name.lower().replace(" ", "_").split("/")[0]
                    cm.add_key(provider_key, auth_token, base_url=base_url,
                               note=f"from cc-switch: {name}")
                    count += 1
            except (json.JSONDecodeError, Exception):
                continue

        _log.info("cc-switch import: %d credentials from %s", count, path)
    except (sqlite3.Error, OSError) as e:
        _log.warning("cc-switch import failed: %s", e)
    return count


class CredentialsManager:
    """SQLite-backed credential and quota manager.

    Thread-safe. Replaces environment variable management for API keys.
    """

    def __init__(
        self,
        db_path: str | Path = DEFAULT_DB_PATH,
    ) -> None:
        self._db_path = Path(db_path)
        self._lock = threading.RLock()
        self._pricing = PricingRegistry()
        self._init_db()
        self._migrate_env_vars()
        # cc-switch import is NOT automatic — use import_from_cc_switch() explicitly

    def _init_db(self) -> None:
        """Initialize schema."""
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self._db_path))
        c = conn.cursor()

        c.execute("""
            CREATE TABLE IF NOT EXISTS credentials (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                provider TEXT NOT NULL,
                api_key TEXT NOT NULL,
                base_url TEXT DEFAULT '',
                weight INTEGER DEFAULT 100,
                is_active INTEGER DEFAULT 1,
                note TEXT DEFAULT '',
                created_at REAL NOT NULL
            )
        """)
        c.execute("""
            CREATE INDEX IF NOT EXISTS idx_cred_provider
            ON credentials(provider)
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS budgets (
                provider TEXT PRIMARY KEY,
                monthly_limit REAL NOT NULL DEFAULT 0.0,
                action TEXT NOT NULL DEFAULT 'warn',
                month TEXT NOT NULL DEFAULT '',
                month_spend REAL NOT NULL DEFAULT 0.0
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS usage_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                provider TEXT NOT NULL,
                model TEXT NOT NULL DEFAULT '',
                tokens_input INTEGER DEFAULT 0,
                tokens_output INTEGER DEFAULT 0,
                cost REAL NOT NULL DEFAULT 0.0,
                timestamp REAL NOT NULL
            )
        """)
        conn.commit()
        conn.close()

    def _migrate_env_vars(self) -> None:
        """Auto-import credentials from environment variables on first run."""
        conn = sqlite3.connect(str(self._db_path))
        c = conn.cursor()
        existing = c.execute("SELECT COUNT(*) FROM credentials").fetchone()[0]
        if existing > 0:
            conn.close()
            return

        env_map = {
            "openai": ("OPENAI_API_KEY", ""),
            "anthropic": ("ANTHROPIC_API_KEY", ""),
            "gemini": ("GOOGLE_API_KEY", ""),
            "deepseek": ("DEEPSEEK_API_KEY", ""),
            "azure": ("AZURE_OPENAI_API_KEY", "AZURE_OPENAI_ENDPOINT"),
        }
        now = time.time()
        for provider, (key_env, url_env) in env_map.items():
            api_key = os.environ.get(key_env, "")
            if api_key:
                base_url = os.environ.get(url_env, "") if url_env else ""
                c.execute(
                    """INSERT INTO credentials
                       (provider, api_key, base_url, weight, is_active, created_at)
                       VALUES (?, ?, ?, 100, 1, ?)""",
                    (provider, api_key, base_url, now),
                )
                _log.info("Migrated %s credential from env", provider)
        conn.commit()
        conn.close()

    # ── Credential CRUD ──────────────────────────────────────────────────────

    def add_key(
        self,
        provider: str,
        api_key: str,
        base_url: str = "",
        weight: int = 100,
        note: str = "",
    ) -> None:
        """Add an API key for a provider."""
        with self._lock:
            conn = sqlite3.connect(str(self._db_path))
            c = conn.cursor()
            c.execute(
                """INSERT INTO credentials
                   (provider, api_key, base_url, weight, is_active, note, created_at)
                   VALUES (?, ?, ?, ?, 1, ?, ?)""",
                (provider, api_key, base_url, weight, note, time.time()),
            )
            conn.commit()
            conn.close()

    def remove_key(self, provider: str, api_key: str) -> bool:
        """Remove a specific key."""
        with self._lock:
            conn = sqlite3.connect(str(self._db_path))
            c = conn.cursor()
            c.execute("DELETE FROM credentials WHERE provider = ? AND api_key = ?",
                      (provider, api_key))
            removed = c.rowcount > 0
            conn.commit()
            conn.close()
        return removed

    def get_key(self, provider: str) -> str | None:
        """Get an API key for *provider*, with weighted random selection.

        Supports multi-key rotation: keys with higher ``weight`` are
        more likely to be returned.
        """
        with self._lock:
            conn = sqlite3.connect(str(self._db_path))
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            rows = c.execute(
                """SELECT * FROM credentials
                   WHERE provider = ? AND is_active = 1
                   ORDER BY weight DESC""",
                (provider,),
            ).fetchall()
            conn.close()

        if not rows:
            return None
        if len(rows) == 1:
            return rows[0]["api_key"]

        # Weighted random selection
        import random
        total_weight = sum(r["weight"] for r in rows)
        r = random.randint(0, total_weight - 1)
        for row in rows:
            r -= row["weight"]
            if r < 0:
                return row["api_key"]
        return rows[-1]["api_key"]

    def list_keys(self, provider: str = "") -> list[dict[str, Any]]:
        """List all stored credentials."""
        with self._lock:
            conn = sqlite3.connect(str(self._db_path))
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            if provider:
                rows = c.execute(
                    "SELECT * FROM credentials WHERE provider = ?", (provider,)
                ).fetchall()
            else:
                rows = c.execute("SELECT * FROM credentials").fetchall()
            conn.close()
        return [{
            "provider": r["provider"],
            "key_preview": r["api_key"][:8] + "..." if len(r["api_key"]) > 8 else "***",
            "weight": r["weight"],
            "active": bool(r["is_active"]),
            "note": r["note"] if r["note"] else "",
        } for r in rows]

    # ── Budget / Quota ───────────────────────────────────────────────────────

    def set_budget(self, provider: str, monthly_limit: float, action: str = "warn") -> None:
        """Set monthly budget for a provider.

        Args:
            provider: Provider name.
            monthly_limit: Monthly spending limit in USD.
            action: What to do when exceeded — ``block``, ``warn``, or ``log``.
        """
        with self._lock:
            conn = sqlite3.connect(str(self._db_path))
            c = conn.cursor()
            current_month = datetime.now().strftime("%Y-%m")
            c.execute(
                """INSERT OR REPLACE INTO budgets
                   (provider, monthly_limit, action, month, month_spend)
                   VALUES (?, ?, ?, COALESCE(
                       (SELECT month FROM budgets WHERE provider = ?), ?), 0)""",
                (provider, monthly_limit, action, provider, current_month),
            )
            conn.commit()
            conn.close()

    def record_usage(self, provider: str, cost: float, model: str = "",
                     tokens_input: int = 0, tokens_output: int = 0) -> None:
        """Record a usage event and update budget tracking."""
        with self._lock:
            conn = sqlite3.connect(str(self._db_path))
            c = conn.cursor()

            # Usage log
            c.execute(
                """INSERT INTO usage_log
                   (provider, model, tokens_input, tokens_output, cost, timestamp)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (provider, model, tokens_input, tokens_output, cost, time.time()),
            )

            # Update monthly spend
            current_month = datetime.now().strftime("%Y-%m")
            c.execute("""
                UPDATE budgets SET month_spend = month_spend + ?,
                    month = ?
                WHERE provider = ? AND month = ?
            """, (cost, current_month, provider, current_month))

            conn.commit()
            conn.close()

    def get_quota(self, provider: str, use_codexbar: bool = True) -> dict[str, Any]:
        """Get quota status for a provider.

        Tries codexbar CLI first (real-time quota), falls back to
        local budget tracking.

        Args:
            provider: Provider name.
            use_codexbar: If True (default), try codexbar first.

        Returns:
            Dict with ``provider``, ``limit``, ``used``, ``remaining``,
            ``usage_pct``, and ``source`` (``"codexbar"`` or ``"local"``).
        """
        # Try codexbar first
        if use_codexbar and codexbar_available():
            cq = fetch_codexbar_quota(provider)
            if cq.get("status") == "available":
                limit = cq.get("limit", 0) or 0
                used = cq.get("used", 0) or 0
                remaining = cq.get("remaining", 0) or max(0, limit - used)
                return {
                    "provider": provider,
                    "source": "codexbar",
                    "limit": limit,
                    "used": used,
                    "remaining": remaining,
                    "usage_pct": round((used / limit * 100) if limit > 0 else 0, 1),
                    "reset_description": cq.get("reset_description", ""),
                }

        # Fallback to local budget tracking
        with self._lock:
            conn = sqlite3.connect(str(self._db_path))
            c = conn.cursor()
            current_month = datetime.now().strftime("%Y-%m")
            row = c.execute(
                "SELECT monthly_limit, action, month_spend FROM budgets WHERE provider = ?",
                (provider,),
            ).fetchone()
            conn.close()

        if not row:
            return {"provider": provider, "source": "local", "status": "unlimited"}

        limit, action, spend = row
        spend = spend or 0.0
        remaining = max(0.0, limit - spend)
        return {
            "provider": provider,
            "source": "local",
            "monthly_limit": limit,
            "spend": round(spend, 4),
            "remaining": round(remaining, 4),
            "usage_pct": round((spend / limit * 100) if limit > 0 else 0, 1),
            "action": action,
            "month": current_month,
        }

    def check_constraint(self, provider: str, estimated_cost: float = 0.0) -> dict[str, Any]:
        """Check if a request would violate budget constraints.

        Returns:
            Dict with ``allowed`` (bool), ``reason`` (str), and
            ``quota`` (dict).
        """
        quota = self.get_quota(provider)
        if quota.get("status") == "unlimited":
            return {"allowed": True, "reason": "unlimited", "quota": quota}

        would_exceed = (quota["spend"] + estimated_cost) > quota["monthly_limit"]

        if not would_exceed:
            return {"allowed": True, "reason": "within_budget", "quota": quota}

        action = quota.get("action", "warn")
        if action == "block":
            return {"allowed": False, "reason": f"Monthly budget ${quota['monthly_limit']:.2f} exceeded",
                    "quota": quota}
        elif action == "warn":
            return {"allowed": True, "reason": f"Warning: {quota['usage_pct']:.0f}% budget used",
                    "quota": quota}
        else:
            return {"allowed": True, "reason": "budget_exceeded_logged", "quota": quota}

    # ── CLI-friendly ─────────────────────────────────────────────────────────

    def get_summary(self) -> dict[str, Any]:
        """Get a summary of all credentials and quotas."""
        keys = self.list_keys()
        providers = list(set(k["provider"] for k in keys))

        quotas = {}
        for p in providers:
            q = self.get_quota(p)
            if q.get("status") != "unlimited":
                quotas[p] = q

        return {
            "total_keys": len(keys),
            "providers": providers,
            "keys": keys,
            "quotas": quotas,
        }

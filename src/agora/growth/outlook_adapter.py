from __future__ import annotations

"""
---
Type: Module
Status: ACTIVE
Version: 1.0.0
Authority: nucleus/Z-Core/L0-Genome/R0-ACT-SYS-AX01-10_holographic_metadata_axiom.md
Layer: L3
---
"""
# =============================================================================
# 0. 形式化摘要 ≝
# =============================================================================
# Outlook Adapter ≡ Module
# 内涵 ≝ {Outlook, Adapter}
# 外延 ≝ {e | e ∈ Organs ∧ implements(e, OutlookAdapter)}
# 功能 ⊢ {Outlook_Adapter, Init_Outlook, Validate_Adapter}
# =============================================================================

# ---
# domain: D-Gateway
# layer: organs/growth
# status: active
# version: 0.1.0
# owner: '@Prime'
# authority: P5 digital twin core loop
# ---
"""
OutlookAdapter - Microsoft Graph API adapter for BOS digital twin.
"""


import logging  # noqa: E402
import os  # noqa: E402
import time  # noqa: E402
from dataclasses import dataclass, field  # noqa: E402
from enum import StrEnum  # noqa: E402
from pathlib import Path  # noqa: E402
from typing import Any  # noqa: E402

_log = logging.getLogger(__name__)

try:
    import msal  # type: ignore[import-not-found]
    from msal import SerializableTokenCache

    _HAS_MSAL = True
except ImportError:
    _HAS_MSAL = False
    msal = None  # type: ignore
    SerializableTokenCache = None  # type: ignore

try:
    import requests
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry

    _HAS_REQUESTS = True
except ImportError:
    _HAS_REQUESTS = False
    requests = None  # type: ignore


class OutlookAuthType(StrEnum):
    DELEGATED = "delegated"
    APPLICATION = "application"


class OutlookMessagePriority(StrEnum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"


@dataclass
class OutlookMessage:
    message_id: str
    subject: str = ""
    from_address: str = ""
    from_name: str = ""
    to_recipients: list[dict[str, str]] = field(default_factory=list)
    cc_recipients: list[dict[str, str]] = field(default_factory=list)
    bcc_recipients: list[dict[str, str]] = field(default_factory=list)
    body: str = ""
    body_type: str = "text"
    received_at: str = ""
    sent_at: str = ""
    is_read: bool = False
    is_draft: bool = False
    importance: str = "normal"
    has_attachments: bool = False
    conversation_id: str = ""
    internet_message_id: str = ""
    web_link: str = ""
    categories: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "message_id": self.message_id,
            "subject": self.subject,
            "from_address": self.from_address,
            "from_name": self.from_name,
            "to_recipients": self.to_recipients,
            "cc_recipients": self.cc_recipients,
            "bcc_recipients": self.bcc_recipients,
            "body": self.body,
            "body_type": self.body_type,
            "received_at": self.received_at,
            "sent_at": self.sent_at,
            "is_read": self.is_read,
            "is_draft": self.is_draft,
            "importance": self.importance,
            "has_attachments": self.has_attachments,
            "conversation_id": self.conversation_id,
            "internet_message_id": self.internet_message_id,
            "web_link": self.web_link,
            "categories": self.categories,
        }


@dataclass
class OutlookAttachment:
    attachment_id: str
    name: str
    content_type: str
    size: int
    content_bytes: bytes | None = None
    content_id: str = ""
    is_inline: bool = False


class OutlookAdapter:
    """Microsoft Graph API adapter for Outlook email operations."""

    GRAPH_API_BASE = "https://graph.microsoft.com/v1.0"
    AUTHORITY_BASE = "https://login.microsoftonline.com"
    DEFAULT_SCOPES = ["Mail.Read", "Mail.Send", "User.Read", "offline_access"]
    APPLICATION_SCOPES = ["https://graph.microsoft.com/.default"]

    def __init__(
        self,
        client_id: str | None = None,
        tenant_id: str | None = None,
        client_secret: str | None = None,
        auth_type: OutlookAuthType | str = OutlookAuthType.DELEGATED,
        token_cache_path: str | None = None,
        timeout: int = 30,
        max_retries: int = 3,
    ) -> None:
        if not _HAS_MSAL:
            raise RuntimeError("MSAL library required. Install: pip install msal")
        if not _HAS_REQUESTS:
            raise RuntimeError(
                "requests library required. Install: pip install requests"
            )

        self._client_id = client_id or os.environ.get("OUTLOOK_CLIENT_ID", "")
        self._tenant_id = tenant_id or os.environ.get("OUTLOOK_TENANT_ID", "common")
        self._client_secret = client_secret or os.environ.get(
            "OUTLOOK_CLIENT_SECRET", ""
        )
        self._auth_type = (
            OutlookAuthType(auth_type) if isinstance(auth_type, str) else auth_type
        )
        self._token_cache_path = token_cache_path or self._default_token_cache_path()
        self._token_cache = self._load_token_cache()
        self._timeout = timeout
        self._session = requests.Session()
        self._setup_retry_policy(max_retries)
        self._msal_app: Any = None
        self._account: dict | None = None
        self._access_token: str | None = None
        self._token_expires_at: float = 0.0
        self._user_email: str = ""
        self._user_display_name: str = ""

        if not self._client_id:
            raise ValueError("client_id required. Set OUTLOOK_CLIENT_ID env var.")
        _log.info("[OutlookAdapter] Initialized for tenant: %s", self._tenant_id)

    def _default_token_cache_path(self) -> str:
        home = Path.home()
        bos_dir = home / ".bos"
        bos_dir.mkdir(exist_ok=True)
        return str(bos_dir / "outlook_token_cache.bin")

    def _load_token_cache(self) -> Any:
        cache = SerializableTokenCache()
        if os.path.exists(self._token_cache_path):
            try:
                with open(self._token_cache_path, "rb") as f:
                    cache.deserialize(f.read())
            except (OSError, ValueError) as e:
                _log.warning("Failed to load token cache: %s", e)
        return cache

    def _save_token_cache(self) -> None:
        if self._token_cache.has_state_changed:
            try:
                with open(self._token_cache_path, "wb") as f:
                    f.write(self._token_cache.serialize())
            except OSError as e:
                _log.warning("Failed to save token cache: %s", e)

    def _setup_retry_policy(self, max_retries: int) -> None:
        retry_strategy = Retry(
            total=max_retries,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "OPTIONS", "POST", "PATCH", "DELETE"],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self._session.mount("https://", adapter)
        self._session.mount("http://", adapter)

    # -----------------------------------------------------------------------
    # Authentication Methods
    # -----------------------------------------------------------------------

    def authenticate_interactive(self, scopes: list[str] | None = None) -> bool:
        """Authenticate using interactive browser flow."""
        if self._auth_type != OutlookAuthType.DELEGATED:
            raise RuntimeError("authenticate_interactive requires DELEGATED auth type")

        scopes = scopes or self.DEFAULT_SCOPES
        authority = f"{self.AUTHORITY_BASE}/{self._tenant_id}"

        self._msal_app = msal.PublicClientApplication(
            client_id=self._client_id,
            authority=authority,
            token_cache=self._token_cache,
        )

        accounts = self._msal_app.get_accounts()
        if accounts:
            self._account = accounts[0]
            result = self._msal_app.acquire_token_silent_with_error(
                scopes=scopes, account=self._account
            )
            if result and "access_token" in result:
                self._update_token(result)
                return True

        result = self._msal_app.acquire_token_interactive(scopes=scopes, port=0)
        if "access_token" in result:
            self._account = self._msal_app.get_accounts()[0]
            self._update_token(result)
            self._save_token_cache()
            self._fetch_user_info()
            return True
        return False

    def authenticate_device_flow(self, scopes: list[str] | None = None) -> bool:
        """Authenticate using device code flow for headless environments."""
        if self._auth_type != OutlookAuthType.DELEGATED:
            raise RuntimeError("authenticate_device_flow requires DELEGATED auth type")

        scopes = scopes or self.DEFAULT_SCOPES
        authority = f"{self.AUTHORITY_BASE}/{self._tenant_id}"

        self._msal_app = msal.PublicClientApplication(
            client_id=self._client_id,
            authority=authority,
            token_cache=self._token_cache,
        )

        accounts = self._msal_app.get_accounts()
        if accounts:
            self._account = accounts[0]
            result = self._msal_app.acquire_token_silent_with_error(
                scopes=scopes, account=self._account
            )
            if result and "access_token" in result:
                self._update_token(result)
                return True

        flow = self._msal_app.initiate_device_flow(scopes=scopes)
        if "user_code" not in flow:
            return False

        print(f"\n{flow['message']}\n")
        result = self._msal_app.acquire_token_by_device_flow(flow, timeout=300)

        if "access_token" in result:
            self._account = self._msal_app.get_accounts()[0]
            self._update_token(result)
            self._save_token_cache()
            self._fetch_user_info()
            return True
        return False

    def authenticate_application(self) -> bool:
        """Authenticate using client credentials flow."""
        if self._auth_type != OutlookAuthType.APPLICATION:
            raise RuntimeError(
                "authenticate_application requires APPLICATION auth type"
            )
        if not self._client_secret:
            raise ValueError("client_secret required for application authentication")

        authority = f"{self.AUTHORITY_BASE}/{self._tenant_id}"
        self._msal_app = msal.ConfidentialClientApplication(
            client_id=self._client_id,
            client_credential=self._client_secret,
            authority=authority,
            token_cache=self._token_cache,
        )

        result = self._msal_app.acquire_token_for_client(scopes=self.APPLICATION_SCOPES)
        if "access_token" in result:
            self._update_token(result)
            return True
        return False

    def _update_token(self, result: dict) -> None:
        self._access_token = result["access_token"]
        expires_in = result.get("expires_in", 3600)
        self._token_expires_at = time.time() + expires_in

    def _ensure_token(self) -> str:
        if not self._access_token:
            raise RuntimeError("Not authenticated. Call authenticate_*() first.")
        if time.time() > (self._token_expires_at - 300):
            if self._auth_type == OutlookAuthType.DELEGATED and self._account:
                result = self._msal_app.acquire_token_silent_with_error(
                    scopes=self.DEFAULT_SCOPES,
                    account=self._account,
                    force_refresh=True,
                )
            elif self._auth_type == OutlookAuthType.APPLICATION:
                result = self._msal_app.acquire_token_for_client(
                    scopes=self.APPLICATION_SCOPES
                )
            else:
                raise RuntimeError("Unable to refresh token")

            if "access_token" in result:
                self._update_token(result)
                self._save_token_cache()
            else:
                raise RuntimeError("Token refresh failed")
        return self._access_token

    def _fetch_user_info(self) -> None:
        try:
            response = self._graph_request("GET", "/me")
            self._user_email = response.get("mail", "")
            self._user_display_name = response.get("displayName", "")
        except (ConnectionError, OSError, KeyError) as e:
            _log.warning("Failed to fetch user info: %s", e)

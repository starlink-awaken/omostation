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
# Mail Tool ≡ Tool
# 内涵 ≝ {Mail, Tool}
# 外延 ≝ {e | e ∈ Organs ∧ implements(e, MailTool)}
# 功能 ⊢ {Mail_Tool, Init_Mail, Validate_Tool}
# =============================================================================

# ---
# domain: D-Gateway
# layer: tools
# status: active
# version: 1.0.0
# owner: '@Prime'
# authority: P5 digital twin core loop
# ---
"""
MailTool — IMAP/SMTP adapter for BOS digital twin.

Provides email read/send capabilities via IMAP (fetch, search, mark-read)
and SMTP (send), with OAuth2 support for Gmail and Outlook.
Extracted metadata is injected into FactGraph as subject-predicate-object triples.
"""


import email
import imaplib
import logging
import os
import smtplib
import ssl
from datetime import datetime
from email.errors import MessageError
from email.header import decode_header
from email.message import EmailMessage
from typing import Any

from agora.mcp.interfaces.base_tool import BaseTool  # type: ignore[import-not-found]
from agora.mcp.interfaces.tool_interface_contract import (  # type: ignore[import-not-found]
    ToolConfig,
    ToolRequest,
    ToolResult,
    ToolStatus,
)

_log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# OAuth2 helpers
# ---------------------------------------------------------------------------

try:
    from google.auth.transport.requests import Request as _GoogleRequest  # type: ignore[import]
    from google.oauth2.credentials import Credentials as _GoogleCredentials  # type: ignore[import]

    _HAS_GOOGLE_AUTH = True
except ImportError:
    _HAS_GOOGLE_AUTH = False
    _GoogleCredentials = None  # type: ignore[assignment,misc]
    _GoogleRequest = None  # type: ignore[assignment,misc]

try:
    import msal  # type: ignore[import]

    _HAS_MSAL = True
except ImportError:
    _HAS_MSAL = False
    msal = None  # type: ignore[assignment]

# ---------------------------------------------------------------------------
# FactGraph injection (best-effort)
# ---------------------------------------------------------------------------


def _inject_factgraph(triples: list[dict[str, Any]]) -> None:
    """Inject email metadata triples into FactGraph. Fail silently."""
    try:
        FactGraph = __import__(  # noqa: N806
            "nucleus.D_Memory.fact_graph",
            fromlist=["FactGraph"],
        ).FactGraph
        fg = FactGraph()
        for triple in triples:
            fg.add_fact(
                subject=str(triple.get("subject", "")),
                predicate=str(triple.get("predicate", "")),
                object_=str(triple.get("object", "")),
            )
    except (ImportError, AttributeError, TypeError):
        _log.debug("[MailTool] FactGraph not available — skipping injection")


# ---------------------------------------------------------------------------
# Sentiment analysis (keyword-based)
# ---------------------------------------------------------------------------

_SENTIMENT_POSITIVE = {"thanks", "great", "excellent", "happy", "appreciate", "wonderful", "love"}
_SENTIMENT_NEGATIVE = {"sorry", "issue", "problem", "fail", "urgent", "broken", "error", "disappointed"}


def _analyze_sentiment(text: str) -> str:
    """Return 'positive', 'negative', or 'neutral' based on keyword matching."""
    lower = text.lower()
    pos = sum(1 for w in _SENTIMENT_POSITIVE if w in lower)
    neg = sum(1 for w in _SENTIMENT_NEGATIVE if w in lower)
    if pos > neg:
        return "positive"
    if neg > pos:
        return "negative"
    return "neutral"


# ---------------------------------------------------------------------------
# IMAP/SMTP helpers
# ---------------------------------------------------------------------------


def _decode_payload(msg: EmailMessage) -> str:
    """Extract decoded body text from an email message."""
    if msg.is_multipart():
        for part in msg.walk():
            ct = part.get_content_type()
            disp = str(part.get("Content-Disposition") or "")
            if ct == "text/plain" and "attachment" not in disp:
                try:
                    charset = part.get_content_charset() or "utf-8"
                    payload = part.get_payload(decode=True)
                    if payload is None:
                        continue
                    return payload.decode(charset, errors="replace")
                except (ValueError, TypeError):
                    continue
    else:
        try:
            charset = msg.get_content_charset() or "utf-8"
            payload = msg.get_payload(decode=True)
            if payload is None:
                return ""
            return payload.decode(charset, errors="replace")
        except (ValueError, TypeError):
            pass
    return ""


def _decode_str(value: str | bytes | None) -> str:
    """Decode a header string or bytes value to str."""
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value


def _decode_header_str(value: str | None) -> str:
    """Decode an email header value that may contain encoded words."""
    if not value:
        return ""
    try:
        parts = decode_header(value)
        decoded = []
        for content, charset in parts:
            if isinstance(content, bytes):
                decoded.append(content.decode(charset or "utf-8", errors="replace"))
            else:
                decoded.append(str(content))
        return "".join(decoded)
    except (LookupError, MessageError, TypeError, ValueError):
        return value


def _xoauth2_string(email_addr: str, access_token: str) -> str:
    """Build an XOAUTH2 SASL PLAIN authentication string."""
    return f"user={email_addr}\x01auth=Bearer {access_token}\x01\x01"


# ---------------------------------------------------------------------------
# MailTool
# ---------------------------------------------------------------------------


class MailTool(BaseTool):
    """BOS tool for email operations via IMAP and SMTP.

    Supports:
    - IMAP: list folders, fetch emails, search, mark-read
    - SMTP: plain/html emails with attachments
    - OAuth2: Gmail (google-auth) and Outlook (MSAL)
    - FactGraph injection: sender/recipient/subject triples
    """

    tool_name = "mail"

    def __init__(
        self,
        config: ToolConfig | None = None,
        imap_host: str | None = None,
        smtp_host: str | None = None,
        email_address: str | None = None,
        oauth2_token_path: str | None = None,
        provider: str = "gmail",
    ) -> None:
        super().__init__(config=config or ToolConfig(name="mail_inbox", mcp_namespace="mail_inbox"))
        self._imap_host = imap_host or os.environ.get("MAIL_IMAP_HOST", "imap.gmail.com")
        self._smtp_host = smtp_host or os.environ.get("MAIL_SMTP_HOST", "smtp.gmail.com")
        self._email_address = email_address or os.environ.get("MAIL_EMAIL_ADDRESS", "")
        self._oauth2_token_path = oauth2_token_path or os.environ.get("MAIL_OAUTH2_TOKEN_PATH", "")
        self._provider = provider.lower()
        self._imap_conn: imaplib.IMAP4_SSL | imaplib.IMAP4 | None = None
        self._smtp_conn: smtplib.SMTP | smtplib.SMTP_SSL | None = None
        self._oauth2_access_token: str | None = None

    # -------------------------------------------------------------------------
    # Connection management
    # -------------------------------------------------------------------------

    def _get_imap_conn(self) -> imaplib.IMAP4_SSL | imaplib.IMAP4:
        """Return a cached or new IMAP connection."""
        if self._imap_conn is not None:
            try:
                self._imap_conn.select()
                return self._imap_conn
            except Exception:
                self._imap_conn = None

        if self._provider == "gmail":
            conn: imaplib.IMAP4_SSL | imaplib.IMAP4 = imaplib.IMAP4_SSL(self._imap_host)
        else:
            conn = imaplib.IMAP4(self._imap_host)
            try:
                conn.starttls()
            except Exception:
                pass

        self._authenticate_imap(conn)
        self._imap_conn = conn
        return conn

    def _authenticate_imap(self, conn: imaplib.IMAP4_SSL | imaplib.IMAP4) -> None:
        """Authenticate IMAP connection using OAuth2 or plain credentials."""
        if self._oauth2_access_token:
            auth_str = _xoauth2_string(self._email_address, self._oauth2_access_token)
            conn.authenticate("XOAUTH2", lambda _: auth_str.encode())
        elif self._provider == "outlook" and _HAS_MSAL and self._oauth2_token_path:
            token = self._load_outlook_token()
            if token:
                auth_str = _xoauth2_string(self._email_address, token)
                conn.authenticate("XOAUTH2", lambda _: auth_str.encode())
        else:
            username = os.environ.get("MAIL_USERNAME", self._email_address)
            password = os.environ.get("MAIL_PASSWORD", "")
            conn.login(username, password)

    def _get_smtp_conn(self) -> smtplib.SMTP | smtplib.SMTP_SSL:
        """Return a cached or new SMTP connection."""
        if self._smtp_conn is not None:
            try:
                self._smtp_conn.noop()
                return self._smtp_conn
            except Exception:
                self._smtp_conn = None

        context = ssl.create_default_context()
        if self._provider == "gmail":
            conn: smtplib.SMTP | smtplib.SMTP_SSL = smtplib.SMTP_SSL(self._smtp_host, 465, context=context)
        else:
            conn = smtplib.SMTP(self._smtp_host, 587)
            try:
                conn.starttls(context=context)
            except Exception:
                pass

        self._authenticate_smtp(conn)
        self._smtp_conn = conn
        return conn

    def _authenticate_smtp(self, conn: smtplib.SMTP | smtplib.SMTP_SSL) -> None:
        """Authenticate SMTP connection using OAuth2 or plain credentials."""
        if self._oauth2_access_token:
            conn.ehlo()
            if self._provider == "gmail" and _HAS_GOOGLE_AUTH:
                auth_str = _xoauth2_string(self._email_address, self._oauth2_access_token)
                conn.auth("XOAUTH2", lambda ___auth_str___=auth_str: ___auth_str___)  # type: ignore[arg-type]
            elif self._provider == "outlook" and _HAS_MSAL:
                token = self._load_outlook_token()
                if token:
                    auth_str = _xoauth2_string(self._email_address, token)
                    conn.auth("XOAUTH2", lambda ___auth_str___=auth_str: ___auth_str___)  # type: ignore[arg-type]
        else:
            username = os.environ.get("MAIL_USERNAME", self._email_address)
            password = os.environ.get("MAIL_PASSWORD", "")
            conn.login(username, password)

    def _load_outlook_token(self) -> str | None:
        """Load Outlook OAuth2 access token from MSAL cache."""
        if not _HAS_MSAL or msal is None:
            return None
        try:
            app = msal.ConfidentialClientApplication(
                client_id=os.environ.get("AZURE_CLIENT_ID", ""),
                authority=f"https://login.microsoftonline.com/{os.environ.get('AZURE_TENANT_ID', '')}",
                client_credential=os.environ.get("AZURE_CLIENT_SECRET", ""),
            )
            result = app.acquire_token_silent(
                scopes=["https://graph.microsoft.com/.default"],
                account=None,
            )
            return result.get("access_token") if result else None
        except Exception:
            return None

    def _refresh_oauth2_token(self) -> bool:
        """Refresh OAuth2 access token. Returns True if successful."""
        if not _HAS_GOOGLE_AUTH or _GoogleCredentials is None:
            return False
        try:
            creds = _GoogleCredentials.from_authorized_user_file(self._oauth2_token_path)
            if creds and creds.refresh_token and not creds.valid:
                req = _GoogleRequest()
                creds.refresh(req)
                with open(self._oauth2_token_path, "w") as fh:
                    fh.write(creds.to_json())
                self._oauth2_access_token = creds.token
                return True
            self._oauth2_access_token = creds.token if creds else None
            return bool(self._oauth2_access_token)
        except Exception:
            return False

    # -------------------------------------------------------------------------
    # Tool actions
    # -------------------------------------------------------------------------

    def _do_execute(self, request: ToolRequest) -> ToolResult:
        action = request.action
        params = request.params

        if action == "list_mailboxes":
            return self._list_mailboxes()
        elif action == "fetch_emails":
            return self._fetch_emails(
                folder=params.get("folder", "INBOX"),
                limit=int(params.get("limit", 10)),
                unread_only=bool(params.get("unread_only", False)),
            )
        elif action == "send_email":
            return self._send_email(
                to=params.get("to", ""),
                subject=params.get("subject", ""),
                body=params.get("body", ""),
                cc=params.get("cc", ""),
                bcc=params.get("bcc", ""),
                attachments=params.get("attachments", []),
            )
        elif action == "mark_read":
            return self._mark_read(
                email_id=str(params.get("email_id", "")),
                folder=params.get("folder", "INBOX"),
            )
        elif action == "search_emails":
            return self._search_emails(
                query=params.get("query", ""),
                folder=params.get("folder", "INBOX"),
                limit=int(params.get("limit", 50)),
            )
        else:
            return ToolResult(
                success=False,
                error=f"Unknown action: {action}",
                status=ToolStatus.FAILURE,
            )

    # -------------------------------------------------------------------------
    # Core methods
    # -------------------------------------------------------------------------

    def list_mailboxes(self) -> list[str]:
        """List all available IMAP folders."""
        try:
            conn = self._get_imap_conn()
            status, folders = conn.list()
            if status != "OK":
                return []
            result = []
            for folder in folders:
                decoded = _decode_header_str(_decode_str(folder) if isinstance(folder, bytes) else str(folder))
                result.append(decoded)
            return result
        except Exception as exc:
            _log.error("[MailTool] list_mailboxes failed: %s", exc)
            return []

    def _list_mailboxes(self) -> ToolResult:
        folders = self.list_mailboxes()
        return ToolResult(
            success=True,
            data={"mailboxes": folders, "count": len(folders)},
            status=ToolStatus.SUCCESS,
        )

    def fetch_emails(
        self,
        folder: str = "INBOX",
        limit: int = 10,
        unread_only: bool = False,
    ) -> list[dict[str, Any]]:
        """Fetch email summaries from a folder."""
        try:
            conn = self._get_imap_conn()
            conn.select(folder)

            search_criteria = "UNSEEN" if unread_only else "ALL"
            status, msg_ids = conn.search(None, search_criteria)
            if status != "OK":
                return []

            ids = list(msg_ids[0].split())
            ids = ids[-limit:] if len(ids) > limit else ids

            emails = []
            for mid in reversed(ids):
                mid_b = mid if isinstance(mid, bytes) else mid
                try:
                    status, msg_data = conn.fetch(
                        str(mid_b, "utf-8") if isinstance(mid_b, bytes) else mid_b, "(RFC822)"
                    )
                    if status != "OK":
                        continue
                    raw: bytes | None = None
                    if isinstance(msg_data[0], tuple):
                        raw = msg_data[0][1]
                    elif isinstance(msg_data[0], bytes):
                        raw = msg_data[0]
                    if raw is None:
                        continue
                    msg = email.message_from_bytes(raw)

                    subject = _decode_header_str(msg.get("Subject"))
                    sender = _decode_header_str(msg.get("From"))
                    recipients = _decode_header_str(msg.get("To"))
                    date_str = msg.get("Date", "")
                    msg_id = msg.get("Message-ID", _decode_str(mid_b))
                    snippet = _decode_payload(msg)[:200]

                    emails.append(
                        {
                            "email_id": _decode_str(mid_b),
                            "message_id": msg_id,
                            "subject": subject,
                            "from": sender,
                            "to": recipients,
                            "date": date_str,
                            "snippet": snippet,
                            "sentiment": _analyze_sentiment(subject + " " + snippet),
                        }
                    )
                except Exception as exc:
                    _log.debug("[MailTool] Failed to parse email %s: %s", mid_b, exc)
                    continue

            return emails
        except Exception as exc:
            _log.error("[MailTool] fetch_emails failed: %s", exc)
            return []

    def _fetch_emails(
        self,
        folder: str,
        limit: int,
        unread_only: bool,
    ) -> ToolResult:
        emails = self.fetch_emails(folder=folder, limit=limit, unread_only=unread_only)

        if emails:
            triples = []
            for e in emails:
                msg_id = e.get("message_id") or e.get("email_id", "")
                triples.extend(
                    [
                        {"subject": f"email:{msg_id}", "predicate": "from", "object": e.get("from", "")},
                        {"subject": f"email:{msg_id}", "predicate": "has_subject", "object": e.get("subject", "")},
                        {
                            "subject": f"email:{msg_id}",
                            "predicate": "sentiment",
                            "object": e.get("sentiment", "neutral"),
                        },
                    ]
                )
            _inject_factgraph(triples)

        return ToolResult(
            success=True,
            data={"emails": emails, "count": len(emails), "folder": folder},
            status=ToolStatus.SUCCESS,
        )

    def send_email(
        self,
        to: str,
        subject: str,
        body: str,
        cc: str = "",
        bcc: str = "",
        attachments: list[str] | None = None,
    ) -> dict[str, Any]:
        """Send an email via SMTP."""
        try:
            msg = EmailMessage()
            msg["From"] = self._email_address
            msg["To"] = to
            if cc:
                msg["Cc"] = cc
            if bcc:
                msg["Bcc"] = bcc
            msg["Subject"] = subject
            msg["Date"] = datetime.now(tz=None).strftime("%a, %d %b %Y %H:%M:%S +0000")
            msg.set_content(body)

            if attachments:
                for filepath in attachments:
                    try:
                        with open(filepath, "rb") as fh:
                            msg.add_attachment(
                                fh.read(),
                                maintype="application",
                                subtype="octet-stream",
                                filename=os.path.basename(filepath),
                            )
                    except OSError:
                        _log.warning("[MailTool] Could not attach file: %s", filepath)

            conn = self._get_smtp_conn()

            recipients = [r.strip() for r in to.split(",") if r.strip()]
            if cc:
                recipients += [r.strip() for r in cc.split(",") if r.strip()]

            conn.send_message(msg, to_addrs=recipients if recipients else None)

            _inject_factgraph(
                [
                    {
                        "subject": f"person:{self._email_address}",
                        "predicate": "sent_email",
                        "object": f"email:{subject}",
                    }
                ]
            )

            return {"success": True, "message_id": msg.get("Message-ID", "")}
        except Exception as exc:
            _log.error("[MailTool] send_email failed: %s", exc)
            return {"success": False, "error": str(exc)}

    def _send_email(
        self,
        to: str,
        subject: str,
        body: str,
        cc: str,
        bcc: str,
        attachments: list[str],
    ) -> ToolResult:
        result = self.send_email(to=to, subject=subject, body=body, cc=cc, bcc=bcc, attachments=attachments or [])
        return ToolResult(
            success=result.get("success", False),
            data=result,
            error=result.get("error"),
            status=ToolStatus.SUCCESS if result.get("success") else ToolStatus.FAILURE,
        )

    def mark_read(self, email_id: str, folder: str = "INBOX") -> bool:
        """Mark an email as read."""
        try:
            conn = self._get_imap_conn()
            conn.select(folder)
            conn.store(email_id, "+FLAGS", "\\Seen")
            return True
        except Exception as exc:
            _log.error("[MailTool] mark_read failed: %s", exc)
            return False

    def _mark_read(self, email_id: str, folder: str) -> ToolResult:
        success = self.mark_read(email_id=email_id, folder=folder)
        return ToolResult(
            success=success,
            data={"email_id": email_id, "folder": folder, "marked_read": success},
            status=ToolStatus.SUCCESS if success else ToolStatus.FAILURE,
        )

    def search_emails(
        self,
        query: str,
        folder: str = "INBOX",
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Search emails using IMAP search criteria."""
        try:
            conn = self._get_imap_conn()
            conn.select(folder)

            imap_query = query.upper()
            status, msg_ids = conn.search(None, imap_query)
            if status != "OK":
                return []

            ids = list(msg_ids[0].split())
            ids = ids[-limit:] if len(ids) > limit else ids

            emails = []
            for mid in reversed(ids):
                mid_b = mid if isinstance(mid, bytes) else mid
                try:
                    status, msg_data = conn.fetch(
                        str(mid_b, "utf-8") if isinstance(mid_b, bytes) else mid_b, "(RFC822)"
                    )
                    if status != "OK":
                        continue
                    raw: bytes | None = None
                    if isinstance(msg_data[0], tuple):
                        raw = msg_data[0][1]
                    elif isinstance(msg_data[0], bytes):
                        raw = msg_data[0]
                    if raw is None:
                        continue
                    msg = email.message_from_bytes(raw)

                    emails.append(
                        {
                            "email_id": _decode_str(mid_b),
                            "subject": _decode_header_str(msg.get("Subject")),
                            "from": _decode_header_str(msg.get("From")),
                            "to": _decode_header_str(msg.get("To")),
                            "date": msg.get("Date", ""),
                        }
                    )
                except Exception:  # noqa: S112
                    continue

            return emails
        except Exception as exc:
            _log.error("[MailTool] search_emails failed: %s", exc)
            return []

    def _search_emails(
        self,
        query: str,
        folder: str,
        limit: int,
    ) -> ToolResult:
        emails = self.search_emails(query=query, folder=folder, limit=limit)
        return ToolResult(
            success=True,
            data={"emails": emails, "count": len(emails), "query": query, "folder": folder},
            status=ToolStatus.SUCCESS,
        )

    # -------------------------------------------------------------------------
    # Lifecycle
    # -------------------------------------------------------------------------

    def initialize(self) -> None:
        """Initialize — refresh OAuth2 token if available."""
        super().initialize()
        if self._oauth2_token_path:
            self._refresh_oauth2_token()

    def shutdown(self) -> None:
        """Close IMAP and SMTP connections."""
        try:
            if self._imap_conn:
                self._imap_conn.logout()
        except Exception:
            pass
        try:
            if self._smtp_conn:
                self._smtp_conn.quit()
        except Exception:
            pass
        self._imap_conn = None
        self._smtp_conn = None
        super().shutdown()


__all__ = ["MailTool"]

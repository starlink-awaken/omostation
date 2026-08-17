from __future__ import annotations

"""
---
Type: Infrastructure
Status: ACTIVE
Version: 0.0.1
Owner: '@Sisyphus'
Layer: D-Memory
Summary: Memory gateway with HMAC token-based access control
Authority: AGENTS.md
---
"""

# =============================================================================
# 0. 形式化摘要 ≝
# =============================================================================
# Memory_Organ ≡ Memory_System
# 内涵 ≝ {Store, Retrieve, Index, Compact}
# 外延 ≝ {m | m ∈ D-Memory ∧ persists(m, Knowledge)}
# 功能 ⊢ {StoreMemories, RetrieveMemories, MaintainIndex}
# =============================================================================

"""
D-Memory: Holographic Memory Gateway
Implements Cryptographic URI Mediation for Memory Access.
Never exposes raw DB paths to external workers.
"""

import collections
import hashlib
import hmac
import logging
import os
import secrets as _secrets
import threading
import time
import uuid
from typing import TypedDict

from eidos.organs.storage_dal import SQLiteOperationalError, SQLiteRelationalProvider

_log = logging.getLogger(__name__)

__all__ = ["MemoryGateway", "TokenIssuanceError"]

# Token field separator — used when minting and when parsing tokens.
_TOKEN_SEP = "."  # WARNING: changing this invalidates all existing tokens; requires full token rotation  # noqa: S105


class TokenIssuanceError(RuntimeError):
    """Raised when a new access token cannot be issued.

    Typically wraps an underlying :exc:`RuntimeError` from
    :meth:`MemoryGateway._init_db` when the backing SQLite database cannot be
    created (e.g. filesystem permission denied, disk full).
    """


class TokenSession(TypedDict):
    """Type-safe snapshot of an active memory-access token.

    All fields are populated atomically inside :meth:`MemoryGateway._generate_token`
    and are considered immutable after creation.
    """

    worker_id: str  # Unique identifier of the requesting worker agent
    role: str  # Normalised role name that maps to a memory partition (DB file)
    expiry: float  # Unix timestamp (seconds) after which the token is no longer valid
    db_path: str  # Absolute filesystem path to the backing SQLite database
    hmac_sig: str  # HMAC-SHA256 hex-digest of ``token_id:worker_id``; used to
    # prevent token forgery during :meth:`MemoryGateway._verify_token`


class MemoryGateway:
    """Holographic Memory Gateway — cryptographic URI mediator for B-OS memory access.

    This gateway is the **only** component that knows the raw filesystem paths to
    memory partitions.  Every other system (workers, orchestrators, MCP clients)
    interacts exclusively through opaque ``bos://memory/<role>`` URIs and
    short-lived access tokens.

    Token Lifecycle
    ---------------
    1. **Creation** — :meth:`issue_access_pass` calls :meth:`_generate_token`,
       which mints a UUID token, signs it with HMAC-SHA256, stores the session in
       :attr:`active_tokens`, and returns ``(uri, token)`` to the caller.
    2. **Validation** — :meth:`_verify_token` checks three things in order:

       * The token exists in :attr:`active_tokens` (not forged / already revoked).
       * The stored HMAC signature matches a fresh computation over
         ``token_id:worker_id`` using the instance secret key (integrity check).
       * The session has not expired (``expiry > time.time()``).

       Expired sessions are evicted lazily on their first failed validation.
    3. **Expiry / Revocation** — Tokens expire automatically after
       :attr:`DEFAULT_TOKEN_EXPIRY` seconds (default 3 600 s / 1 hour).
       Call :meth:`revoke_token` to invalidate a token eagerly.

    HMAC Signing
    ------------
    A per-instance secret key (32 random hex bytes, generated via
    :func:`secrets.token_hex`) is created in :meth:`__init__`.  The secret never
    leaves the process; it is **not** read from environment variables, so every
    restart produces a fresh key and invalidates all previously issued tokens
    (correct behaviour for a transient in-process registry).

    Thread Safety
    -------------
    All reads and writes to :attr:`active_tokens` are protected by
    :attr:`_tokens_lock` (a :class:`threading.RLock`), making the gateway safe
    for concurrent use across multiple worker threads.

    Key Lifecycle
    -------------
    1. **Process-level random generation** — :attr:`_secret_key` is generated
       once per process via :func:`secrets.token_hex` at instantiation time.
       It is 32 random hex bytes (256-bit entropy) and is never persisted.
    2. **Process restart invalidates all tokens** — because the key is
       ephemeral, any token issued before a restart will fail HMAC verification
       after the restart.  Callers must re-issue tokens after process restarts.
    3. **Production rotation strategy** — in long-running deployments consider
       (a) scheduling periodic process restarts during low-traffic windows, or
       (b) replacing the singleton :data:`global_memory_gateway` with a new
       instance and forcing all workers to re-authenticate; tokens carry
       short :attr:`DEFAULT_TOKEN_EXPIRY` TTLs (1 hour) so natural expiry
       already limits the blast radius of a compromised token.

    Token Revocation Example
    ------------------------
    To eagerly invalidate a token before it expires::

        gw = MemoryGateway()
        uri, token = gw.issue_access_pass("worker-42", "researcher")

        # … worker finishes its task …

        revoked = gw.revoke_token(token)
        assert revoked is True  # token was active and is now removed

        # Attempting to use the token after revocation raises PermissionError:
        try:
            gw.read_memory(uri, token)
        except PermissionError:
            pass  # expected — token no longer valid
    """

    DEFAULT_TOKEN_EXPIRY: int = 3600  # seconds
    _MAX_ACTIVE_TOKENS: int = int(os.environ.get("BOS_MAX_ACTIVE_TOKENS", "10000"))

    def __init__(self) -> None:
        # Per-instance secret; intentionally NOT read from env so every process
        # restart invalidates all previously issued tokens.
        self._secret_key: bytes = _secrets.token_hex(32).encode()
        self.base_dir = os.path.expanduser("~/.bos-mcp/memories")
        os.makedirs(self.base_dir, exist_ok=True)

        self._tokens_lock = threading.RLock()
        # Token registry: token -> TokenSession  (guarded by _tokens_lock)
        # Uses OrderedDict so we can evict the oldest entry when capacity is reached.
        self.active_tokens: collections.OrderedDict[str, TokenSession] = collections.OrderedDict()

    @staticmethod
    def _validate_role_name(role: str) -> str:
        """Validate and normalize a role name to prevent path traversal.

        Args:
            role: Raw role name supplied by the caller.

        Returns:
            Normalized lowercase role name with spaces/hyphens replaced by underscores.

        Raises:
            ValueError: If the normalized name contains characters other than
                alphanumeric and underscore.
        """
        normalized = role.replace(" ", "_").replace("-", "_").lower()
        if not normalized.replace("_", "").isalnum():
            raise ValueError(f"Invalid role name: {role!r}. Only alphanumeric and underscore allowed.")
        return normalized

    def _sign_token(self, token_id: str, worker_id: str) -> str:
        """Return HMAC-SHA256 hex-digest of ``token_id:worker_id``.

        Used both when minting a token (stored in :class:`TokenSession`) and when
        verifying it (compared via :func:`hmac.compare_digest` to prevent
        timing-based attacks).

        Args:
            token_id:  The UUID hex string that identifies the token.
            worker_id: The worker that was issued the token.

        Returns:
            64-character lowercase hex string (256-bit HMAC digest).
        """
        msg = f"{token_id}:{worker_id}".encode()
        return hmac.new(self._secret_key, msg, hashlib.sha256).hexdigest()

    def _generate_token(self, worker_id: str, role: str) -> str:
        """Mint and register a new time-bound access token.

        The token is a random UUID hex string.  Its HMAC-SHA256 signature is
        stored alongside the session so that :meth:`_verify_token` can detect
        any tampering without a round-trip to an external authority.

        Args:
            worker_id: Unique identifier of the requesting worker.
            role:      Already-validated (normalised) role name.

        Returns:
            Opaque token string to be passed back to the caller.
        """
        safe_role = self._validate_role_name(role)
        token_id = uuid.uuid4().hex
        sig = self._sign_token(token_id, worker_id)
        token = f"{token_id}.{sig}"

        with self._tokens_lock:
            self.active_tokens[token] = TokenSession(
                worker_id=worker_id,
                role=safe_role,
                expiry=time.time() + self.DEFAULT_TOKEN_EXPIRY,
                db_path=os.path.join(self.base_dir, f"{safe_role}.db"),
                hmac_sig=sig,
            )
            # Enforce capacity limit — evict oldest (LRU-FIFO) entry when over cap.
            if len(self.active_tokens) > self._MAX_ACTIVE_TOKENS:
                _log.warning(
                    "Token capacity limit reached (%d), evicting oldest token",
                    self._MAX_ACTIVE_TOKENS,
                )
                oldest = next(iter(self.active_tokens))
                del self.active_tokens[oldest]
        return token

    def _cleanup_expired_tokens(self) -> int:
        """Remove expired tokens from active_tokens. Thread-safe. Returns count removed.

        Proactively evicts all tokens whose ``expiry`` timestamp is in the past,
        preventing unbounded growth of :attr:`active_tokens` under long-running
        workloads that issue many tokens without explicit revocation.

        Called automatically by :meth:`issue_access_pass` on each new token
        issuance.  May also be invoked independently for maintenance purposes.

        Returns:
            Number of expired token entries deleted from :attr:`active_tokens`.
        """
        now = time.time()
        with self._tokens_lock:
            expired = [t for t, s in self.active_tokens.items() if s["expiry"] < now]
            for t in expired:
                del self.active_tokens[t]
        return len(expired)

    def issue_access_pass(self, worker_id: str, role: str) -> tuple[str, str]:
        """Mint a cryptographic access pass for a worker.

        Called by the Orchestrator **before** spawning a Worker.  The returned
        ``(uri, token)`` pair is the only information the Worker needs; the raw
        SQLite database path is never exposed outside this class.

        Args:
            worker_id: Unique identifier of the worker requesting access.
            role: Role name that determines which memory partition is accessed.

        Returns:
            Tuple of ``(uri, token)``:

            * ``uri`` — opaque ``bos://memory/<role>`` address the Worker should
              pass to :meth:`read_memory` / :meth:`write_memory`.
            * ``token`` — HMAC-signed access token valid for
              :attr:`DEFAULT_TOKEN_EXPIRY` seconds.

        Raises:
            ValueError: If *role* contains illegal characters.
            TokenIssuanceError: If the backing SQLite database cannot be
                initialised — e.g. filesystem permission denied or disk full.
                Wraps the underlying :exc:`RuntimeError` from
                :meth:`_init_db`.

        Examples:
            >>> gw = MemoryGateway()
            >>> uri, token = gw.issue_access_pass("worker-42", "researcher")
            >>> uri
            'bos://memory/researcher'
            >>> isinstance(token, str) and len(token) > 0
            True
        """
        self._cleanup_expired_tokens()
        safe_role = self._validate_role_name(role)
        token = self._generate_token(worker_id, safe_role)
        uri = f"bos://memory/{safe_role}"

        with self._tokens_lock:
            db_path = self.active_tokens[token]["db_path"]
        # SQLite CREATE TABLE IF NOT EXISTS is atomic; concurrent callers are safe.
        # Even if two threads reach this point simultaneously for the same role,
        # _init_db uses "CREATE TABLE IF NOT EXISTS" which SQLite executes atomically.
        if not os.path.exists(db_path):
            try:
                self._init_db(db_path)
            except RuntimeError as exc:
                raise TokenIssuanceError(f"Failed to initialise memory DB for role {safe_role!r}: {exc}") from exc

        _log.info(f"🔑 [D-Memory] Issued cryptographic pass for {worker_id} (Role: {safe_role})")
        return uri, token

    def _verify_token(self, token: str) -> TokenSession:
        """Validate an access token and return its session data.

        Performs three checks (all must pass):

        1. **Existence** — the token is present in :attr:`active_tokens`.
        2. **Integrity** — the stored HMAC signature matches a freshly computed
           digest over ``token_id:worker_id`` using :meth:`_sign_token`.
        3. **Expiry** — ``session["expiry"] > time.time()``.

        Expired tokens are evicted from :attr:`active_tokens` on first detection.

        Args:
            token: Opaque token string previously returned by
                :meth:`issue_access_pass`.

        Returns:
            :class:`TokenSession` mapping with the following keys:

            * ``worker_id`` (str) — identifier of the worker the token was issued to.
            * ``role`` (str) — normalised memory partition name.
            * ``expiry`` (float) — Unix timestamp after which the token is invalid.
            * ``db_path`` (str) — absolute path to the backing SQLite database.
            * ``hmac_sig`` (str) — HMAC-SHA256 hex-digest used for integrity checks.

        Raises:
            PermissionError: If the token is absent, forged, or expired.
            ValueError: If *token* does not contain the expected
                ``'<uuid>.<hmac>'`` format (i.e. no ``'.'`` separator
                is present), preventing silent misuse of malformed tokens.

        Examples:
            >>> gw = MemoryGateway()
            >>> _, token = gw.issue_access_pass("worker-1", "analyst")
            >>> session = gw._verify_token(token)
            >>> session["worker_id"]
            'worker-1'
            >>> session["role"]
            'analyst'
        """
        with self._tokens_lock:
            if token not in self.active_tokens:
                raise PermissionError("Invalid or forged memory token.")

            session = self.active_tokens[token]

            # Re-derive the expected HMAC and compare in constant time
            parts = token.split(_TOKEN_SEP, 1)
            if len(parts) != 2:
                raise ValueError(f"invalid token format: expected 'uuid{_TOKEN_SEP}sig'")
            token_id = parts[0]
            expected_sig = self._sign_token(token_id, session["worker_id"])
            if not hmac.compare_digest(session["hmac_sig"], expected_sig):
                raise PermissionError("Memory token HMAC verification failed.")

            if time.time() > session["expiry"]:
                del self.active_tokens[token]
                raise PermissionError("Memory token expired.")

            return session

    def _init_db(self, path: str) -> None:
        try:
            provider = SQLiteRelationalProvider(path)
            provider.execute("CREATE TABLE IF NOT EXISTS memories (id TEXT PRIMARY KEY, content TEXT, timestamp REAL)")
        except SQLiteOperationalError as e:
            raise RuntimeError(f"MemoryGateway DB init failed: {e}") from e

    # --- RPC Methods exposed via MCP Server later ---

    def read_memory(self, uri: str, token: str, limit: int = 10) -> list[dict]:
        """
        Read the most recent memories accessible via *token*.

        Args:
            uri:   Memory URI (must match the token's allowed scope).
            token: HMAC access token issued by :meth:`issue_access_pass`.
            limit: Maximum number of records to return (default: 10).

        Returns:
            List of dicts with keys ``id``, ``content``, and ``timestamp``,
            ordered by descending timestamp.

        Raises:
            PermissionError: If *token* is invalid, expired, or the *uri* is
                outside the token's allowed scope.
        """
        session = self._verify_token(token)
        expected_uri = f"bos://memory/{session['role']}"
        if not uri.startswith(expected_uri):
            raise PermissionError("Token does not grant access to this memory URI.")

        provider = SQLiteRelationalProvider(session["db_path"])
        rows = provider.fetch_all(
            "SELECT id, content, timestamp FROM memories ORDER BY timestamp DESC LIMIT ?",
            (limit,),
        )
        return [{"id": r["id"], "content": r["content"], "timestamp": r["timestamp"]} for r in rows]

    def write_memory(self, uri: str, token: str, content: str) -> str:
        """
        Persist a new memory entry.

        Args:
            uri:     Memory URI (must match the token's allowed scope).
            token:   HMAC access token issued by :meth:`issue_access_pass`.
            content: Text content to store.

        Returns:
            The 8-character hex ID assigned to the new memory record.

        Raises:
            PermissionError: If *token* is invalid, expired, or the *uri* is
                outside the token's allowed scope.
        """
        session = self._verify_token(token)
        expected_uri = f"bos://memory/{session['role']}"
        if not uri.startswith(expected_uri):
            raise PermissionError("Token does not grant access to this memory URI.")

        mem_id = uuid.uuid4().hex[:8]
        provider = SQLiteRelationalProvider(session["db_path"])
        provider.execute(
            "INSERT INTO memories (id, content, timestamp) VALUES (?, ?, ?)",
            (mem_id, content, time.time()),
        )
        return mem_id

    def revoke_token(self, token: str) -> bool:
        """Eagerly invalidate a previously issued access token.

        Removes *token* from :attr:`active_tokens` so that any subsequent call
        to :meth:`read_memory`, :meth:`write_memory`, or :meth:`_verify_token`
        with that token immediately raises :exc:`PermissionError`.

        Args:
            token: The opaque token string previously returned by
                :meth:`issue_access_pass`.

        Returns:
            ``True`` if the token was found and successfully removed.
            ``False`` if the token was not in the active registry (already
            expired, already revoked, or never issued by this instance).

        Examples:
            >>> gw = MemoryGateway()
            >>> uri, token = gw.issue_access_pass("worker-7", "analyst")
            >>> gw.revoke_token(token)
            True
            >>> gw.revoke_token(token)  # second call — already removed
            False
        """
        with self._tokens_lock:
            if token in self.active_tokens:
                worker_id = self.active_tokens[token].get("worker_id", "unknown")
                del self.active_tokens[token]
                _log.info("[D-Memory] Token revoked (worker=%s)", worker_id)
                return True
            return False

    # ── ISynapseWorker-compatible contract methods ────────────────────────────

    def describe(self) -> dict:
        """Return capability descriptor for the MemoryGateway organ.

        Returns:
            dict with name, version, capabilities, and bos_uri keys.
        """
        return {
            "name": "MemoryGateway",
            "version": "0.0.1",
            "capabilities": [
                "memory.read",
                "memory.write",
                "token.issue",
                "token.revoke",
            ],
            "bos_uri": "bos://d-memory/gateway",
        }

    def heartbeat(self) -> dict:
        """Return liveness status for the MemoryGateway.

        Returns:
            dict with status, ts, and active_token_count.
        """
        return {
            "status": "alive",
            "ts": time.time(),
            "active_token_count": len(self.active_tokens),
        }

    def health_check(self) -> dict:
        """Return detailed health metrics for the MemoryGateway.

        Returns:
            dict with status, version, active_token_count, base_dir, and writable.
        """
        writable = os.access(self.base_dir, os.W_OK)
        return {
            "status": "healthy" if writable else "degraded",
            "version": "0.0.1",
            "active_token_count": len(self.active_tokens),
            "max_token_capacity": self._MAX_ACTIVE_TOKENS,
            "base_dir": self.base_dir,
            "writable": writable,
        }

    def validate_internal_state(self) -> bool:
        """Return True if the gateway base directory is writable."""
        return os.access(self.base_dir, os.W_OK)


# Singleton instance to be imported by the MCP server
global_memory_gateway = MemoryGateway()

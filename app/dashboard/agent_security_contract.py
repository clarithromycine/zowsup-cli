"""Agent security middleware contract draft (v0.8).

This file is intentionally implementation-light and serves as a handoff
contract for backend development.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Protocol, Any


@dataclass(frozen=True)
class VerifyContext:
    now_ts: int
    require_security: bool = True
    window_seconds: int = 300


@dataclass(frozen=True)
class KeyRecord:
    kid: str
    secret: bytes
    revoked: bool
    expires_at: int


@dataclass(frozen=True)
class SecurityDecision:
    accepted: bool
    code: str
    message: str
    retryable: bool
    audit: dict[str, Any]


class KeyStore(Protocol):
    def get_active_key(self, kid: str) -> Optional[KeyRecord]:
        """Return active key record, or None if key is unknown."""


class NonceStore(Protocol):
    def exists(self, agent_id: str, nonce: str) -> bool:
        """Return True if nonce already exists in the replay window."""

    def put(self, agent_id: str, nonce: str, ttl_seconds: int) -> None:
        """Store nonce with TTL."""


def verify_message_security(
    message: dict[str, Any],
    ctx: VerifyContext,
    key_store: KeyStore,
    nonce_store: NonceStore,
) -> SecurityDecision:
    """Verify message-level signature and anti-replay constraints.

    Delegates to app.dashboard.agent_security.verifier implementation.
    """
    from app.dashboard.agent_security.verifier import (  # local import avoids circular import
        verify_message_security as _verify,
    )

    return _verify(message, ctx, key_store, nonce_store)

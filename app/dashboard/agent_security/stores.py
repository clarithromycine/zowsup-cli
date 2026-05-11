from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from app.dashboard.agent_security_contract import KeyRecord, KeyStore, NonceStore


@dataclass
class InMemoryKeyStore(KeyStore):
    _keys: dict[str, KeyRecord]

    @classmethod
    def from_plain_dict(cls, data: dict[str, dict]) -> "InMemoryKeyStore":
        keys: dict[str, KeyRecord] = {}
        for kid, rec in data.items():
            keys[kid] = KeyRecord(
                kid=kid,
                secret=str(rec.get("secret", "")).encode("utf-8"),
                revoked=bool(rec.get("revoked", False)),
                expires_at=int(rec.get("expires_at", 0)),
            )
        return cls(_keys=keys)

    def get_active_key(self, kid: str) -> Optional[KeyRecord]:
        return self._keys.get(kid)


class InMemoryNonceStore(NonceStore):
    """Simple nonce store with TTL based on externally supplied current time."""

    def __init__(self) -> None:
        self._now_ts: int = 0
        self._nonce_expiry: dict[tuple[str, str], int] = {}

    def set_now(self, now_ts: int) -> None:
        self._now_ts = int(now_ts)
        self._prune()

    def _prune(self) -> None:
        expired = [k for k, exp in self._nonce_expiry.items() if exp <= self._now_ts]
        for k in expired:
            self._nonce_expiry.pop(k, None)

    def exists(self, agent_id: str, nonce: str) -> bool:
        self._prune()
        exp = self._nonce_expiry.get((agent_id, nonce))
        return exp is not None and exp > self._now_ts

    def put(self, agent_id: str, nonce: str, ttl_seconds: int) -> None:
        ttl = max(1, int(ttl_seconds))
        self._nonce_expiry[(agent_id, nonce)] = self._now_ts + ttl
        self._prune()

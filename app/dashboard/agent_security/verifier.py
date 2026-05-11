from __future__ import annotations

import hashlib
import hmac
from typing import Any

from app.dashboard.agent_security_contract import (
    KeyStore,
    NonceStore,
    SecurityDecision,
    VerifyContext,
)
from app.dashboard.agent_security.canonical import b64url_no_pad, canonicalize_message


_RETRYABLE_BY_CODE: dict[str, bool] = {
    "ok": False,
    "payload_invalid": False,
    "key_not_found": False,
    "key_revoked": False,
    "signed_at_out_of_window": True,
    "replay_detected": False,
    "signature_invalid": False,
    "internal_error": True,
}


def _decision(
    accepted: bool,
    code: str,
    message: str,
    audit: dict[str, Any],
) -> SecurityDecision:
    return SecurityDecision(
        accepted=accepted,
        code=code,
        message=message,
        retryable=_RETRYABLE_BY_CODE.get(code, False),
        audit=audit,
    )


def verify_message_security(
    message: dict[str, Any],
    ctx: VerifyContext,
    key_store: KeyStore,
    nonce_store: NonceStore,
) -> SecurityDecision:
    agent_id = str(message.get("agent_id", ""))
    msg_id = str(message.get("msg_id", ""))

    sec = message.get("security")
    if not isinstance(sec, dict):
        if ctx.require_security:
            return _decision(
                False,
                "payload_invalid",
                "missing security object",
                {"agent_id": agent_id, "msg_id": msg_id},
            )
        return _decision(True, "ok", "security not required", {"agent_id": agent_id, "msg_id": msg_id})

    required = ["kid", "alg", "nonce", "signed_at", "signature"]
    if any(k not in sec for k in required):
        return _decision(
            False,
            "payload_invalid",
            "missing required security fields",
            {"agent_id": agent_id, "msg_id": msg_id},
        )

    kid = str(sec.get("kid", ""))
    alg = str(sec.get("alg", ""))
    nonce = str(sec.get("nonce", ""))
    incoming_signature = str(sec.get("signature", ""))

    if alg != "hmac-sha256":
        return _decision(
            False,
            "payload_invalid",
            "unsupported security algorithm",
            {"agent_id": agent_id, "msg_id": msg_id, "kid": kid},
        )

    try:
        signed_at = int(sec.get("signed_at"))
    except (TypeError, ValueError):
        return _decision(
            False,
            "payload_invalid",
            "invalid signed_at",
            {"agent_id": agent_id, "msg_id": msg_id, "kid": kid},
        )

    key = key_store.get_active_key(kid)
    if key is None:
        return _decision(
            False,
            "key_not_found",
            "kid not found",
            {"agent_id": agent_id, "msg_id": msg_id, "kid": kid, "signed_at": signed_at, "now_ts": ctx.now_ts},
        )

    if key.revoked or ctx.now_ts > int(key.expires_at):
        return _decision(
            False,
            "key_revoked",
            "key revoked or expired",
            {"agent_id": agent_id, "msg_id": msg_id, "kid": kid, "signed_at": signed_at, "now_ts": ctx.now_ts},
        )

    delta = abs(int(ctx.now_ts) - signed_at)
    if delta > int(ctx.window_seconds):
        return _decision(
            False,
            "signed_at_out_of_window",
            "signed_at outside allowed window",
            {
                "agent_id": agent_id,
                "msg_id": msg_id,
                "kid": kid,
                "signed_at": signed_at,
                "now_ts": ctx.now_ts,
                "delta_seconds": delta,
            },
        )

    if nonce_store.exists(agent_id, nonce):
        return _decision(
            False,
            "replay_detected",
            "nonce already used",
            {"agent_id": agent_id, "msg_id": msg_id, "kid": kid, "nonce": nonce},
        )

    try:
        canonical = canonicalize_message(message)
        expected = b64url_no_pad(
            hmac.new(key.secret, canonical.encode("utf-8"), hashlib.sha256).digest()
        )
    except Exception as exc:  # noqa: BLE001
        return _decision(
            False,
            "internal_error",
            f"canonical/sign failed: {exc}",
            {"agent_id": agent_id, "msg_id": msg_id, "kid": kid},
        )

    if not hmac.compare_digest(expected, incoming_signature):
        return _decision(
            False,
            "signature_invalid",
            "signature mismatch",
            {"agent_id": agent_id, "msg_id": msg_id, "kid": kid},
        )

    nonce_store.put(agent_id, nonce, int(ctx.window_seconds))
    return _decision(
        True,
        "ok",
        "verified",
        {
            "agent_id": agent_id,
            "msg_id": msg_id,
            "kid": kid,
            "signed_at": signed_at,
            "now_ts": ctx.now_ts,
            "delta_seconds": delta,
        },
    )

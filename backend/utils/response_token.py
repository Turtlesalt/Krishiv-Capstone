import base64
import hashlib
import hmac
import json
import os
import time

_SECRET_ENV_VAR = "RESPONSE_TOKEN_SECRET"
_TOKEN_TTL_SECONDS = 7 * 24 * 60 * 60
VALID_VERDICTS = {"accept", "decline", "tentative", "vote"}


def _secret() -> bytes:
    return os.environ[_SECRET_ENV_VAR].encode()


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode().rstrip("=")


def _b64url_decode(data: str) -> bytes:
    return base64.urlsafe_b64decode(data + "=" * (-len(data) % 4))


def sign_payload(payload: dict) -> str:
    """HMAC-sign any JSON payload - shared by email response links and the
    member identity cookie / sign-in links (utils/identity.py)."""
    payload_bytes = json.dumps(payload, separators=(",", ":")).encode()
    signature = hmac.new(_secret(), payload_bytes, hashlib.sha256).digest()
    return f"{_b64url_encode(payload_bytes)}.{_b64url_encode(signature)}"


def verify_payload(token: str) -> dict | None:
    """The payload if the signature checks out, else None. Checks nothing
    else - each caller validates its own fields and expiry."""
    try:
        payload_part, signature_part = token.split(".", 1)
        payload_bytes = _b64url_decode(payload_part)
        signature = _b64url_decode(signature_part)
        expected_signature = hmac.new(_secret(), payload_bytes, hashlib.sha256).digest()
        if not hmac.compare_digest(signature, expected_signature):
            return None
        payload = json.loads(payload_bytes)
        return payload if isinstance(payload, dict) else None
    except Exception:
        return None


def create_response_token(
    plan_id: str, person_id: str, verdict: str, option_id: str | None = None
) -> str:
    if verdict not in VALID_VERDICTS:
        raise ValueError(f"verdict must be one of {sorted(VALID_VERDICTS)}, got {verdict!r}")
    if verdict == "vote" and not option_id:
        raise ValueError("verdict='vote' requires an option_id")
    if verdict != "vote" and option_id:
        raise ValueError("option_id is only valid together with verdict='vote'")

    payload = {
        "plan_id": plan_id,
        "person_id": person_id,
        "verdict": verdict,
        "exp": int(time.time()) + _TOKEN_TTL_SECONDS,
    }
    if option_id:
        payload["option_id"] = option_id
    return sign_payload(payload)


def create_option_token(plan_id: str, person_id: str, option_id: str) -> str:
    """Convenience wrapper for the common case: a vote for one specific
    option among several proposed venues."""
    return create_response_token(plan_id, person_id, "vote", option_id=option_id)


def verify_response_token(token: str) -> dict | None:
    """Verify signature and expiry. Returns None for any invalid, tampered,
    or expired token - untrusted input from an email link, so anything that
    doesn't check out cleanly is treated as invalid rather than raising."""
    try:
        payload = verify_payload(token)
        if payload is None:
            return None
        verdict = payload.get("verdict")
        if verdict not in VALID_VERDICTS:
            return None
        if verdict == "vote" and not payload.get("option_id"):
            return None
        if int(time.time()) > payload["exp"]:
            return None

        return {
            "plan_id": payload["plan_id"],
            "person_id": payload["person_id"],
            "verdict": verdict,
            "option_id": payload.get("option_id"),
        }
    except Exception:
        return None

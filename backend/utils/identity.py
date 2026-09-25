"""Who is looking at a group's pages. Every per-person page (preferences,
favorites, anything added later) asks current_member() - never a ?person=
param or a "pick yourself" dropdown, which let anyone act as anyone.

Identity is a signed, per-group cookie holding the member's email (unique
within a group; names aren't - they get typo'd or shared). It's set when
someone creates or joins the group, or when they open the one-time sign-in
link emailed from the group's /signin page."""

import time

from fastapi import Request, Response

from utils.response_token import sign_payload, verify_payload

_COOKIE_TTL_SECONDS = 180 * 24 * 60 * 60
_SIGNIN_LINK_TTL_SECONDS = 30 * 60


def _cookie_name(group_id: str) -> str:
    return f"sc_member_{group_id}"


def find_member(group: dict, email: str) -> dict | None:
    return next((m for m in group["members"] if m["email"].lower() == email.lower()), None)


def _read(token: str, kind: str, group_id: str) -> str | None:
    """The email in a valid, unexpired token of this kind for this group."""
    payload = verify_payload(token or "")
    if payload is None or payload.get("kind") != kind or payload.get("group") != group_id:
        return None
    if int(time.time()) > payload.get("exp", 0):
        return None
    return payload.get("email")


def _token(kind: str, group_id: str, email: str, ttl: int) -> str:
    return sign_payload(
        {"kind": kind, "group": group_id, "email": email.lower(), "exp": int(time.time()) + ttl}
    )


def current_member(request: Request, group: dict) -> dict | None:
    email = _read(request.cookies.get(_cookie_name(group["id"]), ""), "member", group["id"])
    return find_member(group, email) if email else None


def remember_member(request: Request, response: Response, group_id: str, email: str) -> None:
    response.set_cookie(
        _cookie_name(group_id),
        _token("member", group_id, email, _COOKIE_TTL_SECONDS),
        max_age=_COOKIE_TTL_SECONDS,
        path=f"/groups/{group_id}",
        httponly=True,
        samesite="lax",
        secure=request.url.scheme == "https",
    )


def create_signin_token(group_id: str, email: str) -> str:
    return _token("signin", group_id, email, _SIGNIN_LINK_TTL_SECONDS)


def redeem_signin_token(token: str, group: dict) -> dict | None:
    email = _read(token, "signin", group["id"])
    return find_member(group, email) if email else None


# ---------- Google sign-in / calendar connect (OAuth `state`) ----------
# The Google round trip carries a signed state naming the group, why we went
# to Google (purpose), who we expect (email - absent for a plain sign-in),
# where to land afterwards, and a one-time nonce. The nonce is also set as a
# cookie on the browser that started the flow, so a Google link can't be
# finished in someone else's browser.
#   purpose "join":    just created/joined the group - connect their calendar
#   purpose "signin":  unknown device - Google's verified email says who it is
#   purpose "connect": already signed in, connecting from Preferences
_GOOGLE_STATE_TTL_SECONDS = 15 * 60
CALENDAR_NONCE_COOKIE = "sc_cal_nonce"
GOOGLE_PURPOSES = {"join", "signin", "connect"}


def create_google_state(group_id: str, nonce: str, purpose: str, email: str = "", next_page: str = "") -> str:
    assert purpose in GOOGLE_PURPOSES
    return sign_payload({
        "kind": "google", "group": group_id, "nonce": nonce, "purpose": purpose,
        "email": email.lower(), "next": next_page,
        "exp": int(time.time()) + _GOOGLE_STATE_TTL_SECONDS,
    })


def read_google_state(token: str) -> dict | None:
    payload = verify_payload(token or "")
    if payload is None or payload.get("kind") != "google":
        return None
    if int(time.time()) > payload.get("exp", 0) or payload.get("purpose") not in GOOGLE_PURPOSES:
        return None
    if not all(isinstance(payload.get(k), str) for k in ("group", "nonce", "email", "next")):
        return None
    return payload

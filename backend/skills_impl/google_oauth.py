import hashlib
import json
import os

from google.auth.exceptions import RefreshError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow

from paths import DATA_DIR

TOKEN_FILE = DATA_DIR / "google_token.json"

# google-auth-oauthlib's Flow generates a PKCE code_verifier inside the Flow
# instance itself (see its authorization_url()). Since /oauth2/login and
# /oauth2callback are two separate requests, each building its own fresh
# Flow, that verifier has to be stashed somewhere in between or the token
# exchange fails with "Missing code verifier".
PENDING_FILE = DATA_DIR / ".oauth_pending.json"

SCOPES = [
    "https://www.googleapis.com/auth/calendar.readonly",
    "https://www.googleapis.com/auth/gmail.send",
]


def redirect_uri(base_url: str | None = None) -> str:
    """Where Google sends people back to. An explicit GOOGLE_OAUTH_REDIRECT_URI
    wins; otherwise it's built from the address the site is actually being
    visited on (base_url), so a missing setting can't bounce people to
    localhost. Whatever it resolves to must be listed under "Authorized
    redirect URIs" for the OAuth client in Google Cloud Console."""
    explicit = os.getenv("GOOGLE_OAUTH_REDIRECT_URI")
    if explicit:
        return explicit
    if base_url:
        return f"{base_url.rstrip('/')}/oauth2callback"
    fallback = os.getenv("APP_BASE_URL", f"http://localhost:{os.getenv('PORT', '8000')}")
    return f"{fallback.rstrip('/')}/oauth2callback"


def is_configured() -> bool:
    return bool(os.getenv("GOOGLE_CLIENT_ID") and os.getenv("GOOGLE_CLIENT_SECRET"))


# Per-member connections ask for calendar.readonly only, but Google hands
# back every scope that account ever granted this client (e.g. gmail.send if
# the app owner connects their own calendar too) - don't treat that as an error.
os.environ.setdefault("OAUTHLIB_RELAX_TOKEN_SCOPE", "1")

CALENDAR_SCOPE = "https://www.googleapis.com/auth/calendar.readonly"
# openid + email: the same Google step that connects someone's calendar also
# tells us, verified by Google, which email they are - so it doubles as sign-in
MEMBER_SCOPES = ["openid", "https://www.googleapis.com/auth/userinfo.email", CALENDAR_SCOPE]
MEMBER_TOKENS_DIR = DATA_DIR / "member_calendar_tokens"
MEMBER_PENDING_DIR = DATA_DIR / ".oauth_pending_members"


def build_flow(scopes: list[str] = SCOPES, base_url: str | None = None) -> Flow:
    client_config = {
        "web": {
            "client_id": os.environ["GOOGLE_CLIENT_ID"],
            "client_secret": os.environ["GOOGLE_CLIENT_SECRET"],
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [redirect_uri(base_url)],
        }
    }
    return Flow.from_client_config(client_config, scopes=scopes, redirect_uri=redirect_uri(base_url))


def save_pending_verifier(code_verifier: str) -> None:
    PENDING_FILE.parent.mkdir(parents=True, exist_ok=True)
    PENDING_FILE.write_text(json.dumps({"code_verifier": code_verifier}))


def pop_pending_verifier() -> str | None:
    if not PENDING_FILE.exists():
        return None
    code_verifier = json.loads(PENDING_FILE.read_text()).get("code_verifier")
    PENDING_FILE.unlink(missing_ok=True)
    return code_verifier


def save_credentials(creds: Credentials) -> None:
    TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
    TOKEN_FILE.write_text(creds.to_json())


def get_credentials() -> Credentials:
    if not TOKEN_FILE.exists():
        base_url = os.getenv("APP_BASE_URL", f"http://localhost:{os.getenv('PORT', '8000')}").rstrip("/")
        raise RuntimeError(
            f"No Google OAuth token found. Visit {base_url}/oauth2/login in your "
            "browser first to connect your Google account."
        )
    creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        save_credentials(creds)
    return creds


# ---------- per-member calendar connections ----------
# Separate from the app's own token above (which sends the group's email):
# each member connects their own calendar, read-only, so the agent reads
# *their* events rather than whoever connected the app. Tokens are keyed by
# email (not group), since one person's calendar is the same in every group.

def _member_token_file(email: str):
    return MEMBER_TOKENS_DIR / f"{hashlib.sha256(email.strip().lower().encode()).hexdigest()}.json"


def save_member_pending_verifier(nonce: str, code_verifier: str) -> None:
    MEMBER_PENDING_DIR.mkdir(parents=True, exist_ok=True)
    (MEMBER_PENDING_DIR / f"{nonce}.json").write_text(json.dumps({"code_verifier": code_verifier}))


def pop_member_pending_verifier(nonce: str) -> str | None:
    if not nonce.isalnum():
        return None
    path = MEMBER_PENDING_DIR / f"{nonce}.json"
    if not path.exists():
        return None
    code_verifier = json.loads(path.read_text()).get("code_verifier")
    path.unlink(missing_ok=True)
    return code_verifier


def save_member_credentials(email: str, creds: Credentials) -> None:
    MEMBER_TOKENS_DIR.mkdir(parents=True, exist_ok=True)
    _member_token_file(email).write_text(creds.to_json())


def member_calendar_connected(email: str) -> bool:
    return _member_token_file(email).exists()


def disconnect_member_calendar(email: str) -> None:
    _member_token_file(email).unlink(missing_ok=True)


def get_member_credentials(email: str) -> Credentials | None:
    """The member's own read-only calendar credentials, or None if they
    haven't connected (or revoked access, in which case the stale token is
    dropped so the UI shows them as not connected again)."""
    path = _member_token_file(email)
    if not path.exists():
        return None
    creds = Credentials.from_authorized_user_file(str(path), MEMBER_SCOPES)
    if creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
        except RefreshError:
            path.unlink(missing_ok=True)
            return None
        save_member_credentials(email, creds)
    return creds


def verified_google_email(creds: Credentials) -> str | None:
    """The Google account's email from the signed ID token, if Google has
    verified it - never trusted from anything the browser sent."""
    from google.oauth2 import id_token

    raw = getattr(creds, "id_token", None)
    if not raw:
        return None
    try:
        claims = id_token.verify_oauth2_token(raw, Request(), os.environ["GOOGLE_CLIENT_ID"])
    except ValueError:
        return None
    if not claims.get("email_verified"):
        return None
    return claims.get("email", "").strip().lower() or None

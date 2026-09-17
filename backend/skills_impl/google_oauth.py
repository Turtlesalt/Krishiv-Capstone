import json
import os
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
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


def redirect_uri() -> str:
    port = os.getenv("PORT", "8000")
    return os.getenv("GOOGLE_OAUTH_REDIRECT_URI", f"http://localhost:{port}/oauth2callback")


def build_flow() -> Flow:
    client_config = {
        "web": {
            "client_id": os.environ["GOOGLE_CLIENT_ID"],
            "client_secret": os.environ["GOOGLE_CLIENT_SECRET"],
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [redirect_uri()],
        }
    }
    return Flow.from_client_config(client_config, scopes=SCOPES, redirect_uri=redirect_uri())


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
        raise RuntimeError(
            "No Google OAuth token found. Visit http://localhost:"
            f"{os.getenv('PORT', '8000')}/oauth2/login in your browser first "
            "to connect your Google account."
        )
    creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        save_credentials(creds)
    return creds

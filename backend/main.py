import html
import json
import math
import os
import uuid
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# Local dev only: allows the OAuth code exchange over http://localhost.
# Never do this for a deployment reachable over the public internet.
os.environ.setdefault("OAUTHLIB_INSECURE_TRANSPORT", "1")

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from google.genai import errors as genai_errors

import groups
from agent import context as agent_context
from agent import loop as agent_loop
from skills_impl import google_oauth
from skills_impl.email import deliver as deliver_email
from utils import identity
from utils.response_token import verify_response_token

BASE_DIR = Path(__file__).resolve().parent

app = FastAPI(title="SyncCircle")
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


def _asset_version(filename: str) -> str:
    # Cache-bust a static asset using its own mtime, so browsers always pick
    # up edits without needing a hard refresh.
    return str(int((BASE_DIR / "static" / filename).stat().st_mtime))


def _style_version() -> str:
    return _asset_version("style.css")


def _script_version() -> str:
    return _asset_version("app.js")


templates.env.globals["style_version"] = _style_version
templates.env.globals["script_version"] = _script_version


def _circle_point(index: int, total: int, cx: float = 50, cy: float = 50, r: float = 38) -> dict:
    # Position of the i-th node evenly spaced around a ring, starting at the
    # top (12 o'clock) and going clockwise - used by the circle-diagram SVG.
    total = max(total, 1)
    angle = math.radians(-90 + (360 / total) * index)
    return {"x": round(cx + r * math.cos(angle), 2), "y": round(cy + r * math.sin(angle), 2)}


def _member_verdicts(group_id: str, session_id: str) -> dict:
    return {name: record.get("verdict") for name, record in groups.get_responses(group_id, session_id).items()}


templates.env.globals["circle_point"] = _circle_point
templates.env.globals["member_verdicts"] = _member_verdicts


def _circle_summary(group: dict, verdicts: dict) -> str:
    total = len(group["members"])
    if total == 0:
        return "It's just the ghosts in here. Share the invite link."
    responded = len(verdicts)
    pending = [m["name"] for m in group["members"] if m["name"] not in verdicts]
    if responded == 0:
        return "Plan's out. Now we wait for replies…"
    if pending:
        return f"{responded} of {total} are in. Still waiting on {', '.join(pending)} 👀"
    return f"All {total} replied. Full house."


def _flow_stage(group: dict) -> str:
    runs = group.get("runs", [])
    if not runs:
        return "gather"
    session_id = runs[-1]["session_id"]
    if not _member_verdicts(group["id"], session_id):
        return "wait"
    if groups.tally_votes(group["id"], session_id).get("winner"):
        return "confirm"
    return "reevaluate"


def _latest_circle_state(group: dict) -> dict:
    runs = group.get("runs", [])
    if not runs:
        return {
            "session_id": None,
            "verdicts": {},
            "summary": "Nothing cooking yet. Say the word.",
            "stage": "gather",
        }
    latest = runs[-1]
    verdicts = _member_verdicts(group["id"], latest["session_id"])
    return {
        "session_id": latest["session_id"],
        "verdicts": verdicts,
        "summary": _circle_summary(group, verdicts),
        "stage": _flow_stage(group),
    }


def _friendly_agent_error(exc: Exception) -> str:
    if isinstance(exc, genai_errors.ClientError) and getattr(exc, "code", None) == 429:
        return (
            "The agent's out of juice for now (Gemini's free-tier limit). "
            "Give it a few minutes and try again. (Setup tip: switch GEMINI_MODEL "
            "in .env to a model with separate quota, or turn on billing.)"
        )
    if isinstance(exc, genai_errors.APIError):
        return f"Well, that didn't work. Gemini said no ({getattr(exc, 'code', '?')}): {exc}. Try again?"
    return f"Something broke on our end: {exc}. Try again?"


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/oauth2/login")
def oauth2_login():
    flow = google_oauth.build_flow()
    auth_url, _state = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
    )
    google_oauth.save_pending_verifier(flow.code_verifier)
    return RedirectResponse(auth_url)


@app.get("/oauth2callback")
def oauth2callback(request: Request):
    flow = google_oauth.build_flow()
    flow.fetch_token(
        authorization_response=str(request.url),
        code_verifier=google_oauth.pop_pending_verifier(),
    )
    google_oauth.save_credentials(flow.credentials)
    return {"status": "Google account connected. You can close this tab and set MOCK_MODE=false."}


@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    return templates.TemplateResponse(request, "index.html", {})


def _get_group_or_404(group_id: str) -> dict:
    group = groups.get_group(group_id)
    if group is None:
        raise HTTPException(status_code=404, detail="Can't find that group. Check the link?")
    return group


# Pages a sign-in can send you back to (whitelisted: `next` comes from a URL).
_SIGNIN_NEXT = {"preferences", "favorites"}


def _safe_next(next_page: str) -> str:
    return next_page if next_page in _SIGNIN_NEXT else ""


def _signin_redirect(group_id: str, next_page: str) -> RedirectResponse:
    return RedirectResponse(f"/groups/{group_id}/signin?next={next_page}", status_code=303)


def _send_signin_link(group: dict, member: dict, next_page: str) -> None:
    base_url = os.getenv("APP_BASE_URL", f"http://localhost:{os.getenv('PORT', '8000')}").rstrip("/")
    token = identity.create_signin_token(group["id"], member["email"])
    link = f"{base_url}/groups/{group['id']}/signin/verify?token={token}&next={next_page}"
    body = (
        f"Hi {member['name']},\n\nOpen this link to sign in to \"{group['name']}\" on SyncCircle:\n"
        f"{link}\n\nIt works for 30 minutes. Didn't ask for this? Ignore it - nothing changes."
    )
    html_body = (
        f'<p style="font-family:Arial,Helvetica,sans-serif;font-size:14px;">Hi {html.escape(member["name"])},</p>'
        '<p style="font-family:Arial,Helvetica,sans-serif;font-size:14px;">'
        f'<a href="{html.escape(link)}">Sign in to &ldquo;{html.escape(group["name"])}&rdquo;</a>'
        " &middot; works for 30 minutes.</p>"
    )
    deliver_email(member["email"], f"Your sign-in link for {group['name']}", body, html_body)


def _signin_page(request: Request, group: dict, next_page: str, sent: bool = False,
                 error: str | None = None, status_code: int = 200):
    return templates.TemplateResponse(
        request,
        "signin.html",
        {"group": group, "next": next_page, "sent": sent, "error": error},
        status_code=status_code,
    )


@app.post("/groups")
def create_group(
    request: Request,
    group_name: str = Form(...),
    your_name: str = Form(...),
    your_email: str = Form(...),
    your_location: str = Form(...),
    your_interests: str = Form(""),
    your_dislikes: str = Form(""),
):
    group = groups.create_group(
        group_name, your_name, your_email, your_location, your_interests, your_dislikes
    )
    response = RedirectResponse(f"/groups/{group['id']}", status_code=303)
    identity.remember_member(request, response, group["id"], your_email)
    return response


@app.get("/groups/{group_id}", response_class=HTMLResponse)
def group_page(request: Request, group_id: str):
    group = _get_group_or_404(group_id)
    join_url = str(request.base_url).rstrip("/") + f"/groups/{group_id}/join"
    return templates.TemplateResponse(
        request,
        "group.html",
        {
            "group": group,
            "join_url": join_url,
            "runs": group.get("runs", []),
            "circle_state": _latest_circle_state(group),
        },
    )


@app.get("/groups/{group_id}/join", response_class=HTMLResponse)
def join_page(request: Request, group_id: str):
    group = _get_group_or_404(group_id)
    return templates.TemplateResponse(request, "join.html", {"group": group})


@app.post("/groups/{group_id}/join")
def join_group(
    request: Request,
    group_id: str,
    name: str = Form(...),
    email: str = Form(...),
    location: str = Form(...),
    interests: str = Form(""),
    dislikes: str = Form(""),
):
    group = _get_group_or_404(group_id)
    if identity.find_member(group, email):
        # Already a member: typing someone's email into the join form must not
        # sign you in as them, so they go through the emailed link instead.
        return _signin_redirect(group_id, "")
    groups.add_member(group_id, name, email, location, interests, dislikes)
    response = RedirectResponse(f"/groups/{group_id}", status_code=303)
    identity.remember_member(request, response, group_id, email)
    return response


@app.get("/groups/{group_id}/signin", response_class=HTMLResponse)
def signin_page(request: Request, group_id: str, next: str = ""):
    return _signin_page(request, _get_group_or_404(group_id), _safe_next(next))


@app.post("/groups/{group_id}/signin", response_class=HTMLResponse)
def send_signin(request: Request, group_id: str, email: str = Form(...), next: str = Form("")):
    group = _get_group_or_404(group_id)
    member = identity.find_member(group, email.strip())
    if member is not None:
        try:
            _send_signin_link(group, member, _safe_next(next))
        except Exception as exc:
            return _signin_page(request, group, _safe_next(next),
                                error=f"Couldn't send the email ({exc}). Is Gmail connected? Try again in a bit.")
    # Same answer whether or not the email is in the group, so this page
    # can't be used to check who's a member.
    return _signin_page(request, group, _safe_next(next), sent=True)


@app.get("/groups/{group_id}/signin/verify")
def verify_signin(request: Request, group_id: str, token: str, next: str = ""):
    group = _get_group_or_404(group_id)
    member = identity.redeem_signin_token(token, group)
    if member is None:
        return _signin_page(request, group, _safe_next(next), status_code=400,
                            error="That sign-in link has expired or isn't valid. Get a fresh one below.")
    response = RedirectResponse(f"/groups/{group_id}/{_safe_next(next)}".rstrip("/"), status_code=303)
    identity.remember_member(request, response, group_id, member["email"])
    return response


@app.get("/groups/{group_id}/preferences", response_class=HTMLResponse)
def preferences_page(request: Request, group_id: str):
    group = _get_group_or_404(group_id)
    member = identity.current_member(request, group)
    if member is None:
        return _signin_redirect(group_id, "preferences")
    return templates.TemplateResponse(
        request,
        "preferences.html",
        {"group": group, "person": member["name"], "member": member},
    )


@app.post("/groups/{group_id}/preferences")
def update_preferences(
    request: Request,
    group_id: str,
    interests: str = Form(""),
    dislikes: str = Form(""),
):
    group = _get_group_or_404(group_id)
    member = identity.current_member(request, group)
    if member is None:
        return _signin_redirect(group_id, "preferences")
    groups.update_member_preferences(group_id, member["name"], interests, dislikes)
    return RedirectResponse(f"/groups/{group_id}/preferences", status_code=303)


@app.get("/groups/{group_id}/favorites", response_class=HTMLResponse)
def favorites_page(request: Request, group_id: str):
    group = _get_group_or_404(group_id)
    member = identity.current_member(request, group)
    if member is None:
        return _signin_redirect(group_id, "favorites")
    return templates.TemplateResponse(
        request,
        "favorites.html",
        {
            "group": group,
            "person": member["name"],
            "favorites": groups.list_favorites(group_id, member["name"]),
            "categories": groups.FAVORITE_CATEGORIES,
        },
    )


@app.post("/groups/{group_id}/favorites")
def add_favorite(
    request: Request,
    group_id: str,
    name: str = Form(...),
    category: str = Form(...),
    notes: str = Form(""),
):
    group = _get_group_or_404(group_id)
    member = identity.current_member(request, group)
    if member is None:
        return _signin_redirect(group_id, "favorites")
    groups.add_favorite(group_id, member["name"], name, category, notes)
    return RedirectResponse(f"/groups/{group_id}/favorites", status_code=303)


@app.post("/groups/{group_id}/favorites/{favorite_id}/delete")
def delete_favorite(request: Request, group_id: str, favorite_id: str):
    group = _get_group_or_404(group_id)
    member = identity.current_member(request, group)
    if member is None:
        return _signin_redirect(group_id, "favorites")
    groups.remove_favorite(group_id, member["name"], favorite_id)
    return RedirectResponse(f"/groups/{group_id}/favorites", status_code=303)


def _recap_is_grounded(text: str, group_id: str, session_id: str) -> bool:
    """Mechanical (non-LLM) grounding check for a plan recap:
    1. Every option this plan has ever offered must itself trace back to a
       real find_nearby_places result - if it doesn't, the ground truth is
       already suspect and nothing built on it should be trusted.
    2. The recap text itself must be grounded (see groups.is_text_grounded) -
       catches a fabricated venue even if it was never one of the recorded
       options (this is exactly how 'Tokyo Bites' slipped through an
       earlier, narrower version of this check).
    3. If the deterministic vote tally has a clear winner, the recap can't
       be naming a *different* option as the plan/winner instead.
    This can't catch every possible LLM misstatement (that would need full
    NLP fact-checking), but it catches the failure mode that matters here:
    a venue or vote outcome that contradicts recorded data."""
    known_names = {p["name"].strip().lower() for p in groups.get_known_places(group_id, session_id)}
    options = groups.get_options(group_id, session_id)
    option_names = {o["name"].strip().lower() for o in options}
    if option_names and not option_names.issubset(known_names):
        return False

    if not groups.is_text_grounded(group_id, session_id, text):
        return False

    if not options:
        return True

    tally = groups.tally_votes(group_id, session_id)
    if tally["winner"]:
        winner_name = next((o["name"] for o in options if o["option_id"] == tally["winner"]), None)
        lowered_text = text.lower()
        other_option_named = any(
            o["name"].lower() in lowered_text
            for o in options
            if o["option_id"] != tally["winner"]
        )
        if winner_name and other_option_named and winner_name.lower() not in lowered_text:
            return False
    return True


def _plain_recap(group_id: str, session_id: str) -> str:
    """Deterministic fallback recap, built only from code-computed facts -
    used when the agent's own summary fails the grounding check above."""
    options = groups.get_options(group_id, session_id)
    if not options:
        return "The agent's summary couldn't be verified against recorded data, so it's been withheld here - check email for what was actually sent."

    names_by_id = {o["option_id"]: o["name"] for o in options}
    tally = groups.tally_votes(group_id, session_id)
    if not tally["counts"]:
        return f"Options proposed: {', '.join(names_by_id.values())}. No votes recorded yet."

    counts_readable = ", ".join(f"{names_by_id.get(opt, opt)}: {c}" for opt, c in tally["counts"].items())
    if tally["winner"]:
        return f"Vote tally - {counts_readable}. '{names_by_id[tally['winner']]}' has a clear plurality."
    tied = [names_by_id.get(opt, opt) for opt in tally["tied_options"]]
    return f"Vote tally - {counts_readable}. Currently tied between {tied}."


def _error_page(request: Request, group_id: str, group: dict, error: str):
    join_url = str(request.base_url).rstrip("/") + f"/groups/{group_id}/join"
    return templates.TemplateResponse(
        request,
        "group.html",
        {
            "group": group,
            "join_url": join_url,
            "runs": group.get("runs", []),
            "circle_state": _latest_circle_state(group),
            "error": error,
        },
        status_code=502,
    )


@app.post("/groups/{group_id}/plan")
def plan(request: Request, group_id: str, date: str = Form(...), note: str = Form("")):
    group = groups.get_group(group_id)
    if group is None:
        raise HTTPException(status_code=404, detail="Can't find that group. Check the link?")
    if not group["members"]:
        raise HTTPException(status_code=400, detail="Group has no members yet")

    message = f"Plan something for the group for {date}."
    if note:
        message += f" Additional context from the organizer: {note}"

    # Generated up front (rather than after the loop returns) so that
    # send_email - called mid-loop - can already read it via
    # agent_context.get_session_id() to build response-link tokens.
    session_id = str(uuid.uuid4())
    agent_context.set_group_id(group_id)
    agent_context.set_session_id(session_id)
    try:
        messages, final_text = agent_loop.run_kickoff(message)
    except Exception as exc:
        return _error_page(request, group_id, group, _friendly_agent_error(exc))

    (groups.sessions_dir(group_id) / f"{session_id}.json").write_text(json.dumps(messages, indent=2))

    if not _recap_is_grounded(final_text, group_id, session_id):
        final_text = _plain_recap(group_id, session_id)

    group.setdefault("runs", []).append(
        {"session_id": session_id, "request": message, "response": final_text}
    )
    groups.save_group(group)

    return RedirectResponse(f"/groups/{group_id}", status_code=303)


def _reply(group_id: str, session_id: str, person: str, message: str) -> dict:
    group = groups.get_group(group_id)
    if group is None:
        raise HTTPException(status_code=404, detail="Can't find that group. Check the link?")
    session_path = groups.sessions_dir(group_id) / f"{session_id}.json"
    if not session_path.exists():
        raise HTTPException(status_code=404, detail="Unknown session_id")

    agent_context.set_group_id(group_id)
    agent_context.set_session_id(session_id)
    contents = json.loads(session_path.read_text())
    injected = f"Reply from {person}: {message}"
    contents, final_text = agent_loop.run_resume(contents, injected)
    session_path.write_text(json.dumps(contents, indent=2))

    if not _recap_is_grounded(final_text, group_id, session_id):
        final_text = _plain_recap(group_id, session_id)

    for run in group.get("runs", []):
        if run["session_id"] == session_id:
            run["request"] = f"{run['request']} | {injected}"
            run["response"] = final_text
    groups.save_group(group)

    return {"session_id": session_id, "response": final_text}


@app.post("/groups/{group_id}/reply")
def group_reply(
    request: Request,
    group_id: str,
    session_id: str = Form(...),
    person: str = Form(...),
    message: str = Form(...),
):
    try:
        _reply(group_id, session_id, person, message)
    except HTTPException:
        raise
    except Exception as exc:
        group = groups.get_group(group_id)
        return _error_page(request, group_id, group, _friendly_agent_error(exc))
    return RedirectResponse(f"/groups/{group_id}", status_code=303)


@app.get("/respond", response_class=HTMLResponse)
def respond(request: Request, token: str):
    decoded = verify_response_token(token)
    if decoded is None or decoded["verdict"] == "vote":
        return templates.TemplateResponse(request, "respond.html", {"valid": False}, status_code=400)

    group_id, _, session_id = decoded["plan_id"].partition(":")
    person = decoded["person_id"]
    verdict = decoded["verdict"]

    group = groups.get_group(group_id)
    session_path = groups.sessions_dir(group_id) / f"{session_id}.json"
    if group is None or not session_path.exists():
        return templates.TemplateResponse(request, "respond.html", {"valid": False}, status_code=404)

    groups.upsert_response(group_id, session_id, person, verdict)

    agent_error = None
    try:
        _reply(group_id, session_id, person, f"{person} responded via the email button: {verdict}")
    except Exception as exc:
        agent_error = _friendly_agent_error(exc)

    return templates.TemplateResponse(
        request,
        "respond.html",
        {
            "valid": True,
            "verdict": verdict,
            "person": person,
            "group_name": group["name"],
            "agent_error": agent_error,
        },
    )


def _tally_note(tally: dict, group_id: str, session_id: str) -> str:
    if not tally["counts"]:
        return "No votes recorded yet."

    names_by_id = {o["option_id"]: o["name"] for o in groups.get_options(group_id, session_id)}
    counts_readable = ", ".join(
        f"{names_by_id.get(opt, opt)}: {count}" for opt, count in tally["counts"].items()
    )
    if tally["winner"]:
        winner_name = names_by_id.get(tally["winner"], tally["winner"])
        return (
            f"Vote tally so far - {counts_readable}. '{winner_name}' has a clear plurality: "
            "trust this count and confirm it as the plan rather than recounting yourself."
        )
    tied_names = [names_by_id.get(opt, opt) for opt in tally["tied_options"]]
    return (
        f"Vote tally so far - {counts_readable}. It's currently tied between {tied_names} - "
        "do not pick one yourself; tell the group about the tie and ask them to help break it, "
        "or wait for more votes."
    )


@app.get("/vote", response_class=HTMLResponse)
def vote(request: Request, token: str):
    decoded = verify_response_token(token)
    if decoded is None or decoded["verdict"] != "vote" or not decoded.get("option_id"):
        return templates.TemplateResponse(request, "respond.html", {"valid": False}, status_code=400)

    group_id, _, session_id = decoded["plan_id"].partition(":")
    person = decoded["person_id"]
    option_id = decoded["option_id"]

    group = groups.get_group(group_id)
    session_path = groups.sessions_dir(group_id) / f"{session_id}.json"
    if group is None or not session_path.exists():
        return templates.TemplateResponse(request, "respond.html", {"valid": False}, status_code=404)

    groups.upsert_response(group_id, session_id, person, "vote", option_id=option_id)
    tally = groups.tally_votes(group_id, session_id)
    option_name = next(
        (o["name"] for o in groups.get_options(group_id, session_id) if o["option_id"] == option_id),
        option_id,
    )

    agent_error = None
    try:
        _reply(group_id, session_id, person, f"{person} voted for '{option_name}'. {_tally_note(tally, group_id, session_id)}")
    except Exception as exc:
        agent_error = _friendly_agent_error(exc)

    return templates.TemplateResponse(
        request,
        "vote.html",
        {
            "valid": True,
            "option_name": option_name,
            "person": person,
            "group_name": group["name"],
            "agent_error": agent_error,
        },
    )


@app.post("/webhook/email-reply")
def email_reply_webhook(payload: dict):
    """Wire this up to your inbound-email provider (e.g. SendGrid Inbound
    Parse, Postmark inbound webhooks) once you're off MOCK_MODE. Expected
    payload: {"group_id": ..., "session_id": ..., "person": ..., "message": ...}."""
    return _reply(payload["group_id"], payload["session_id"], payload["person"], payload["message"])


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="127.0.0.1", port=int(os.getenv("PORT", "8000")), reload=True)

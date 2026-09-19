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
        return "No members yet."
    responded = len(verdicts)
    pending = [m["name"] for m in group["members"] if m["name"] not in verdicts]
    if responded == 0:
        return "Waiting on everyone to respond."
    if pending:
        return f"{responded} of {total} responded — waiting on {', '.join(pending)}."
    return f"All {total} responded."


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
            "summary": "No plan yet — ask the agent to get started.",
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
            "Gemini's free-tier request quota for this model is used up for now. "
            "Wait a bit and try again, switch GEMINI_MODEL in .env to a model with "
            "separate quota, or enable billing on the Google AI Studio project."
        )
    if isinstance(exc, genai_errors.APIError):
        return f"Gemini API error ({getattr(exc, 'code', '?')}): {exc}"
    return f"The agent hit an unexpected error: {exc}"


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


@app.post("/groups")
def create_group(
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
    return RedirectResponse(f"/groups/{group['id']}", status_code=303)


@app.get("/groups/{group_id}", response_class=HTMLResponse)
def group_page(request: Request, group_id: str):
    group = groups.get_group(group_id)
    if group is None:
        raise HTTPException(status_code=404, detail="Unknown group")
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
    group = groups.get_group(group_id)
    if group is None:
        raise HTTPException(status_code=404, detail="Unknown group")
    return templates.TemplateResponse(request, "join.html", {"group": group})


@app.post("/groups/{group_id}/join")
def join_group(
    group_id: str,
    name: str = Form(...),
    email: str = Form(...),
    location: str = Form(...),
    interests: str = Form(""),
    dislikes: str = Form(""),
):
    if groups.get_group(group_id) is None:
        raise HTTPException(status_code=404, detail="Unknown group")
    groups.add_member(group_id, name, email, location, interests, dislikes)
    return RedirectResponse(f"/groups/{group_id}", status_code=303)


@app.get("/groups/{group_id}/preferences", response_class=HTMLResponse)
def preferences_page(request: Request, group_id: str, person: str = ""):
    group = groups.get_group(group_id)
    if group is None:
        raise HTTPException(status_code=404, detail="Unknown group")
    if not group["members"]:
        raise HTTPException(status_code=400, detail="Group has no members yet")
    if not person or not any(m["name"] == person for m in group["members"]):
        person = group["members"][0]["name"]
    member = next(m for m in group["members"] if m["name"] == person)

    return templates.TemplateResponse(
        request,
        "preferences.html",
        {"group": group, "person": person, "member": member},
    )


@app.post("/groups/{group_id}/preferences")
def update_preferences(
    group_id: str,
    name: str = Form(...),
    interests: str = Form(""),
    dislikes: str = Form(""),
):
    if groups.get_group(group_id) is None:
        raise HTTPException(status_code=404, detail="Unknown group")
    groups.update_member_preferences(group_id, name, interests, dislikes)
    return RedirectResponse(f"/groups/{group_id}/preferences?person={name}", status_code=303)


@app.get("/groups/{group_id}/favorites", response_class=HTMLResponse)
def favorites_page(request: Request, group_id: str, person: str = ""):
    group = groups.get_group(group_id)
    if group is None:
        raise HTTPException(status_code=404, detail="Unknown group")
    if not group["members"]:
        raise HTTPException(status_code=400, detail="Group has no members yet")
    if not person or not any(m["name"] == person for m in group["members"]):
        person = group["members"][0]["name"]

    return templates.TemplateResponse(
        request,
        "favorites.html",
        {
            "group": group,
            "person": person,
            "favorites": groups.list_favorites(group_id, person),
            "categories": groups.FAVORITE_CATEGORIES,
        },
    )


@app.post("/groups/{group_id}/favorites")
def add_favorite(
    group_id: str,
    person: str = Form(...),
    name: str = Form(...),
    category: str = Form(...),
    notes: str = Form(""),
):
    if groups.get_group(group_id) is None:
        raise HTTPException(status_code=404, detail="Unknown group")
    groups.add_favorite(group_id, person, name, category, notes)
    return RedirectResponse(f"/groups/{group_id}/favorites?person={person}", status_code=303)


@app.post("/groups/{group_id}/favorites/{favorite_id}/delete")
def delete_favorite(group_id: str, favorite_id: str, person: str = Form(...)):
    if groups.get_group(group_id) is None:
        raise HTTPException(status_code=404, detail="Unknown group")
    groups.remove_favorite(group_id, person, favorite_id)
    return RedirectResponse(f"/groups/{group_id}/favorites?person={person}", status_code=303)


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
        raise HTTPException(status_code=404, detail="Unknown group")
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
        raise HTTPException(status_code=404, detail="Unknown group")
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

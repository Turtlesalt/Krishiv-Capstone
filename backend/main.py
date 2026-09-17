import json
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

BASE_DIR = Path(__file__).resolve().parent

app = FastAPI(title="Hangout Planner Agent")
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


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
):
    group = groups.create_group(group_name, your_name, your_email, your_location)
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
        {"group": group, "join_url": join_url, "runs": group.get("runs", [])},
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
):
    if groups.get_group(group_id) is None:
        raise HTTPException(status_code=404, detail="Unknown group")
    groups.add_member(group_id, name, email, location)
    return RedirectResponse(f"/groups/{group_id}", status_code=303)


def _error_page(request: Request, group_id: str, group: dict, error: str):
    join_url = str(request.base_url).rstrip("/") + f"/groups/{group_id}/join"
    return templates.TemplateResponse(
        request,
        "group.html",
        {"group": group, "join_url": join_url, "runs": group.get("runs", []), "error": error},
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

    agent_context.set_group_id(group_id)
    try:
        messages, final_text = agent_loop.run_kickoff(message)
    except Exception as exc:
        return _error_page(request, group_id, group, _friendly_agent_error(exc))

    session_id = str(uuid.uuid4())
    (groups.sessions_dir(group_id) / f"{session_id}.json").write_text(json.dumps(messages, indent=2))

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
    contents = json.loads(session_path.read_text())
    injected = f"Reply from {person}: {message}"
    contents, final_text = agent_loop.run_resume(contents, injected)
    session_path.write_text(json.dumps(contents, indent=2))

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


@app.post("/webhook/email-reply")
def email_reply_webhook(payload: dict):
    """Wire this up to your inbound-email provider (e.g. SendGrid Inbound
    Parse, Postmark inbound webhooks) once you're off MOCK_MODE. Expected
    payload: {"group_id": ..., "session_id": ..., "person": ..., "message": ...}."""
    return _reply(payload["group_id"], payload["session_id"], payload["person"], payload["message"])


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="127.0.0.1", port=int(os.getenv("PORT", "8000")), reload=True)

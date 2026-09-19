import os

from agent.context import get_group_id
from groups import get_group


def _find_member(group: dict, person: str) -> dict | None:
    return next((m for m in group["members"] if m["name"].lower() == person.lower()), None)


def get_freebusy(person: str, start_date: str, end_date: str) -> dict:
    group = get_group(get_group_id())
    if group is None:
        return {"error": "Unknown group"}
    member = _find_member(group, person)
    if member is None:
        return {
            "error": f"Unknown person '{person}'. Known people: {[m['name'] for m in group['members']]}"
        }

    mock_mode = os.getenv("MOCK_MODE", "true").lower() == "true"
    if mock_mode:
        return {
            "person": person,
            "start_date": start_date,
            "end_date": end_date,
            "busy": [],
            "source": "mock",
        }

    from googleapiclient.discovery import build

    from skills_impl import google_oauth

    creds = google_oauth.get_credentials()
    service = build("calendar", "v3", credentials=creds)
    calendar_id = member.get("calendar_id", "primary")
    body = {
        "timeMin": f"{start_date}T00:00:00Z",
        "timeMax": f"{end_date}T23:59:59Z",
        "items": [{"id": calendar_id}],
    }
    result = service.freebusy().query(body=body).execute()
    busy = result["calendars"][calendar_id]["busy"]
    return {
        "person": person,
        "start_date": start_date,
        "end_date": end_date,
        "busy": busy,
        "source": "google_calendar",
    }

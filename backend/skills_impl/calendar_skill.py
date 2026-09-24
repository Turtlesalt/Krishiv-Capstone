import os
import re
from datetime import datetime, timedelta, timezone

from agent.context import get_group_id
from groups import get_group
from skills_impl import google_oauth


def _find_member(group: dict, person: str) -> dict | None:
    return next((m for m in group["members"] if m["name"].lower() == person.lower()), None)


def _calendar_service(member: dict):
    """(service, calendar_id) for this member: their own connected calendar
    if they've linked it, otherwise the app account's (the old behaviour)."""
    from googleapiclient.discovery import build

    creds = google_oauth.get_member_credentials(member["email"])
    if creds is not None:
        return build("calendar", "v3", credentials=creds), "primary"
    return build("calendar", "v3", credentials=google_oauth.get_credentials()), member.get("calendar_id", "primary")


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

    service, calendar_id = _calendar_service(member)
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


# An event counts as academic work if its title says so. Titles only - event
# descriptions can hold anything and never leave the member's calendar.
ACADEMIC_TITLE_RE = re.compile(
    r"\b(assignments?|homework|hw\d*|exams?|mid[- ]?(?:term|sem)s?|end[- ]?(?:term|sem)s?|finals?|"
    r"quiz(?:zes)?|tests?|projects?|submissions?|due|deadlines?|labs?|viva|presentations?|"
    r"essays?|reports?|papers?|problem sets?|psets?)\b",
    re.I,
)


def get_academic_items(member: dict, days_ahead: int = 14) -> list[dict]:
    """Upcoming events on the member's *own* connected calendar whose title
    looks like an assignment/exam. Raises LookupError if they haven't
    connected - the app account's calendar isn't theirs, so it's never used
    as a stand-in here."""
    creds = google_oauth.get_member_credentials(member["email"])
    if creds is None:
        raise LookupError(f"{member['name']} hasn't connected their calendar")

    from googleapiclient.discovery import build

    now = datetime.now(timezone.utc)
    service = build("calendar", "v3", credentials=creds)
    result = service.events().list(
        calendarId="primary",
        timeMin=now.isoformat(),
        timeMax=(now + timedelta(days=days_ahead)).isoformat(),
        singleEvents=True,
        orderBy="startTime",
        maxResults=250,
        fields="items(summary,start)",
    ).execute()

    items = []
    for event in result.get("items", []):
        title = (event.get("summary") or "").strip()
        start = event.get("start", {})
        when = start.get("dateTime") or start.get("date")
        if title and when and ACADEMIC_TITLE_RE.search(title):
            items.append({"title": title, "due": when})
    return items

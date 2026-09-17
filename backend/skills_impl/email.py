import base64
import os
from email.message import EmailMessage

from agent.context import get_group_id
from groups import get_group


def send_email(person: str, subject: str, body: str) -> dict:
    group = get_group(get_group_id())
    if group is None:
        return {"error": "Unknown group"}
    member = next((m for m in group["members"] if m["name"].lower() == person.lower()), None)
    if member is None:
        return {
            "error": f"Unknown person '{person}'. Known people: {[m['name'] for m in group['members']]}"
        }
    to_addr = member["email"]

    mock_mode = os.getenv("MOCK_MODE", "true").lower() == "true"
    if mock_mode:
        print(f"[MOCK EMAIL] To: {to_addr}\nSubject: {subject}\n\n{body}\n")
        return {"status": "mocked", "to": to_addr, "subject": subject}

    from googleapiclient.discovery import build

    from skills_impl import google_oauth

    creds = google_oauth.get_credentials()
    service = build("gmail", "v1", credentials=creds)

    message = EmailMessage()
    message["To"] = to_addr
    message["Subject"] = subject
    message.set_content(body)
    raw = base64.urlsafe_b64encode(message.as_bytes()).decode()

    service.users().messages().send(userId="me", body={"raw": raw}).execute()
    return {"status": "sent", "to": to_addr, "subject": subject}

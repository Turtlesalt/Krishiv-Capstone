import base64
import html
import os
from email.message import EmailMessage

import groups
from agent.context import get_group_id, get_session_id
from utils.response_token import create_option_token, create_response_token

# (label, button background) for each single-option verdict, in display order.
_VERDICT_BUTTONS = [
    ("accept", "Accept", "#7A8B5C"),
    ("tentative", "Tentative", "#D9A441"),
    ("decline", "Decline", "#9B4A3F"),
]

_CARD_STYLE = (
    "border:1px solid #E7D9C6;border-radius:12px;padding:14px 16px;"
    "margin-bottom:12px;font-family:Arial,Helvetica,sans-serif;background-color:#FBF6EF;"
)


def _button_html(url: str, label: str, color: str) -> str:
    return (
        f'<a href="{url}" style="display:inline-block;padding:10px 20px;'
        f"background-color:{color};color:#ffffff;text-decoration:none;"
        f'font-family:Arial,Helvetica,sans-serif;font-size:14px;font-weight:bold;'
        f'border-radius:6px;">{label}</a>'
    )


def _response_buttons_html(plan_id: str, person_name: str) -> str:
    cells = []
    for verdict, label, color in _VERDICT_BUTTONS:
        token = create_response_token(plan_id, person_name, verdict)
        base_url = os.environ["APP_BASE_URL"].rstrip("/")
        url = f"{base_url}/respond?token={token}"
        cells.append(f'<td style="padding:0 8px 0 0;">{_button_html(url, label, color)}</td>')
    return (
        '<table role="presentation" cellpadding="0" cellspacing="0" style="margin-top:20px;">'
        f"<tr>{''.join(cells)}</tr></table>"
    )


def _option_card_html(option: dict, vote_url: str) -> str:
    meta_bits = []
    if option.get("is_favorite"):
        who = ", ".join(option.get("favorited_by", [])) or "someone in the group"
        meta_bits.append(f"★ {who}'s favorite")
    if option.get("rating") is not None:
        reviews = option.get("review_count")
        review_bit = f" ({reviews} reviews)" if reviews else ""
        meta_bits.append(f"{option['rating']:.1f}★{review_bit}")
    # A far-away option always says so explicitly - distance_note (set once
    # the search had to widen beyond the tight default radius) takes
    # priority over the plain distance so it can't read as "just nearby".
    if option.get("distance_note"):
        meta_bits.append(option["distance_note"])
    elif option.get("distance_km") is not None:
        meta_bits.append(f"{option['distance_km']:.1f} km away")
    if option.get("cuisine"):
        meta_bits.append(str(option["cuisine"]).title())
    meta_line = " &middot; ".join(html.escape(bit) for bit in meta_bits)

    return (
        f'<div style="{_CARD_STYLE}">'
        f'<div style="font-size:15px;font-weight:bold;color:#2A211C;">{html.escape(option["name"])}</div>'
        f'<div style="font-size:13px;color:#6B5C4E;margin-top:2px;">{html.escape(option["address"])}</div>'
        + (f'<div style="font-size:12px;color:#6B5C4E;margin-top:4px;">{meta_line}</div>' if meta_line else "")
        + f'<div>{_button_html(vote_url, "Vote for this", "#C1502E")}</div>'
        + "</div>"
    )


def _options_block_html(plan_id: str, person_name: str, options: list[dict]) -> str:
    base_url = os.environ["APP_BASE_URL"].rstrip("/")

    cards = []
    for option in options:
        token = create_option_token(plan_id, person_name, option["option_id"])
        vote_url = f"{base_url}/vote?token={token}"
        cards.append(_option_card_html(option, vote_url))

    decline_token = create_response_token(plan_id, person_name, "decline")
    decline_url = f"{base_url}/respond?token={decline_token}"
    decline_button = f'<div style="margin-top:4px;">{_button_html(decline_url, "I\'m out", "#9B4A3F")}</div>'

    return "".join(cards) + decline_button


def _proposal_html(body: str, action_html: str) -> str:
    body_html = html.escape(body).replace("\n", "<br>")
    return (
        '<div style="background-color:#F5EDE3;font-family:Arial,Helvetica,sans-serif;'
        'font-size:14px;color:#2A211C;">'
        f"{body_html}</div>"
        f'<div style="margin-top:20px;">{action_html}</div>'
    )


def send_email(
    person: str,
    subject: str,
    body: str,
    is_proposal: bool = False,
    options: list[dict] | None = None,
) -> dict:
    group = groups.get_group(get_group_id())
    if group is None:
        return {"error": "Unknown group"}
    member = next((m for m in group["members"] if m["name"].lower() == person.lower()), None)
    if member is None:
        return {
            "error": f"Unknown person '{person}'. Known people: {[m['name'] for m in group['members']]}"
        }
    to_addr = member["email"]
    group_id, session_id = get_group_id(), get_session_id()

    if not groups.is_text_grounded(group_id, session_id, f"{subject}\n{body}"):
        return {
            "error": (
                "Refusing to send: the subject/body quotes a specific name that doesn't "
                "match any real venue this session has looked up, a member, or the group "
                "name. If you're naming a venue, it must come from find_nearby_places - "
                "call it first, or rephrase without quoting an unverified name."
            )
        }

    leaked = groups.study_match_leak(group_id, session_id, member["name"], f"{subject}\n{body}")
    if leaked:
        return {
            "error": (
                f"Refusing to send: this email names '{leaked}', but {member['name']} isn't one of "
                "the members who has it. Only email a shared assignment/exam to the members listed "
                "in that match."
            )
        }

    plan_id = f"{group_id}:{session_id}"
    html_body = None
    if options:
        # Ground truth check: an option can only be emailed (and later voted
        # on / tallied) if it's a venue find_nearby_places actually returned
        # for this session - never a name the LLM supplied on its own.
        known_names = {p["name"].strip().lower() for p in groups.get_known_places(group_id, session_id)}
        unverified = [o["name"] for o in options if o["name"].strip().lower() not in known_names]
        if unverified:
            return {
                "error": (
                    f"Refusing to send: {unverified} were not returned by find_nearby_places "
                    "this session. Call find_nearby_places first and only pass options it "
                    "actually returned - never a venue from your own knowledge."
                )
            }
        numbered_options = groups.save_options(group_id, session_id, options)
        html_body = _proposal_html(body, _options_block_html(plan_id, member["name"], numbered_options))
    elif is_proposal:
        html_body = _proposal_html(body, _response_buttons_html(plan_id, member["name"]))

    return deliver(to_addr, subject, body, html_body)


def deliver(to_addr: str, subject: str, body: str, html_body: str | None = None) -> dict:
    """Actually send (or, in MOCK_MODE, print) one email. No agent checks -
    callers passing LLM-written text must ground it first, as send_email does."""
    mock_mode = os.getenv("MOCK_MODE", "true").lower() == "true"
    if mock_mode:
        print(f"[MOCK EMAIL] To: {to_addr}\nSubject: {subject}\n\n{body}\n")
        if html_body:
            print(f"[MOCK EMAIL HTML]\n{html_body}\n")
        return {"status": "mocked", "to": to_addr, "subject": subject}

    from googleapiclient.discovery import build

    from skills_impl import google_oauth

    creds = google_oauth.get_credentials()
    service = build("gmail", "v1", credentials=creds)

    message = EmailMessage()
    message["To"] = to_addr
    message["Subject"] = subject
    message.set_content(body)
    if html_body:
        message.add_alternative(html_body, subtype="html")
    raw = base64.urlsafe_b64encode(message.as_bytes()).decode()

    service.users().messages().send(userId="me", body={"raw": raw}).execute()
    return {"status": "sent", "to": to_addr, "subject": subject}

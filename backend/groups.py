import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from paths import DATA_DIR as _DATA_ROOT
from skills_impl.geocoding import geocode

_SAFE_QUOTED_WORDS = {"accept", "decline", "tentative", "vote", "yes", "no"}
# Word-boundary lookaround keeps this from treating an apostrophe inside a
# contraction (Let's, Jeff's, don't) as an opening/closing quote.
_QUOTED_PHRASE_RE = re.compile(r"(?<!\w)['\"]([^'\"]{2,60})['\"](?!\w)")


def _member(name: str, email: str, location: str, interests: str = "", dislikes: str = "") -> dict:
    # Geocoded once here, at signup - venue search then always uses this
    # cached coordinate instead of a city-level string, so "Lavale, Pune"
    # searches near Lavale specifically rather than biasing toward central
    # Pune. Best-effort: a geocoding hiccup shouldn't block joining a group,
    # so this falls back to text-only (find_nearby_places will geocode the
    # text itself, and cache that result the same way).
    lat = lon = None
    if location.strip():
        try:
            resolved = geocode(location)
        except Exception:
            resolved = None
        if resolved:
            lat, lon = resolved["lat"], resolved["lon"]
    return {
        "name": name,
        "email": email,
        "location": location,
        "location_lat": lat,
        "location_lon": lon,
        "interests": interests,
        "dislikes": dislikes,
    }


DATA_DIR = _DATA_ROOT / "groups"
DATA_DIR.mkdir(parents=True, exist_ok=True)


def _group_dir(group_id: str) -> Path:
    return DATA_DIR / group_id


def _group_file(group_id: str) -> Path:
    return _group_dir(group_id) / "group.json"


def create_group(
    name: str,
    creator_name: str,
    creator_email: str,
    creator_location: str = "",
    creator_interests: str = "",
    creator_dislikes: str = "",
) -> dict:
    group_id = uuid.uuid4().hex[:10]
    group = {
        "id": group_id,
        "name": name,
        "members": [_member(creator_name, creator_email, creator_location, creator_interests, creator_dislikes)],
        "runs": [],
    }
    _group_dir(group_id).mkdir(parents=True, exist_ok=True)
    (_group_dir(group_id) / "past_plans.json").write_text("[]")
    responses_file(group_id).write_text("{}")
    options_file(group_id).write_text("{}")
    known_places_file(group_id).write_text("{}")
    favorites_file(group_id).write_text("{}")
    sessions_dir(group_id)
    save_group(group)
    return group


def get_group(group_id: str) -> Optional[dict]:
    path = _group_file(group_id)
    if not path.exists():
        return None
    return json.loads(path.read_text())


def save_group(group: dict) -> None:
    _group_file(group["id"]).write_text(json.dumps(group, indent=2))


def add_member(
    group_id: str,
    name: str,
    email: str,
    location: str = "",
    interests: str = "",
    dislikes: str = "",
) -> dict:
    group = get_group(group_id)
    if group is None:
        raise ValueError(f"Unknown group '{group_id}'")
    if not any(m["email"].lower() == email.lower() for m in group["members"]):
        group["members"].append(_member(name, email, location, interests, dislikes))
        save_group(group)
    return group


def update_member_preferences(group_id: str, name: str, interests: str, dislikes: str) -> dict:
    group = get_group(group_id)
    if group is None:
        raise ValueError(f"Unknown group '{group_id}'")
    for m in group["members"]:
        if m["name"].lower() == name.lower():
            m["interests"] = interests
            m["dislikes"] = dislikes
            save_group(group)
            return group
    raise ValueError(f"Unknown member '{name}' in group '{group_id}'")


def past_plans_file(group_id: str) -> Path:
    return _group_dir(group_id) / "past_plans.json"


def responses_file(group_id: str) -> Path:
    return _group_dir(group_id) / "responses.json"


def upsert_response(
    group_id: str, session_id: str, person: str, verdict: str, option_id: Optional[str] = None
) -> None:
    """Record (or overwrite) one person's response to one plan (session) -
    accept/decline/tentative, or a vote for a specific option_id. Keyed by
    session_id so a group's whole response history for every plan lives in
    a single file, same as group.json holds every run."""
    path = responses_file(group_id)
    all_responses = json.loads(path.read_text()) if path.exists() else {}
    session_responses = all_responses.setdefault(session_id, {})
    record = {"verdict": verdict, "responded_at": datetime.now(timezone.utc).isoformat()}
    if option_id:
        record["option_id"] = option_id
    session_responses[person] = record
    path.write_text(json.dumps(all_responses, indent=2))


def get_responses(group_id: str, session_id: str) -> dict:
    path = responses_file(group_id)
    if not path.exists():
        return {}
    return json.loads(path.read_text()).get(session_id, {})


def options_file(group_id: str) -> Path:
    return _group_dir(group_id) / "options.json"


def save_options(group_id: str, session_id: str, options: list[dict]) -> list[dict]:
    """Persist the canonical, numbered option list (option_1..option_4) for
    one plan, so a vote's option_id can be resolved back to a venue name
    later. Numbering happens here - once - so every recipient's email uses
    matching IDs as long as the caller passes the same options in the same
    order for each of them."""
    path = options_file(group_id)
    all_options = json.loads(path.read_text()) if path.exists() else {}
    numbered = [{"option_id": f"option_{i + 1}", **option} for i, option in enumerate(options[:4])]
    all_options[session_id] = numbered
    path.write_text(json.dumps(all_options, indent=2))
    return numbered


def get_options(group_id: str, session_id: str) -> list[dict]:
    path = options_file(group_id)
    if not path.exists():
        return []
    return json.loads(path.read_text()).get(session_id, [])


def known_places_file(group_id: str) -> Path:
    return _group_dir(group_id) / "known_places.json"


def record_known_places(group_id: str, session_id: str, places: list[dict]) -> None:
    """Append real find_nearby_places results to this session's registry of
    grounded venues. This is the source of truth send_email checks against -
    a venue name can only be emailed as an 'option' if it showed up here
    first, i.e. it actually came back from a real search, never from the
    LLM's own text."""
    if not places:
        return
    path = known_places_file(group_id)
    all_places = json.loads(path.read_text()) if path.exists() else {}
    session_places = all_places.setdefault(session_id, [])
    existing_names = {p["name"].strip().lower() for p in session_places}
    for place in places:
        name = (place.get("name") or "").strip()
        if name and name.lower() not in existing_names:
            session_places.append({"name": name, "address": place.get("address", "")})
            existing_names.add(name.lower())
    path.write_text(json.dumps(all_places, indent=2))


def get_known_places(group_id: str, session_id: str) -> list[dict]:
    path = known_places_file(group_id)
    if not path.exists():
        return []
    return json.loads(path.read_text()).get(session_id, [])


def is_text_grounded(group_id: str, session_id: str, text: str) -> bool:
    """Mechanical (non-LLM) check: any quoted, multi-word phrase in `text`
    - how the model tends to cite a specific name - must match a real
    known place from find_nearby_places, a member name, or the group name.
    Doesn't try to catch every possible hallucination (that needs full NLP
    fact-checking); it specifically catches a fabricated venue quoted as
    fact, which is the exact failure mode this exists for."""
    group = get_group(group_id)
    if group is None:
        return True

    known_names = {p["name"].strip().lower() for p in get_known_places(group_id, session_id)}
    safe_terms = known_names | _SAFE_QUOTED_WORDS
    safe_terms |= {m["name"].strip().lower() for m in group["members"]}
    safe_terms.add(group["name"].strip().lower())

    for phrase in _QUOTED_PHRASE_RE.findall(text):
        lowered = phrase.strip().lower()
        if lowered in safe_terms:
            continue
        if len(lowered.split()) == 1:
            continue  # single quoted words are usually emphasis, not a name claim
        return False
    return True


def tally_votes(group_id: str, session_id: str) -> dict:
    """Deterministic vote count for one plan. Re-evaluation should trust
    these numbers rather than re-deriving them from raw message history -
    counting is mechanical and shouldn't be left to the agent to guess at."""
    counts: dict[str, int] = {}
    declines = 0
    for record in get_responses(group_id, session_id).values():
        if record.get("verdict") == "vote" and record.get("option_id"):
            counts[record["option_id"]] = counts.get(record["option_id"], 0) + 1
        elif record.get("verdict") == "decline":
            declines += 1

    if not counts:
        return {"counts": {}, "winner": None, "tied_options": [], "total_votes": 0, "declines": declines}

    top = max(counts.values())
    tied_options = sorted(opt for opt, c in counts.items() if c == top)
    winner = tied_options[0] if len(tied_options) == 1 else None
    return {
        "counts": counts,
        "winner": winner,
        "tied_options": [] if winner else tied_options,
        "total_votes": sum(counts.values()),
        "declines": declines,
    }


def sessions_dir(group_id: str) -> Path:
    d = _group_dir(group_id) / "sessions"
    d.mkdir(parents=True, exist_ok=True)
    return d


FAVORITE_CATEGORIES = ["restaurant", "bar", "cafe", "activity", "other"]


def favorite_category_matches(favorite_category: str, category: str) -> bool:
    """True if a caller-supplied category (as passed to find_nearby_places or
    get_favorite_spots, which document it as accepting the plural form, e.g.
    "restaurants") matches a favorite's stored category (always singular, one
    of FAVORITE_CATEGORIES). An empty category matches everything. This is
    the one place this normalization lives - both call sites import it so it
    can't silently diverge into two different rules again."""
    category = category.strip().lower()
    if not category:
        return True
    return favorite_category.strip().lower() in (category, category.rstrip("s"))


def favorites_file(group_id: str) -> Path:
    return _group_dir(group_id) / "favorites.json"


def add_favorite(group_id: str, person: str, name: str, category: str, notes: str = "") -> dict:
    if category not in FAVORITE_CATEGORIES:
        raise ValueError(f"category must be one of {FAVORITE_CATEGORIES}, got {category!r}")
    path = favorites_file(group_id)
    all_favorites = json.loads(path.read_text()) if path.exists() else {}
    favorite = {
        "id": uuid.uuid4().hex[:10],
        "name": name.strip(),
        "category": category,
        "notes": notes.strip(),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    all_favorites.setdefault(person, []).append(favorite)
    path.write_text(json.dumps(all_favorites, indent=2))
    return favorite


def list_favorites(group_id: str, person: Optional[str] = None) -> list[dict]:
    """All favorites, each tagged with its owner's name - or just one
    person's, if given. Returned flat (not grouped) so a caller filtering
    by category/keyword doesn't need to know about the per-person nesting."""
    path = favorites_file(group_id)
    all_favorites = json.loads(path.read_text()) if path.exists() else {}
    if person is not None:
        return [{"person": person, **f} for f in all_favorites.get(person, [])]
    return [{"person": p, **f} for p, favs in all_favorites.items() for f in favs]


def remove_favorite(group_id: str, person: str, favorite_id: str) -> None:
    path = favorites_file(group_id)
    all_favorites = json.loads(path.read_text()) if path.exists() else {}
    favorites = all_favorites.get(person, [])
    remaining = [f for f in favorites if f["id"] != favorite_id]
    if len(remaining) == len(favorites):
        raise ValueError(f"Unknown favorite '{favorite_id}' for '{person}' in group '{group_id}'")
    all_favorites[person] = remaining
    path.write_text(json.dumps(all_favorites, indent=2))

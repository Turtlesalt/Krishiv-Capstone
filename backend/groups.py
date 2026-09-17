import json
import uuid
from pathlib import Path
from typing import Optional


def _member(name: str, email: str, location: str) -> dict:
    return {"name": name, "email": email, "location": location}


DATA_DIR = Path(__file__).resolve().parent / "data" / "groups"
DATA_DIR.mkdir(parents=True, exist_ok=True)


def _group_dir(group_id: str) -> Path:
    return DATA_DIR / group_id


def _group_file(group_id: str) -> Path:
    return _group_dir(group_id) / "group.json"


def create_group(name: str, creator_name: str, creator_email: str, creator_location: str = "") -> dict:
    group_id = uuid.uuid4().hex[:10]
    group = {
        "id": group_id,
        "name": name,
        "members": [_member(creator_name, creator_email, creator_location)],
        "runs": [],
    }
    _group_dir(group_id).mkdir(parents=True, exist_ok=True)
    (_group_dir(group_id) / "past_plans.json").write_text("[]")
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


def add_member(group_id: str, name: str, email: str, location: str = "") -> dict:
    group = get_group(group_id)
    if group is None:
        raise ValueError(f"Unknown group '{group_id}'")
    if not any(m["name"].lower() == name.lower() for m in group["members"]):
        group["members"].append(_member(name, email, location))
        save_group(group)
    return group


def past_plans_file(group_id: str) -> Path:
    return _group_dir(group_id) / "past_plans.json"


def sessions_dir(group_id: str) -> Path:
    d = _group_dir(group_id) / "sessions"
    d.mkdir(parents=True, exist_ok=True)
    return d

from agent.context import get_group_id
from groups import get_group


def get_member_locations() -> dict:
    group = get_group(get_group_id())
    if group is None:
        return {"error": "Unknown group"}
    return {
        "members": [
            {"name": m["name"], "location": m.get("location") or "unknown"}
            for m in group["members"]
        ]
    }

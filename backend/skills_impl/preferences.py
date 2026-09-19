from agent.context import get_group_id
from groups import get_group


def get_member_preferences() -> dict:
    group = get_group(get_group_id())
    if group is None:
        return {"error": "Unknown group"}
    return {
        "members": [
            {
                "name": m["name"],
                "interests": m.get("interests") or "none provided",
                "dislikes": m.get("dislikes") or "none provided",
            }
            for m in group["members"]
        ]
    }

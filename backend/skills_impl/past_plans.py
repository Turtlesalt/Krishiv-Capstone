import json

from agent.context import get_group_id
from groups import past_plans_file


def get_past_plans(limit: int = 20) -> dict:
    path = past_plans_file(get_group_id())
    plans = json.loads(path.read_text()) if path.exists() else []
    plans_sorted = sorted(plans, key=lambda p: p["date"], reverse=True)
    return {"past_plans": plans_sorted[:limit]}

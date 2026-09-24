from agent.context import get_group_id, get_session_id
from groups import favorite_category_matches, get_group, list_favorites, record_known_places


def _matches_keyword(favorite: dict, keyword: str) -> bool:
    haystack = f"{favorite['name']} {favorite.get('notes', '')}".lower()
    return keyword in haystack


def get_favorite_spots(category: str = "", keyword: str = "") -> dict:
    group_id = get_group_id()
    if get_group(group_id) is None:
        return {"error": "Unknown group"}

    keyword = keyword.strip().lower()

    matches = list_favorites(group_id)
    if category:
        matches = [f for f in matches if favorite_category_matches(f["category"], category)]
    if keyword:
        matches = [f for f in matches if _matches_keyword(f, keyword)]

    if matches:
        # A favorite is a real, user-entered venue - ground it the same way
        # a find_nearby_places result is, so send_email's options gate
        # doesn't refuse a legitimate favorite-based proposal.
        record_known_places(
            group_id,
            get_session_id(),
            [{"name": f["name"], "address": f.get("notes", "")} for f in matches],
        )

    return {"favorites": matches}

import math
import os
import re
import time

import requests

from agent.context import get_group_id, get_session_id
from groups import get_group, list_favorites, record_known_places
from skills_impl.geocoding import geocode

# Free, keyless OpenStreetMap services - no Google billing account needed.
# Both are shared public infrastructure with real usage limits (roughly
# 1 request/second, a descriptive User-Agent required), which is fine at
# this app's scale but wouldn't be for production traffic.
OVERPASS_URL = "https://overpass-api.de/api/interpreter"
_USER_AGENT = "hangout-planner-agent/0.1 (capstone project, local use)"

# Start tight (a true "near me" radius) and only widen if that doesn't turn
# up enough matching places - keeps recommendations close by default
# instead of defaulting to a city-wide search.
_RADIUS_STEPS_M = [5000, 10000, 15000]
_MIN_DESIRED_RESULTS = 3

# Fetch a much wider candidate pool when a keyword is given, since we filter
# it down client-side afterward and don't want the true match cut off by an
# overly small fetch limit.
_CANDIDATE_POOL_MULTIPLIER = 3
_KEYWORD_CANDIDATE_POOL_MULTIPLIER = 10

_CATEGORY_KEYWORDS = [
    (("restaurant", "food", "dinner", "lunch", "eat"), "amenity", "restaurant"),
    (("cafe", "coffee"), "amenity", "cafe"),
    (("bar", "pub", "drink"), "amenity", "bar"),
    (("bowling",), "leisure", "bowling_alley"),
    (("park",), "leisure", "park"),
    (("cinema", "movie"), "amenity", "cinema"),
    (("museum",), "tourism", "museum"),
]

# Rough, unscientific fallback for "how far is that, really" when we don't
# have a routing API - deliberately conservative (city/mixed-road speed)
# so we under-promise on drive time rather than over-promise.
_ASSUMED_KMH = 22


def _osm_tag_for(category: str) -> tuple[str, str]:
    lowered = category.lower()
    for keywords, key, value in _CATEGORY_KEYWORDS:
        if any(kw in lowered for kw in keywords):
            return key, value
    return "amenity", "restaurant"


def _resolve_coordinates(location: str) -> dict | None:
    return geocode(location)


def _format_address(tags: dict, location: str) -> str:
    parts = []
    house_street = " ".join(filter(None, [tags.get("addr:housenumber"), tags.get("addr:street")]))
    if house_street:
        parts.append(house_street)
    area = tags.get("addr:suburb") or tags.get("addr:city")
    if area:
        parts.append(area)
    return ", ".join(parts) if parts else f"near {location}"


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    earth_radius_km = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlambda / 2) ** 2
    return 2 * earth_radius_km * math.asin(math.sqrt(a))


def _drive_minutes(distance_km: float) -> int:
    return max(1, round(distance_km / _ASSUMED_KMH * 60))


def _matches_keyword(tags: dict, keyword: str) -> bool:
    needle = keyword.strip().lower()
    haystack = f"{tags.get('name', '')} {tags.get('cuisine', '').replace(';', ' ')}".lower()
    return needle in haystack


# The public Overpass instance is shared infrastructure and occasionally
# returns a transient 429/502/503/504 under load - worth a couple of quick
# retries before giving up, rather than surfacing a blip as a hard failure.
_TRANSIENT_STATUS_CODES = {429, 502, 503, 504}
_OVERPASS_RETRY_DELAYS_SECONDS = [2, 5]


def _overpass_search(lat: float, lon: float, location: str, category: str, keyword: str, radius_m: int, pool_size: int) -> list[dict]:
    key, value = _osm_tag_for(category)
    overpass_query = (
        "[out:json][timeout:15];"
        f'node["{key}"="{value}"](around:{radius_m},{lat},{lon});'
        f"out center {pool_size};"
    )

    response = None
    for attempt, delay in enumerate([0, *_OVERPASS_RETRY_DELAYS_SECONDS]):
        if delay:
            time.sleep(delay)
        response = requests.post(
            OVERPASS_URL,
            data={"data": overpass_query},
            headers={"User-Agent": _USER_AGENT},
            timeout=20,
        )
        if response.status_code not in _TRANSIENT_STATUS_CODES:
            break
    response.raise_for_status()
    elements = response.json().get("elements", [])

    candidates = []
    for el in elements:
        tags = el.get("tags", {})
        name = tags.get("name")
        if not name:
            continue
        if keyword and not _matches_keyword(tags, keyword):
            continue
        candidate = {
            "name": name,
            "address": _format_address(tags, location),
            "cuisine": tags["cuisine"].replace(";", ", ") if tags.get("cuisine") else None,
            "source": "openstreetmap",
        }
        if el.get("lat") is not None and el.get("lon") is not None:
            candidate["distance_km"] = round(_haversine_km(lat, lon, el["lat"], el["lon"]), 1)
        candidates.append(candidate)
    return candidates


def _split_terms(text: str) -> list[str]:
    return [t.strip().lower() for t in (text or "").split(",") if t.strip()]


def _collect_preference_terms(members: list[str] | None) -> dict:
    group = get_group(get_group_id())
    if group is None:
        return {"interests": [], "dislikes": []}
    relevant = group["members"] if not members else [m for m in group["members"] if m["name"] in members]
    interests, dislikes = [], []
    for m in relevant:
        interests += _split_terms(m.get("interests", ""))
        dislikes += _split_terms(m.get("dislikes", ""))
    return {"interests": interests, "dislikes": dislikes}


def _place_text(place: dict) -> str:
    return f"{place.get('name', '')} {place.get('cuisine', '') or ''}".lower()


# A stated dislike is usually a phrase ("spicy food", "loud bars"), but the
# generic noun rarely shows up verbatim in a place's cuisine/category text -
# what needs to match is the distinguishing word ("spicy", "loud"). Stripped
# out here so "spicy food" still catches a place tagged "Spicy Sushi".
_DISLIKE_STOPWORDS = {"food", "foods", "drink", "drinks", "place", "places", "spot", "spots", "stuff", "things", "cuisine"}


def _dislike_keywords(term: str) -> list[str]:
    words = [w for w in re.findall(r"[a-z0-9]+", term) if w not in _DISLIKE_STOPWORDS]
    return words or [term]


def _apply_dislike_filter(places: list[dict], dislikes: list[str]) -> list[dict]:
    if not dislikes:
        return places
    keyword_sets = [_dislike_keywords(d) for d in dislikes]
    kept = []
    for place in places:
        # Only drop a place when a dislike keyword clearly appears in its own
        # name/cuisine data - if we have no cuisine/category info to check
        # against, we skip the filter for that place rather than guess.
        if not place.get("cuisine"):
            kept.append(place)
            continue
        haystack = _place_text(place)
        if any(any(re.search(rf"\b{re.escape(kw)}\b", haystack) for kw in kws) for kws in keyword_sets):
            continue
        kept.append(place)
    return kept


def _collect_relevant_favorites(members: list[str] | None, category: str, keyword: str) -> list[dict]:
    group_id = get_group_id()
    group = get_group(group_id)
    if group is None:
        return []
    names = members or [m["name"] for m in group["members"]]
    favorites = [f for f in list_favorites(group_id) if f["person"] in names]

    category = category.strip().lower()
    keyword = keyword.strip().lower()
    matches = []
    for f in favorites:
        if category and f["category"].lower() not in (category, category.rstrip("s")):
            continue
        haystack = f"{f['name']} {f.get('notes', '')}".lower()
        if keyword and keyword not in haystack:
            continue
        matches.append(f)
    return matches


def _merge_favorites(places: list[dict], favorites: list[dict]) -> list[dict]:
    by_name = {p["name"].strip().lower(): p for p in places}
    merged = list(places)
    for fav in favorites:
        key = fav["name"].strip().lower()
        if key in by_name:
            by_name[key]["is_favorite"] = True
            by_name[key]["favorited_by"] = by_name[key].get("favorited_by", []) + [fav["person"]]
        else:
            merged.append(
                {
                    "name": fav["name"],
                    "address": fav.get("notes") or "saved favorite - no address on file",
                    "cuisine": None,
                    "is_favorite": True,
                    "favorited_by": [fav["person"]],
                    "source": "favorite",
                }
            )
    return merged


def _rank(places: list[dict], interests: list[str]) -> list[dict]:
    def tier(place: dict) -> int:
        if place.get("is_favorite"):
            return 2
        if interests and any(term in _place_text(place) for term in interests):
            return 1
        return 0

    def sort_key(place: dict):
        return (
            -tier(place),
            place.get("distance_km") if place.get("distance_km") is not None else 0,
        )

    return sorted(places, key=sort_key)


def _attach_distance_notes(places: list[dict], tight_radius_km: float) -> None:
    for place in places:
        distance_km = place.get("distance_km")
        if distance_km is not None and distance_km > tight_radius_km:
            place["distance_note"] = f"{distance_km:.1f} km away (~{_drive_minutes(distance_km)} min drive) - outside the immediate area"


def find_nearby_places(
    location: str,
    category: str,
    keyword: str = "",
    max_results: int = 5,
    members: list[str] | None = None,
) -> dict:
    """members: names of the people this search is for (from
    get_member_locations/get_member_preferences), used to prioritize their
    favorite spots and interests and filter out a clear dislike match.
    Omit to consider the whole group."""
    keyword = keyword.strip()
    query = f"{keyword + ' ' if keyword else ''}{category} near {location}".strip()
    mock_mode = os.getenv("MOCK_MODE", "true").lower() == "true"

    if mock_mode:
        return _mock_find_nearby_places(location, category, keyword, max_results, members, query)

    coords = _resolve_coordinates(location)
    if coords is None:
        return {"error": f"Could not find a real place matching '{location}'. Try a more specific name."}
    lat, lon = coords["lat"], coords["lon"]

    prefs = _collect_preference_terms(members)
    favorites = _collect_relevant_favorites(members, category, keyword)
    pool_multiplier = _KEYWORD_CANDIDATE_POOL_MULTIPLIER if keyword else _CANDIDATE_POOL_MULTIPLIER

    by_name: dict[str, dict] = {}
    used_radius_m = _RADIUS_STEPS_M[0]
    for radius_m in _RADIUS_STEPS_M:
        pool_size = max_results * pool_multiplier
        for place in _overpass_search(lat, lon, location, category, keyword, radius_m, pool_size):
            key = place["name"].strip().lower()
            if key not in by_name:
                by_name[key] = place
        used_radius_m = radius_m
        filtered_now = _apply_dislike_filter(list(by_name.values()), prefs["dislikes"])
        if len(filtered_now) >= min(_MIN_DESIRED_RESULTS, max_results):
            break

    filtered = _apply_dislike_filter(list(by_name.values()), prefs["dislikes"])
    merged = _merge_favorites(filtered, favorites)
    ranked = _rank(merged, prefs["interests"])
    _attach_distance_notes(ranked, _RADIUS_STEPS_M[0] / 1000)
    places = ranked[:max_results]

    if not places:
        return {
            "query": query,
            "places": [],
            "note": (
                f"No '{category}{(' ' + keyword) if keyword else ''}' venue found within "
                f"{used_radius_m / 1000:.0f}km of '{location}' (and no saved favorite matched "
                "either). Say this plainly rather than substituting an unrelated venue; try a "
                "different cuisine/keyword or a wider area instead."
            ),
        }

    result = {"query": query, "places": places, "search_radius_km": used_radius_m / 1000}
    if used_radius_m != _RADIUS_STEPS_M[0]:
        result["note"] = (
            f"Widened the search to {used_radius_m / 1000:.0f}km to find enough options - "
            "some of these are a real drive away, not walking distance."
        )
    record_known_places(get_group_id(), get_session_id(), places)
    return result


def _mock_find_nearby_places(location, category, keyword, max_results, members, query):
    label = f"{keyword.title()} {category.title()}" if keyword else category.title()
    prefs = _collect_preference_terms(members)
    favorites = _collect_relevant_favorites(members, category, keyword)

    # A representative mix: one nearby match and one far enough away to
    # prove radius expansion + distance transparency work, without hitting
    # a real network call.
    raw = [
        {"name": f"Mock {label} Spot 1", "address": f"near {location}", "distance_km": 1.2,
         "cuisine": keyword or category, "source": "openstreetmap"},
        {"name": f"Mock {label} Spot 2", "address": f"near {location}", "distance_km": 3.8,
         "cuisine": keyword or category, "source": "openstreetmap"},
        {"name": f"Mock {label} Spot 3", "address": f"near {location}", "distance_km": 12.4,
         "cuisine": keyword or category, "source": "openstreetmap"},
    ][: max(max_results, 3)]

    filtered = _apply_dislike_filter(raw, prefs["dislikes"])
    merged = _merge_favorites(filtered, favorites)
    ranked = _rank(merged, prefs["interests"])
    _attach_distance_notes(ranked, _RADIUS_STEPS_M[0] / 1000)
    places = ranked[:max_results]

    record_known_places(get_group_id(), get_session_id(), places)
    return {"query": query, "places": places, "search_radius_km": _RADIUS_STEPS_M[-1] / 1000}

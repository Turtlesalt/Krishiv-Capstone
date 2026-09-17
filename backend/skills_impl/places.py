import os

import requests

# Free, keyless OpenStreetMap services - no Google billing account needed.
# Both are shared public infrastructure with real usage limits (roughly
# 1 request/second, a descriptive User-Agent required), which is fine at
# this app's scale but wouldn't be for production traffic.
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
OVERPASS_URL = "https://overpass-api.de/api/interpreter"
_USER_AGENT = "hangout-planner-agent/0.1 (capstone project, local use)"

_SEARCH_RADIUS_METERS = 3000

_CATEGORY_KEYWORDS = [
    (("restaurant", "food", "dinner", "lunch", "eat"), "amenity", "restaurant"),
    (("cafe", "coffee"), "amenity", "cafe"),
    (("bar", "pub", "drink"), "amenity", "bar"),
    (("bowling",), "leisure", "bowling_alley"),
    (("park",), "leisure", "park"),
    (("cinema", "movie"), "amenity", "cinema"),
    (("museum",), "tourism", "museum"),
]


def _osm_tag_for(category: str) -> tuple[str, str]:
    lowered = category.lower()
    for keywords, key, value in _CATEGORY_KEYWORDS:
        if any(kw in lowered for kw in keywords):
            return key, value
    return "amenity", "restaurant"


def _geocode(location: str) -> tuple[float, float] | None:
    response = requests.get(
        NOMINATIM_URL,
        params={"q": location, "format": "json", "limit": 1},
        headers={"User-Agent": _USER_AGENT},
        timeout=10,
    )
    response.raise_for_status()
    results = response.json()
    if not results:
        return None
    return float(results[0]["lat"]), float(results[0]["lon"])


def _format_address(tags: dict, location: str) -> str:
    parts = []
    house_street = " ".join(filter(None, [tags.get("addr:housenumber"), tags.get("addr:street")]))
    if house_street:
        parts.append(house_street)
    area = tags.get("addr:suburb") or tags.get("addr:city")
    if area:
        parts.append(area)
    return ", ".join(parts) if parts else f"near {location}"


def find_nearby_places(location: str, category: str, max_results: int = 5) -> dict:
    query = f"{category} near {location}"
    mock_mode = os.getenv("MOCK_MODE", "true").lower() == "true"

    if mock_mode:
        return {
            "query": query,
            "places": [
                {"name": f"Mock {category.title()} Spot {i + 1}", "address": f"near {location}", "source": "mock"}
                for i in range(min(max_results, 3))
            ],
        }

    coords = _geocode(location)
    if coords is None:
        return {"error": f"Could not find a real place matching '{location}'. Try a more specific name."}
    lat, lon = coords

    key, value = _osm_tag_for(category)
    overpass_query = (
        "[out:json][timeout:15];"
        f'node["{key}"="{value}"](around:{_SEARCH_RADIUS_METERS},{lat},{lon});'
        f"out center {max_results * 3};"
    )
    response = requests.post(
        OVERPASS_URL,
        data={"data": overpass_query},
        headers={"User-Agent": _USER_AGENT},
        timeout=20,
    )
    response.raise_for_status()
    elements = response.json().get("elements", [])

    places = []
    for el in elements:
        tags = el.get("tags", {})
        name = tags.get("name")
        if not name:
            continue
        places.append({"name": name, "address": _format_address(tags, location)})
        if len(places) >= max_results:
            break

    if not places:
        return {
            "query": query,
            "places": [],
            "note": f"No named '{category}' venues found within {_SEARCH_RADIUS_METERS}m of '{location}'.",
        }

    return {"query": query, "places": places}

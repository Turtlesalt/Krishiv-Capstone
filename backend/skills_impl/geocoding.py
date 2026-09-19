import json
from pathlib import Path

import requests

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
_USER_AGENT = "hangout-planner-agent/0.1 (capstone project, local use)"

# Geocoding a free-text location string ("Lavale, Pune") is cheap to get
# wrong or slow to redo, so it happens once per distinct string and the
# resolved coordinates are cached here permanently - every later search
# (find_nearby_places, member location lookups) reuses the cached lat/lon
# instead of re-hitting Nominatim, which is both faster and keeps us well
# under its ~1 req/sec public-usage policy.
_CACHE_PATH = Path(__file__).resolve().parent.parent / "data" / "geocode_cache.json"


def _normalize(location: str) -> str:
    return " ".join(location.strip().lower().split())


def _load_cache() -> dict:
    if not _CACHE_PATH.exists():
        return {}
    return json.loads(_CACHE_PATH.read_text())


def _save_cache(cache: dict) -> None:
    _CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    _CACHE_PATH.write_text(json.dumps(cache, indent=2))


def geocode(location: str) -> dict | None:
    """Resolve a free-text location to {"lat", "lon", "display_name"},
    caching the result so the same text is only ever sent to Nominatim once.
    Returns None if the location couldn't be resolved at all."""
    location = location.strip()
    if not location:
        return None

    key = _normalize(location)
    cache = _load_cache()
    if key in cache:
        return cache[key]

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

    resolved = {
        "lat": float(results[0]["lat"]),
        "lon": float(results[0]["lon"]),
        "display_name": results[0].get("display_name", location),
    }
    cache[key] = resolved
    _save_cache(cache)
    return resolved

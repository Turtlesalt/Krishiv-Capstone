import requests


def get_weather(location: str, date: str) -> dict:
    geo = requests.get(
        "https://geocoding-api.open-meteo.com/v1/search",
        params={"name": location, "count": 1},
        timeout=10,
    ).json()
    results = geo.get("results")
    if not results:
        return {"error": f"Could not find location '{location}'"}
    lat, lon = results[0]["latitude"], results[0]["longitude"]

    forecast = requests.get(
        "https://api.open-meteo.com/v1/forecast",
        params={
            "latitude": lat,
            "longitude": lon,
            "daily": "temperature_2m_max,temperature_2m_min,precipitation_probability_max",
            "timezone": "auto",
            "start_date": date,
            "end_date": date,
        },
        timeout=10,
    ).json()
    daily = forecast.get("daily")
    if not daily or not daily.get("time"):
        return {"error": f"No forecast available for {location} on {date}"}

    return {
        "location": location,
        "date": date,
        "temp_max_c": daily["temperature_2m_max"][0],
        "temp_min_c": daily["temperature_2m_min"][0],
        "precipitation_probability_pct": daily["precipitation_probability_max"][0],
    }

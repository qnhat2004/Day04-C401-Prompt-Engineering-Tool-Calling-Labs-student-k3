from __future__ import annotations

from typing import Any
import requests

from tools._shared import TIMEOUT, err


def get_weather(location: str = "", days: int = 1) -> dict[str, Any]:
    """Tra cứu dự báo thời tiết miễn phí qua Open-Meteo API."""
    try:
        if not location:
            return err("weather", ValueError("Missing location argument"))
        
        # Geocoding location to lat/lon
        geo_url = f"https://geocoding-api.open-meteo.com/v1/search?name={location}&count=1&language=en&format=json"
        geo_resp = requests.get(geo_url, timeout=TIMEOUT)
        geo_resp.raise_for_status()
        geo_data = geo_resp.json()
        
        results = geo_data.get("results")
        if not results:
            return {"tool": "weather", "location": location, "error": "Location not found", "items": []}
            
        lat = results[0]["latitude"]
        lon = results[0]["longitude"]
        city_name = results[0].get("name", location)
        country = results[0].get("country", "")

        # Fetch weather
        weather_url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current_weather=true"
        weather_resp = requests.get(weather_url, timeout=TIMEOUT)
        weather_resp.raise_for_status()
        weather_data = weather_resp.json()

        current = weather_data.get("current_weather", {})
        temp = current.get("temperature")
        windspeed = current.get("windspeed")

        items = [{
            "location": f"{city_name}, {country}",
            "temperature": f"{temp}°C",
            "windspeed": f"{windspeed} km/h",
            "summary": f"Thời tiết tại {city_name}: {temp}°C, tốc độ gió {windspeed} km/h."
        }]

        return {"tool": "weather", "location": location, "days": int(days or 1), "items": items}
    except Exception as exc:
        return err("weather", exc)

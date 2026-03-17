from typing import Tuple

import httpx

from app_config import settings


async def geocode_address(address: str) -> Tuple[float, float]:
    """
    Use Google Geocoding API to convert address to lat/lng.
    In a real deployment this should handle errors and quota limits robustly.
    """
    # Always keep a safe fallback so the demo never crashes on geocoding issues.
    fallback = (37.7749, -122.4194)  # San Francisco demo coordinates

    if not settings.google_maps_api_key:
        return fallback

    try:
        params = {
            "address": address,
            "key": settings.google_maps_api_key,
        }
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get("https://maps.googleapis.com/maps/api/geocode/json", params=params)
            resp.raise_for_status()
            data = resp.json()

        results = data.get("results") or []
        if not results:
            return fallback

        location = results[0]["geometry"]["location"]
        return float(location["lat"]), float(location["lng"])
    except Exception:
        # For hackathon/demo: never fail the job because of geocoding.
        return fallback


from __future__ import annotations

from typing import List, Optional

import httpx

from app_config import settings
from models import Clinic, Job


async def search_clinics_for_job(job: Job, lat: float, lng: float) -> List[Clinic]:
    """
    Use Google Places API to find clinics matching specialization within radius.
    In MOCK_CALLS mode or when API key missing, return deterministic mock clinics.
    """
    # Use real Google Places whenever an API key is available, regardless of
    # whether calls are mocked. This lets you see real locations even when
    # the voice interaction is still simulated.
    if not settings.google_maps_api_key:
        return _mock_clinics(job)

    radius_meters = int(job.max_radius_miles * 1609.34)

    params = {
        "location": f"{lat},{lng}",
        "radius": radius_meters,
        "keyword": job.doctor_specialization,
        "type": "doctor",
        "key": settings.google_maps_api_key,
    }

    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get("https://maps.googleapis.com/maps/api/place/nearbysearch/json", params=params)
        resp.raise_for_status()
        data = resp.json()

    clinics: List[Clinic] = []
    for place in data.get("results", []):
        phone = await _fetch_phone_for_place(place.get("place_id"))
        if not phone:
            continue
        rating = place.get("rating")
        name = place.get("name") or "Unknown Clinic"
        address = place.get("vicinity") or place.get("formatted_address") or "Unknown address"
        loc = place.get("geometry", {}).get("location", {})
        clinic = Clinic(
            job=job,
            name=name,
            address=address,
            phone=phone,
            rating=float(rating) if rating is not None else None,
            latitude=float(loc.get("lat")) if loc.get("lat") is not None else None,
            longitude=float(loc.get("lng")) if loc.get("lng") is not None else None,
        )
        clinics.append(clinic)

    # Filter to a small number for hackathon demo
    return clinics[:5]


async def _fetch_phone_for_place(place_id: Optional[str]) -> Optional[str]:
    if not place_id:
        return None
    params = {
        "place_id": place_id,
        "fields": "formatted_phone_number",
        "key": settings.google_maps_api_key,
    }
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get("https://maps.googleapis.com/maps/api/place/details/json", params=params)
        resp.raise_for_status()
        data = resp.json()
    result = data.get("result", {})
    return result.get("formatted_phone_number")


def _mock_clinics(job: Job) -> List[Clinic]:
    """
    Simple deterministic clinics for demo / tests.
    """
    base = [
        {
            "name": f"{job.doctor_specialization} Care Center",
            "address": "123 Main St, Demo City",
            "phone": "+15550001001",
            "rating": 4.5,
        },
        {
            "name": f"{job.doctor_specialization} Specialists Group",
            "address": "456 Oak Ave, Demo City",
            "phone": "+15550001002",
            "rating": 4.2,
        },
        {
            "name": f"{job.doctor_specialization} Clinic",
            "address": "789 Pine Rd, Demo City",
            "phone": "+15550001003",
            "rating": 3.9,
        },
    ]
    clinics: List[Clinic] = []
    for item in base:
        clinics.append(
            Clinic(
                job=job,
                name=item["name"],
                address=item["address"],
                phone=item["phone"],
                rating=item["rating"],
            )
        )
    return clinics


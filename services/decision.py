from __future__ import annotations

from datetime import datetime
from typing import Iterable, Optional

from models import AppointmentOption


def pick_best_appointment(options: Iterable[AppointmentOption]) -> Optional[AppointmentOption]:
    """
    Choose the earliest valid appointment by date then time.
    Ignores options where insurance_accepted is explicitly False.
    """
    parsed: list[tuple[AppointmentOption, datetime]] = []
    for opt in options:
        if opt.insurance_accepted is False:
            continue
        try:
            dt = datetime.fromisoformat(f"{opt.date}T{opt.time}")
        except Exception:
            continue
        parsed.append((opt, dt))

    if not parsed:
        return None

    parsed.sort(key=lambda x: x[1])
    return parsed[0][0]


from __future__ import annotations

from typing import Optional

import pywhatkit

from app_config import settings
from models import AppointmentOption, Job, Clinic


def _normalize_phone(phone: str) -> str:
    digits = "".join(ch for ch in phone if ch.isdigit())
    if not digits:
        return phone
    cc = settings.whatsapp_country_code.lstrip("+")
    if digits.startswith(cc):
        return f"+{digits}"
    return f"+{cc}{digits}"


def send_whatsapp_confirmation(job: Job, appointment: AppointmentOption, clinic: Clinic) -> Optional[str]:
    """
    Return error message on failure, or None on success / skipped.
    """
    if not settings.send_whatsapp:
        return None

    to_number = _normalize_phone(job.patient_phone)

    message = (
        f"Hello {job.patient_name}, your appointment is confirmed.\n\n"
        f"Clinic: {clinic.name}\n"
        f"Doctor: {appointment.provider or 'Not specified'}\n"
        f"Date: {appointment.date}\n"
        f"Time: {appointment.time}\n"
        f"Address: {clinic.address}\n\n"
        f"Please arrive 10 minutes early."
    )

    try:
        # For hackathon/demo we rely on the instant send API.
        pywhatkit.sendwhatmsg_instantly(to_number, message, wait_time=10, tab_close=True, close_time=3)
        return None
    except Exception as exc:  # noqa: BLE001
        return str(exc)

